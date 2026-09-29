"""
Testes Unitários do Módulo de Benchmark das Estratégias do Catálogo.
Valida o cálculo do RSI, a métrica de estatísticas e a execução das
estratégias de Lead-Lag, Donchian, Cointegração e Funding Carry Trade.
"""

from __future__ import annotations
import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.strategy_catalog_tester import (
    compute_rsi_series,
    _calc_stats,
    test_donchian_breakout,
    test_lead_lag_strategy,
    test_funding_carry_trade,
    StrategyResult
)


class TestStrategyCatalogTester(unittest.TestCase):
    """Suíte de testes das estratégias quantitativas do catálogo."""

    def test_compute_rsi_series(self):
        prices = [10.0 + (i * 0.5) for i in range(30)]
        rsi = compute_rsi_series(prices, period=14)
        self.assertEqual(len(rsi), len(prices))
        # Preços estritamente ascendentes -> RSI alto (> 70)
        self.assertGreater(rsi[-1], 70.0)

    def test_calc_stats(self):
        trades = [0.05, 0.03, -0.02, 0.04, -0.01]
        res = _calc_stats(trades, "Test", "BTCUSDT", "1h", "Desc")
        self.assertEqual(res.total_trades, 5)
        self.assertEqual(res.winning_trades, 3)
        self.assertEqual(res.win_rate_pct, 60.0)
        self.assertGreater(res.profit_factor, 1.0)
        self.assertAlmostEqual(res.total_net_return_pct, 9.0, places=1)

    def test_donchian_breakout_dummy(self):
        # 30 candles com alta progressiva no final
        candles = [{"high_price": 100.0 + i, "low_price": 99.0 + i, "close_price": 100.0 + i} for i in range(30)]
        res = test_donchian_breakout(candles, "BTCUSDT")
        self.assertIsInstance(res, StrategyResult)
        self.assertEqual(res.name, "Donchian 20 Breakout")

    def test_funding_carry_trade(self):
        res = test_funding_carry_trade(total_days=100, annual_rate_pct=25.0)
        self.assertEqual(res.total_trades, 100)
        self.assertEqual(res.win_rate_pct, 100.0)
        self.assertGreater(res.total_net_return_pct, 0.0)
        self.assertEqual(res.max_drawdown_pct, 0.0)

    def test_lead_lag_strategy_dummy(self):
        c_leader = [
            {"close_price": 100.0},
            {"close_price": 101.5},  # +1.5% disparou
            {"close_price": 101.6},
            {"close_price": 101.7},
            {"close_price": 101.8}
        ]
        c_follower = [
            {"close_price": 50.0},
            {"close_price": 50.05},  # +0.1% atrasado
            {"close_price": 50.5},
            {"close_price": 51.0},   # seguiu
            {"close_price": 51.1}
        ]
        res = test_lead_lag_strategy(c_leader, c_follower)
        self.assertIsInstance(res, StrategyResult)
        self.assertGreaterEqual(res.total_trades, 1)


if __name__ == "__main__":
    unittest.main()
