#!/usr/bin/env python3
"""
Testes Unitários do Roteador Inteligente de Execução (Smart Order Router),
Order Book Imbalance (OBI), Sentimento de Funding e Calibração Walk-Forward.
"""

import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.smart_order_router import (
    OrderBookLevel,
    OrderBookSnapshot,
    compute_order_book_imbalance,
    evaluate_funding_sentiment,
    calculate_maker_execution_price,
    create_smart_execution_plan,
    calibrate_walk_forward_thresholds
)


class TestSmartOrderRouter(unittest.TestCase):

    def test_order_book_imbalance_buy_pressure(self):
        """Valida que livro com mais bids que asks produz OBI fortemente positivo."""
        bids = [OrderBookLevel(100.0 - i * 0.1, 15.0) for i in range(10)] # 150 total
        asks = [OrderBookLevel(100.2 + i * 0.1, 5.0) for i in range(10)]  # 50 total
        snap = OrderBookSnapshot("ETHUSDT", 1700000000000, bids, asks)

        obi = compute_order_book_imbalance(snap, depth_levels=10)
        self.assertAlmostEqual(obi, (150 - 50) / 200, places=3)
        self.assertGreater(obi, 0.30)

    def test_order_book_imbalance_empty(self):
        """Valida tratamento seguro de livro vazio."""
        snap = OrderBookSnapshot("BTCUSDT", 1700000000000, [], [])
        obi = compute_order_book_imbalance(snap)
        self.assertEqual(obi, 0.0)

    def test_funding_sentiment_filter(self):
        """Valida bloqueio contracíclico de compras em euforia e shorts em desespero."""
        regime, can_buy, can_sell = evaluate_funding_sentiment(0.0008) # 0.08% > 0.05%
        self.assertEqual(regime, "BULLISH_OVERHEATED")
        self.assertFalse(can_buy)
        self.assertTrue(can_sell)

        regime_bear, can_buy_b, can_sell_b = evaluate_funding_sentiment(-0.0006)
        self.assertEqual(regime_bear, "BEARISH_OVERHEATED")
        self.assertTrue(can_buy_b)
        self.assertFalse(can_sell_b)

        regime_neu, can_b_neu, can_s_neu = evaluate_funding_sentiment(0.0001)
        self.assertEqual(regime_neu, "NEUTRAL_BALANCED")
        self.assertTrue(can_b_neu)
        self.assertTrue(can_s_neu)

    def test_smart_execution_maker_post_only(self):
        """Valida geração do plano Maker e cálculo de economia de taxas."""
        plan = create_smart_execution_plan(
            symbol="ETHUSDT",
            side="BUY",
            size=1.5,
            best_bid=3000.0,
            best_ask=3000.5,
            atr_val=40.0,
            maker_fee=0.0002,
            taker_fee=0.0004
        )
        self.assertEqual(plan.order_type, "LIMIT_MAKER_POST_ONLY")
        self.assertGreater(plan.target_price, 3000.0)
        self.assertLess(plan.target_price, 3000.5)
        self.assertGreater(plan.estimated_fee_savings_brl, 0.0)
        self.assertGreater(plan.cancel_threshold_price, plan.target_price)

    def test_walk_forward_calibration(self):
        """Valida que aumento de volatilidade recente eleva o limiar angular."""
        low_vol_returns = [0.002 * (i % 2) for i in range(30)]
        high_vol_returns = [0.025 * ((i % 3) - 1) for i in range(30)]

        angle_low, _ = calibrate_walk_forward_thresholds(low_vol_returns, base_angle_deg=28.0)
        angle_high, _ = calibrate_walk_forward_thresholds(high_vol_returns, base_angle_deg=28.0)

        self.assertGreater(angle_high, angle_low)


if __name__ == "__main__":
    unittest.main()
