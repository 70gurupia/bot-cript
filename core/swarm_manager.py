"""
Gerenciador e Orquestrador Assincrono da Flotilha de 40 Bots (SwarmManager).
Conecta os 40 sub-bots distribuidos em 8 grupos estrategicos especializados
ao simulador de Paper Trading (PaperTradingExchange) com execucao Maker e controle de risco.
"""

from __future__ import annotations
import time
import math
from typing import Dict, Any, List, Optional, Tuple
from core.paper_exchange import PaperTradingExchange
from core.logger import telemetry


from strategy.laia_entry_evaluator import LaiaEntryEvaluator

GROUP_DEFINITIONS = [
    {
        "group_id": "G1",
        "name": "G1_G3_BTC",
        "strategy": "G3_NEWTONIAN_SCALP",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "bot_indices": range(1, 6)
    },
    {
        "group_id": "G2",
        "name": "G2_G3_ETH",
        "strategy": "G3_NEWTONIAN_SCALP",
        "symbol": "ETHUSDT",
        "timeframe": "15m",
        "bot_indices": range(6, 11)
    },
    {
        "group_id": "G3",
        "name": "G3_LEAD_LAG_MULTI",
        "strategy": "LEAD_LAG_ARBITRAGE",
        "symbol": "ETHUSDT",
        "timeframe": "15m",
        "bot_indices": range(11, 16)
    },
    {
        "group_id": "G4",
        "name": "G4_TTM_SQUEEZE_PULLBACK",
        "strategy": "TTM_SQUEEZE_PULLBACK",
        "symbol": "DOGEUSDT",
        "timeframe": "1h",
        "bot_indices": range(16, 21)
    },
    {
        "group_id": "G5",
        "name": "G5_OBI_ORDER_FLOW_SCALP",
        "strategy": "OBI_ORDER_FLOW_SCALP",
        "symbol": "SOLUSDT",
        "timeframe": "15m",
        "bot_indices": range(21, 26)
    },
    {
        "group_id": "G6",
        "name": "G6_OBI_ORDER_FLOW_SCALP",
        "strategy": "OBI_ORDER_FLOW_SCALP",
        "symbol": "DOTUSDT",
        "timeframe": "15m",
        "bot_indices": range(26, 31)
    },
    {
        "group_id": "G7",
        "name": "G7_TREND_LAIA_CONFLUENCE",
        "strategy": "TREND_FOLLOWING_LAIA",
        "symbol": "BNBUSDT",
        "timeframe": "1h",
        "bot_indices": range(31, 36)
    },
    {
        "group_id": "G8",
        "name": "G8_FUNDING_CARRY_SNIPE",
        "strategy": "FUNDING_CARRY_SNIPE",
        "symbol": "BTCUSDT",
        "timeframe": "8h",
        "bot_indices": range(36, 41)
    }
]


