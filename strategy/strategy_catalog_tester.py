"""
Testador e Benchmark das Estratégias do Catálogo Quantitativo (2024).
Implementa e avalia 6 famílias operacionais representativas:
1. Cointegração e Pairs Trading (SOL/AVAX)
2. Lead-Lag Temporal (BTC -> ETH)
3. Donchian Channel Breakout (BTC & SOL)
4. Reversão RSI + Bollinger Bands (ADA & XRP)
5. Opening Range Breakout - ORB NY (LINK & BNB)
6. Funding Rate Carry Trade Passivo
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class StrategyResult:
    """Metricas consolidadas de desempenho de uma estrategia."""
    name: str
    symbol_or_pair: str
    timeframe: str
    total_trades: int
    winning_trades: int
    win_rate_pct: float
    total_net_return_pct: float
    profit_factor: float
    max_drawdown_pct: float
    description: str


def compute_rsi_series(prices: List[float], period: int = 14) -> List[float]:
    """Calcula o Indice de Forca Relativa (RSI) para uma serie de precos."""
    if len(prices) <= period:
        return [50.0] * len(prices)
    rsi_vals = [50.0] * period
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
    avg_gain = sum(gains) / float(period)
    avg_loss = sum(losses) / float(period)
    first_rsi = 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))) if avg_loss > 0 else 100.0
    rsi_vals.append(first_rsi)

    for i in range(period + 1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gain = max(0.0, diff)
        loss = max(0.0, -diff)
        avg_gain = (avg_gain * (period - 1) + gain) / float(period)
        avg_loss = (avg_loss * (period - 1) + loss) / float(period)
        rs = avg_gain / avg_loss if avg_loss > 0 else 100.0
        val = 100.0 - (100.0 / (1.0 + rs))
        rsi_vals.append(val)
    return rsi_vals


def _calc_stats(trades: List[float], name: str, pair: str, tf: str, desc: str) -> StrategyResult:
    """Calcula estatisticas padronizadas para uma lista de retornos de trades."""
    if not trades:
        return StrategyResult(name, pair, tf, 0, 0, 0.0, 0.0, 0.0, 0.0, desc)
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = round((len(wins) / len(trades)) * 100.0, 1)
    net_return = round(sum(trades) * 100.0, 2)
    sum_win = sum(wins)
    sum_loss = abs(sum(losses))
    pf = round(sum_win / sum_loss, 2) if sum_loss > 0 else 99.0

    peak = 0.0
    eq = 0.0
    max_dd = 0.0
    for t in trades:
        eq += t
        peak = max(peak, eq)
        dd = peak - eq
        max_dd = max(max_dd, dd)
    return StrategyResult(
        name=name,
        symbol_or_pair=pair,
        timeframe=tf,
        total_trades=len(trades),
        winning_trades=len(wins),
        win_rate_pct=win_rate,
        total_net_return_pct=net_return,
        profit_factor=pf,
        max_drawdown_pct=round(max_dd * 100.0, 1),
        description=desc
    )


def _check_pair_entry(z: float) -> Tuple[bool, int]:
    """Verifica gatilho de entrada por desvio estatístico de Z-Score."""
    if z >= 2.0:
        return True, -1
    if z <= -2.0:
        return True, 1
    return False, 0


def _check_pair_exit(pos_side: int, z: float) -> bool:
    """Verifica condicoes de saida para operacao de arbitragem estatistica."""
    if abs(z) >= 3.5:
        return True
    if pos_side == -1 and z <= 0.0:
        return True
    if pos_side == 1 and z >= 0.0:
        return True
    return False


def test_pairs_cointegration(
    candles_a: List[Dict[str, Any]],
    candles_b: List[Dict[str, Any]],
    pair_label: str = "SOL/AVAX"
) -> StrategyResult:
    """Testa estrategia de Cointegracao e reversao de Z-Score de spread (1h)."""
    n = min(len(candles_a), len(candles_b))
    if n < 60:
        return _calc_stats([], "Cointegração Pairs Trading", pair_label, "1h", "Dados insuficientes")

    closes_a = [c["close_price"] for c in candles_a[:n]]
    closes_b = [c["close_price"] for c in candles_b[:n]]
    spreads = [math.log(closes_a[i]) - math.log(closes_b[i]) for i in range(n)]

    trades = []
    in_pos, pos_side, entry_s = False, 0, 0.0

    for i in range(40, n - 1):
        window = spreads[i - 40:i]
        m = sum(window) / 40.0
        s = math.sqrt(sum((x - m) ** 2 for x in window) / 40.0)
        z = (spreads[i] - m) / s if s > 0 else 0.0

        if not in_pos:
            should_enter, side = _check_pair_entry(z)
            if should_enter:
                in_pos, pos_side, entry_s = True, side, spreads[i]
        else:
            if _check_pair_exit(pos_side, z):
                pnl = (spreads[i] - entry_s) * pos_side - 0.0008
                trades.append(pnl)
                in_pos = False

    return _calc_stats(trades, "Cointegração Pairs Trading", pair_label, "1h", "Reversão do Z-Score de spread em 2 sigmas")


def test_lead_lag_strategy(
    candles_leader: List[Dict[str, Any]],
    candles_follower: List[Dict[str, Any]]
) -> StrategyResult:
    """Testa defasagem temporal onde BTC lidera e ETH absorve o movimento (15m)."""
    n = min(len(candles_leader), len(candles_follower))
    if n < 5:
        return _calc_stats([], "Lead-Lag Temporal", "BTC -> ETH", "15m", "Dados insuficientes")

    trades = []
    for i in range(1, n - 2):
        l_ret = (candles_leader[i]["close_price"] - candles_leader[i - 1]["close_price"]) / candles_leader[i - 1]["close_price"]
        f_ret = (candles_follower[i]["close_price"] - candles_follower[i - 1]["close_price"]) / candles_follower[i - 1]["close_price"]

        # Se líder disparou > 0.8% e seguidor ficou atrasado (< 0.25%)
        if l_ret >= 0.008 and f_ret < 0.0025:
            nxt_ret = (candles_follower[i + 2]["close_price"] - candles_follower[i]["close_price"]) / candles_follower[i]["close_price"]
            trades.append(nxt_ret - 0.0004)  # deduz taxas
        elif l_ret <= -0.008 and f_ret > -0.0025:
            nxt_ret = (candles_follower[i]["close_price"] - candles_follower[i + 2]["close_price"]) / candles_follower[i]["close_price"]
            trades.append(nxt_ret - 0.0004)

    return _calc_stats(trades, "Lead-Lag Temporal", "BTC -> ETH", "15m", "Explosão direcional no líder com retardo no seguidor")


def test_donchian_breakout(
    candles: List[Dict[str, Any]],
    symbol: str = "BTCUSDT"
) -> StrategyResult:
    """Testa rompimento de canal de Donchian de 20 periodos em 1h."""
    if len(candles) < 30:
        return _calc_stats([], "Donchian 20 Breakout", symbol, "1h", "Dados insuficientes")

    trades = []
    in_pos = False
    side = 0
    entry_p = 0.0

    for i in range(20, len(candles) - 1):
        window = candles[i - 20:i]
        high_20 = max(c["high_price"] for c in window)
        low_10 = min(c["low_price"] for c in window[-10:])
        c_p = candles[i]["close_price"]

        if not in_pos and c_p > high_20:
            in_pos, side, entry_p = True, 1, c_p
        elif in_pos:
            if c_p < low_10:
                pnl = ((c_p - entry_p) / entry_p) - 0.0006
                trades.append(pnl)
                in_pos = False

    return _calc_stats(trades, "Donchian 20 Breakout", symbol, "1h", "Trend Following de rompimento clássico de máximas")


def test_rsi_bollinger_reversion(
    candles: List[Dict[str, Any]],
    symbol: str = "ADAUSDT"
) -> StrategyResult:
    """Testa exaustao extrema de RSI (<30 ou >70) com toque em Bandas de Bollinger em 15m."""
    if len(candles) < 35:
        return _calc_stats([], "RSI + Bollinger Reversion", symbol, "15m", "Dados insuficientes")

    closes = [c["close_price"] for c in candles]
    rsis = compute_rsi_series(closes, period=14)
    trades = []

    for i in range(25, len(candles) - 4):
        window = closes[i - 20:i]
        m = sum(window) / 20.0
        std = math.sqrt(sum((x - m) ** 2 for x in window) / 20.0)
        lower_bb = m - 1.8 * std
        upper_bb = m + 1.8 * std

        cp = candles[i]["close_price"]
        lp = candles[i]["low_price"]
        hp = candles[i]["high_price"]
        rsi = rsis[i]

        # Condicao de compra por exaustao
        if lp <= lower_bb and rsi < 32:
            exit_p = candles[i + 3]["close_price"]
            pnl = ((exit_p - cp) / cp) - 0.0004
            trades.append(pnl)
        elif hp >= upper_bb and rsi > 68:
            exit_p = candles[i + 3]["close_price"]
            pnl = ((cp - exit_p) / cp) - 0.0004
            trades.append(pnl)

    return _calc_stats(trades, "RSI + Bollinger Reversion", symbol, "15m", "Reversão à média com exaustão de oscilador e bandas")


def test_orb_ny_session(
    candles: List[Dict[str, Any]],
    symbol: str = "LINKUSDT"
) -> StrategyResult:
    """Testa Opening Range Breakout (ORB) na primeira hora de Nova York (13h-14h UTC)."""
    trades = []
    # Agrupar por dia
    by_day: Dict[str, List[Dict[str, Any]]] = {}
    for c in candles:
        d = c["open_time"] // 86400000
        by_day.setdefault(str(d), []).append(c)

    for day_candles in by_day.values():
        if len(day_candles) < 6:
            continue
        # Candle das 13:00 e 14:00
        orb_high = max(c["high_price"] for c in day_candles[:2])
        orb_low = min(c["low_price"] for c in day_candles[:2])

        for c in day_candles[2:6]:
            if c["close_price"] > orb_high:
                ret = (day_candles[-1]["close_price"] - c["close_price"]) / c["close_price"] - 0.0006
                trades.append(ret)
                break
            elif c["close_price"] < orb_low:
                ret = (c["close_price"] - day_candles[-1]["close_price"]) / c["close_price"] - 0.0006
                trades.append(ret)
                break

    return _calc_stats(trades, "ORB Nova York (13h-18h)", symbol, "1h", "Rompimento da faixa de abertura bancária com condução intradiária")


def test_funding_carry_trade(
    total_days: int = 366,
    annual_rate_pct: float = 24.5
) -> StrategyResult:
    """Simula o rendimento delta-neutro estavel de Funding Rate (3 coletas/dia)."""
    daily_rate = (annual_rate_pct / 100.0) / 365.0
    trades = [daily_rate for _ in range(total_days)]
    return _calc_stats(trades, "Cash & Carry Funding Rate", "BTC Spot/Futures", "8h", "Captura contínua de taxa de financiamento delta-neutra")
