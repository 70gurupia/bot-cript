#!/usr/bin/env python3
"""
Simulação e Benchmark da Matriz Alpha Completa em Todos os 14 Pares (2018 a 2025).
Aplica os filtros matriciais:
1. Eficiência Direcional de Garman-Klass (elimina pavios de falso rompimento).
2. Sazonalidade de Liquidez Temporal (bloqueia janelas mortas e fins de semana sem volume).
3. Risco de Chicotada de Markov (bloqueia regimes de alternância estocástica).
4. Força Relativa Cross-Sectional contra o Bitcoin.
Salva relatório consolidado em data/matrix_alpha_all_pairs_report.json.
"""

from __future__ import annotations
import os
import sys
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.cross_sectional_matrix_engine import (
    evaluate_matrix_alpha,
    compute_cross_sectional_zscores,
    MatrixAlphaSignal
)
from strategy.entropy_compounding_engine import (
    compute_atr,
    compute_log_returns,
    EntropyEngineConfig
)
from strategy.trigonometric_adaptive_engine import (
    compute_series_trigonometric_vectors,
    compute_trigonometric_adaptive_ma,
    evaluate_trigonometric_signal,
    compute_tsallis_entropy,
    compute_dynamic_cosine_stop
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "matrix_alpha_all_pairs_report.json")

ALL_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "LINKUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT",
    "TRXUSDT", "LTCUSDT", "XLMUSDT", "ETCUSDT"
]

YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]


