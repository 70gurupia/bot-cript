"""
Loop Assíncrono Central Integrador do Bot Cripto (Core Event Loop).
Orquestra o ciclo contínuo de verificação de circuit breaker, ingestão de dados,
supervisão cognitiva da Laia, validação de risco na Tesouraria e despacho de ordens Maker.
"""

from __future__ import annotations
import asyncio
import time
from typing import Dict, Any, Optional

from core.kill_switch import CircuitBreakerManager, circuit_breaker as global_cb
from core.exchange_adapter import ExchangeAdapter
from core.logger import telemetry
from treasury.treasury_controller import TreasuryController
from treasury.correlation_matrix import OrderProposal
from strategy.laia_entry_evaluator import LaiaEntryEvaluator


class BotEventLoop:
    """Gerenciador do ciclo de vida assíncrono de eventos e negociações do bot."""

    def __init__(
        self,
        adapter: Optional[ExchangeAdapter] = None,
        treasury: Optional[TreasuryController] = None,
        evaluator: Optional[LaiaEntryEvaluator] = None,
        cb_manager: Optional[CircuitBreakerManager] = None,
        tick_interval_sec: float = 2.0
    ):
        self.adapter = adapter or ExchangeAdapter(paper_trading=True)
        self.treasury = treasury or TreasuryController()
        self.evaluator = evaluator or LaiaEntryEvaluator()
        self.cb = cb_manager or global_cb
        self.tick_interval_sec = tick_interval_sec
        self.is_running: bool = False
        self.total_ticks: int = 0
        self.current_equity_usd: float = 10000.0
        self.current_aggregate_exposure: float = 0.0

    def _check_system_health(self) -> tuple[bool, str]:
        """Valida travas físicas do circuit breaker e batimento cardíaco da corretora."""
        cb_check = self.cb.is_trading_allowed("EVENT_LOOP")
        if not cb_check.get("allowed", False):
            return False, f"CIRCUIT_BREAKER_LOCKED: {cb_check.get('reason')}"

        health = self.adapter.check_connection_health()
        if not health.get("healthy", False):
            return False, f"EXCHANGE_UNHEALTHY: {health.get('action')}"

        return True, "OK"

    def _evaluate_signals(
        self,
        symbol: str,
        btc_ret: float,
        alt_ret: float,
        hour_utc: int,
        funding: float
    ) -> Dict[str, Any]:
        """Consulta o avaliador cognitivo Laia para obter confluência e score de qualidade."""
        eval_res = self.evaluator.evaluate_entry(
            symbol=symbol,
            btc_return_15m=btc_ret,
            alt_return_15m=alt_ret,
            hour_utc=hour_utc,
            funding_rate=funding,
            is_mechanical_signal_active=True
        )
        return {
            "action": eval_res.action,
            "score": eval_res.entry_quality_score,
            "risk_mode": eval_res.risk_mode,
            "confidence": eval_res.confidence
        }

    async def _execute_order_safely(
        self,
        symbol: str,
        side: str,
        price: float,
        risk_mode: str
    ) -> Dict[str, Any]:
        """Valida margem na Tesouraria e envia ordem limite Maker para a corretora."""
        equity = self.current_equity_usd
        alloc_pct = 0.05 if risk_mode == "ANTI_MARTINGALE_EXPAND" else 0.04
        order_amount_usd = max(15.0, equity * alloc_pct)

        proposal = OrderProposal(
            agent_id="CORE_EVENT_LOOP",
            symbol=symbol,
            side="BUY" if side.lower() == "buy" else "SELL",
            requested_amount_usd=order_amount_usd,
            agent_sharpe_ratio=2.0,
            stop_loss_pct=0.02,
            leverage=1.0
        )

        val_res = self.treasury.evaluate_order(
            proposal=proposal,
            total_equity=equity,
            current_aggregate_exposure=self.current_aggregate_exposure,
            current_symbol_exposure=0.0,
            active_portfolio_symbols=[]
        )

        if not val_res.approved:
            telemetry.emit_event(
                event="ORDER_REJECTED_BY_TREASURY",
                level="WARNING",
                agent_id="CORE_EVENT_LOOP",
                payload={"symbol": symbol, "reason": val_res.rejection_reason}
            )
            return {"status": "REJECTED_BY_TREASURY", "reason": val_res.rejection_reason}

        amount_contracts = max(0.001, val_res.adjusted_amount_usd / max(1.0, price))
        order_res = await self.adapter.submit_order(
            agent_id="CORE_EVENT_LOOP",
            symbol=symbol,
            side=side,
            order_type="limit",
            amount=amount_contracts,
            price=price,
            leverage=1.0,
            margin_type="ISOLATED"
        )
        self.current_aggregate_exposure += val_res.adjusted_amount_usd

        telemetry.emit_event(
            event="ORDER_EXECUTED_BY_LOOP",
            level="INFO",
            agent_id="CORE_EVENT_LOOP",
            payload={"symbol": symbol, "side": side, "order_id": order_res.get("id")}
        )
        return {"status": "SUBMITTED", "order": order_res}

    async def step(
        self,
        symbol: str = "ETHUSDT",
        btc_ret_15m: float = 0.012,
        alt_ret_15m: float = 0.001,
        hour_utc: int = 14,
        funding: float = 0.0001
    ) -> Dict[str, Any]:
        """Executa um ciclo atômico de decisão, risco e execução."""
        self.total_ticks += 1
        is_healthy, health_reason = self._check_system_health()
        if not is_healthy:
            return {"status": "PAUSED", "reason": health_reason, "tick": self.total_ticks}

        ticker = await self.adapter.fetch_ticker_normalized(symbol)
        curr_price = float(ticker.get("last", 3000.0))

        eval_info = self._evaluate_signals(symbol, btc_ret_15m, alt_ret_15m, hour_utc, funding)
        action = eval_info["action"]

        if action in {"LONG", "BUY"}:
            exec_res = await self._execute_order_safely(symbol, "buy", curr_price, eval_info["risk_mode"])
            return {
                "status": "ORDER_PROCESSED",
                "action": action,
                "execution": exec_res,
                "tick": self.total_ticks
            }

        return {
            "status": "HOLD",
            "action": action,
            "score": eval_info["score"],
            "tick": self.total_ticks
        }

    async def run_forever(self, max_ticks: Optional[int] = None):
        """Executa o loop contínuo de negociação com intervalo configurável."""
        self.is_running = True
        ticks_done = 0
        while self.is_running:
            await self.step()
            ticks_done += 1
            if max_ticks and ticks_done >= max_ticks:
                break
            await asyncio.sleep(self.tick_interval_sec)
        self.is_running = False

    def stop(self):
        """Interrompe a execução contínua do loop."""
        self.is_running = False
