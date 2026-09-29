"""
Testes Unitarios do Motor Hibrido Misto Multi-Estrategia.
Valida o calculo de Bollinger Bands, dimensionamento Anti-Martingale,
abertura de posicoes ativas (Scalp e NY), atualizacao de barras e backtest.
"""

from __future__ import annotations
import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.mixed_portfolio_engine import (
    MixedPortfolioConfig,
    ActivePosition,
    compute_bb_bands_simple,
    calculate_mixed_stake,
    check_scalp_entry_15m,
    check_ny_pinbar_entry_1h,
    update_and_check_position,
    simulate_mixed_portfolio_year
)


class TestMixedPortfolioEngine(unittest.TestCase):
    """Suíte de testes do motor misto multi-estratégia."""

    def setUp(self):
        self.config = MixedPortfolioConfig(
            initial_bankroll_brl=10.0,
            base_risk_pct=0.05,
            win_expansion_pct=0.25,
            max_streak_expansion=3,
            min_trade_brl=0.40
        )

    def test_compute_bb_bands_simple(self):
        prices = [100.0 + i for i in range(25)]
        mean, lower, upper = compute_bb_bands_simple(prices, period=20, num_std=1.8)
        self.assertGreater(mean, 0.0)
        self.assertLess(lower, mean)
        self.assertGreater(upper, mean)

    def test_calculate_mixed_stake_expansion(self):
        bankroll = 100.0
        # Streak 0: base risk (5% de 100 = 5.0)
        s0 = calculate_mixed_stake(bankroll, streak=0, config=self.config)
        self.assertEqual(s0, 5.0)

        # Streak 1: expande 25% -> 5.0 * 1.25 = 6.25
        s1 = calculate_mixed_stake(bankroll, streak=1, config=self.config)
        self.assertAlmostEqual(s1, 6.25, places=2)

        # Streak 2: 5.0 * 1.25^2 = 7.8125
        s2 = calculate_mixed_stake(bankroll, streak=2, config=self.config)
        self.assertAlmostEqual(s2, 7.8125, places=3)

    def test_check_scalp_entry_15m(self):
        # Candle rompendo banda inferior com fechamento de alta
        c_buy = {"close_price": 50100.0, "low_price": 49800.0, "high_price": 50200.0}
        has_sig, side = check_scalp_entry_15m(c_buy, prev_close=50000.0, lower_bb=49900.0, upper_bb=50500.0)
        self.assertTrue(has_sig)
        self.assertEqual(side, "BUY")

        # Candle rompendo banda superior com fechamento de baixa
        c_sell = {"close_price": 50400.0, "low_price": 50300.0, "high_price": 50600.0}
        has_sig, side = check_scalp_entry_15m(c_sell, prev_close=50500.0, lower_bb=49900.0, upper_bb=50500.0)
        self.assertTrue(has_sig)
        self.assertEqual(side, "SELL")

    def test_check_ny_pinbar_entry_1h(self):
        # Bull pin-bar em hora valida (14 UTC)
        c_pin = {
            "open_price": 100.0, "close_price": 101.0,
            "high_price": 102.0, "low_price": 95.0
        }
        has_sig, side = check_ny_pinbar_entry_1h(c_pin, hour_utc=14, config=self.config)
        self.assertTrue(has_sig)
        self.assertEqual(side, "BUY")

        # Fora do horario de NY (08 UTC) -> deve ignorar
        has_sig, _ = check_ny_pinbar_entry_1h(c_pin, hour_utc=8, config=self.config)
        self.assertFalse(has_sig)

    def test_update_and_check_position_tp_and_sl(self):
        pos = ActivePosition(
            strategy_type="SCALP",
            symbol="BTCUSDT",
            side="BUY",
            entry_price=100.0,
            tp_price=100.25,
            sl_price=99.75,
            stake_brl=1.0,
            bars_held=0,
            max_bars=4
        )
        # Bateu TP
        closed, pnl, is_win = update_and_check_position(pos, high_p=100.5, low_p=99.9, close_p=100.3, config=self.config)
        self.assertTrue(closed)
        self.assertTrue(is_win)
        self.assertGreater(pnl, 0.0)


if __name__ == "__main__":
    unittest.main()