class SubBotState:
    """Estado individual e rastreamento de performance de um sub-bot da flotilha."""

    def __init__(
        self,
        bot_id: str,
        group_id: str,
        group_name: str,
        strategy: str,
        symbol: str,
        timeframe: str
    ):
        self.bot_id = bot_id
        self.group_id = group_id
        self.group_name = group_name
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.is_active: bool = True
        self.trades_count: int = 0
        self.wins_count: int = 0
        self.realized_pnl_usd: float = 0.0
        self.active_position_id: Optional[str] = None
        self.last_signal_time: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Converte o estado do sub-bot para dicionario serializavel."""
        wr = (self.wins_count / self.trades_count * 100.0) if self.trades_count > 0 else 0.0
        return {
            "bot_id": self.bot_id,
            "group_id": self.group_id,
            "group_name": self.group_name,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "is_active": self.is_active,
            "trades_count": self.trades_count,
            "wins_count": self.wins_count,
            "win_rate_pct": round(wr, 1),
            "realized_pnl_usd": round(self.realized_pnl_usd, 2),
            "has_open_position": self.active_position_id is not None
        }


class SwarmManager:
    """Orquestrador assincrono da flotilha de 40 bots com conexao a Paper Exchange."""

    def __init__(
        self,
        exchange: Optional[PaperTradingExchange] = None,
        initial_balance_usd: float = 10000.0,
        min_laia_score: float = 65.0
    ):
        self.exchange = exchange or PaperTradingExchange(initial_balance_usd=initial_balance_usd)
        self.bots: Dict[str, SubBotState] = {}
        self.initial_balance_usd = initial_balance_usd
        self.peak_equity = initial_balance_usd
        self.max_drawdown_pct = 0.0
        self.laia_evaluator = LaiaEntryEvaluator(min_quality_score=min_laia_score)
        self._init_swarm_bots()

    def _init_swarm_bots(self):
        """Inicializa os 40 sub-bots nos 8 grupos definidos."""
        for g_def in GROUP_DEFINITIONS:
            for idx in g_def["bot_indices"]:
                b_id = f"bot_{idx:02d}"
                self.bots[b_id] = SubBotState(
                    bot_id=b_id,
                    group_id=g_def["group_id"],
                    group_name=g_def["name"],
                    strategy=g_def["strategy"],
                    symbol=g_def["symbol"],
                    timeframe=g_def["timeframe"]
                )

    def get_bot(self, bot_id: str) -> Optional[SubBotState]:
        """Retorna o estado do sub-bot especificado."""
        return self.bots.get(bot_id)

    def evaluate_entry_with_laia(
        self,
        bot_id: str,
        btc_return_15m: float,
        alt_return_15m: float,
        hour_utc: int,
        funding_rate: float = 0.0001,
        alt_volume_ratio: float = 1.0
    ) -> Dict[str, Any]:
        """Avalia uma oportunidade de entrada com o modelo Laia EQS."""
        bot = self.bots.get(bot_id)
        if not bot:
            return {"allowed": False, "score": 0.0, "reason": "Bot inexistente."}

        res = self.laia_evaluator.evaluate_entry(
            symbol=bot.symbol,
            btc_return_15m=btc_return_15m,
            alt_return_15m=alt_return_15m,
            hour_utc=hour_utc,
            funding_rate=funding_rate,
            alt_volume_ratio=alt_volume_ratio,
            is_mechanical_signal_active=True
        )
        return {
            "allowed": res.entry_quality_score >= self.laia_evaluator.min_quality_score,
            "score": res.entry_quality_score,
            "action": res.action,
            "risk_mode": res.risk_mode,
            "reasons": res.reasons
        }

    def _update_drawdown(self, current_equity: float):
        """Atualiza a metrica de drawdown maximo da flotilha."""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        if self.peak_equity > 0:
            dd = ((self.peak_equity - current_equity) / self.peak_equity) * 100.0
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd

    def _sync_open_positions(self):
        """Sincroniza posicoes abertas com os sub-bots correspondentes."""
        for pos in self.exchange.positions.values():
            if not pos.is_closed:
                bot = self.bots.get(pos.agent_id)
                if bot and not bot.active_position_id:
                    bot.active_position_id = pos.position_id

    def process_market_candle(
        self,
        symbol: str,
        high: float,
        low: float,
        close: float
    ):
        """Propaga o candle para a Paper Exchange e atualiza drawdown."""
        self.exchange.on_market_candle(symbol=symbol, high=high, low=low, close=close)
        self._sync_open_positions()
        current_eq = self.exchange.get_equity()
        self._update_drawdown(current_eq)

    def dispatch_order(
        self,
        bot_id: str,
        side: str,
        price: float,
        amount: float,
        order_type: str = "LIMIT",
        leverage: float = 1.0,
        laia_filter_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Despacha uma ordem para a Paper Exchange em nome do sub-bot com filtro opcional Laia."""
        bot = self.bots.get(bot_id)
        if not bot or not bot.is_active:
            return {"success": False, "reason": f"Sub-bot {bot_id} inativo ou inexistente."}

        # Filtro de alta probabilidade cognitivo Laia EQS
        if laia_filter_context:
            laia_res = self.evaluate_entry_with_laia(
                bot_id=bot_id,
                btc_return_15m=laia_filter_context.get("btc_return_15m", 0.0),
                alt_return_15m=laia_filter_context.get("alt_return_15m", 0.0),
                hour_utc=laia_filter_context.get("hour_utc", 12),
                funding_rate=laia_filter_context.get("funding_rate", 0.0001),
                alt_volume_ratio=laia_filter_context.get("alt_volume_ratio", 1.0)
            )
            if not laia_res["allowed"]:
                return {
                    "success": False,
                    "reason": f"Filtro Laia EQS rejeitou entrada (Score: {laia_res['score']:.1f} < {self.laia_evaluator.min_quality_score:.1f})."
                }

        order_res = self.exchange.create_order(
            agent_id=bot_id,
            symbol=bot.symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            leverage=leverage,
            margin_type="ISOLATED"
        )

        if order_res.get("success") and "position_id" in order_res:
            bot.active_position_id = order_res["position_id"]

        return order_res

    def _find_bot_position(self, bot_id: str) -> Optional[str]:
        """Localiza a posicao ativa do bot na exchange com fallback."""
        bot = self.bots.get(bot_id)
        if bot and bot.active_position_id:
            return bot.active_position_id
        for pos in self.exchange.positions.values():
            if not pos.is_closed and pos.agent_id == bot_id:
                if bot:
                    bot.active_position_id = pos.position_id
                return pos.position_id
        return None

    def close_bot_position(self, bot_id: str, exit_price: float) -> Dict[str, Any]:
        """Fecha a posicao aberta do sub-bot e registra o resultado contabil."""
        bot = self.bots.get(bot_id)
        pos_id = self._find_bot_position(bot_id)
        if not bot or not pos_id:
            return {"success": False, "reason": "Nenhuma posicao ativa para encerrar."}

        res = self.exchange.close_position(pos_id, exit_price)

        if res.get("success"):
            pnl = res.get("realized_pnl_usd", 0.0)
            bot.trades_count += 1
            bot.realized_pnl_usd += pnl
            if pnl > 0:
                bot.wins_count += 1
            bot.active_position_id = None
            self._update_drawdown(self.exchange.get_equity())

        return res

    def get_swarm_summary(self) -> Dict[str, Any]:
        """Gera o resumo consolidado de metricas da flotilha em tempo real."""
        equity = self.exchange.get_equity()
        self._update_drawdown(equity)
        tot_trades = sum(b.trades_count for b in self.bots.values())
        tot_wins = sum(b.wins_count for b in self.bots.values())
        wr = (tot_wins / tot_trades * 100.0) if tot_trades > 0 else 0.0
        open_pos = len([p for p in self.exchange.positions.values() if not p.is_closed])
        net_ret = ((equity - self.initial_balance_usd) / self.initial_balance_usd) * 100.0

        return {
            "total_bots": len(self.bots),
            "active_bots": sum(1 for b in self.bots.values() if b.is_active),
            "total_groups": len(GROUP_DEFINITIONS),
            "cash_balance_usd": round(self.exchange.cash_balance_usd, 2),
            "total_equity_usd": round(equity, 2),
            "net_return_pct": round(net_ret, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "total_trades": tot_trades,
            "win_rate_pct": round(wr, 1),
            "open_positions_count": open_pos,
            "timestamp_utc": int(time.time() * 1000)
        }

    def _summarize_single_group(self, g_def: Dict[str, Any]) -> Dict[str, Any]:
        """Resume as metricas de um grupo individual."""
        g_id = g_def["group_id"]
        group_bots = [b for b in self.bots.values() if b.group_id == g_id]
        t_trades = sum(b.trades_count for b in group_bots)
        t_wins = sum(b.wins_count for b in group_bots)
        t_pnl = sum(b.realized_pnl_usd for b in group_bots)
        wr = (t_wins / t_trades * 100.0) if t_trades > 0 else 0.0
        return {
            "group_id": g_id,
            "name": g_def["name"],
            "strategy": g_def["strategy"],
            "symbol": g_def["symbol"],
            "timeframe": g_def["timeframe"],
            "bots_count": len(group_bots),
            "total_trades": t_trades,
            "wins_count": t_wins,
            "win_rate_pct": round(wr, 1),
            "realized_pnl_usd": round(t_pnl, 2)
        }

    def get_groups_summary(self) -> List[Dict[str, Any]]:
        """Gera relatorio analitico consolidado dos 8 grupos de 5 bots."""
        return [self._summarize_single_group(g) for g in GROUP_DEFINITIONS]

    def get_bots_list(self) -> List[Dict[str, Any]]:
        """Retorna a lista estruturada de todos os 40 sub-bots."""
        return [b.to_dict() for b in self.bots.values()]

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Retorna as posicoes ativas na Paper Exchange."""
        out = []
        for pos in self.exchange.positions.values():
            if not pos.is_closed:
                out.append({
                    "position_id": pos.position_id,
                    "agent_id": pos.agent_id,
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "amount": pos.amount,
                    "entry_price": pos.entry_price,
                    "leverage": pos.leverage,
                    "collateral_usd": round(pos.collateral_usd, 2),
                    "unrealized_pnl_usd": round(pos.unrealized_pnl_usd, 2),
                    "liquidation_price": round(pos.liquidation_price, 4)
                })
        return out


# Instancia singleton global do SwarmManager para monitoramento
swarm_manager = SwarmManager()
