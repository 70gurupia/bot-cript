"""
Simulador Local de Corretora em Memória (PaperTradingExchange).
Permite execução de ordens com fricções reais de mercado (taxas maker/taker,
slippage sintético de 0.05%, checagem de liquidação teórica e imposição de margem isolada).
"""

import time
import math
import uuid
from typing import Dict, Any, List, Optional
from config.settings import settings
from core.kill_switch import circuit_breaker
from core.logger import telemetry


class Position:
    def __init__(
        self,
        position_id: str,
        agent_id: str,
        symbol: str,
        side: str,  # "LONG" ou "SHORT"
        amount: float,
        entry_price: float,
        leverage: float,
        collateral_usd: float,
        margin_type: str = "ISOLATED"
    ):
        self.position_id = position_id
        self.agent_id = agent_id
        self.symbol = symbol
        self.side = side.upper()
        self.amount = amount
        self.entry_price = entry_price
        self.leverage = leverage
        self.collateral_usd = collateral_usd
        self.margin_type = margin_type.upper()
        self.unrealized_pnl_usd: float = 0.0
        self.is_closed: bool = False
        self.exit_price: Optional[float] = None
        self.realized_pnl_usd: float = 0.0
        self.created_at_utc: int = int(time.time() * 1000)

        # Preço teórico de liquidação (perda de 90% do colateral isolado)
        maintenance_margin_pct = 0.90
        if self.side == "LONG":
            self.liquidation_price = self.entry_price * (1.0 - (maintenance_margin_pct / self.leverage))
        else:
            self.liquidation_price = self.entry_price * (1.0 + (maintenance_margin_pct / self.leverage))

    def update_price(self, current_price: float) -> bool:
        """Atualiza PnL não-realizado e verifica liquidação forçada."""
        if self.is_closed:
            return False

        if self.side == "LONG":
            price_diff = current_price - self.entry_price
            is_liquidated = current_price <= self.liquidation_price
        else:
            price_diff = self.entry_price - current_price
            is_liquidated = current_price >= self.liquidation_price

        self.unrealized_pnl_usd = price_diff * self.amount

        # Se atingiu o preço de liquidação
        if is_liquidated:
            self.close(self.liquidation_price)
            self.realized_pnl_usd = -self.collateral_usd  # Perde todo o colateral isolado
            return True
        return False

    def close(self, exit_price: float) -> float:
        """Encerra a posição calculando o PnL líquido."""
        self.is_closed = True
        self.exit_price = exit_price
        if self.side == "LONG":
            self.realized_pnl_usd = (exit_price - self.entry_price) * self.amount
        else:
            self.realized_pnl_usd = (self.entry_price - exit_price) * self.amount
        return self.realized_pnl_usd


class PaperOrder:
    def __init__(
        self,
        order_id: str,
        agent_id: str,
        symbol: str,
        side: str,         # "BUY" ou "SELL"
        order_type: str,   # "LIMIT" ou "MARKET"
        amount: float,
        price: float,
        leverage: float,
        margin_type: str = "ISOLATED"
    ):
        self.order_id = order_id
        self.agent_id = agent_id
        self.symbol = symbol
        self.side = side.upper()
        self.order_type = order_type.upper()
        self.amount = amount
        self.price = price
        self.leverage = leverage
        self.margin_type = margin_type.upper()
        self.status = "OPEN"  # "OPEN", "FILLED", "CANCELLED", "REJECTED"
        self.created_at_utc = int(time.time() * 1000)
        self.filled_price: Optional[float] = None
        self.fee_usd: float = 0.0


