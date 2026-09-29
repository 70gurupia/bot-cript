"""
Motor de Micro-Scalping de Centavos (Cent Scalper Engine).
Implementa a captura sistematica de micro-flutuacoes de +0.25% para gerar
ganhos fracionados (10 trades de R$ 0,10 = R$ 1,00/dia), com trava automatica
de meta batida (Daily Profit Lock) e controle estrito de perda diaria.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class CentScalperConfig:
    """Parametros operacionais do motor de micro-scalping."""
    initial_bankroll_brl: float = 10.0
    target_cent_per_trade_brl: float = 0.10
    daily_profit_target_brl: float = 1.00
    daily_max_loss_brl: float = 0.30
    price_target_pct: float = 0.0025  # +0.25% de deslocamento do ativo
    price_stop_pct: float = 0.0025    # -0.25% de stop loss simetrico
    time_stop_bars: int = 4           # 4 barras de 15m (1 hora)
    leverage: float = 5.0             # Alavancagem isolada
    maker_fee: float = 0.0002         # 0.02% taxa Maker da exchange
    taker_fee: float = 0.0004         # 0.04% taxa Taker
    max_daily_attempts: int = 15      # Limite maximo de operacoes no dia


@dataclass
class CentScalperDayResult:
    """Resultado individual de um dia de micro-scalping."""
    date_str: str
    trades_count: int
    winning_trades: int
    net_pnl_brl: float
    goal_reached: bool
    stopped_loss: bool


def compute_bollinger_bands(
    prices: List[float],
    period: int = 20,
    num_std: float = 1.8
) -> Tuple[List[float], List[float], List[float]]:
    """Calcula Bandas de Bollinger com a biblioteca padrao do Python."""
    if len(prices) < period:
        return prices[:], prices[:], prices[:]

    means = []
    lowers = []
    uppers = []

    for i in range(len(prices)):
        if i < period - 1:
            means.append(prices[i])
            lowers.append(prices[i])
            uppers.append(prices[i])
            continue
        window = prices[i - period + 1 : i + 1]
        m = sum(window) / float(period)
        variance = sum((x - m) ** 2 for x in window) / float(period)
        std = math.sqrt(variance)
        means.append(m)
        lowers.append(m - num_std * std)
        uppers.append(m + num_std * std)

    return means, lowers, uppers


def check_scalp_entry_condition(
    candle: Dict[str, Any],
    prev_close: float,
    lower_bb: float,
    upper_bb: float
) -> Tuple[bool, str]:
    """Identifica reversao a media em microestrutura estocastica."""
    c_p = candle["close_price"]
    l_p = candle["low_price"]
    h_p = candle["high_price"]

    if l_p <= lower_bb and c_p > prev_close:
        return True, "BUY"
    if h_p >= upper_bb and c_p < prev_close:
        return True, "SELL"

    return False, ""


def _check_target_hit(pos: Dict[str, Any], candle: Dict[str, Any]) -> Tuple[bool, float, bool]:
    """Verifica se o Take Profit (+0.25%) foi alcancado."""
    if pos["side"] == "BUY" and candle["high_price"] >= pos["tp"]:
        return True, pos["tp"], True
    if pos["side"] == "SELL" and candle["low_price"] <= pos["tp"]:
        return True, pos["tp"], True
    return False, 0.0, False


def _check_stop_or_time_hit(
    pos: Dict[str, Any],
    candle: Dict[str, Any],
    config: CentScalperConfig
) -> Tuple[bool, float, bool]:
    """Verifica Stop Loss (-0.25%) ou encerramento por tempo."""
    if pos["side"] == "BUY" and candle["low_price"] <= pos["sl"]:
        return True, pos["sl"], False
    if pos["side"] == "SELL" and candle["high_price"] >= pos["sl"]:
        return True, pos["sl"], False

    if pos["bars"] >= config.time_stop_bars:
        c_p = candle["close_price"]
        is_win = (c_p > pos["entry"]) if pos["side"] == "BUY" else (pos["entry"] > c_p)
        return True, c_p, is_win

    return False, 0.0, False


def _check_scalp_exit(
    pos: Dict[str, Any],
    candle: Dict[str, Any],
    config: CentScalperConfig
) -> Tuple[bool, float, bool]:
    """Verifica gatilhos compostos de saida para a posicao de scalping."""
    target_hit, tp_p, is_tp_win = _check_target_hit(pos, candle)
    if target_hit:
        return True, tp_p, is_tp_win
    return _check_stop_or_time_hit(pos, candle, config)


def process_active_scalp(
    pos: Dict[str, Any],
    candle: Dict[str, Any],
    config: CentScalperConfig,
    bankroll: float
) -> Tuple[bool, float, bool]:
    """Processa a barra atual e calcula o resultado liquido em Reais (BRL)."""
    pos["bars"] += 1
    exited, exit_price, is_win = _check_scalp_exit(pos, candle, config)
    if not exited:
        return False, 0.0, False

    pnl_pct = (exit_price - pos["entry"]) / pos["entry"] if pos["side"] == "BUY" else (pos["entry"] - exit_price) / pos["entry"]
    notional_brl = bankroll * config.leverage
    pnl_gross = notional_brl * pnl_pct
    fee_brl = notional_brl * (config.maker_fee * 2.0)
    net_pnl_brl = round(pnl_gross - fee_brl, 4)

    return True, net_pnl_brl, is_win


def _check_daily_locks(
    day_profit: float,
    config: CentScalperConfig
) -> Tuple[bool, bool]:
    """Verifica se a meta diaria foi alcancada ou se o stop diario foi acionado."""
    if day_profit >= config.daily_profit_target_brl:
        return True, False
    if day_profit <= -config.daily_max_loss_brl:
        return True, True
    return False, False


def _record_closed_day(
    history: List[CentScalperDayResult],
    current_day: Any,
    trades: int,
    wins: int,
    profit: float,
    config: CentScalperConfig,
    bankroll: float,
    stopped: bool
) -> float:
    """Registra o fechamento de um dia de scalping e atualiza o balanco."""
    if current_day is not None:
        history.append(CentScalperDayResult(
            date_str=str(current_day),
            trades_count=trades,
            winning_trades=wins,
            net_pnl_brl=round(profit, 2),
            goal_reached=profit >= config.daily_profit_target_brl,
            stopped_loss=stopped
        ))
        return max(1.0, bankroll + profit)
    return bankroll


def _try_open_scalp(
    c: Dict[str, Any],
    prev_c: float,
    lower_bb: float,
    upper_bb: float,
    config: CentScalperConfig
) -> Optional[Dict[str, Any]]:
    """Cria nova ordem de scalping caso haja condicao de reversao."""
    should_enter, side = check_scalp_entry_condition(c, prev_c, lower_bb, upper_bb)
    if not should_enter:
        return None
    ep = c["close_price"]
    tp = ep * (1.0 + config.price_target_pct) if side == "BUY" else ep * (1.0 - config.price_target_pct)
    sl = ep * (1.0 - config.price_stop_pct) if side == "BUY" else ep * (1.0 + config.price_stop_pct)
    return {"side": side, "entry": ep, "tp": tp, "sl": sl, "bars": 0}


def _handle_position_or_entry(
    pos: Optional[Dict[str, Any]],
    c: Dict[str, Any],
    prev_close: float,
    lower_bb: float,
    upper_bb: float,
    config: CentScalperConfig,
    bankroll: float,
    day_trades: int
) -> Tuple[Optional[Dict[str, Any]], float, int, int]:
    """Processa posicao aberta existente ou tenta abrir uma nova ordem."""
    if pos is not None:
        closed, net_pnl, is_win = process_active_scalp(pos, c, config, bankroll)
        if closed:
            return None, net_pnl, 1, (1 if is_win else 0)
        return pos, 0.0, 0, 0
    if day_trades < config.max_daily_attempts:
        new_pos = _try_open_scalp(c, prev_close, lower_bb, upper_bb, config)
        return new_pos, 0.0, 0, 0
    return None, 0.0, 0, 0


def simulate_cent_scalper_year(
    candles: List[Dict[str, Any]],
    config: CentScalperConfig
) -> Dict[str, Any]:
    """Executa o teste historico dia a dia de colheita de micro-ganhos de centavos."""
    if len(candles) < 30:
        return {"error": "Candles insuficientes"}

    closes = [c["close_price"] for c in candles]
    _, lowers, uppers = compute_bollinger_bands(closes, period=20, num_std=1.8)

    bankroll = config.initial_bankroll_brl
    days_history: List[CentScalperDayResult] = []
    current_day = None

    day_trades = 0
    day_profit = 0.0
    day_locked = False
    day_stopped = False
    day_wins = 0

    total_trades = 0
    total_wins = 0
    pos: Optional[Dict[str, Any]] = None

    for i in range(25, len(candles)):
        c = candles[i]
        dt = datetime.fromtimestamp(c["open_time"] / 1000.0, tz=timezone.utc).date()

        if dt != current_day:
            bankroll = _record_closed_day(days_history, current_day, day_trades, day_wins, day_profit, config, bankroll, day_stopped)
            current_day, day_trades, day_profit, day_locked, day_stopped, day_wins = dt, 0, 0.0, False, False, 0
            pos = None

        if day_locked:
            continue

        pos, net_pnl, inc_trd, inc_win = _handle_position_or_entry(
            pos, c, closes[i - 1], lowers[i], uppers[i], config, bankroll, day_trades
        )
        if inc_trd > 0:
            day_profit += net_pnl
            day_trades += inc_trd
            total_trades += inc_trd
            day_wins += inc_win
            total_wins += inc_win
            day_locked, day_stopped = _check_daily_locks(day_profit, config)

    bankroll = _record_closed_day(days_history, current_day, day_trades, day_wins, day_profit, config, bankroll, day_stopped)

    total_days = len(days_history)
    positive_days = sum(1 for d in days_history if d.net_pnl_brl > 0)
    goal_days = sum(1 for d in days_history if d.goal_reached)
    total_net_profit_brl = round(bankroll - config.initial_bankroll_brl, 2)
    win_rate = round((total_wins / total_trades * 100.0), 1) if total_trades > 0 else 0.0

    return {
        "initial_bankroll_brl": config.initial_bankroll_brl,
        "final_bankroll_brl": round(bankroll, 2),
        "total_net_profit_brl": total_net_profit_brl,
        "total_return_pct": round((total_net_profit_brl / config.initial_bankroll_brl) * 100.0, 2),
        "total_days": total_days,
        "positive_days": positive_days,
        "positive_days_pct": round((positive_days / total_days * 100.0), 1) if total_days else 0.0,
        "goal_reached_days": goal_days,
        "total_trades": total_trades,
        "overall_win_rate_pct": win_rate,
        "daily_average_gain_brl": round(total_net_profit_brl / total_days, 2) if total_days else 0.0
    }
