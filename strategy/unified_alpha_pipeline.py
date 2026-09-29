"""
Pipeline Alfa Unificado do Bot Cripto (Unified Alpha Pipeline).
Integra formalmente todos os motores desenvolvidos no fluxo operacional contínuo:
1. Geração 3 Newtoniana (Trigonometria, TAMA, Tsallis, Momento Fy).
2. Roteador Inteligente Maker Post-Only e Order Book Imbalance (OBI).
3. Filtro Contracíclico de Sentimento por Taxa de Financiamento.
4. Motor Anti-Martingale com Trava Inviolável no Cofre (Ratchet Vault).
5. Emissão de Alertas Operacionais de Telemetria (Telegram/Webhook).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

from strategy.trigonometric_adaptive_engine import (
    TrigonometricVector,
    TrigonometricSignal,
    compute_normalized_cartesian_vector,
    compute_trigonometric_adaptive_ma,
    evaluate_trigonometric_signal,
    compute_tsallis_entropy,
    compute_dynamic_cosine_stop
)
from strategy.smart_order_router import (
    OrderBookSnapshot,
    ExecutionPlan,
    compute_order_book_imbalance,
    evaluate_funding_sentiment,
    create_smart_execution_plan,
    calibrate_walk_forward_thresholds
)
from strategy.entropy_compounding_engine import (
    EntropyEngineConfig,
    calculate_compounding_stake,
    update_monthly_vault
)
from strategy.anti_martingale_engine import AntiMartingaleConfig
from monitoring.operational_alerts import (
    format_trade_entry_alert,
    format_streak_milestone_alert,
    format_vault_ratchet_alert,
    format_eod_summary_alert
)


@dataclass
class UnifiedTradeDecision:
    """Decisão determinística final de negociação consolidada pelo pipeline."""
    should_trade: bool
    symbol: str
    side: str
    execution_plan: Optional[ExecutionPlan]
    take_profit_price: float
    stop_loss_price: float
    allocated_stake_brl: float
    current_vault_brl: float
    alert_message: str
    reason: str


def _extract_best_quotes(
    close_price: float,
    book_snapshot: Optional[OrderBookSnapshot]
) -> Tuple[float, float]:
    """Extrai as melhores cotações de compra e venda com fallback seguro."""
    if book_snapshot and book_snapshot.bids and book_snapshot.asks:
        return book_snapshot.bids[0].price, book_snapshot.asks[0].price
    return close_price - 0.01, close_price + 0.01


def _calculate_exit_prices(
    side: str,
    close_price: float,
    atr_val: float,
    angle_rad: float
) -> Tuple[float, float]:
    """Calcula TP (2x ATR) e Trailing SL (modulado por cosseno)."""
    tp = close_price + 2.0 * atr_val if side == "BUY" else close_price - 2.0 * atr_val
    stop_dist = compute_dynamic_cosine_stop(atr_val, angle_rad, base_multiplier=1.2)
    sl = close_price - stop_dist if side == "BUY" else close_price + stop_dist
    return round(tp, 4), round(sl, 4)


class UnifiedAlphaPipeline:
    """Pipeline orquestrador que consome dados de mercado e produz ordens e alertas."""

    def __init__(
        self,
        bankroll_brl: float = 500.0,
        anti_martingale_cfg: Optional[AntiMartingaleConfig] = None
    ):
        self.bankroll = bankroll_brl
        self.vault = 0.0
        self.streak = 0
        self.am_cfg = anti_martingale_cfg or AntiMartingaleConfig()
        self.entropy_cfg = EntropyEngineConfig()
        self.recent_returns: List[float] = []
        self.active_theta_thresh = 28.0
        self.active_entropy_thresh = 0.75

    def update_walk_forward(self, returns_window: List[float]):
        """Re-calibra os limiares com base na volatilidade recente."""
        self.recent_returns = returns_window
        ang, ent = calibrate_walk_forward_thresholds(
            returns_window, base_angle_deg=28.0, base_entropy_thresh=0.75
        )
        self.active_theta_thresh = ang
        self.active_entropy_thresh = ent

    def _validate_macro_and_book(
        self,
        funding_rate: float,
        side: str,
        book_snapshot: Optional[OrderBookSnapshot]
    ) -> Tuple[bool, float, str]:
        """Valida se o funding e o desequilíbrio de book confirmam a operação."""
        _, can_buy, can_sell = evaluate_funding_sentiment(funding_rate)
        if side == "BUY" and not can_buy:
            return False, 0.0, "FUNDING_OVERHEATED_BLOCK_BUY"
        if side == "SELL" and not can_sell:
            return False, 0.0, "FUNDING_OVERHEATED_BLOCK_SELL"

        obi = 0.0
        if book_snapshot:
            obi = compute_order_book_imbalance(book_snapshot, depth_levels=10)
            if side == "BUY" and obi < -0.30:
                return False, obi, "ORDER_BOOK_RESISTANCE_BLOCK_BUY"
            if side == "SELL" and obi > 0.30:
                return False, obi, "ORDER_BOOK_SUPPORT_BLOCK_SELL"

        return True, obi, "OK"

    def _evaluate_signals_and_vector(
        self,
        close_price: float,
        prev_close_price: float,
        atr_val: float,
        volume: float,
        avg_volume_20: float,
        recent_log_rets: List[float]
    ) -> Tuple[TrigonometricVector, TrigonometricSignal]:
        """Calcula o vetor newtoniano e avalia o sinal de entrada."""
        v_mass = (volume / avg_volume_20) if avg_volume_20 > 0 else 1.0
        vec = compute_normalized_cartesian_vector(
            p_curr=close_price, p_prev=prev_close_price, atr_val=atr_val,
            delta_t=3, volume_mass=v_mass
        )
        tsallis_val = compute_tsallis_entropy(recent_log_rets[-20:], q=1.5) if len(recent_log_rets) >= 20 else 1.0
        sin_sq = vec.sin_theta ** 2
        alpha_t = 0.0645 + (0.40 - 0.0645) * sin_sq
        tama_val = alpha_t * close_price + (1.0 - alpha_t) * prev_close_price

        sig = evaluate_trigonometric_signal(
            vector=vec, entropy_val=tsallis_val, tama_val=tama_val,
            close_price=close_price, entropy_thresh=self.active_entropy_thresh
        )
        return vec, sig

    def process_market_tick(
        self,
        symbol: str,
        close_price: float,
        prev_close_price: float,
        atr_val: float,
        volume: float,
        avg_volume_20: float,
        recent_log_rets: List[float],
        funding_rate: float = 0.0001,
        book_snapshot: Optional[OrderBookSnapshot] = None
    ) -> UnifiedTradeDecision:
        """Processa a vela atual e emite a decisão determinística unificada."""
        vec, sig = self._evaluate_signals_and_vector(
            close_price, prev_close_price, atr_val, volume, avg_volume_20, recent_log_rets
        )

        if not sig.has_signal or sig.regime != "TREND_EXPANSION" or abs(sig.momentum_force) < 0.45:
            return UnifiedTradeDecision(
                should_trade=False, symbol=symbol, side="NONE", execution_plan=None,
                take_profit_price=0.0, stop_loss_price=0.0, allocated_stake_brl=0.0,
                current_vault_brl=self.vault, alert_message="", reason="NO_CONFLUENCE"
            )

        is_valid, obi, reason = self._validate_macro_and_book(funding_rate, sig.side, book_snapshot)
        if not is_valid:
            return UnifiedTradeDecision(
                should_trade=False, symbol=symbol, side=sig.side, execution_plan=None,
                take_profit_price=0.0, stop_loss_price=0.0, allocated_stake_brl=0.0,
                current_vault_brl=self.vault, alert_message="", reason=reason
            )

        stake = calculate_compounding_stake(self.bankroll, self.streak, self.entropy_cfg)
        tp, sl = _calculate_exit_prices(sig.side, close_price, atr_val, vec.angle_rad)
        best_bid, best_ask = _extract_best_quotes(close_price, book_snapshot)

        order_size = stake / close_price if close_price > 0 else 0.0
        plan = create_smart_execution_plan(
            symbol=symbol, side=sig.side, size=order_size,
            best_bid=best_bid, best_ask=best_ask, atr_val=atr_val
        )
        alert = format_trade_entry_alert(
            symbol=symbol, side=sig.side, entry_price=plan.target_price,
            take_profit=tp, stop_loss=sl, angle_deg=vec.angle_deg,
            momentum_force=vec.momentum_force, order_book_imbalance=obi
        )

        return UnifiedTradeDecision(
            should_trade=True, symbol=symbol, side=sig.side, execution_plan=plan,
            take_profit_price=tp, stop_loss_price=sl,
            allocated_stake_brl=round(stake, 2), current_vault_brl=round(self.vault, 2),
            alert_message=alert, reason="UNIFIED_ALPHA_TRIGGERED"
        )

    def register_trade_outcome(self, is_win: bool, pnl_brl: float) -> Tuple[float, float, str]:
        """Atualiza a banca, streaks e realiza o travamento no Cofre Inviolável."""
        if is_win:
            self.bankroll += pnl_brl
            self.streak += 1
            if self.streak >= self.am_cfg.max_streak_expansion:
                self.streak = 0
        else:
            self.bankroll = max(10.0, self.bankroll + pnl_brl)
            self.streak = 0

        tot = self.bankroll + self.vault
        new_vault, new_bankroll = update_monthly_vault(tot, self.vault, self.bankroll)
        transferred = new_vault - self.vault
        self.vault = new_vault
        self.bankroll = new_bankroll

        vault_alert = ""
        if transferred > 0:
            vault_alert = format_vault_ratchet_alert(self.vault, transferred, self.bankroll)

        return self.bankroll, self.vault, vault_alert
