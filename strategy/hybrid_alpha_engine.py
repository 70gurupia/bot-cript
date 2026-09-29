"""
Motor Hibrido de Alta Rentabilidade (Hybrid Alpha Engine).
Combina Arbitragem de Funding Rate Passivo (fluxo de caixa delta-neutral continuo)
com Price Action Institucional nos Pares Campeoes (LINK, BNB, SOL) durante a Sessao de Nova York (13h as 18h UTC).
Inclui projecoes quantitativas de rendimento diario em Reais (R$/dia).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from evolution.fitness_evaluator import (
    TradeRecord,
    PerformanceReport,
    evaluate_strategy_performance
)


@dataclass
class HybridAlphaConfig:
    """Configuracao do motor quantitativo hibrido."""
    symbols: List[str] = field(default_factory=lambda: ["LINKUSDT", "BNBUSDT", "SOLUSDT"])
    initial_balance_usd: float = 1000.0
    usd_brl_rate: float = 5.65
    funding_rate_per_8h: float = 0.00025  # ~27.3% ao ano estavel
    funding_allocation_pct: float = 0.70  # 70% em arbitragem passiva
    price_action_allocation_pct: float = 0.30  # 30% em operacoes cirurgicas
    ny_session_start_hour: int = 13
    ny_session_end_hour: int = 18
    risk_per_trade_pct: float = 0.015
    target_rr_ratio: float = 2.0
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage_pct: float = 0.0003


@dataclass
class DailyProjections:
    """Projecoes de retorno diario em Reais para diferentes faixas de banca."""
    bankroll_brl_10: float
    bankroll_brl_100: float
    bankroll_brl_300: float
    bankroll_brl_500: float
    bankroll_brl_1000: float
    daily_gain_brl_10: float
    daily_gain_brl_100: float
    daily_gain_brl_300: float
    daily_gain_brl_500: float
    daily_gain_brl_1000: float
    annual_return_pct: float


@dataclass
class HybridMonthReport:
    """Relatorio consolidado mensal do motor hibrido."""
    month_label: str
    initial_balance_usd: float
    final_balance_usd: float
    funding_income_usd: float
    price_action_pnl_usd: float
    total_return_pct: float
    trades_count: int
    win_rate_pct: float
    daily_average_brl: float


def is_ny_session(dt: datetime, start_h: int = 13, end_h: int = 18) -> bool:
    """Verifica se o timestamp pertence a janela nobre de Nova York."""
    return start_h <= dt.hour <= end_h


def is_funding_hour(dt: datetime) -> bool:
    """Verifica se e horario de liquidacao de taxa de financiamento (00h, 08h, 16h UTC)."""
    return dt.hour in (0, 8, 16) and dt.minute == 0


def _check_bull_pin_bar(
    c: Dict[str, Any],
    ema50: float,
    vol_ma: float,
    last_low: float,
    body: float,
    lower_wick: float
) -> Tuple[bool, float, float]:
    """Valida gatilho altista de Pin Bar em suporte com volume."""
    c_p = c["close_price"]
    l_p = c["low_price"]
    if c_p > ema50 and lower_wick >= 1.5 * max(0.001, body) and c["volume"] > vol_ma:
        if (l_p - last_low) / max(0.001, l_p) <= 0.012:
            sl = l_p * 0.997
            risk = c_p - sl
            if risk > 0:
                return True, sl, c_p + 2.0 * risk
    return False, 0.0, 0.0


def _check_bear_pin_bar(
    c: Dict[str, Any],
    ema50: float,
    vol_ma: float,
    last_high: float,
    body: float,
    upper_wick: float
) -> Tuple[bool, float, float]:
    """Valida gatilho baixista de Pin Bar em resistencia com volume."""
    c_p = c["close_price"]
    h_p = c["high_price"]
    if c_p < ema50 and upper_wick >= 1.5 * max(0.001, body) and c["volume"] > vol_ma:
        if (last_high - h_p) / max(0.001, h_p) <= 0.012:
            sl = h_p * 1.003
            risk = sl - c_p
            if risk > 0:
                return True, sl, c_p - 2.0 * risk
    return False, 0.0, 0.0


def detect_pin_bar_signal(
    c: Dict[str, Any],
    ema50: float,
    vol_ma: float,
    last_low: float,
    last_high: float
) -> Tuple[bool, str, float, float]:
    """Detecta rejeicao de pavio (Pin Bar) em suporte ou resistencia na sessao de NY."""
    c_p = c["close_price"]
    o_p = c["open_price"]
    body = abs(c_p - o_p)
    lower_wick = min(c_p, o_p) - c["low_price"]
    upper_wick = c["high_price"] - max(c_p, o_p)

    valid_bull, sl_b, tp_b = _check_bull_pin_bar(c, ema50, vol_ma, last_low, body, lower_wick)
    if valid_bull:
        return True, "BUY", sl_b, tp_b

    valid_bear, sl_s, tp_s = _check_bear_pin_bar(c, ema50, vol_ma, last_high, body, upper_wick)
    if valid_bear:
        return True, "SELL", sl_s, tp_s

    return False, "", 0.0, 0.0


def _check_stop_loss_trigger(pos: Dict[str, Any], c: Dict[str, Any], config: HybridAlphaConfig) -> Tuple[bool, float]:
    """Verifica acionamento de Stop Loss para compra ou venda."""
    if pos["side"] == "BUY" and c["low_price"] <= pos["sl"]:
        return True, pos["sl"] * (1.0 - config.slippage_pct)
    if pos["side"] == "SELL" and c["high_price"] >= pos["sl"]:
        return True, pos["sl"] * (1.0 + config.slippage_pct)
    return False, 0.0


def _check_take_profit_trigger(pos: Dict[str, Any], c: Dict[str, Any], config: HybridAlphaConfig) -> Tuple[bool, float]:
    """Verifica acionamento de Take Profit para compra ou venda."""
    if pos["side"] == "BUY" and c["high_price"] >= pos["tp"]:
        return True, pos["tp"] * (1.0 - config.slippage_pct)
    if pos["side"] == "SELL" and c["low_price"] <= pos["tp"]:
        return True, pos["tp"] * (1.0 + config.slippage_pct)
    return False, 0.0


def check_trade_exit(
    pos: Dict[str, Any],
    c: Dict[str, Any],
    dt: datetime,
    config: HybridAlphaConfig
) -> Tuple[bool, float, str]:
    """Verifica condicoes de saida para ordem de Price Action."""
    sl_hit, sl_price = _check_stop_loss_trigger(pos, c, config)
    if sl_hit:
        return True, sl_price, "SL"

    tp_hit, tp_price = _check_take_profit_trigger(pos, c, config)
    if tp_hit:
        return True, tp_price, "TP"

    if dt.hour >= 20 or pos["bars"] >= 16:
        slip = -config.slippage_pct if pos["side"] == "BUY" else config.slippage_pct
        return True, c["close_price"] * (1.0 + slip), "TIME"

    return False, 0.0, ""


def process_closed_trade(
    pos: Dict[str, Any],
    exit_price: float,
    config: HybridAlphaConfig
) -> float:
    """Calcula PnL liquido deduzindo taxa maker de entrada e taker de saida."""
    if pos["side"] == "BUY":
        pnl_pct = (exit_price - pos["entry"]) / pos["entry"]
    else:
        pnl_pct = (pos["entry"] - exit_price) / pos["entry"]

    notional = pos["size"] * pos["entry"]
    pnl_gross = notional * pnl_pct
    fee = notional * (config.maker_fee + config.taker_fee)
    return round(pnl_gross - fee, 4)


def compute_daily_projections(annual_ret_pct: float, usd_brl: float = 5.65) -> DailyProjections:
    """Calcula projecoes matematicas realistas de ganho em R$/dia por faixa de banca."""
    daily_rate = (1.0 + annual_ret_pct / 100.0) ** (1.0 / 365.0) - 1.0

    b10 = 10.0
    b100 = 100.0
    b300 = 300.0
    b500 = 500.0
    b1000 = 1000.0

    return DailyProjections(
        bankroll_brl_10=b10,
        bankroll_brl_100=b100,
        bankroll_brl_300=b300,
        bankroll_brl_500=b500,
        bankroll_brl_1000=b1000,
        daily_gain_brl_10=round(b10 * daily_rate, 2),
        daily_gain_brl_100=round(b100 * daily_rate, 2),
        daily_gain_brl_300=round(b300 * daily_rate, 2),
        daily_gain_brl_500=round(b500 * daily_rate, 2),
        daily_gain_brl_1000=round(b1000 * daily_rate, 2),
        annual_return_pct=round(annual_ret_pct, 2)
    )
