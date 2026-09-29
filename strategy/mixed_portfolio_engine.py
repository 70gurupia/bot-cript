"""
Motor Hibrido Misto Multi-Estrategia (Mixed Portfolio Engine).
Orquestra 4 frentes com posicoes ativas, gestao de estado e Anti-Martingale:
1. Micro-Scalp de Centavos em 15m (BTCUSDT: TP +0.25%, SL -0.25%, tempo max 4 barras).
2. Price Action Nova York em 1h (SOL, LINK, BNB: TP +1.0%, SL -0.5%, tempo max 8 barras).
3. Carry Trade de Funding Rate Passivo (creditado diariamente).
4. Reinvestimento Composto Anti-Martingale (+25% em vitorias consecutivas, reset imediato na perda).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class MixedPortfolioConfig:
    """Parametros operacionais do motor misto multi-estrategia."""
    initial_bankroll_brl: float = 10.0
    target_bankroll_brl: float = 10000.0
    base_risk_pct: float = 0.05          # 5% de risco base da banca por trade
    win_expansion_pct: float = 0.25      # Expansao de 25% na vitoria consecutiva
    max_streak_expansion: int = 3        # Trava de realizacao apos 3 vitorias consecutivas
    min_trade_brl: float = 0.40          # Lote minimo operacional
    funding_rate_8h: float = 0.00025     # Taxa media de funding (~27% ao ano)
    maker_fee: float = 0.0002            # Taxa Maker passiva
    taker_fee: float = 0.0004            # Taxa Taker ativa
    ny_session_start: int = 13           # 13:00 UTC
    ny_session_end: int = 18             # 18:00 UTC
    leverage: float = 4.0                # Alavancagem moderada para micro-capital


@dataclass
class ActivePosition:
    """Representa uma ordem de mercado ativa em monitoramento."""
    strategy_type: str  # "SCALP" ou "NY"
    symbol: str
    side: str
    entry_price: float
    tp_price: float
    sl_price: float
    stake_brl: float
    bars_held: int = 0
    max_bars: int = 4


@dataclass
class MixedDaySummary:
    """Resumo consolidado de um dia operacional misto."""
    date_str: str
    starting_balance: float
    ending_balance: float
    total_trades: int
    winning_trades: int
    funding_earned_brl: float
    net_pnl_brl: float
    peak_balance: float


def compute_bb_bands_simple(
    prices: List[float],
    period: int = 20,
    num_std: float = 1.8
) -> Tuple[float, float, float]:
    """Calcula a ultima barra das Bandas de Bollinger."""
    if len(prices) < period:
        p = prices[-1] if prices else 0.0
        return p, p, p
    window = prices[-period:]
    mean = sum(window) / float(period)
    variance = sum((x - mean) ** 2 for x in window) / float(period)
    std = math.sqrt(variance)
    return mean, mean - num_std * std, mean + num_std * std


def calculate_mixed_stake(
    bankroll: float,
    streak: int,
    config: MixedPortfolioConfig
) -> float:
    """Calcula o lote da operacao aplicando Anti-Martingale com teto de seguranca."""
    base_stake = max(config.min_trade_brl, bankroll * config.base_risk_pct)
    if streak <= 0:
        return base_stake
    effective_streak = min(streak, config.max_streak_expansion)
    multiplier = (1.0 + config.win_expansion_pct) ** effective_streak
    max_cap = bankroll * 0.35
    return min(max_cap, base_stake * multiplier)


def check_scalp_entry_15m(
    c: Dict[str, Any],
    prev_close: float,
    lower_bb: float,
    upper_bb: float
) -> Tuple[bool, str]:
    """Identifica reversao estocastica em 15m para micro-scalping."""
    cp = c["close_price"]
    lp = c["low_price"]
    hp = c["high_price"]
    if lp <= lower_bb and cp > prev_close:
        return True, "BUY"
    if hp >= upper_bb and cp < prev_close:
        return True, "SELL"
    return False, ""


def check_ny_pinbar_entry_1h(
    c: Dict[str, Any],
    hour_utc: int,
    config: MixedPortfolioConfig
) -> Tuple[bool, str]:
    """Identifica rejeicao de pavio institucional na sessao de Nova York."""
    if not (config.ny_session_start <= hour_utc <= config.ny_session_end):
        return False, ""
    op = c["open_price"]
    cp = c["close_price"]
    hp = c["high_price"]
    lp = c["low_price"]
    rng = hp - lp
    if rng <= 0:
        return False, ""
    body = abs(cp - op)
    lower_wick = min(op, cp) - lp
    upper_wick = hp - max(op, cp)

    if (lower_wick / rng >= 0.55) and (body / rng <= 0.35):
        return True, "BUY"
    if (upper_wick / rng >= 0.55) and (body / rng <= 0.35):
        return True, "SELL"
    return False, ""


def _check_tp_trigger(pos: ActivePosition, high_p: float, low_p: float) -> bool:
    """Verifica se a barra atual acionou o Take Profit."""
    if pos.side == "BUY" and high_p >= pos.tp_price:
        return True
    if pos.side == "SELL" and low_p <= pos.tp_price:
        return True
    return False


def _check_sl_trigger(pos: ActivePosition, high_p: float, low_p: float) -> bool:
    """Verifica se a barra atual acionou o Stop Loss."""
    if pos.side == "BUY" and low_p <= pos.sl_price:
        return True
    if pos.side == "SELL" and high_p >= pos.sl_price:
        return True
    return False


def _calc_net_pnl(pos: ActivePosition, exit_price: float, config: MixedPortfolioConfig) -> float:
    """Calcula o resultado financeiro liquido deduzindo taxas de corretora."""
    fee_rate = config.maker_fee if pos.strategy_type == "SCALP" else config.taker_fee
    if pos.side == "BUY":
        gross_pct = (exit_price - pos.entry_price) / pos.entry_price
    else:
        gross_pct = (pos.entry_price - exit_price) / pos.entry_price
    notional = pos.stake_brl * config.leverage
    return (notional * gross_pct) - (notional * fee_rate * 2.0)


def update_and_check_position(
    pos: ActivePosition,
    high_p: float,
    low_p: float,
    close_p: float,
    config: MixedPortfolioConfig
) -> Tuple[bool, float, bool]:
    """Atualiza a barra da posicao e verifica se atingiu TP, SL ou limite de tempo."""
    pos.bars_held += 1

    if _check_tp_trigger(pos, high_p, low_p):
        return True, _calc_net_pnl(pos, pos.tp_price, config), True

    if _check_sl_trigger(pos, high_p, low_p):
        return True, _calc_net_pnl(pos, pos.sl_price, config), False

    if pos.bars_held >= pos.max_bars:
        is_win = (close_p > pos.entry_price) if pos.side == "BUY" else (pos.entry_price > close_p)
        return True, _calc_net_pnl(pos, close_p, config), is_win

    return False, 0.0, False


def _process_active_positions(
    active_positions: List[ActivePosition],
    high_p: float,
    low_p: float,
    close_p: float,
    config: MixedPortfolioConfig
) -> Tuple[List[ActivePosition], float, int, int]:
    """Processa todas as posicoes ativas do ativo atual."""
    retained = []
    total_pnl = 0.0
    closed_count = 0
    win_count = 0

    for pos in active_positions:
        closed, pnl, is_win = update_and_check_position(pos, high_p, low_p, close_p, config)
        if closed:
            total_pnl += pnl
            closed_count += 1
            win_count += (1 if is_win else 0)
        else:
            retained.append(pos)

    return retained, total_pnl, closed_count, win_count


def _open_new_scalp_position(
    c: Dict[str, Any],
    prev_close: float,
    lower_bb: float,
    upper_bb: float,
    bankroll: float,
    streak: int,
    config: MixedPortfolioConfig
) -> Optional[ActivePosition]:
    """Cria nova posicao de scalping em BTCUSDT."""
    should_enter, side = check_scalp_entry_15m(c, prev_close, lower_bb, upper_bb)
    if not should_enter:
        return None
    ep = c["close_price"]
    tp = ep * 1.0025 if side == "BUY" else ep * 0.9975
    sl = ep * 0.9975 if side == "BUY" else ep * 1.0025
    stake = calculate_mixed_stake(bankroll, streak, config)
    return ActivePosition(
        strategy_type="SCALP",
        symbol="BTCUSDT",
        side=side,
        entry_price=ep,
        tp_price=tp,
        sl_price=sl,
        stake_brl=stake,
        bars_held=0,
        max_bars=4
    )


def _open_new_ny_position(
    c: Dict[str, Any],
    symbol: str,
    hour_utc: int,
    bankroll: float,
    streak: int,
    config: MixedPortfolioConfig
) -> Optional[ActivePosition]:
    """Cria nova posicao de Price Action em altcoin na sessao de NY."""
    should_enter, side = check_ny_pinbar_entry_1h(c, hour_utc, config)
    if not should_enter:
        return None
    ep = c["close_price"]
    tp = ep * 1.010 if side == "BUY" else ep * 0.990
    sl = ep * 0.995 if side == "BUY" else ep * 1.005
    stake = calculate_mixed_stake(bankroll, streak, config)
    return ActivePosition(
        strategy_type="NY",
        symbol=symbol,
        side=side,
        entry_price=ep,
        tp_price=tp,
        sl_price=sl,
        stake_brl=stake,
        bars_held=0,
        max_bars=8
    )


def _handle_daily_rollover(
    history: List[MixedDaySummary],
    cur_date: Any,
    day_start_b: float,
    bankroll: float,
    day_trd: int,
    day_w: int,
    day_fund: float,
    peak_b: float,
    config: MixedPortfolioConfig
) -> Tuple[float, float, float]:
    """Processa a virada do dia, salvando resumo e creditando funding rate diario."""
    if cur_date is not None:
        history.append(MixedDaySummary(
            date_str=str(cur_date),
            starting_balance=round(day_start_b, 2),
            ending_balance=round(bankroll, 2),
            total_trades=day_trd,
            winning_trades=day_w,
            funding_earned_brl=round(day_fund, 3),
            net_pnl_brl=round(bankroll - day_start_b, 2),
            peak_balance=round(peak_b, 2)
        ))
    fund_inc = (bankroll * 0.25) * (config.funding_rate_8h * 3.0)
    new_bankroll = bankroll + fund_inc
    return new_bankroll, new_bankroll, fund_inc


def _step_scalp_flow(
    active_scalps: List[ActivePosition],
    c: Dict[str, Any],
    prev_close: float,
    closes_slice: List[float],
    bankroll: float,
    streak: int,
    config: MixedPortfolioConfig
) -> Tuple[List[ActivePosition], float, int, int, int]:
    """Executa a rotina de atualizacao e abertura de Scalp em 15m."""
    updated, pnl, trd, win = _process_active_positions(
        active_scalps, c["high_price"], c["low_price"], c["close_price"], config
    )
    new_streak = streak
    if trd > 0:
        new_streak = (streak + 1) if win > 0 else 0

    if len(updated) == 0 and bankroll > 1.0:
        _, l_bb, u_bb = compute_bb_bands_simple(closes_slice, period=20, num_std=1.8)
        new_pos = _open_new_scalp_position(c, prev_close, l_bb, u_bb, bankroll, new_streak, config)
        if new_pos:
            updated.append(new_pos)

    return updated, pnl, trd, win, new_streak


def _step_ny_flow(
    active_ny: List[ActivePosition],
    t_open: int,
    hour_utc: int,
    bankroll: float,
    streak: int,
    alt_by_time: Dict[str, Dict[int, Dict[str, Any]]],
    config: MixedPortfolioConfig
) -> Tuple[List[ActivePosition], float, int, int, int]:
    """Executa a rotina de atualizacao e abertura de trades NY em altcoins."""
    total_pnl = 0.0
    total_trd = 0
    total_win = 0
    current_streak = streak
    current_active = active_ny[:]

    for sym in ["SOLUSDT", "LINKUSDT", "BNBUSDT"]:
        c_1h = alt_by_time.get(sym, {}).get(t_open)
        if not c_1h:
            continue

        pair_ny = [p for p in current_active if p.symbol == sym]
        other_ny = [p for p in current_active if p.symbol != sym]
        upd, pnl, trd, win = _process_active_positions(pair_ny, c_1h["high_price"], c_1h["low_price"], c_1h["close_price"], config)
        current_active = other_ny + upd
        total_pnl += pnl
        total_trd += trd
        total_win += win
        if trd > 0:
            current_streak = (current_streak + 1) if win > 0 else 0

        if len([p for p in current_active if p.symbol == sym]) == 0 and len(current_active) < 2:
            new_p = _open_new_ny_position(c_1h, sym, hour_utc, bankroll, current_streak, config)
            if new_p:
                current_active.append(new_p)

    return current_active, total_pnl, total_trd, total_win, current_streak


def _compile_summary_report(
    daily_history: List[MixedDaySummary],
    bankroll: float,
    peak_bankroll: float,
    config: MixedPortfolioConfig
) -> Dict[str, Any]:
    """Compila os dados da simulacao em relatorio final estruturado."""
    total_days = len(daily_history)
    positive_days = sum(1 for d in daily_history if d.net_pnl_brl > 0)
    total_trd = sum(d.total_trades for d in daily_history)
    total_w = sum(d.winning_trades for d in daily_history)
    total_fund = sum(d.funding_earned_brl for d in daily_history)
    win_rate = round((total_w / total_trd * 100.0), 1) if total_trd else 0.0
    net_profit = round(bankroll - config.initial_bankroll_brl, 2)

    return {
        "initial_bankroll_brl": config.initial_bankroll_brl,
        "final_bankroll_brl": round(bankroll, 2),
        "total_net_profit_brl": net_profit,
        "total_return_pct": round((net_profit / config.initial_bankroll_brl) * 100.0, 2),
        "peak_bankroll_brl": round(peak_bankroll, 2),
        "total_days": total_days,
        "positive_days": positive_days,
        "positive_days_pct": round((positive_days / total_days * 100.0), 1) if total_days else 0.0,
        "total_trades": total_trd,
        "overall_win_rate_pct": win_rate,
        "total_funding_earned_brl": round(total_fund, 2),
        "reached_target_10k": bankroll >= config.target_bankroll_brl,
        "daily_average_gain_brl": round(net_profit / total_days, 2) if total_days else 0.0
    }


def simulate_mixed_portfolio_year(
    candles_15m_btc: List[Dict[str, Any]],
    candles_1h_altcoins: Dict[str, List[Dict[str, Any]]],
    config: MixedPortfolioConfig
) -> Dict[str, Any]:
    """Executa o backtest do motor misto com complexidade controlada <= 10."""
    bankroll = config.initial_bankroll_brl
    peak_bankroll = bankroll
    streak = 0
    daily_history: List[MixedDaySummary] = []
    current_day = None

    day_trades, day_wins = 0, 0
    day_funding = 0.0
    day_start_balance = bankroll

    closes_btc = [c["close_price"] for c in candles_15m_btc]
    alt_by_time = {sym: {c["open_time"]: c for c in c_list} for sym, c_list in candles_1h_altcoins.items()}
    active_scalps: List[ActivePosition] = []
    active_ny: List[ActivePosition] = []

    for i in range(25, len(candles_15m_btc)):
        c = candles_15m_btc[i]
        dt = datetime.fromtimestamp(c["open_time"] / 1000.0, tz=timezone.utc)

        if dt.date() != current_day:
            bankroll, day_start_balance, fund_inc = _handle_daily_rollover(
                daily_history, current_day, day_start_balance, bankroll, day_trades, day_wins, day_funding, peak_bankroll, config
            )
            current_day = dt.date()
            day_trades, day_wins, day_funding = 0, 0, fund_inc

        if bankroll <= 0.80 or bankroll >= config.target_bankroll_brl:
            continue

        active_scalps, pnl_s, trd_s, win_s, streak = _step_scalp_flow(
            active_scalps, c, closes_btc[i-1], closes_btc[max(0, i-20):i+1], bankroll, streak, config
        )
        bankroll += pnl_s
        day_trades += trd_s
        day_wins += win_s

        if dt.minute == 0 and bankroll > 1.0:
            active_ny, pnl_ny, trd_ny, win_ny, streak = _step_ny_flow(
                active_ny, c["open_time"], dt.hour, bankroll, streak, alt_by_time, config
            )
            bankroll += pnl_ny
            day_trades += trd_ny
            day_wins += win_ny

        peak_bankroll = max(peak_bankroll, bankroll)

    _handle_daily_rollover(daily_history, current_day, day_start_balance, bankroll, day_trades, day_wins, day_funding, peak_bankroll, config)
    return _compile_summary_report(daily_history, bankroll, peak_bankroll, config)
