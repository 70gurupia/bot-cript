#!/usr/bin/env python3
"""
Testes Unitarios do Pipeline de Walk-Forward Mes a Mes em Graficos de 15m.
Valida particionamento mensal, execucao sequencial, conformidade EOD e geracao do dashboard.
"""

import os
import sys
import json
import sqlite3
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.run_daytrade_monthly_walk_forward import (
    get_monthly_ranges,
    load_candles_15m,
    run_single_month,
    run_full_year_walk_forward,
    build_html_dashboard,
    DB_PATH,
    REPORT_JSON_PATH,
    DASHBOARD_HTML_PATH
)


class TestMonthlyWalkForward(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(DB_PATH), f"Banco de dados deve existir em {DB_PATH}")

    def test_01_monthly_ranges_count(self):
        ranges = get_monthly_ranges(2024)
        self.assertEqual(len(ranges), 12, "Devem existir exatamente 12 meses no ano")
        for i in range(1, 12):
            self.assertGreater(ranges[i][1], ranges[i - 1][2], "Meses devem ser estritamente sequenciais")

    def test_02_load_candles_month(self):
        conn = sqlite3.connect(DB_PATH)
        ranges = get_monthly_ranges(2024)
        candles = load_candles_15m(conn, "BTCUSDT", ranges[0][1], ranges[0][2])
        conn.close()
        self.assertGreater(len(candles), 2800, "Janeiro deve possuir mais de 2800 candles de 15m")
        self.assertEqual(candles[0]["symbol"], "BTCUSDT")

    def test_03_run_single_month_invariants(self):
        conn = sqlite3.connect(DB_PATH)
        ranges = get_monthly_ranges(2024)
        candles = load_candles_15m(conn, "BTCUSDT", ranges[0][1], ranges[0][2])
        conn.close()

        rep, stats = run_single_month(candles, 10000.0, "BTCUSDT", ranges[0][0])
        self.assertEqual(stats["overnight_carried"], 0, "Invariante de Day Trade: 0 posicoes carregadas overnight")
        self.assertGreater(stats["total_candles"], 0)
        self.assertIn("return_pct", stats)
        self.assertIn("sharpe_ratio_15m", stats)

    def test_04_full_walk_forward_execution(self):
        # Executa simulacao completa de 2024
        summary = run_full_year_walk_forward(symbol="BTCUSDT", year=2024, initial_balance=10000.0)
        self.assertEqual(len(summary["monthly_breakdown"]), 12, "Deve haver 12 quebras mensais")
        self.assertEqual(summary["overnight_positions_carried"], 0, "Regra EOD: Total overnight deve ser 0")
        self.assertGreater(summary["total_trades"], 0)
        self.assertIn("chart_sample_15m", summary)
        self.assertGreater(len(summary["chart_sample_15m"]["candles"]), 0)

    def test_05_dashboard_html_generation(self):
        summary = run_full_year_walk_forward(symbol="BTCUSDT", year=2024, initial_balance=10000.0)
        html = build_html_dashboard(summary)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Day Trade 15m", html)
        self.assertIn("equityCanvas", html)
        self.assertIn("candleCanvas", html)
        self.assertIn("100% Flat ao final do dia", html)


if __name__ == "__main__":
    unittest.main()