class PaperTradingExchange:
    """Motor central de simulação de execução com fidelidade de mercado."""

    MAKER_FEE_PCT = 0.02           # 0.02% de taxa para ordens limite preenchidas como maker
    TAKER_FEE_PCT = 0.04           # 0.04% de taxa para ordens a mercado
    SYNTHETIC_SLIPPAGE_PCT = 0.05  # 0.05% de slippage penalizado em ordens a mercado

    def __init__(self, initial_balance_usd: float = 10000.0):
        self.initial_balance_usd = initial_balance_usd
        self.cash_balance_usd = initial_balance_usd
        self.positions: Dict[str, Position] = {}
        self.open_orders: Dict[str, PaperOrder] = {}
        self.trade_history: List[Dict[str, Any]] = []

    def get_equity(self) -> float:
        """Calcula o patrimônio líquido total (saldo disponível + colaterais + PnL aberto)."""
        equity = self.cash_balance_usd
        for pos in self.positions.values():
            if not pos.is_closed:
                equity += pos.collateral_usd + pos.unrealized_pnl_usd
        return equity

    def create_order(
        self,
        agent_id: str,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float,
        leverage: float = 1.0,
        margin_type: str = "ISOLATED"
    ) -> Dict[str, Any]:
        """Cria e processa uma ordem respeitando todas as regras de segurança e saldo."""
        # 1. Checagem de freio de emergência (Kill Switch)
        cb_check = circuit_breaker.is_trading_allowed(agent_id)
        if not cb_check["allowed"]:
            return {"success": False, "reason": f"Recusada por Kill Switch: {cb_check['reason']}"}

        # 2. Invariantes de margem e alavancagem
        if margin_type.upper() != "ISOLATED":
            return {"success": False, "reason": "Margem deve ser obrigatoriamente ISOLATED."}

        if leverage > settings.risk_limits.max_leverage_ceiling:
            return {
                "success": False,
                "reason": f"Alavancagem solicitada ({leverage}x) excede o teto ({settings.risk_limits.max_leverage_ceiling}x)."
            }

        # 3. Cálculo de colateral necessário
        notional_value = amount * price
        collateral_needed = notional_value / leverage

        if collateral_needed > self.cash_balance_usd:
            return {
                "success": False,
                "reason": f"Saldo insuficiente. Necessário colateral de ${collateral_needed:.2f}, disponível: ${self.cash_balance_usd:.2f}."
            }

        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        order = PaperOrder(order_id, agent_id, symbol, side, order_type, amount, price, leverage, margin_type)

        # 4. Execução imediata para ordem a mercado
        if order.order_type == "MARKET":
            return self._execute_market_order(order, collateral_needed)

        # 5. Fila de ordens para ordem limite
        self.open_orders[order_id] = order
        telemetry.emit_event(
            event="LIMIT_ORDER_PLACED",
            level="INFO",
            agent_id=agent_id,
            payload={
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "price": price,
                "amount": amount,
                "leverage": leverage
            }
        )
        return {"success": True, "order_id": order_id, "status": "OPEN", "order": order}

    def _execute_market_order(self, order: PaperOrder, initial_collateral_estimate: float) -> Dict[str, Any]:
        """Executa ordem a mercado aplicando slippage sintético e taxa taker."""
        # Aplicação de slippage desfavorável
        if order.side == "BUY":
            filled_price = order.price * (1.0 + (self.SYNTHETIC_SLIPPAGE_PCT / 100.0))
            pos_side = "LONG"
        else:
            filled_price = order.price * (1.0 - (self.SYNTHETIC_SLIPPAGE_PCT / 100.0))
            pos_side = "SHORT"

        notional = order.amount * filled_price
        actual_collateral = notional / order.leverage
        taker_fee = notional * (self.TAKER_FEE_PCT / 100.0)

        # Checa se o saldo cobre colateral real + taxa
        if (actual_collateral + taker_fee) > self.cash_balance_usd:
            return {
                "success": False,
                "reason": f"Saldo insuficiente após slippage. Necessário: ${actual_collateral + taker_fee:.2f}, disponível: ${self.cash_balance_usd:.2f}."
            }

        # Deduz colateral e taxa do saldo disponível
        self.cash_balance_usd -= (actual_collateral + taker_fee)

        order.status = "FILLED"
        order.filled_price = filled_price
        order.fee_usd = taker_fee

        # Cria a posição aberta
        pos_id = f"pos_{uuid.uuid4().hex[:8]}"
        position = Position(
            position_id=pos_id,
            agent_id=order.agent_id,
            symbol=order.symbol,
            side=pos_side,
            amount=order.amount,
            entry_price=filled_price,
            leverage=order.leverage,
            collateral_usd=actual_collateral,
            margin_type=order.margin_type
        )
        self.positions[pos_id] = position

        self.trade_history.append({
            "event": "MARKET_FILL",
            "order_id": order.order_id,
            "position_id": pos_id,
            "agent_id": order.agent_id,
            "symbol": order.symbol,
            "side": order.side,
            "filled_price": filled_price,
            "amount": order.amount,
            "fee_usd": taker_fee,
            "collateral_usd": actual_collateral,
            "timestamp": int(time.time() * 1000)
        })

        telemetry.emit_event(
            event="ORDER_FILLED",
            level="INFO",
            agent_id=order.agent_id,
            payload={
                "order_id": order.order_id,
                "position_id": pos_id,
                "symbol": order.symbol,
                "filled_price": filled_price,
                "fee_usd": round(taker_fee, 4),
                "leverage": order.leverage
            }
        )

        return {
            "success": True,
            "order_id": order.order_id,
            "position_id": pos_id,
            "status": "FILLED",
            "filled_price": filled_price,
            "fee_usd": taker_fee
        }

    def close_position(self, position_id: str, exit_price: float) -> Dict[str, Any]:
        """Encerra uma posição ativa, deduz taxa de saída e credita o colateral + PnL ao saldo."""
        position = self.positions.get(position_id)
        if not position or position.is_closed:
            return {"success": False, "reason": "Posição não encontrada ou já encerrada."}

        # Aplica taxa de saída (taker fee)
        notional_exit = position.amount * exit_price
        exit_fee = notional_exit * (self.TAKER_FEE_PCT / 100.0)

        realized_pnl = position.close(exit_price)
        net_return = position.collateral_usd + realized_pnl - exit_fee

        # Retorna o colateral restante e o lucro líquido ao saldo
        self.cash_balance_usd += max(0.0, net_return)

        # Checa se a perda do agente aciona o Circuit Breaker L1
        if realized_pnl < 0:
            circuit_breaker.trip_level_1_agent(
                agent_id=position.agent_id,
                daily_loss_usd=abs(realized_pnl),
                allocated_capital=position.collateral_usd * position.leverage
            )

        # Checa se o drawdown global da carteira aciona o Circuit Breaker L2
        current_equity = self.get_equity()
        circuit_breaker.trip_level_2_portfolio(
            current_equity_usd=current_equity,
            baseline_equity_usd=self.initial_balance_usd,
            reason="Verificação pós-fechamento de trade."
        )

        telemetry.emit_event(
            event="POSITION_CLOSED",
            level="INFO",
            agent_id=position.agent_id,
            payload={
                "position_id": position_id,
                "symbol": position.symbol,
                "exit_price": exit_price,
                "realized_pnl_usd": round(realized_pnl, 2),
                "exit_fee_usd": round(exit_fee, 4),
                "cash_balance": round(self.cash_balance_usd, 2)
            }
        )

        return {
            "success": True,
            "position_id": position_id,
            "realized_pnl_usd": realized_pnl,
            "fee_usd": exit_fee,
            "cash_balance_usd": self.cash_balance_usd
        }

    def _try_fill_limit_order(self, order: PaperOrder, high: float, low: float) -> bool:
        """Verifica se as condições de preço do candle satisfazem a execução da ordem limite."""
        if order.side == "BUY" and low <= order.price:
            return True
        if order.side == "SELL" and high >= order.price:
            return True
        return False

    def _execute_filled_order(self, order: PaperOrder, order_id: str, orders_to_remove: list):
        """Executa a alocação de margem e abertura da posição da ordem limite preenchida."""
        filled_price = order.price
        notional = order.amount * filled_price
        maker_fee = notional * (self.MAKER_FEE_PCT / 100.0)
        collateral = notional / order.leverage

        if collateral <= self.cash_balance_usd:
            self.cash_balance_usd -= (collateral + maker_fee)
            order.status = "FILLED"
            order.filled_price = filled_price
            order.fee_usd = maker_fee
            orders_to_remove.append(order_id)

            pos_id = f"pos_{uuid.uuid4().hex[:8]}"
            pos_side = "LONG" if order.side == "BUY" else "SHORT"
            self.positions[pos_id] = Position(
                pos_id, order.agent_id, order.symbol, pos_side,
                order.amount, filled_price, order.leverage, collateral, order.margin_type
            )

    def _process_limit_orders(self, symbol: str, high: float, low: float):
        """Varre e processa ordens limite pendentes para o símbolo."""
        orders_to_remove = []
        for order_id, order in self.open_orders.items():
            if order.symbol != symbol or order.status != "OPEN":
                continue
            if self._try_fill_limit_order(order, high, low):
                self._execute_filled_order(order, order_id, orders_to_remove)

        for oid in orders_to_remove:
            del self.open_orders[oid]

    def _update_open_positions(self, symbol: str, close: float):
        """Atualiza PnL e verifica liquidação para posições abertas."""
        for pos in self.positions.values():
            if not pos.is_closed and pos.symbol == symbol:
                liquidated = pos.update_price(close)
                if liquidated:
                    telemetry.emit_event(
                        event="POSITION_LIQUIDATED",
                        level="CRITICAL",
                        agent_id=pos.agent_id,
                        payload={
                            "position_id": pos.position_id,
                            "symbol": pos.symbol,
                            "loss_usd": pos.collateral_usd,
                            "liquidation_price": pos.liquidation_price
                        }
                    )

    def on_market_candle(self, symbol: str, high: float, low: float, close: float):
        """Processa a chegada de um novo candle de mercado para preencher limites e checar liquidações."""
        self._process_limit_orders(symbol, high, low)
        self._update_open_positions(symbol, close)
