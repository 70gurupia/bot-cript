#!/usr/bin/env python3
"""
Simulação Comparativa dos Indicadores Avançados (2018 a 2024):
Compara 3 Gerações:
1. Baseline: Entropia de Shannon Pura
2. Geração 2: Geometria Trigonométrica Básica (TAMA + Theta)
3. Geração 3: Newtoniana Avançada (Momento F_y = sin(theta) * Volume + Tsallis + Cosine Trailing)
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
from scripts.run_stress_test_2018_2019 import (
    load_candles,
    evaluate_entropy_model,
    simulate_bankroll_evolution
)
from scripts.run_trigonometric_backtest_comparison import evaluate_trigonometric_model

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "advanced_indicators_7years_report.json")

YEARS = [
    (2018, "Bear Market (-82%)"),
    (2019, "Recuperação / Acumulação"),
    (2020, "Covid Crash + Bull Run"),
    (2021, "Mega Bull Market / Topo Duplo"),
    (2022, "Bear Market FTX/Luna (-65%)"),
    (2023, "Consolidação Pré-ETF"),
    (2024, "Bull Market dos ETFs")
]


def _evaluate_advanced_trade(
    candles: List[Dict[str, Any]],
    start_idx: int,
    side: str,
    entry_p: float,
    atr_val: float,
    angle_rad: float
) -> Tuple[bool, float]:
    """Avalia o trade com trailing stop dinâmico modulado pelo cosseno."""
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


def evaluate_advanced_newton_model(
    candles: List[Dict[str, Any]],
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Testa o modelo Newtoniano com momento F_y = sin(theta) * m e Tsallis."""
    if len(candles) < 40:
        return {"trades": 0, "wins": 0, "win_rate_pct": 0.0, "net_return_pct": 0.0}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["vol"] for c in candles]

    log_rets = compute_log_returns(closes)
    atrs = compute_atr(highs, lows, closes, cfg.atr_period)
    vectors = compute_series_trigonometric_vectors(closes, atrs, volumes=volumes, window=10)
    tama = compute_trigonometric_adaptive_ma(closes, vectors, fast_period=4, slow_period=30)

    trades = 0
    wins = 0
    total_pnl = 0.0
    i = cfg.entropy_window + 10

    while i < len(candles) - 12:
        # Entropia de Tsallis q = 1.5 na janela deslizante
        tsallis_val = compute_tsallis_entropy(log_rets[i - 20:i], q=1.5)

        sig = evaluate_trigonometric_signal(
            vector=vectors[i],
            entropy_val=tsallis_val,
            tama_val=tama[i],
            close_price=closes[i],
            entropy_thresh=0.75
        )

        # Filtro Newtoniano: exige sinal válido, expansão e força de momento real com volume
        if sig.has_signal and sig.regime == "TREND_EXPANSION" and abs(sig.momentum_force) > 0.45:
            trades += 1
            win, pnl = _evaluate_advanced_trade(
                candles, i, sig.side, closes[i], atrs[i], vectors[i].angle_rad
            )
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


def _run_comparison_year(
    conn: sqlite3.Connection,
    year: int,
    desc: str,
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Roda a comparação das 3 gerações em um ano específico."""
    s_ms = int(datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    e_ms = int(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

    eth_c = load_candles(conn, "ETHUSDT", s_ms, e_ms)
    btc_c = load_candles(conn, "BTCUSDT", s_ms, e_ms)

    # 1. Baseline
    b_eth = evaluate_entropy_model(eth_c, cfg)
    b_btc = evaluate_entropy_model(btc_c, cfg)

    # 2. Trigonométrico G2
    g2_eth = evaluate_trigonometric_model(eth_c, cfg)
    g2_btc = evaluate_trigonometric_model(btc_c, cfg)

    # 3. Newtoniano Avançado G3
    g3_eth = evaluate_advanced_newton_model(eth_c, cfg)
    g3_btc = evaluate_advanced_newton_model(btc_c, cfg)

    return {
        "year": year,
        "desc": desc,
        "eth_g1_baseline": b_eth,
        "eth_g2_trig": g2_eth,
        "eth_g3_newton": g3_eth,
        "btc_g1_baseline": b_btc,
        "btc_g2_trig": g2_btc,
        "btc_g3_newton": g3_btc
    }


def main():
    print("==========================================================================================")
    print("SIMULAÇÃO COMPARATIVA DE 7 ANOS (3 GERAÇÕES): BASELINE VS G2 TRIG VS G3 NEWTONIANO")
    print("==========================================================================================")

    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()

    results = []
    print(f"{'Ano':<6} | {'Regime':<24} | {'ETH G1 PnL':<11} | {'ETH G2 PnL':<11} | {'ETH G3 PnL (WR)':<18} | {'BTC G3 PnL (WR)'}")
    print("-" * 104)

    for y, desc in YEARS:
        res = _run_comparison_year(conn, y, desc, cfg)
        results.append(res)

        g1_p = f"{res['eth_g1_baseline']['net_return_pct']:>+5.1f}%"
        g2_p = f"{res['eth_g2_trig']['net_return_pct']:>+5.1f}%"
        g3_p = f"{res['eth_g3_newton']['net_return_pct']:>+5.1f}% ({res['eth_g3_newton']['win_rate_pct']}%)"
        btc_g3 = f"{res['btc_g3_newton']['net_return_pct']:>+5.1f}% ({res['btc_g3_newton']['win_rate_pct']}%)"

        print(f"{y:<6} | {desc:<24} | {g1_p:<11} | {g2_p:<11} | {g3_p:<18} | {btc_g3}")

    conn.close()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Relatório salvo em: {REPORT_PATH}")
    print("==========================================================================================")
    return 0


if __name__ == "__main__":
    main()
