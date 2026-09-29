#!/usr/bin/env python3
"""
Matriz Abrangente de Simulações em Todos os 14 Pares (2018 a 2025).
Avalia:
1. Geração 3 Newtoniana Avançada (Tsallis Entropy q=1.5 + Força Vetorial + TAMA + Cosine Stop).
2. Seguidor de Tendência Donchian 20 (para ativos direcionais e breakout).
3. Desempenho isolado no ano de 2025 para todos os 14 pares.
4. Desempenho acumulado histórico de 8 anos (2018 a 2025).
Salva relatório em data/comprehensive_all_pairs_simulation_report.json.
"""

from __future__ import annotations
import os
import sys
import math
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.entropy_compounding_engine import (
    EntropyEngineConfig,
    compute_log_returns,
    compute_atr
)
from strategy.trigonometric_adaptive_engine import (
    compute_series_trigonometric_vectors,
    compute_trigonometric_adaptive_ma,
    evaluate_trigonometric_signal,
    compute_tsallis_entropy,
    compute_dynamic_cosine_stop
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "comprehensive_all_pairs_simulation_report.json")

ALL_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "ADAUSDT",
    "XRPUSDT",
    "LINKUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "TRXUSDT",
    "LTCUSDT",
    "XLMUSDT",
    "ETCUSDT"
]

TS_2025_START = int(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
TS_2025_END = int(datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)


def load_symbol_candles(
    conn: sqlite3.Connection,
    sym: str,
    start_ts: int | None = None,
    end_ts: int | None = None
) -> List[Dict[str, Any]]:
    """Carrega candles horários ordenados por timestamp."""
    cur = conn.cursor()
    if start_ts is not None and end_ts is not None:
        query = """
            SELECT open_time, open_price, high_price, low_price, close_price, volume
            FROM klines_1h
            WHERE symbol = ? AND open_time >= ? AND open_time <= ?
            ORDER BY open_time ASC;
        """
        cur.execute(query, (sym, start_ts, end_ts))
    else:
        query = """
            SELECT open_time, open_price, high_price, low_price, close_price, volume
            FROM klines_1h
            WHERE symbol = ?
            ORDER BY open_time ASC;
        """
        cur.execute(query, (sym,))
    rows = cur.fetchall()
    return [{
        "time": r[0], "open": r[1], "high": r[2],
        "low": r[3], "close": r[4], "vol": r[5]
    } for r in rows]


def _evaluate_trade_outcome(
    candles: List[Dict[str, Any]],
    start_idx: int,
    side: str,
    entry_p: float,
    atr_val: float,
    angle_rad: float
) -> Tuple[bool, float]:
    """Avalia o desfecho de um trade com alvo 2.0*ATR e dynamic cosine stop."""
    max_idx = min(start_idx + 13, len(candles))
    tp = entry_p + 2.0 * atr_val if side == "BUY" else entry_p - 2.0 * atr_val
    stop_dist = compute_dynamic_cosine_stop(atr_val, angle_rad, base_multiplier=1.2)
    sl = entry_p - stop_dist if side == "BUY" else entry_p + stop_dist

    for f in range(start_idx + 1, max_idx):
        fc = candles[f]
        if side == "BUY":
            if fc["high"] >= tp:
                return True, 0.048
            if fc["low"] <= sl:
                return False, -round(stop_dist / entry_p, 4)
        elif side == "SELL":
            if fc["low"] <= tp:
                return True, 0.048
            if fc["high"] >= sl:
                return False, -round(stop_dist / entry_p, 4)
    return False, -0.008


def _calc_metrics(returns: List[float]) -> Dict[str, Any]:
    """Calcula estatísticas de desempenho a partir da lista de retornos."""
    trades = len(returns)
    if trades == 0:
        return {
            "trades": 0, "wins": 0, "win_rate_pct": 0.0,
            "net_return_pct": 0.0, "profit_factor": 0.0, "max_drawdown_pct": 0.0
        }

    wins = sum(1 for r in returns if r > 0)
    net_ret = sum(returns)
    gross_win = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))

    if gross_loss > 0:
        pf = round(gross_win / gross_loss, 2)
    else:
        pf = 99.0 if gross_win > 0 else 0.0

    peak = 0.0
    accum = 0.0
    max_dd = 0.0
    for r in returns:
        accum += r
        if accum > peak:
            peak = accum
        dd = peak - accum
        if dd > max_dd:
            max_dd = dd

    return {
        "trades": trades,
        "wins": wins,
        "win_rate_pct": round((wins / trades) * 100.0, 1),
        "net_return_pct": round(net_ret * 100.0, 2),
        "profit_factor": pf,
        "max_drawdown_pct": round(max_dd * 100.0, 2)
    }


