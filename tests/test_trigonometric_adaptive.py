#!/usr/bin/env python3
"""
Testes Unitários da Estratégia Trigonométrica Adaptativa no Plano Cartesiano.
Valida:
1. Identidades trigonométricas no espaço normalizado (sin^2 + cos^2 = 1, tan = dy/dx).
2. Resposta angular em choques direcionais e mercado horizontal.
3. Adaptação da Média TAMA (dinâmica rápida vs lenta).
4. Sinais combinados com compressão de Entropia de Shannon.
"""

import math
import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.trigonometric_adaptive_engine import (
    compute_normalized_cartesian_vector,
    compute_series_trigonometric_vectors,
    compute_trigonometric_adaptive_ma,
    evaluate_trigonometric_signal
)


class TestTrigonometricAdaptiveEngine(unittest.TestCase):

    def test_fundamental_trigonometric_identity(self):
        """Valida que sin^2(theta) + cos^2(theta) == 1 em qualquer vetor cartesiano."""
        vec = compute_normalized_cartesian_vector(
            p_curr=110.0, p_prev=100.0, atr_val=2.5, delta_t=14
        )
        identity = (vec.sin_theta ** 2) + (vec.cos_theta ** 2)
        self.assertAlmostEqual(identity, 1.0, places=3)
        self.assertGreater(vec.angle_deg, 0.0)
        self.assertAlmostEqual(vec.tan_theta, math.tan(vec.angle_rad), places=3)

    def test_horizontal_market_zero_angle(self):
        """Valida que mercado lateral produz theta = 0, sin = 0, cos = 1, tan = 0."""
        vec = compute_normalized_cartesian_vector(
            p_curr=100.0, p_prev=100.0, atr_val=1.5, delta_t=10
        )
        self.assertEqual(vec.angle_deg, 0.0)
        self.assertEqual(vec.sin_theta, 0.0)
        self.assertEqual(vec.cos_theta, 1.0)
        self.assertEqual(vec.tan_theta, 0.0)

    def test_series_vector_generation(self):
        """Gera vetores para série sintética e valida dimensões."""
        closes = [100.0 + i * 1.5 for i in range(30)]
        atrs = [2.0] * 30
        vectors = compute_series_trigonometric_vectors(closes, atrs, window=10)
        self.assertEqual(len(vectors), 30)
        # Último vetor deve apontar alta expressiva
        self.assertGreater(vectors[-1].angle_deg, 20.0)
        self.assertGreater(vectors[-1].sin_theta, 0.3)

    def test_tama_adaptive_smoothing(self):
        """Valida que TAMA responde mais rápido quando o ângulo cartesiano é íngreme."""
        closes = [100.0] * 15 + [105.0, 112.0, 120.0, 130.0, 142.0]
        atrs = [2.0] * len(closes)
        vectors = compute_series_trigonometric_vectors(closes, atrs, window=5)
        tama = compute_trigonometric_adaptive_ma(closes, vectors, fast_period=4, slow_period=30)
        self.assertEqual(len(tama), len(closes))
        # No final do movimento de alta acelerada, a TAMA deve ter acompanhado fortemente a subida
        self.assertGreater(tama[-1], 115.0)

    def test_signal_evaluation_with_entropy(self):
        """Valida emissão de sinal de compra quando há congruência de ângulo e baixa entropia."""
        vec = compute_normalized_cartesian_vector(
            p_curr=120.0, p_prev=100.0, atr_val=2.0, delta_t=10
        )
        sig = evaluate_trigonometric_signal(
            vector=vec,
            entropy_val=0.60,       # Entropia comprimida (favorável)
            tama_val=115.0,          # Preço 120 acima da média 115
            close_price=120.0,
            entropy_thresh=0.75
        )
        self.assertTrue(sig.has_signal)
        self.assertEqual(sig.side, "BUY")
        self.assertGreater(sig.confidence, 0.8)

    def test_angular_exhaustion_detection(self):
        """Valida que desaceleração angular (d_theta < 0) em topo sinaliza exaustão."""
        vec = compute_normalized_cartesian_vector(
            p_curr=130.0, p_prev=100.0, atr_val=2.0, delta_t=10,
            prev_angle_rad=1.10 # Ângulo anterior era ainda mais íngreme
        )
        sig = evaluate_trigonometric_signal(
            vector=vec, entropy_val=0.50, tama_val=125.0, close_price=130.0
        )
        self.assertTrue(sig.has_signal)
        self.assertEqual(sig.regime, "ANGULAR_EXHAUSTION")


if __name__ == "__main__":
    unittest.main()
