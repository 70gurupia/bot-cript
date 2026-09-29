"""
Motor de Execucao Intraday e Day Trade em 15 Minutos.
Aplica regras estritas de fechamento compulsorio no fim do dia (EOD Flat as 23:45 UTC),
limite maximo de operacoes diarias, stop de perda diaria (Daily Loss Limit),
cooldown entre trades e anualizacao de 15m (35.040 barras/ano).
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from evolution.fitness_evaluator import (
    TradeRecord,
    PerformanceReport,
    evaluate_strategy_performance,
    FIFTEEN_MIN_ANNUALIZATION_FACTOR
)


@dataclass
class DayTradeConfig:
    """Parametros operacionais para Day Trade em barras de 15 minutos."""
    symbol: str = "BTCUSDT"
    initial_balance: float = 10000.0
    leverage: float = 2.0
    risk_per_trade_pct: float = 0.01  # 1.0% do capital por operacao
    stop_loss_pct: float = 0.008      # 0.8% Stop Loss rapido
    take_profit_pct: float = 0.018    # 1.8% Take Profit rapido
    max_hold_bars: int = 16           # Maximo 4 horas em barras de 15m
    max_daily_trades: int = 3         # Maximo de 3 operacoes por dia
    max_daily_loss_pct: float = 0.015 # 1.5% Perda maxima por sessao diaria
    cooldown_bars: int = 4            # 1 hora (4 velas de 15m) de intervalo
    eod_flat_hour_utc: int = 23
    eod_flat_minute_utc: int = 45
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage_pct: float = 0.0005


@dataclass
class DayTradePosition:
    """Posicao intraday aberta."""
    entry_time: int
    entry_price: float
    side: str  # "BUY" ou "SELL"
    size: float
    stop_loss: float
    take_profit: float
    bars_held: int = 0


@dataclass
class DayTradeReport:
    """Resultado detalhado de uma sessao ou mes de Day Trade."""
    symbol: str
    period_start: str
    period_end: str
    total_candles: int
    performance: PerformanceReport
    trades: List[TradeRecord]
    equity_curve: List[float]
    overnight_positions_carried: int = 0  # Invariante: deve ser 0


def is_eod_candle(open_time_ms: int, flat_hour: int = 23, flat_minute: int = 45) -> bool:
    """Determina se o candle corresponde a barra de fechamento compulsorio diario."""
    dt = datetime.fromtimestamp(open_time_ms / 1000.0, tz=timezone.utc)
    return dt.hour == flat_hour and dt.minute >= flat_minute


def compute_fast_ema(prices: List[float], period: int) -> List[float]:
    """Calcula a Media Movel Exponencial rapida sem bibliotecas externas."""
    if not prices:
        return []
    ema = [prices[0]]
    multiplier = 2.0 / (period + 1)
    for price in prices[1:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def compute_fast_rsi(prices: List[float], period: int = 14) -> List[float]:
    """Calcula o Indice de Forca Relativa intraday."""
    if len(prices) <= period:
        return [50.0] * len(prices)
    gains = []
    losses = []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gains.append(max(0.0, delta))
        losses.append(max(0.0, -delta))

    rsi = [50.0] * (period + 1)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0.0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100.0 - (100.0 / (1.0 + rs)))
    return rsi


def generate_daytrade_signals(candles: List[Dict[str, Any]]) -> List[str]:
    """Gera sinais intradiarios de pullback a favor da tendencia (EMA + RSI)."""
    if len(candles) < 25:
        return ["HOLD"] * len(candles)
    closes = [c["close_price"] for c in candles]
    trend_period = min(50, max(15, len(candles) // 3))
    ema_trend = compute_fast_ema(closes, period=trend_period)
    rsi = compute_fast_rsi(closes, period=14)

    signals = ["HOLD"]
    for i in range(1, len(candles)):
        c = candles[i]
        is_bull = c["close_price"] > ema_trend[i]
        is_bear = c["close_price"] < ema_trend[i]

        buy_cond = is_bull and rsi[i - 1] < 48.0 and c["close_price"] > c["open_price"]
        sell_cond = is_bear and rsi[i - 1] > 52.0 and c["close_price"] < c["open_price"]

        if buy_cond:
            signals.append("BUY")
        elif sell_cond:
            signals.append("SELL")
        else:
            signals.append("HOLD")
    return signals


def _check_eod_and_time_exit(
    pos: DayTradePosition,
    candle: Dict[str, Any],
    config: DayTradeConfig
) -> Tuple[bool, float, str]:
    """Verifica saidas por horario EOD ou expiracao de tempo intraday."""
    c = candle["close_price"]
    ot = candle["open_time"]
    if is_eod_candle(ot, config.eod_flat_hour_utc, config.eod_flat_minute_utc):
        slip = -config.slippage_pct if pos.side == "BUY" else config.slippage_pct
        return True, c * (1.0 + slip), "EOD_FLAT"
    if pos.bars_held >= config.max_hold_bars:
        slip = -config.slippage_pct if pos.side == "BUY" else config.slippage_pct
        return True, c * (1.0 + slip), "TIME_LIMIT"
    return False, 0.0, ""


def _check_price_targets(
    pos: DayTradePosition,
    candle: Dict[str, Any],
    config: DayTradeConfig
) -> Tuple[bool, float, str]:
    """Verifica acionamento de Stop Loss e Take Profit."""
    h = candle["high_price"]
    l = candle["low_price"]
    if pos.side == "BUY":
        if l <= pos.stop_loss:
            return True, pos.stop_loss * (1.0 - config.slippage_pct), "STOP_LOSS"
        if h >= pos.take_profit:
            return True, pos.take_profit * (1.0 - config.slippage_pct), "TAKE_PROFIT"
    else:
        if h >= pos.stop_loss:
            return True, pos.stop_loss * (1.0 + config.slippage_pct), "STOP_LOSS"
        if l <= pos.take_profit:
            return True, pos.take_profit * (1.0 + config.slippage_pct), "TAKE_PROFIT"
    return False, 0.0, ""


def _check_exit_conditions(
    pos: DayTradePosition,
    candle: Dict[str, Any],
    config: DayTradeConfig
) -> Tuple[bool, float, str]:
    """Verifica condicoes compostas de saida intraday."""
    exited, price, reason = _check_eod_and_time_exit(pos, candle, config)
    if exited:
        return exited, price, reason
    return _check_price_targets(pos, candle, config)


def _should_block_daily_entry(
    daily_trades: int,
    daily_pnl: float,
    start_bal: float,
    cooldown: int,
    candle: Dict[str, Any],
    config: DayTradeConfig
) -> bool:
    """Bloqueia novas entradas por limite diario de trades, perda maxima, cooldown ou EOD."""
    if cooldown > 0:
        return True
    if daily_trades >= config.max_daily_trades:
        return True
    if start_bal > 0 and (daily_pnl / start_bal) <= -config.max_daily_loss_pct:
        return True
    if is_eod_candle(candle["open_time"], config.eod_flat_hour_utc, config.eod_flat_minute_utc):
        return True
    return False


def _open_new_position(
    signal: str,
    candle: Dict[str, Any],
    balance: float,
    config: DayTradeConfig
) -> Optional[DayTradePosition]:
    """Calcula tamanho de posicao e abre nova ordem com margem isolada."""
    if signal not in ("BUY", "SELL"):
        return None
    c = candle["close_price"]
    exec_price = c * (1.0 + config.slippage_pct) if signal == "BUY" else c * (1.0 - config.slippage_pct)
    risk_amount = balance * config.risk_per_trade_pct
    notional_value = min((risk_amount / config.stop_loss_pct) * config.leverage, balance * config.leverage * 0.95)
    size = notional_value / exec_price

    if signal == "BUY":
        sl = exec_price * (1.0 - config.stop_loss_pct)
        tp = exec_price * (1.0 + config.take_profit_pct)
    else:
        sl = exec_price * (1.0 + config.stop_loss_pct)
        tp = exec_price * (1.0 - config.take_profit_pct)

    return DayTradePosition(
        entry_time=candle["open_time"],
        entry_price=exec_price,
        side=signal,
        size=size,
        stop_loss=sl,
        take_profit=tp,
        bars_held=0
    )


def _execute_trade_close(
    pos: DayTradePosition,
    exit_price: float,
    exit_time: int,
    config: DayTradeConfig
) -> Tuple[float, TradeRecord]:
    """Calcula PnL, deduz taxas e gera o registro de trade."""
    if pos.side == "BUY":
        pnl_pct = (exit_price - pos.entry_price) / pos.entry_price
    else:
        pnl_pct = (pos.entry_price - exit_price) / pos.entry_price

    notional = pos.size * pos.entry_price
    pnl_abs = notional * pnl_pct
    fee = notional * (config.taker_fee * 2.0)
    net_pnl = pnl_abs - fee

    rec = TradeRecord(
        entry_time=pos.entry_time,
        exit_time=exit_time,
        entry_price=pos.entry_price,
        exit_price=exit_price,
        side=pos.side,
        size=pos.size,
        pnl_abs=round(pnl_abs, 4),
        pnl_pct=round(pnl_pct * 100.0, 4),
        fee_paid=round(fee, 4)
    )
    return net_pnl, rec


def _compute_bar_equity(pos: Optional[DayTradePosition], candle: Dict[str, Any], balance: float) -> float:
    """Calcula o valor liquido da conta considerando lucro/prejuizo flutuante."""
    if pos is None:
        return balance
    c = candle["close_price"]
    pnl_pct = (c - pos.entry_price) / pos.entry_price if pos.side == "BUY" else (pos.entry_price - c) / pos.entry_price
    unrealized = (pos.size * pos.entry_price) * pnl_pct
    return balance + unrealized


def _check_overnight(idx: int, candles: List[Dict[str, Any]]) -> int:
    """Detecta se uma posicao cruzou a meia-noite UTC (invariante de day trade)."""
    if idx <= 0:
        return 0
    dt_prev = datetime.fromtimestamp(candles[idx - 1]["open_time"] / 1000.0, tz=timezone.utc)
    dt_curr = datetime.fromtimestamp(candles[idx]["open_time"] / 1000.0, tz=timezone.utc)
    return 1 if dt_prev.date() != dt_curr.date() else 0


def _build_empty_report(config: DayTradeConfig) -> DayTradeReport:
    """Retorna relatorio neutro para conjunto de candles vazio."""
    empty_perf = evaluate_strategy_performance([], [], [config.initial_balance])
    return DayTradeReport(
        symbol=config.symbol,
        period_start="",
        period_end="",
        total_candles=0,
        performance=empty_perf,
        trades=[],
        equity_curve=[config.initial_balance],
        overnight_positions_carried=0
    )


def _update_existing_position(
    pos: DayTradePosition,
    candle: Dict[str, Any],
    idx: int,
    candles: List[Dict[str, Any]],
    config: DayTradeConfig,
    balance: float
) -> Tuple[Optional[DayTradePosition], float, Optional[TradeRecord], int, int]:
    """Processa a barra atual para uma posicao aberta, verificando saidas e overnight."""
    pos.bars_held += 1
    should_exit, exit_price, _ = _check_exit_conditions(pos, candle, config)
    if should_exit:
        net_pnl, rec = _execute_trade_close(pos, exit_price, candle["open_time"], config)
        new_bal = max(10.0, balance + net_pnl)
        return None, new_bal, rec, config.cooldown_bars, 0
    overnight = _check_overnight(idx, candles)
    return pos, balance, None, 0, overnight


def _try_enter_position(
    idx: int,
    signals: List[str],
    candle: Dict[str, Any],
    balance: float,
    config: DayTradeConfig,
    daily_trades: int,
    daily_pnl: float,
    day_start_bal: float,
    cooldown: int
) -> Tuple[Optional[DayTradePosition], int]:
    """Verifica e executa abertura de nova posicao caso nao bloqueada."""
    if idx >= len(signals):
        return None, 0
    blocked = _should_block_daily_entry(daily_trades, daily_pnl, day_start_bal, cooldown, candle, config)
    if not blocked and signals[idx] in ("BUY", "SELL"):
        new_pos = _open_new_position(signals[idx], candle, balance, config)
        if new_pos is not None:
            return new_pos, 1
    return None, 0


def _handle_day_transition(
    c_date: Any,
    curr_date: Any,
    balance: float,
    daily_trades: int,
    daily_pnl: float,
    day_start_bal: float
) -> Tuple[Any, int, float, float]:
    """Reseta contadores de operacao diaria caso tenha mudado o dia UTC."""
    if c_date != curr_date:
        return c_date, 0, 0.0, balance
    return curr_date, daily_trades, daily_pnl, day_start_bal


def _finalize_remaining_position(
    pos: Optional[DayTradePosition],
    candles: List[Dict[str, Any]],
    config: DayTradeConfig,
    balance: float,
    trades: List[TradeRecord],
    equity_curve: List[float]
) -> float:
    """Encerra compulsoriamente a posicao residual na ultima barra da simulacao."""
    if pos is not None and candles:
        net_pnl, rec = _execute_trade_close(pos, candles[-1]["close_price"], candles[-1]["open_time"], config)
        balance = max(10.0, balance + net_pnl)
        trades.append(rec)
        equity_curve[-1] = round(balance, 2)
    return balance


def simulate_daytrade_session(
    candles: List[Dict[str, Any]],
    config: DayTradeConfig
) -> DayTradeReport:
    """Executa a simulacao rigorosa de Day Trade em 15m para a serie de candles fornecida."""
    if not candles:
        return _build_empty_report(config)

    signals = generate_daytrade_signals(candles)
    balance = max(100.0, config.initial_balance)
    equity_curve = [balance]
    periodic_returns = []
    trades: List[TradeRecord] = []
    position: Optional[DayTradePosition] = None
    overnight_count = 0

    daily_trades = 0
    daily_pnl = 0.0
    day_start_bal = balance
    cooldown = 0
    curr_date = datetime.fromtimestamp(candles[0]["open_time"] / 1000.0, tz=timezone.utc).date()

    for idx, candle in enumerate(candles):
        prev_equity = equity_curve[-1]
        c_date = datetime.fromtimestamp(candle["open_time"] / 1000.0, tz=timezone.utc).date()

        curr_date, daily_trades, daily_pnl, day_start_bal = _handle_day_transition(
            c_date, curr_date, balance, daily_trades, daily_pnl, day_start_bal
        )
        cooldown = max(0, cooldown - 1)

        if position is not None:
            position, balance, rec, new_cd, ovn = _update_existing_position(position, candle, idx, candles, config, balance)
            if rec is not None:
                trades.append(rec)
                daily_pnl += (rec.pnl_abs - rec.fee_paid)
                cooldown = new_cd
            overnight_count += ovn

        if position is None:
            new_pos, inc_trades = _try_enter_position(
                idx, signals, candle, balance, config, daily_trades, daily_pnl, day_start_bal, cooldown
            )
            if new_pos is not None:
                position = new_pos
                daily_trades += inc_trades

        curr_eq = _compute_bar_equity(position, candle, balance)
        equity_curve.append(round(curr_eq, 2))
        bar_ret = (curr_eq - prev_equity) / prev_equity if prev_equity > 0 else 0.0
        periodic_returns.append(bar_ret)

    balance = _finalize_remaining_position(position, candles, config, balance, trades, equity_curve)

    perf = evaluate_strategy_performance(
        trades=trades,
        returns=periodic_returns,
        equity_curve=equity_curve,
        annualization_factor=FIFTEEN_MIN_ANNUALIZATION_FACTOR
    )
    p_start = datetime.fromtimestamp(candles[0]["open_time"] / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    p_end = datetime.fromtimestamp(candles[-1]["open_time"] / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

    return DayTradeReport(
        symbol=config.symbol,
        period_start=p_start,
        period_end=p_end,
        total_candles=len(candles),
        performance=perf,
        trades=trades,
        equity_curve=equity_curve,
        overnight_positions_carried=overnight_count
    )
