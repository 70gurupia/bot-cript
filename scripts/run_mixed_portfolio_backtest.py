#!/usr/bin/env python3
"""
Pipeline de Execucao e Backtest do Motor Hibrido Misto Multi-Estrategia.
Carrega dados reais de 2024 (35.136 candles de 15m e 8.784 candles de 1h de SOL, LINK, BNB).
Simula a evolucao de R$ 10,00 com reinvestimento Anti-Martingale, Funding Passivo e Scalping.
Salva relatorio consolidado em data/mixed_portfolio_report.json.
"""

from __future__ import annotations
import os
import sys
import json
import sqlite3
from typing import List, Dict, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.mixed_portfolio_engine import (
    MixedPortfolioConfig,
    simulate_mixed_portfolio_year
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "mixed_portfolio_report.json")


def load_candles_15m_symbol(db_path: str, symbol: str = "BTCUSDT") -> List[Dict[str, Any]]:
    """Carrega candles de 15m para 2024."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM klines_15m
        WHERE symbol = ? AND open_time >= 1704067200000
        ORDER BY open_time ASC;
    """, (symbol,))
    rows = cur.fetchall()
    conn.close()
    return [{
        "open_time": r[0], "open_price": r[1], "high_price": r[2],
        "low_price": r[3], "close_price": r[4], "volume": r[5]
    } for r in rows]


def load_candles_1h_symbols(db_path: str, symbols: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Carrega candles de 1h para a lista de ativos em 2024."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    out = {}
    for s in symbols:
        cur.execute("""
            SELECT open_time, open_price, high_price, low_price, close_price, volume
            FROM klines_1h
            WHERE symbol = ? AND open_time >= 1704067200000
            ORDER BY open_time ASC;
        """, (s,))
        rows = cur.fetchall()
        out[s] = [{
            "open_time": r[0], "open_price": r[1], "high_price": r[2],
            "low_price": r[3], "close_price": r[4], "volume": r[5]
        } for r in rows]
    conn.close()
    return out


def main():
    print("==================================================================")
    print("BACKTEST: MOTOR HÍBRIDO MISTO MULTI-ESTRATÉGIA (2024)")
    print("==================================================================")

    candles_15m = load_candles_15m_symbol(DB_PATH, "BTCUSDT")
    print(f"Candles 15m (BTCUSDT): {len(candles_15m)}")

    altcoins = ["SOLUSDT", "LINKUSDT", "BNBUSDT"]
    candles_1h = load_candles_1h_symbols(DB_PATH, altcoins)
    for sym, c_list in candles_1h.items():
        print(f"Candles 1h ({sym}): {len(c_list)}")

    # Cenarios de banca inicial
    cfg_10 = MixedPortfolioConfig(initial_bankroll_brl=10.0, base_risk_pct=0.04, win_expansion_pct=0.25)
    cfg_50 = MixedPortfolioConfig(initial_bankroll_brl=50.0, base_risk_pct=0.04, win_expansion_pct=0.25)
    cfg_100 = MixedPortfolioConfig(initial_bankroll_brl=100.0, base_risk_pct=0.04, win_expansion_pct=0.25)

    print("\nExecutando simulação para Banca R$ 10,00...")
    res_10 = simulate_mixed_portfolio_year(candles_15m, candles_1h, cfg_10)

    print("Executando simulação para Banca R$ 50,00...")
    res_50 = simulate_mixed_portfolio_year(candles_15m, candles_1h, cfg_50)

    print("Executando simulação para Banca R$ 100,00...")
    res_100 = simulate_mixed_portfolio_year(candles_15m, candles_1h, cfg_100)

    report = {
        "title": "Backtest Motor Hibrido Misto (Scalp Centavos + NY Breakout + Funding + Anti-Martingale)",
        "year": 2024,
        "scenarios": {
            "bankroll_10_brl": res_10,
            "bankroll_50_brl": res_50,
            "bankroll_100_brl": res_100
        }
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[OK] Relatório salvo em: {REPORT_PATH}")
    print("\nRESULTADOS POR FAIXA DE BANCA:")
    for name, s in report["scenarios"].items():
        init_b = s["initial_bankroll_brl"]
        fin_b = s["final_bankroll_brl"]
        ret_p = s["total_return_pct"]
        pos_d = s["positive_days"]
        tot_d = s["total_days"]
        peak_b = s["peak_bankroll_brl"]
        funding = s["total_funding_earned_brl"]
        win_r = s["overall_win_rate_pct"]
        print(f"\n  Banca Inicial R$ {init_b:,.2f}:")
        print(f"    - Saldo Final: R$ {fin_b:,.2f} ({ret_p:+.2f}%)")
        print(f"    - Saldo de Pico: R$ {peak_b:,.2f}")
        print(f"    - Dias Positivos: {pos_d}/{tot_d} ({s['positive_days_pct']}%)")
        print(f"    - Taxa de Acerto Geral: {win_r}%")
        print(f"    - Funding Passivo Coletado: R$ {funding:,.2f}")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
