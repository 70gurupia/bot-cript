#!/usr/bin/env python3
"""
Simulação Comparativa Histórica de 7 Anos (2018 a 2024).
Avalia se a introdução da Trigonometria Cartesiana e TAMA melhora ou atrapalha
o desempenho do sistema em relação ao Baseline em todos os regimes de mercado.
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
    compute_rolling_entropy,
    compute_atr,
    update_monthly_vault
)
from strategy.trigonometric_adaptive_engine import (
    compute_series_trigonometric_vectors,
    compute_trigonometric_adaptive_ma,
    evaluate_trigonometric_signal
)
from scripts.run_stress_test_2018_2019 import (
    load_candles,
    evaluate_entropy_model,
    simulate_bankroll_evolution
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "trigonometric_comparison_7years_report.json")

YEARS = [
    (2018, "Bear Market (-82%)"),
    (2019, "Recuperação / Acumulação"),
    (2020, "Covid Crash + Bull Run"),
    (2021, "Mega Bull Market / Topo Duplo"),
    (2022, "Bear Market FTX/Luna (-65%)"),
    (2023, "Consolidação Pré-ETF"),
    (2024, "Bull Market dos ETFs")
]


def _evaluate_trade_window(
    candles: List[Dict[str, Any]],
    start_idx: int,
    side: str,
    tp: float,
    sl: float
) -> Tuple[bool, float]:
    """Testa se o trade atingiu Take-Profit ou Stop-Loss nos 12 candles futuros."""
    max_idx = min(start_idx + 13, len(candles))
    for f in range(start_idx + 1, max_idx):
        fc = candles[f]
        if side == "BUY":
            if fc["high"] >= tp:
                return True, 0.048
            if fc["low"] <= sl:
                return False, -0.024
        elif side == "SELL":
            if fc["low"] <= tp:
                return True, 0.048
            if fc["high"] >= sl:
                return False, -0.024
    return False, -0.010


def evaluate_trigonometric_model(
    candles: List[Dict[str, Any]],
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Testa o modelo aprimorado com vetores cartesianos, TAMA e aceleração angular."""
    if len(candles) < 40:
        return {"trades": 0, "wins": 0, "win_rate_pct": 0.0, "net_return_pct": 0.0}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    log_rets = compute_log_returns(closes)
    entropies = compute_rolling_entropy(log_rets, cfg.entropy_window, cfg.entropy_bins)
    atrs = compute_atr(highs, lows, closes, cfg.atr_period)
    vectors = compute_series_trigonometric_vectors(closes, atrs, window=10)
    tama = compute_trigonometric_adaptive_ma(closes, vectors, fast_period=4, slow_period=30)

    trades = 0
    wins = 0
    total_pnl = 0.0
    i = cfg.entropy_window + 10

    while i < len(candles) - 12:
        sig = evaluate_trigonometric_signal(
            vector=vectors[i],
            entropy_val=entropies[i],
            tama_val=tama[i],
            close_price=closes[i],
            entropy_thresh=0.75
        )

        # Só opera se houver sinal e o regime for de expansão direcional sem exaustão
        if sig.has_signal and sig.regime == "TREND_EXPANSION":
            trades += 1
            atr = atrs[i]
            c_p = closes[i]
            tp = c_p + 2.0 * atr if sig.side == "BUY" else c_p - 2.0 * atr
            sl = c_p - 1.0 * atr if sig.side == "BUY" else c_p + 1.0 * atr

            win, pnl = _evaluate_trade_window(candles, i, sig.side, tp, sl)
            total_pnl += pnl
            wins += 1 if win else 0
            i += 6
        i += 1

    wr = round((wins / trades * 100.0), 1) if trades else 0.0
    return {
        "trades": trades,
        "wins": wins,
        "win_rate_pct": wr,
        "net_return_pct": round(total_pnl * 100.0, 2)
    }


def _run_single_year(
    conn: sqlite3.Connection,
    year: int,
    desc: str,
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Executa a comparação de um ano específico para ETH e BTC."""
    s_ms = int(datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    e_ms = int(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

    eth_c = load_candles(conn, "ETHUSDT", s_ms, e_ms)
    btc_c = load_candles(conn, "BTCUSDT", s_ms, e_ms)

    # 1. Baseline (Entropia pura)
    base_eth = evaluate_entropy_model(eth_c, cfg)
    base_btc = evaluate_entropy_model(btc_c, cfg)

    # 2. Modelo Trigonométrico Adaptativo (TVT + TAMA)
    trig_eth = evaluate_trigonometric_model(eth_c, cfg)
    trig_btc = evaluate_trigonometric_model(btc_c, cfg)

    # Simulação da Banca R$ 500 no ETH
    sim_base = simulate_bankroll_evolution(
        [0.048] * base_eth["wins"] + [-0.024] * (base_eth["trades"] - base_eth["wins"]), 500.0
    )
    sim_trig = simulate_bankroll_evolution(
        [0.048] * trig_eth["wins"] + [-0.024] * (trig_eth["trades"] - trig_eth["wins"]), 500.0
    )

    return {
        "year": year,
        "desc": desc,
        "eth_baseline": base_eth,
        "eth_trigonometric": trig_eth,
        "btc_baseline": base_btc,
        "btc_trigonometric": trig_btc,
        "banca_baseline": sim_base,
        "banca_trigonometric": sim_trig
    }


def main():
    print("==========================================================================================")
    print("BATERIA COMPARATIVA DE 7 ANOS: BASELINE VS MODELO TRIGONOMÉTRICO CARTESIANO (TAMA)")
    print("==========================================================================================")

    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()

    results = []
    print(f"{'Ano':<6} | {'Regime':<26} | {'ETH Base WR':<12} | {'ETH Trig WR':<12} | {'ETH Base PnL':<13} | {'ETH Trig PnL':<13} | {'Veredito'}")
    print("-" * 106)

    for y, desc in YEARS:
        res = _run_single_year(conn, y, desc, cfg)
        results.append(res)

        b_wr = f"{res['eth_baseline']['win_rate_pct']}% ({res['eth_baseline']['trades']}t)"
        t_wr = f"{res['eth_trigonometric']['win_rate_pct']}% ({res['eth_trigonometric']['trades']}t)"
        b_pnl = f"{res['eth_baseline']['net_return_pct']:>+6.1f}%"
        t_pnl = f"{res['eth_trigonometric']['net_return_pct']:>+6.1f}%"

        # Avaliação de melhoria
        pnl_diff = res['eth_trigonometric']['net_return_pct'] - res['eth_baseline']['net_return_pct']
        wr_diff = res['eth_trigonometric']['win_rate_pct'] - res['eth_baseline']['win_rate_pct']

        if pnl_diff > 0 and wr_diff >= 0:
            veredito = f"MELHOROU (+{pnl_diff:.1f}%)"
        elif wr_diff > 3.0:
            veredito = f"MAIS PRECISO (+{wr_diff:.1f}% WR)"
        elif pnl_diff >= -2.0:
            veredito = "EQUIVALENTE"
        else:
            veredito = f"PIOROU ({pnl_diff:.1f}%)"

        print(f"{y:<6} | {desc:<26} | {b_wr:<12} | {t_wr:<12} | {b_pnl:<13} | {t_pnl:<13} | {veredito}")

    conn.close()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Relatório salvo em: {REPORT_PATH}")
    print("==========================================================================================")
    return 0


if __name__ == "__main__":
    main()
