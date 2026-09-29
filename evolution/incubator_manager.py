"""
Gerenciador da Incubadora em Tempo Real com Quarentena (Fase 4).
Controla o ciclo de vida dos clones em paper trading, aplica fricções reais de mercado
e executa a auditoria rigorosa de critérios de graduação para capital real.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from strategy.ast_engine import StrategyAST
from core.paper_exchange import PaperTradingExchange
from evolution.fitness_evaluator import (
    TradeRecord,
    PerformanceReport,
    evaluate_strategy_performance,
    calculate_max_drawdown
)


@dataclass
class CandidateAgent:
    """Representa um agente em avaliacao na quarentena da incubadora."""
    strategy: StrategyAST
    paper_exchange: PaperTradingExchange
    admitted_at_timestamp: int
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    hourly_returns: List[float] = field(default_factory=list)
    status: str = "QUARANTINE"  # "QUARANTINE", "GRADUATED", "ELIMINATED"
    elimination_reason: Optional[str] = None
    graduation_report: Optional[PerformanceReport] = None
    last_position_id: Optional[str] = None
    last_entry_price: float = 0.0
    last_entry_time: float = 0.0


class IncubatorManager:
    """Gerenciador do ciclo probatorio de estrategias na incubadora."""

    def __init__(
        self,
        initial_balance_usd: float = 10000.0,
        max_clones_in_quarantine: int = 20,
        min_quarantine_trades: int = 30,
        min_graduation_sharpe: float = 1.25,
        max_graduation_drawdown: float = 4.5,
        rejection_drawdown_limit: float = 8.0
    ):
        self.initial_balance_usd = initial_balance_usd
        self.max_clones_in_quarantine = max_clones_in_quarantine
        self.min_quarantine_trades = min_quarantine_trades
        self.min_graduation_sharpe = min_graduation_sharpe
        self.max_graduation_drawdown = max_graduation_drawdown
        self.rejection_drawdown_limit = rejection_drawdown_limit
        self.candidates: Dict[str, CandidateAgent] = {}

    def admit_strategy(self, strategy: StrategyAST) -> CandidateAgent:
        """Admite uma nova estrategia na fila de quarentena da incubadora."""
        active_quarantine = len(self.get_quarantine_candidates())
        if active_quarantine >= self.max_clones_in_quarantine:
            raise ValueError(f"Capacidade maxima da incubadora atingida ({self.max_clones_in_quarantine} clones).")

        exchange = PaperTradingExchange(initial_balance_usd=self.initial_balance_usd)
        candidate = CandidateAgent(
            strategy=strategy,
            paper_exchange=exchange,
            admitted_at_timestamp=int(time.time() * 1000),
            equity_curve=[self.initial_balance_usd]
        )
        self.candidates[strategy.strategy_id] = candidate
        return candidate

    def get_quarantine_candidates(self) -> List[CandidateAgent]:
        """Retorna agentes atualmente em periodo probatorio na quarentena."""
        return [c for c in self.candidates.values() if c.status == "QUARANTINE"]

    def get_graduated_candidates(self) -> List[CandidateAgent]:
        """Retorna agentes que superaram com sucesso os criterios de graduacao."""
        return [c for c in self.candidates.values() if c.status == "GRADUATED"]

    def get_eliminated_candidates(self) -> List[CandidateAgent]:
        """Retorna agentes descartados por violacoes de risco ou rebaixamento."""
        return [c for c in self.candidates.values() if c.status == "ELIMINATED"]

    def _evaluate_exit_condition(self, candidate: CandidateAgent, current_price: float, market_state: Dict[str, Any]) -> bool:
        """Verifica se a saida foi disparada por Stop Loss, Take Profit ou regra AST."""
        entry_p = candidate.last_entry_price
        if entry_p <= 0.0:
            return False

        # 1. Stop Loss percentual
        price_drop = (entry_p - current_price) / entry_p
        if price_drop >= candidate.strategy.stop_loss_pct:
            return True

        # 2. Take Profit percentual
        price_gain = (current_price - entry_p) / entry_p
        if price_gain >= candidate.strategy.take_profit_pct:
            return True

        # 3. Regra de saida da arvore sintatica
        ast_exit = candidate.strategy.evaluate_signals(market_state, has_open_position=True)
        return ast_exit == "SELL"

    def _close_candidate_trade(self, candidate: CandidateAgent, current_price: float, timestamp: float) -> None:
        """Fecha a posicao aberta do candidato e registra a operacao."""
        pos_id = candidate.last_position_id
        if not pos_id:
            return

        res = candidate.paper_exchange.close_position(pos_id, current_price)
        if res.get("success", False):
            pnl_abs = (current_price - candidate.last_entry_price) * 1.0  # Proporcional ao lote
            pnl_pct = (current_price - candidate.last_entry_price) / candidate.last_entry_price
            rec = TradeRecord(
                entry_time=candidate.last_entry_time,
                exit_time=timestamp,
                entry_price=candidate.last_entry_price,
                exit_price=current_price,
                side="BUY",
                size=1.0,
                pnl_abs=pnl_abs,
                pnl_pct=pnl_pct,
                fee_paid=res.get("fee_usd", 0.0)
            )
            candidate.trades.append(rec)
            candidate.last_position_id = None
            candidate.last_entry_price = 0.0

    def _open_candidate_trade(self, candidate: CandidateAgent, current_price: float, timestamp: float) -> None:
        """Abre posicao fracionaria para o candidato na incubadora."""
        balance = candidate.paper_exchange.cash_balance_usd
        if balance <= 100.0:
            return

        # Aloca 10% do saldo em margem isolada
        order_amount_usd = balance * 0.10
        amount = round(order_amount_usd / current_price, 6)

        order_res = candidate.paper_exchange.create_order(
            agent_id=candidate.strategy.strategy_id,
            symbol=candidate.strategy.symbol,
            side="BUY",
            order_type="MARKET",
            amount=amount,
            price=current_price,
            leverage=1.0,
            margin_type="ISOLATED"
        )
        if order_res.get("success", False):
            candidate.last_position_id = order_res.get("position_id")
            candidate.last_entry_price = current_price
            candidate.last_entry_time = timestamp

    def _audit_quarantine_status(self, candidate: CandidateAgent) -> None:
        """Audita se o agente deve ser graduado ou eliminado com base em seu historico."""
        current_dd = calculate_max_drawdown(candidate.equity_curve)

        # Regra de corte imediato: rebaixamento superior ao teto de rejeicao
        if current_dd > self.rejection_drawdown_limit:
            candidate.status = "ELIMINATED"
            candidate.elimination_reason = f"Drawdown maximo ({current_dd:.2f}%) excedeu teto de {self.rejection_drawdown_limit}%"
            if candidate.last_position_id:
                candidate.paper_exchange.close_position(candidate.last_position_id, candidate.last_entry_price)
            return

        # Regra de graduacao: minimo de 30 trades fechados
        if len(candidate.trades) >= self.min_quarantine_trades:
            report = evaluate_strategy_performance(
                trades=candidate.trades,
                returns=candidate.hourly_returns,
                equity_curve=candidate.equity_curve
            )
            if (report.total_trades >= self.min_quarantine_trades and
                report.sharpe_ratio >= self.min_graduation_sharpe and
                report.max_drawdown <= self.max_graduation_drawdown):
                candidate.status = "GRADUATED"
                candidate.graduation_report = report

    def process_candle(
        self,
        symbol: str,
        candle: Dict[str, Any],
        prev_candle: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Processa um novo candle horario para todos os candidatos ativos na incubadora.
        Gera sinais, executa ordens na corretora virtual e audita a quarentena.
        """
        current_price = float(candle["close"])
        high_price = float(candle.get("high", current_price))
        low_price = float(candle.get("low", current_price))
        timestamp = float(candle.get("timestamp", time.time()))

        market_state = dict(candle)
        if prev_candle:
            market_state["prev_context"] = prev_candle

        for candidate in self.get_quarantine_candidates():
            if candidate.strategy.symbol != symbol:
                continue

            # Atualiza cotacao nas posicoes abertas e preenche limites
            candidate.paper_exchange.on_market_candle(symbol, high_price, low_price, current_price)


            has_position = candidate.last_position_id is not None
            if has_position:
                if self._evaluate_exit_condition(candidate, current_price, market_state):
                    self._close_candidate_trade(candidate, current_price, timestamp)
            else:
                signal = candidate.strategy.evaluate_signals(market_state, has_open_position=False)
                if signal == "BUY":
                    self._open_candidate_trade(candidate, current_price, timestamp)

            # Rastreia evolucao da curva de patrimonio
            equity = candidate.paper_exchange.get_equity()
            candidate.equity_curve.append(equity)
            if len(candidate.equity_curve) >= 2:
                prev_eq = candidate.equity_curve[-2]
                ret = (equity - prev_eq) / prev_eq if prev_eq > 0 else 0.0
                candidate.hourly_returns.append(ret)

            # Audita status de quarentena
            self._audit_quarantine_status(candidate)
