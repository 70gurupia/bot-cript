#!/usr/bin/env python3
"""
Pipeline de Teste e Validacao do Motor de Micro-Scalping de Centavos.
Simula a colheita de micro-ganhos de R$ 0,10 ao longo de 2024 com banca de R$ 10,00, R$ 50,00 e R$ 100,00.
Exporta relatorio JSON consolidado em data/cent_scalper_report.json.
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

from strategy.cent_scalper_engine import (
    CentScalperConfig,
    simulate_cent_scalper_year
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "cent_scalper_report.json")


def load_candles_15m_all(db_path: str, symbol: str = "BTCUSDT") -> List[Dict[str, Any]]:
    """Carrega todo o historico de 15m de 2024 para o ativo selecionado."""
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


def run_scalper_simulations(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Executa a simulacao para tres cenarios de banca: R$ 10,00, R$ 50,00 e R$ 100,00."""
    cfg_10 = CentScalperConfig(initial_bankroll_brl=10.0, leverage=5.0)
    cfg_50 = CentScalperConfig(initial_bankroll_brl=50.0, leverage=4.0)
    cfg_100 = CentScalperConfig(initial_bankroll_brl=100.0, leverage=3.0)

    res_10 = simulate_cent_scalper_year(candles, cfg_10)
    res_50 = simulate_cent_scalper_year(candles, cfg_50)
    res_100 = simulate_cent_scalper_year(candles, cfg_100)

    return {
        "title": "Simulacao de Micro-Scalping de Centavos (Meta: 10 trades de R$ 0,10/dia)",
        "asset": "BTCUSDT",
        "timeframe": "15m",
        "year": 2024,
        "scenarios": {
            "bankroll_10_brl": res_10,
            "bankroll_50_brl": res_50,
            "bankroll_100_brl": res_100
        }
    }


def main():
    print("\n==================================================================")
    print("BACKTEST: MOTOR DE MICRO-SCALPING DE CENTAVOS (2024)")
    print("==================================================================")
    print(f"Banco de Dados: {DB_PATH}")

    candles = load_candles_15m_all(DB_PATH, symbol="BTCUSDT")
    print(f"Candles de 15m carregados para 2024: {len(candles)}")

    report = run_scalper_simulations(candles)

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[OK] Relatório JSON salvo em: {REPORT_PATH}")

    print("\nRESULTADOS POR FAIXA DE BANCA INICIAL:")
    scenarios = report["scenarios"]
    for name, s in scenarios.items():
        init_b = s["initial_bankroll_brl"]
        fin_b = s["final_bankroll_brl"]
        ret_p = s["total_return_pct"]
        pos_d = s["positive_days"]
        tot_d = s["total_days"]
        avg_g = s["daily_average_gain_brl"]
        win_r = s["overall_win_rate_pct"]
        print(f"\n  Banca Inicial R$ {init_b:,.2f}:")
        print(f"    - Saldo Final: R$ {fin_b:,.2f} ({ret_p:+.2f}%)")
        print(f"    - Dias Positivos: {pos_d}/{tot_d} ({s['positive_days_pct']}%)")
        print(f"    - Taxa de Acerto dos Micro-Trades: {win_r}%")
        print(f"    - Ganho Médio Diário: R$ {avg_g:.2f} / dia")
    print("==================================================================\n")
    return 0


if __name__ == "__main__":
    main()
