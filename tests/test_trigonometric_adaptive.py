#!/usr/bin/env python3
"""
Testes Unitários da Estratégia Trigonométrica Adaptativa Avançada no Plano Cartesiano.
Valida:
1. Identidades trigonométricas no espaço normalizado (sin^2 + cos^2 = 1).
2. Momento linear newtoniano com massa de volume (F_y = sin(theta) * m).
3. Geometria diferencial de curvatura (kappa) e raio de curvatura (R).
4. Entropia não-extensiva de Tsallis (q = 1.5) e multiescala (MSE).
5. Trailing stop modularizado pelo cosseno.
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
    evaluate_trigonometric_signal,
    compute_tsallis_entropy,
    compute_multiscale_entropy,
    compute_dynamic_cosine_stop
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

    def test_volume_momentum_newton(self):
        """Valida que volume institucional amplifica a força vetorial F_y."""
        vec_low_vol = compute_normalized_cartesian_vector(
            p_curr=110.0, p_prev=100.0, atr_val=2.0, delta_t=10, volume_mass=0.5
        )
        vec_high_vol = compute_normalized_cartesian_vector(
            p_curr=110.0, p_prev=100.0, atr_val=2.0, delta_t=10, volume_mass=2.5
        )
        self.assertAlmostEqual(vec_high_vol.momentum_force, vec_low_vol.momentum_force * 5.0, places=2)

    def test_differential_curvature(self):
        """Valida cálculo de curvatura e raio de curvatura em aceleração de preço."""
        vec = compute_normalized_cartesian_vector(
            p_curr=120.0, p_prev=100.0, atr_val=2.0, delta_t=10, prev_slope=0.10
        )
        self.assertGreater(vec.curvature, 0.0)
        self.assertGreater(vec.radius_of_curvature, 0.0)

    def test_tsallis_entropy(self):
        """Valida que a Entropia de Tsallis retorna entre 0.0 e 1.0."""
        rets = [0.01 * (i % 3 - 1) for i in range(30)]
        sq = compute_tsallis_entropy(rets, q=1.5)
        self.assertGreaterEqual(sq, 0.0)
        self.assertLessEqual(sq, 1.0)

    def test_multiscale_entropy(self):
        """Valida cálculo em 3 resoluções fractais."""
        rets = [0.005 * i for i in range(30)]
        mse = compute_multiscale_entropy(rets, windows=(6, 12, 24))
        self.assertIn("fast", mse)
        self.assertIn("medium", mse)
        self.assertIn("slow", mse)

    def test_dynamic_cosine_stop(self):
        """Valida que o stop loss encurta quando o ângulo se torna íngreme."""
        stop_flat = compute_dynamic_cosine_stop(atr_val=10.0, angle_rad=0.0) # cos(0) = 1.0 -> 15.0
        stop_steep = compute_dynamic_cosine_stop(atr_val=10.0, angle_rad=math.radians(60.0)) # cos(60) = 0.5 -> 7.5
        self.assertLess(stop_steep, stop_flat)
        self.assertAlmostEqual(stop_steep, stop_flat * 0.5, places=1)


if __name__ == "__main__":
    unittest.main()
