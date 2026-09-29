"""
Testes unitários para o avaliador de entradas Laia (Alpha Discovery).
Valida o cálculo do Entry Quality Score, o veto a falsos rompimentos,
a detecção de acumulação institucional oculta e a filtragem em lote.
"""

import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.laia_entry_evaluator import LaiaEntryEvaluator, EntryEvaluationResult


class TestLaiaEntryEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = LaiaEntryEvaluator(min_quality_score=70.0)

    def test_high_quality_lead_lag_entry(self):
        """Testa uma entrada ideal de Lead-Lag na sessão de NY com funding seguro."""
        res = self.evaluator.evaluate_entry(
            symbol="ETHUSDT",
            btc_return_15m=0.015,  # BTC disparou +1.5%
            alt_return_15m=0.001,  # ETH atrasado em +0.1%
            hour_utc=15,           # Sessão de Nova York
            funding_rate=-0.0002,  # Funding negativo (short squeeze iminente)
            alt_volume_ratio=1.2,
            is_mechanical_signal_active=True
        )
        self.assertEqual(res.action, "LONG")
        self.assertGreaterEqual(res.entry_quality_score, 85.0)
        self.assertEqual(res.risk_mode, "ANTI_MARTINGALE_EXPAND")
        self.assertTrue(res.is_superior_to_mechanical)
        self.assertIn("Descompasso temporal Lead-Lag de alta probabilidade.", res.reasons)

    def test_filter_dangerous_false_breakout(self):
        """Testa o veto a uma entrada perigosa (Ásia + funding esticado + sem descompasso)."""
        res = self.evaluator.evaluate_entry(
            symbol="ETHUSDT",
            btc_return_15m=0.002,
            alt_return_15m=0.002,
            hour_utc=2,            # Madrugada / Ásia
            funding_rate=0.0008,   # Funding extremamente positivo (risco de liquidação)
            alt_volume_ratio=0.8,
            is_mechanical_signal_active=True
        )
        self.assertEqual(res.action, "FILTERED_NO_TRADE")
        self.assertLess(res.entry_quality_score, 70.0)
        self.assertEqual(res.risk_mode, "NO_TRADE")
        self.assertTrue(res.is_superior_to_mechanical)  # Superior por evitar armadilha

    def test_hidden_accumulation_discovery(self):
        """Testa a descoberta de acumulação oculta (BTC cai, altcoin sobe com volume)."""
        res = self.evaluator.evaluate_entry(
            symbol="SOLUSDT",
            btc_return_15m=-0.012, # BTC caiu -1.2%
            alt_return_15m=0.004,  # SOL descorrelacionou em alta +0.4%
            hour_utc=14,           # Nova York
            funding_rate=0.0001,
            alt_volume_ratio=1.8,  # Volume alto
            is_mechanical_signal_active=False
        )
        self.assertEqual(res.action, "LONG")
        self.assertGreaterEqual(res.entry_quality_score, 70.0)
        self.assertTrue(any("Acumulacao institucional oculta" in r for r in res.reasons))

    def test_batch_filtering(self):
        """Testa o processamento de lote de oportunidades em múltiplos pares."""
        batch = [
            {
                "symbol": "ETHUSDT",
                "btc_return_15m": 0.014,
                "alt_return_15m": 0.001,
                "hour_utc": 10,
                "funding_rate": 0.0001,
                "is_mechanical_signal_active": True
            },
            {
                "symbol": "DOGEUSDT",
                "btc_return_15m": 0.001,
                "alt_return_15m": 0.001,
                "hour_utc": 3,
                "funding_rate": 0.0009,
                "is_mechanical_signal_active": True
            }
        ]
        results = self.evaluator.filter_opportunity_batch(batch)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].action, "LONG")
        self.assertEqual(results[1].action, "FILTERED_NO_TRADE")

    def test_neutral_market_hold(self):
        """Testa o comportamento em mercado parado sem sinais."""
        res = self.evaluator.evaluate_entry(
            symbol="BTCUSDT",
            btc_return_15m=0.0005,
            alt_return_15m=0.0005,
            hour_utc=20,
            funding_rate=0.0001,
            is_mechanical_signal_active=False
        )
        self.assertEqual(res.action, "HOLD_WAIT")
        self.assertEqual(res.risk_mode, "NO_TRADE")


if __name__ == "__main__":
    unittest.main()
