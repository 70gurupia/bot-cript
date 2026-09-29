#!/usr/bin/env python3
"""
Simulação da Geração 3 Newtoniana Avançada em Todos os Outros Pares do Banco:
BNBUSDT, ADAUSDT, XRPUSDT, LINKUSDT, DOGEUSDT, SOLUSDT, DOTUSDT, AVAXUSDT,
LTCUSDT, TRXUSDT, XLMUSDT, ETCUSDT.
Salva relatório consolidado em data/advanced_all_pairs_report.json.
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
from scripts.run_stress_test_2018_2019 import load_candles
from scripts.run_advanced_indicators_simulation import _evaluate_advanced_trade

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "advanced_all_pairs_report.json")

OTHER_SYMBOLS = [
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


def evaluate_pair_g3(
    candles: List[Dict[str, Any]],
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Testa a G3 Newtoniana em uma série de candles de determinado ativo."""
    if len(candles) < 50:
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
        tsallis_val = compute_tsallis_entropy(log_rets[i - 20:i], q=1.5)

        sig = evaluate_trigonometric_signal(
            vector=vectors[i],
            entropy_val=tsallis_val,
            tama_val=tama[i],
            close_price=closes[i],
            entropy_thresh=0.75
        )

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


def _get_symbol_date_range(conn: sqlite3.Connection, sym: str) -> Tuple[int, int, int]:
    """Obtém timestamp inicial, final e total de candles de um símbolo."""
    cur = conn.cursor()
    cur.execute("SELECT MIN(open_time), MAX(open_time), COUNT(*) FROM klines_1h WHERE symbol = ?", (sym,))
    row = cur.fetchone()
    return row[0], row[1], row[2]


def main():
    print("==========================================================================================")
    print("SIMULAÇÃO DA GERAÇÃO 3 NEWTONIANA EM TODOS OS OUTROS PARES DISPONÍVEIS")
    print("==========================================================================================")

    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()

    summary_results = []
    print(f"{'Símbolo':<10} | {'Período Histórico':<24} | {'Velas':<7} | {'Trades':<7} | {'Win Rate':<10} | {'Retorno Total':<14} | {'Status'}")
    print("-" * 96)

    for sym in OTHER_SYMBOLS:
        min_ts, max_ts, count = _get_symbol_date_range(conn, sym)
        if not count or count < 100:
            continue

        start_dt = datetime.fromtimestamp(min_ts / 1000, tz=timezone.utc).strftime("%m/%Y")
        end_dt = datetime.fromtimestamp(max_ts / 1000, tz=timezone.utc).strftime("%m/%Y")
        period_str = f"{start_dt} a {end_dt}"

        candles = load_candles(conn, sym, min_ts, max_ts)
        res = evaluate_pair_g3(candles, cfg)

        wr_str = f"{res['win_rate_pct']}%"
        ret_str = f"{res['net_return_pct']:>+7.2f}%"

        if res['net_return_pct'] > 50.0:
            status = "EXCELENTE (Alfa Alto)"
        elif res['net_return_pct'] > 0.0:
            status = "POSITIVO (Lucrativo)"
        elif res['net_return_pct'] >= -10.0:
            status = "NEUTRO / EQUILÍBRIO"
        else:
            status = "DESFAVORÁVEL (Evitar)"

        print(f"{sym:<10} | {period_str:<24} | {count:<7} | {res['trades']:<7} | {wr_str:<10} | {ret_str:<14} | {status}")

        summary_results.append({
            "symbol": sym,
            "period": period_str,
            "candles_count": count,
            "performance": res,
            "status": status
        })

    conn.close()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=2)

    print(f"\n[OK] Relatório salvo em: {REPORT_PATH}")
    print("==========================================================================================")
    return 0


if __name__ == "__main__":
    main()