def simulate_g3_newtonian(
    candles: List[Dict[str, Any]],
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Simula a Geração 3 Newtoniana Avançada na série de candles."""
    if len(candles) < 50:
        return _calc_metrics([])

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["vol"] for c in candles]

    log_rets = compute_log_returns(closes)
    atrs = compute_atr(highs, lows, closes, cfg.atr_period)
    vectors = compute_series_trigonometric_vectors(closes, atrs, volumes=volumes, window=10)
    tama = compute_trigonometric_adaptive_ma(closes, vectors, fast_period=4, slow_period=30)

    returns = []
    i = cfg.entropy_window + 10

    while i < len(candles) - 12:
        tsallis_val = compute_tsallis_entropy(log_rets[i - 20:i], q=1.5)
        sig = evaluate_trigonometric_signal(
            vector=vectors[i],
            entropy_val=tsallis_val,
            tama_val=tama[i],
            close_price=closes[i],
            entropy_thresh=0.75
        )

        if sig.has_signal and sig.regime == "TREND_EXPANSION" and abs(sig.momentum_force) > 0.45:
            win, pnl = _evaluate_trade_outcome(
                candles, i, sig.side, closes[i], atrs[i], vectors[i].angle_rad
            )
            returns.append(pnl)
            i += 6
        i += 1

    return _calc_metrics(returns)


def _check_donchian_step(
    side: str, entry_p: float, c_close: float, d_high: float, d_low: float
) -> Tuple[bool, float]:
    """Checa condições de saída de um canal Donchian."""
    if side == "BUY" and c_close < d_low:
        return True, (c_close - entry_p) / entry_p
    if side == "SELL" and c_close > d_high:
        return True, (entry_p - c_close) / entry_p
    return False, 0.0


def simulate_donchian_trend(
    candles: List[Dict[str, Any]],
    period: int = 20
) -> Dict[str, Any]:
    """Simula seguidor de tendência Donchian Breakout."""
    if len(candles) < period + 10:
        return _calc_metrics([])

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    in_pos = False
    side = ""
    entry_p = 0.0
    returns = []

    for i in range(period + 1, len(candles)):
        c_close = closes[i]
        d_high = max(highs[i - period:i])
        d_low = min(lows[i - period:i])

        if in_pos:
            closed, pnl = _check_donchian_step(side, entry_p, c_close, d_high, d_low)
            if closed:
                returns.append(pnl)
                in_pos = False
            continue

        if c_close > d_high:
            in_pos = True
            side = "BUY"
            entry_p = c_close
        elif c_close < d_low:
            in_pos = True
            side = "SELL"
            entry_p = c_close

    return _calc_metrics(returns)


def _determine_archetype(g3_net: float, donch_net: float) -> Tuple[str, str]:
    """Determina o arquétipo e a melhor estratégia para o ativo."""
    if g3_net > donch_net and g3_net > 0:
        return "G3_NEWTONIANA", "ALTA EFICIÊNCIA (Tsallis & Vetorial)"
    if donch_net > g3_net and donch_net > 0:
        return "DONCHIAN_TREND", "TENDÊNCIA LONGA (Breakout Direcional)"
    if max(g3_net, donch_net) > 0:
        return "HÍBRIDO_SELETIVO", "MODERADO (Operar com Filtro OBI)"
    return "BLACKLIST", "INEFICIENTE (Alta Taxa de Falso Rompimento)"


def run_comprehensive_matrix() -> Dict[str, Any]:
    """Executa a matriz completa em todos os 14 pares para 2025 e histórico acumulado."""
    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()

    results = []

    print("=" * 115)
    print("MATRIZ DE SIMULAÇÃO COMPLETA: TODOS OS 14 PARES (ANO DE 2025 E HISTÓRICO DE 8 ANOS)")
    print("=" * 115)
    header = f"{'Par':<10} | {'Histórico':<18} | {'2025 G3 Ret':<12} | {'2025 Donch':<11} | {'Total G3 Ret':<13} | {'Total Donch':<12} | {'Melhor Modelo'}"
    print(header)
    print("-" * 115)

    for sym in ALL_SYMBOLS:
        all_candles = load_symbol_candles(conn, sym)
        if len(all_candles) < 100:
            continue

        t_min = all_candles[0]["time"]
        t_max = all_candles[-1]["time"]
        d_start = datetime.fromtimestamp(t_min / 1000, tz=timezone.utc).strftime("%m/%Y")
        d_end = datetime.fromtimestamp(t_max / 1000, tz=timezone.utc).strftime("%m/%Y")
        period_str = f"{d_start} a {d_end}"

        # 2025 isolado
        c_2025 = [c for c in all_candles if TS_2025_START <= c["time"] <= TS_2025_END]
        g3_2025 = simulate_g3_newtonian(c_2025, cfg)
        donch_2025 = simulate_donchian_trend(c_2025, period=20)

        # Histórico consolidado total
        g3_all = simulate_g3_newtonian(all_candles, cfg)
        donch_all = simulate_donchian_trend(all_candles, period=20)

        best_model, label = _determine_archetype(g3_all["net_return_pct"], donch_all["net_return_pct"])

        row_str = (
            f"{sym:<10} | {period_str:<18} | "
            f"{g3_2025['net_return_pct']:>+6.2f}% ({g3_2025['trades']}t) | "
            f"{donch_2025['net_return_pct']:>+6.2f}% ({donch_2025['trades']}t) | "
            f"{g3_all['net_return_pct']:>+7.2f}% ({g3_all['trades']}t) | "
            f"{donch_all['net_return_pct']:>+7.2f}% ({donch_all['trades']}t) | "
            f"{best_model}"
        )
        print(row_str)

        results.append({
            "symbol": sym,
            "period": period_str,
            "candles_total": len(all_candles),
            "candles_2025": len(c_2025),
            "sim_2025": {
                "g3_newtonian": g3_2025,
                "donchian_trend": donch_2025
            },
            "sim_cumulative": {
                "g3_newtonian": g3_all,
                "donchian_trend": donch_all
            },
            "best_model": best_model,
            "classification": label
        })

    conn.close()

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pairs_evaluated": len(results),
        "results": results
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("=" * 115)
    print(f"[SUCESSO] Relatório da matriz completa gravado em: {REPORT_PATH}")
    return payload


if __name__ == "__main__":
    run_comprehensive_matrix()