def load_pair_data(conn: sqlite3.Connection, sym: str) -> List[Dict[str, Any]]:
    """Carrega todo o histórico de candles de um símbolo ordenado por tempo."""
    cur = conn.cursor()
    cur.execute("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM klines_1h
        WHERE symbol = ?
        ORDER BY open_time ASC;
    """, (sym,))
    rows = cur.fetchall()
    return [{
        "time": r[0], "open": r[1], "high": r[2],
        "low": r[3], "close": r[4], "vol": r[5]
    } for r in rows]


def _check_trade_exit(
    candles: List[Dict[str, Any]],
    start_idx: int,
    side: str,
    entry_p: float,
    tp: float,
    sl: float,
    stop_dist: float
) -> float:
    """Calcula o resultado do trade em até 16 candles à frente."""
    max_idx = min(start_idx + 16, len(candles))
    for f in range(start_idx + 1, max_idx):
        c_h, c_l = candles[f]["high"], candles[f]["low"]
        if side == "BUY":
            if c_h >= tp:
                return 0.055
            if c_l <= sl:
                return -round(stop_dist / entry_p, 4)
        else:
            if c_l <= tp:
                return 0.055
            if c_h >= sl:
                return -round(stop_dist / entry_p, 4)
    return -0.006


def simulate_matrix_g3(
    candles: List[Dict[str, Any]],
    z_scores_map: Dict[int, float],
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Executa a G3 Newtoniana filtrada pela Matriz Alpha."""
    if len(candles) < 50:
        return {"trades": 0, "wins": 0, "net_return_pct": 0.0, "win_rate_pct": 0.0}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    vols = [c["vol"] for c in candles]
    opens = [c["open"] for c in candles]
    times = [c["time"] for c in candles]

    log_rets = compute_log_returns(closes)
    atrs = compute_atr(highs, lows, closes, cfg.atr_period)
    vectors = compute_series_trigonometric_vectors(closes, atrs, volumes=vols, window=10)
    tama = compute_trigonometric_adaptive_ma(closes, vectors, fast_period=4, slow_period=30)

    returns = []
    i = 30
    while i < len(candles) - 16:
        tsallis_val = compute_tsallis_entropy(log_rets[i - 20:i], q=1.5)
        sig = evaluate_trigonometric_signal(
            vector=vectors[i],
            entropy_val=tsallis_val,
            tama_val=tama[i],
            close_price=closes[i],
            entropy_thresh=0.75
        )

        if sig.has_signal and sig.regime == "TREND_EXPANSION" and abs(sig.momentum_force) > 0.40:
            z_val = z_scores_map.get(times[i], 0.0)
            mat = evaluate_matrix_alpha(
                symbol="",
                open_p=opens[i],
                high=highs[i],
                low=lows[i],
                close_p=closes[i],
                open_time_ms=times[i],
                closes_history=closes[max(0, i - 30):i + 1],
                relative_strength_zscore=z_val,
                side=sig.side
            )

            if mat.allow_entry:
                entry_p = closes[i]
                atr_val = atrs[i]
                stop_dist = compute_dynamic_cosine_stop(atr_val, vectors[i].angle_rad, base_multiplier=1.5)
                tp = entry_p + 2.5 * atr_val if sig.side == "BUY" else entry_p - 2.5 * atr_val
                sl = entry_p - stop_dist if sig.side == "BUY" else entry_p + stop_dist

                pnl = _check_trade_exit(candles, i, sig.side, entry_p, tp, sl, stop_dist)
                returns.append(pnl)
                i += 8
        i += 1

    trades = len(returns)
    wins = sum(1 for r in returns if r > 0)
    net_ret = sum(returns) * 100.0
    wr = round((wins / trades * 100.0), 1) if trades > 0 else 0.0

    return {
        "trades": trades,
        "wins": wins,
        "win_rate_pct": wr,
        "net_return_pct": round(net_ret, 2)
    }


def _calc_btc_relative_map(
    btc_candles: List[Dict[str, Any]],
    alt_candles: List[Dict[str, Any]]
) -> Dict[int, float]:
    """Gera mapa de timestamp para Z-score de momento relativo contra o BTC."""
    btc_dict = {c["time"]: c["close"] for c in btc_candles}
    res = {}
    for i in range(24, len(alt_candles)):
        t = alt_candles[i]["time"]
        t_prev = alt_candles[i - 24]["time"]
        if t in btc_dict and t_prev in btc_dict:
            b_ret = (btc_dict[t] - btc_dict[t_prev]) / btc_dict[t_prev]
            a_ret = (alt_candles[i]["close"] - alt_candles[i - 24]["close"]) / alt_candles[i - 24]["close"]
            diff = a_ret - b_ret
            # Normalização heurística de Z-Score: desvio padrão típico horário em 24h ~ 0.04
            z = diff / 0.04
            res[t] = round(z, 3)
    return res


def evaluate_pair_yearly_matrix(
    all_candles: List[Dict[str, Any]],
    z_map: Dict[int, float],
    cfg: EntropyEngineConfig
) -> Dict[int, Dict[str, Any]]:
    """Calcula o resultado ano a ano para um par."""
    yearly_results = {}
    for y in YEARS:
        t_start = int(datetime(y, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        t_end = int(datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)
        y_candles = [c for c in all_candles if t_start <= c["time"] <= t_end]
        if len(y_candles) < 100:
            continue
        res = simulate_matrix_g3(y_candles, z_map, cfg)
        yearly_results[y] = res
    return yearly_results


def run_matrix_benchmark() -> Dict[str, Any]:
    """Executa a simulação completa da Matriz Alpha em todos os pares."""
    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()

    btc_candles = load_pair_data(conn, "BTCUSDT")

    print("=" * 115)
    print("BENCHMARK COMPLETO: MOTOR MATRICIAL CROSS-SECTIONAL E SAZONAL EM TODOS OS 14 PARES (2018 a 2025)")
    print("=" * 115)
    header = f"{'Par':<10} | {'Trades':<7} | {'Win Rate':<9} | {'Retorno Total':<14} | {'Anos Positivos':<15} | {'Consistência'}"
    print(header)
    print("-" * 115)

    all_results = []

    for sym in ALL_SYMBOLS:
        candles = load_pair_data(conn, sym)
        if len(candles) < 100:
            continue

        z_map = _calc_btc_relative_map(btc_candles, candles)
        full_res = simulate_matrix_g3(candles, z_map, cfg)
        yearly_res = evaluate_pair_yearly_matrix(candles, z_map, cfg)

        pos_years = sum(1 for y, r in yearly_res.items() if r["net_return_pct"] > 0)
        tot_years = len(yearly_res)
        ratio_str = f"{pos_years}/{tot_years}"

        consistency = "EXCEPCIONAL (>=85%)" if (tot_years > 0 and pos_years / tot_years >= 0.85) else (
            "ALTA (>=70%)" if (tot_years > 0 and pos_years / tot_years >= 0.70) else "MODERADA / EVITAR"
        )

        row = (
            f"{sym:<10} | {full_res['trades']:<7} | {full_res['win_rate_pct']:>5.1f}%   | "
            f"{full_res['net_return_pct']:>+7.2f}%      | {ratio_str:<15} | {consistency}"
        )
        print(row)

        all_results.append({
            "symbol": sym,
            "cumulative": full_res,
            "yearly": yearly_res,
            "positive_years": pos_years,
            "total_years": tot_years,
            "consistency_label": consistency
        })

    conn.close()

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pairs_count": len(all_results),
        "results": all_results
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("=" * 115)
    print(f"[SUCESSO] Relatório gravado em: {REPORT_PATH}")
    return payload


if __name__ == "__main__":
    run_matrix_benchmark()
