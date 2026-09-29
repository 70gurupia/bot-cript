#!/usr/bin/env python3
"""
Testes Unitarios do Motor de Micro-Scalping de Centavos.
Valida calculo de bandas de Bollinger, deteccao de micro-reversoes, gestao de taxas e simulacao.
"""

import os
import sys
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.cent_scalper_engine import (
    CentScalperConfig,
    compute_bollinger_bands,
    check_scalp_entry_condition,
    process_active_scalp,
    simulate_cent_scalper_year
)
from scripts.run_cent_scalper_backtest import (
    load_candles_15m_all,
    run_scalper_simulations,
    DB_PATH,
    REPORT_PATH
)


class TestCentScalper(unittest.TestCase):
    def setUp(self):
        self.cfg = CentScalperConfig(
            initial_bankroll_brl=10.0,
            target_cent_per_trade_brl=0.10,
            leverage=5.0
        )

    def test_01_bollinger_bands(self):
        prices = [100.0 + i for i in range(30)]
        means, lowers, uppers = compute_bollinger_bands(prices, period=20, num_std=1.8)
        self.assertEqual(len(means), len(prices))
        self.assertLess(lowers[-1], means[-1])
        self.assertGreater(uppers[-1], means[-1])

    def test_02_entry_condition(self):
        candle_buy = {"close_price": 98.0, "low_price": 94.0, "high_price": 100.0}
        should_enter, side = check_scalp_entry_condition(candle_buy, prev_close=96.0, lower_bb=95.0, upper_bb=105.0)
        self.assertTrue(should_enter)
        self.assertEqual(side, "BUY")

        candle_sell = {"close_price": 104.0, "low_price": 100.0, "high_price": 106.0}
        should_enter_s, side_s = check_scalp_entry_condition(candle_sell, prev_close=105.0, lower_bb=95.0, upper_bb=105.0)
        self.assertTrue(should_enter_s)
        self.assertEqual(side_s, "SELL")

    def test_03_scalp_take_profit(self):
        pos = {
            "side": "BUY",
            "entry": 100.0,
            "tp": 100.25,
            "sl": 99.75,
            "bars": 0
        }
        candle = {"close_price": 100.30, "high_price": 100.35, "low_price": 100.0}
        closed, net_pnl, is_win = process_active_scalp(pos, candle, self.cfg, bankroll=10.0)
        self.assertTrue(closed)
        self.assertTrue(is_win)
        self.assertGreater(net_pnl, 0.0)

    def test_04_scalp_simulation_execution(self):
        self.assertTrue(os.path.exists(DB_PATH), f"Banco {DB_PATH} deve existir")
        candles = load_candles_15m_all(DB_PATH, symbol="BTCUSDT")[:200]
        res = simulate_cent_scalper_year(candles, self.cfg)
        self.assertIn("final_bankroll_brl", res)
        self.assertIn("total_trades", res)

    def test_05_report_generation(self):
        self.assertTrue(os.path.exists(REPORT_PATH), f"Relatório JSON {REPORT_PATH} deve existir")


if __name__ == "__main__":
    unittest.main()
