#!/usr/bin/env python3
"""
Testes Unitarios do Motor Hibrido (Hybrid Alpha).
Valida deteccao de sessao de NY, captura de Funding Rate, sinais de Pin Bar e projecoes em R$.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.hybrid_alpha_engine import (
    HybridAlphaConfig,
    is_ny_session,
    is_funding_hour,
    detect_pin_bar_signal,
    compute_daily_projections
)
from scripts.run_hybrid_alpha_walk_forward import (
    run_hybrid_walk_forward,
    generate_html_dashboard,
    REPORT_JSON_PATH,
    DASHBOARD_HTML_PATH
)


class TestHybridAlpha(unittest.TestCase):
    def setUp(self):
        self.cfg = HybridAlphaConfig(
            symbols=["LINKUSDT", "BNBUSDT", "SOLUSDT"],
            initial_balance_usd=1000.0,
            usd_brl_rate=5.65
        )

    def test_01_ny_session_detection(self):
        dt_ny = datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(is_ny_session(dt_ny, 13, 18), "15h UTC deve ser sessao de NY")

        dt_asia = datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(is_ny_session(dt_asia, 13, 18), "03h UTC nao e sessao de NY")

    def test_02_funding_hour_detection(self):
        self.assertTrue(is_funding_hour(datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)))
        self.assertTrue(is_funding_hour(datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)))
        self.assertTrue(is_funding_hour(datetime(2024, 1, 1, 16, 0, 0, tzinfo=timezone.utc)))
        self.assertFalse(is_funding_hour(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)))

    def test_03_pin_bar_detection(self):
        candle = {
            "open_price": 100.0,
            "close_price": 102.0,
            "high_price": 103.0,
            "low_price": 95.0,  # Pavio inferior longo de 5.0 (corpo 2.0 -> wick 2.5x corpo)
            "volume": 5000.0
        }
        sig, side, sl, tp = detect_pin_bar_signal(
            c=candle,
            ema50=98.0,
            vol_ma=2000.0,
            last_low=95.5,
            last_high=110.0
        )
        self.assertTrue(sig, "Deve detectar Pin Bar de compra em suporte com volume")
        self.assertEqual(side, "BUY")
        self.assertLess(sl, candle["close_price"])
        self.assertGreater(tp, candle["close_price"])

    def test_04_daily_projections(self):
        proj = compute_daily_projections(annual_ret_pct=30.0, usd_brl=5.65)
        self.assertGreater(proj.daily_gain_brl_1000, 0.0)
        self.assertEqual(proj.annual_return_pct, 30.0)

    def test_05_hybrid_walk_forward_pipeline(self):
        data = run_hybrid_walk_forward(self.cfg)
        self.assertGreater(data["total_return_pct"], 0.0, "Retorno do motor hibrido deve ser positivo")
        self.assertGreater(data["total_trades"], 0)
        self.assertEqual(len(data["monthly_reports"]), 12)
        self.assertTrue(os.path.exists(REPORT_JSON_PATH))
        self.assertTrue(os.path.exists(DASHBOARD_HTML_PATH))


if __name__ == "__main__":
    unittest.main()
