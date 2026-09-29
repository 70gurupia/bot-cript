#!/usr/bin/env python3
"""
Testes Unitários do Pipeline Alfa Unificado (strategy/unified_alpha_pipeline.py).
Valida a integração completa entre G3 Newtoniana, SmartOrderRouter, OBI,
Anti-Martingale, Ratchet Vault e Alertas Operacionais.
"""

import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.unified_alpha_pipeline import UnifiedAlphaPipeline
from strategy.smart_order_router import OrderBookSnapshot, OrderBookLevel


class TestUnifiedAlphaPipeline(unittest.TestCase):

    def setUp(self):
        self.pipeline = UnifiedAlphaPipeline(bankroll_brl=500.0)

    def test_full_pipeline_buy_signal_generation(self):
        """Valida que uma confluência ideal emite um plano de execução completo."""
        rets = [0.005] * 20 # Retornos calmos para baixa entropia
        bids = [OrderBookLevel(3000.0 - i * 0.1, 10.0) for i in range(10)]
        asks = [OrderBookLevel(3000.2 + i * 0.1, 2.0) for i in range(10)]
        book = OrderBookSnapshot("ETHUSDT", 1700000000000, bids, asks)

        # Preço subiu 60 dólares em relação ao candle anterior com 3x volume
        decision = self.pipeline.process_market_tick(
            symbol="ETHUSDT",
            close_price=3060.0,
            prev_close_price=3000.0,
            atr_val=20.0,
            volume=3000.0,
            avg_volume_20=1000.0,
            recent_log_rets=rets,
            funding_rate=0.0001,
            book_snapshot=book
        )

        self.assertTrue(decision.should_trade)
        self.assertEqual(decision.side, "BUY")
        self.assertIsNotNone(decision.execution_plan)
        self.assertEqual(decision.execution_plan.order_type, "LIMIT_MAKER_POST_ONLY")
        self.assertGreater(decision.take_profit_price, decision.close_price if hasattr(decision, 'close_price') else 3060.0)
        self.assertLess(decision.stop_loss_price, 3060.0)
        self.assertIn("SINAL EXECUTADO", decision.alert_message)

    def test_pipeline_funding_block(self):
        """Valida que funding superaquecido barra compra mesmo com sinal técnico."""
        rets = [0.005] * 20
        decision = self.pipeline.process_market_tick(
            symbol="ETHUSDT",
            close_price=3060.0,
            prev_close_price=3000.0,
            atr_val=20.0,
            volume=3000.0,
            avg_volume_20=1000.0,
            recent_log_rets=rets,
            funding_rate=0.0008 # 0.08% > 0.05% -> Bloqueia compras
        )
        self.assertFalse(decision.should_trade)
        self.assertEqual(decision.reason, "FUNDING_OVERHEATED_BLOCK_BUY")

    def test_pipeline_vault_lock_progression(self):
        """Valida que vitórias consecutivas acionam as travas do cofre e geram alertas."""
        # 1ª Vitória
        b, v, alert1 = self.pipeline.register_trade_outcome(is_win=True, pnl_brl=250.0)
        self.assertEqual(self.pipeline.streak, 1)

        # 2ª Vitória levando banca total para R$ 1.050,00 (Marco de R$ 1.000 atingido)
        b, v, alert2 = self.pipeline.register_trade_outcome(is_win=True, pnl_brl=300.0)
        self.assertGreater(v, 0.0)
        self.assertIn("COFRE INVIOLÁVEL ACIONADO", alert2)


if __name__ == "__main__":
    unittest.main()
