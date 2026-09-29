#!/usr/bin/env python3
"""
Testes Unitários do Motor Matricial Cross-Sectional e de Extremos.
Valida as propriedades matemáticas e comportamentais de strategy/cross_sectional_matrix_engine.py.
"""

import unittest
from datetime import datetime, timezone
import math
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.cross_sectional_matrix_engine import (
    compute_garman_klass_volatility,
    compute_candle_efficiency,
    evaluate_temporal_session,
    compute_cross_sectional_zscores,
    evaluate_markov_whipsaw_risk,
    evaluate_matrix_alpha,
    MatrixAlphaSignal
)


class TestCrossSectionalMatrixEngine(unittest.TestCase):

    def test_garman_klass_volatility_positive(self):
        """Valida que a volatilidade de Garman-Klass é positiva para velas normais."""
        vol = compute_garman_klass_volatility(high=105.0, low=95.0, open_p=98.0, close_p=103.0)
        self.assertGreater(vol, 0.0)
        self.assertIsInstance(vol, float)

    def test_garman_klass_zero_or_invalid(self):
        """Valida que preços inválidos ou nulos retornam 0.0 de forma segura."""
        self.assertEqual(compute_garman_klass_volatility(0.0, 10.0, 10.0, 10.0), 0.0)
        self.assertEqual(compute_garman_klass_volatility(10.0, -1.0, 10.0, 10.0), 0.0)

    def test_candle_efficiency_full_body(self):
        """Valida que um candle sem pavios possui eficiência máxima (1.0)."""
        eff = compute_candle_efficiency(open_p=100.0, high=110.0, low=100.0, close_p=110.0)
        self.assertAlmostEqual(eff, 1.0, places=3)

    def test_candle_efficiency_doji(self):
        """Valida que um doji puro (abertura igual ao fechamento) possui eficiência 0.0."""
        eff = compute_candle_efficiency(open_p=105.0, high=110.0, low=100.0, close_p=105.0)
        self.assertAlmostEqual(eff, 0.0, places=3)

    def test_candle_efficiency_zero_spread(self):
        """Valida que vela de spread zero não causa divisão por zero."""
        eff = compute_candle_efficiency(open_p=100.0, high=100.0, low=100.0, close_p=100.0)
        self.assertEqual(eff, 0.0)

    def test_temporal_session_us_expansion(self):
        """Valida que as 14:00 UTC em dia de semana é classificado como US_EXPANSION."""
        # 15/01/2025 foi quarta-feira
        dt = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        ts_ms = int(dt.timestamp() * 1000)
        res = evaluate_temporal_session(ts_ms)
        self.assertEqual(res["session_name"], "US_EXPANSION")
        self.assertTrue(res["is_high_liquidity_window"])
        self.assertFalse(res["is_weekend"])
        self.assertGreaterEqual(res["liquidity_weight"], 1.20)

    def test_temporal_session_weekend(self):
        """Valida que sábado recebe penalização de liquidez."""
        # 18/01/2025 foi sábado
        dt = datetime(2025, 1, 18, 14, 0, 0, tzinfo=timezone.utc)
        ts_ms = int(dt.timestamp() * 1000)
        res = evaluate_temporal_session(ts_ms)
        self.assertTrue(res["is_weekend"])
        self.assertFalse(res["is_high_liquidity_window"])
        self.assertLess(res["liquidity_weight"], 1.0)

    def test_cross_sectional_zscores(self):
        """Valida normalização em Z-score de um conjunto de retornos."""
        rets = {"BTC": 0.02, "ETH": 0.04, "SOL": 0.06}
        z = compute_cross_sectional_zscores(rets)
        self.assertIn("SOL", z)
        self.assertGreater(z["SOL"], z["BTC"])
        # A soma dos Z-scores de uma distribuição deve ser muito próxima de zero
        self.assertAlmostEqual(sum(z.values()), 0.0, places=2)

    def test_cross_sectional_empty_or_single(self):
        """Valida tratamento seguro de listas vazias ou unitárias."""
        self.assertEqual(compute_cross_sectional_zscores({}), {})
        self.assertEqual(compute_cross_sectional_zscores({"BTC": 0.05}), {"BTC": 0.0})

    def test_markov_whipsaw_detection(self):
        """Valida que alternâncias bilaterais consecutivas ativam risco de chicotada."""
        alternating_closes = [100.0, 102.0, 99.0, 103.0, 98.0, 104.0, 97.0, 105.0] * 4
        is_whip, rate = evaluate_markov_whipsaw_risk(alternating_closes, window=24)
        self.assertTrue(is_whip)
        self.assertGreater(rate, 0.58)

    def test_markov_trend_clean(self):
        """Valida que tendência direcional contínua não é classificada como chicotada."""
        clean_trend = [100.0 + i * 1.5 for i in range(35)]
        is_whip, rate = evaluate_markov_whipsaw_risk(clean_trend, window=24)
        self.assertFalse(is_whip)
        self.assertEqual(rate, 0.0)

    def test_evaluate_matrix_alpha_approved(self):
        """Valida aprovação de trade com boas condições matriciais."""
        dt = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        ts_ms = int(dt.timestamp() * 1000)
        clean_trend = [100.0 + i * 1.0 for i in range(30)]

        sig = evaluate_matrix_alpha(
            symbol="ETHUSDT",
            open_p=125.0,
            high=131.0,
            low=124.5,
            close_p=130.5,
            open_time_ms=ts_ms,
            closes_history=clean_trend,
            relative_strength_zscore=1.20,
            side="BUY"
        )
        self.assertTrue(sig.allow_entry)
        self.assertGreater(sig.confidence_score, 0.50)
        self.assertEqual(sig.rejection_reason, "")

    def test_evaluate_matrix_alpha_rejected_whipsaw(self):
        """Valida rejeição de entrada quando o mercado está em regime de chicotada."""
        dt = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        ts_ms = int(dt.timestamp() * 1000)
        alternating_closes = [100.0, 102.0, 99.0, 103.0, 98.0] * 7

        sig = evaluate_matrix_alpha(
            symbol="DOGEUSDT",
            open_p=125.0,
            high=131.0,
            low=124.5,
            close_p=130.5,
            open_time_ms=ts_ms,
            closes_history=alternating_closes,
            relative_strength_zscore=0.50,
            side="BUY"
        )
        self.assertFalse(sig.allow_entry)
        self.assertIn("WHIPSAW_REGIME_DETECTED", sig.rejection_reason)


if __name__ == "__main__":
    unittest.main()
