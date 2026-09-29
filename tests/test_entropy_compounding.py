"""
Testes Unitários do Motor Quântico de Entropia e Retornos Logarítmicos.
Valida o cálculo de log-returns, entropia de Shannon normalizada,
detecção determinística de compressão entrópica e ratchet vault.
"""

from __future__ import annotations
import unittest
import math
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.entropy_compounding_engine import (
    EntropyEngineConfig,
    compute_log_returns,
    compute_shannon_entropy,
    compute_rolling_entropy,
    compute_atr,
    compute_fast_ema,
    detect_entropy_breakout,
    calculate_compounding_stake,
    update_monthly_vault
)


class TestEntropyCompoundingEngine(unittest.TestCase):
    """Suíte de testes das equações determinísticas de entropia e retornos logarítmicos."""

    def setUp(self):
        self.cfg = EntropyEngineConfig()

    def test_compute_log_returns(self):
        prices = [100.0, 105.0, 102.0]
        rets = compute_log_returns(prices)
        self.assertEqual(len(rets), 3)
        self.assertEqual(rets[0], 0.0)
        self.assertAlmostEqual(rets[1], math.log(105.0 / 100.0), places=5)
        self.assertAlmostEqual(rets[2], math.log(102.0 / 105.0), places=5)

    def test_shannon_entropy_deterministic_bounds(self):
        # Série com retornos idênticos deve ter entropia zero (mínima dispersão)
        flat_rets = [0.01] * 20
        h_zero = compute_shannon_entropy(flat_rets, bins_count=10)
        self.assertEqual(h_zero, 0.0)

        # Série uniformemente distribuída deve ter entropia normalizada próxima de 1.0
        uniform_rets = [i * 0.005 for i in range(100)]
        h_uniform = compute_shannon_entropy(uniform_rets, bins_count=10)
        self.assertGreater(h_uniform, 0.85)
        self.assertLessEqual(h_uniform, 1.0)

    def test_rolling_entropy_length(self):
        log_rets = [0.01 * ((-1) ** i) for i in range(50)]
        entropies = compute_rolling_entropy(log_rets, window=24, bins_count=10)
        self.assertEqual(len(entropies), 50)
        self.assertEqual(entropies[0], 1.0)
        self.assertLessEqual(entropies[30], 1.0)

    def test_detect_entropy_breakout_deterministic_rules(self):
        # Caso 1: Alta entropia (0.85 >= 0.72) -> Não deve gerar sinal (mercado caótico)
        sig, side, _, _ = detect_entropy_breakout(
            close_p=100.0, ema50_p=95.0, h_norm=0.85, z_log=2.2, atr=2.0, cfg=self.cfg
        )
        self.assertFalse(sig)

        # Caso 2: Baixa entropia (0.60 < 0.72) com z_score forte de compra (> 1.75) e acima da EMA50
        sig_buy, side_buy, sl_buy, tp_buy = detect_entropy_breakout(
            close_p=100.0, ema50_p=95.0, h_norm=0.60, z_log=2.1, atr=2.0, cfg=self.cfg
        )
        self.assertTrue(sig_buy)
        self.assertEqual(side_buy, "BUY")
        self.assertEqual(sl_buy, 100.0 - (1.2 * 2.0))
        self.assertEqual(tp_buy, 100.0 + (2.4 * 2.0))
        # Validação do Payoff 2:1
        self.assertAlmostEqual((tp_buy - 100.0) / (100.0 - sl_buy), 2.0, places=2)

    def test_compounding_stake_anti_martingale(self):
        bankroll = 500.0
        # Risco base de 8% = R$ 40
        s0 = calculate_compounding_stake(bankroll, streak=0, cfg=self.cfg)
        self.assertEqual(s0, 40.0)

        # Streak 1: expande +25% = R$ 50
        s1 = calculate_compounding_stake(bankroll, streak=1, cfg=self.cfg)
        self.assertEqual(s1, 50.0)

        # Streak 2: expande +25% = R$ 62.50
        s2 = calculate_compounding_stake(bankroll, streak=2, cfg=self.cfg)
        self.assertEqual(s2, 62.5)

    def test_update_monthly_vault(self):
        # Se ultrapassa R$ 1.000, deve blindar R$ 200 no cofre
        vault, bankroll = update_monthly_vault(total_equity=1100.0, vault=0.0, active_bankroll=1100.0)
        self.assertEqual(vault, 200.0)
        self.assertEqual(bankroll, 900.0)
        self.assertEqual(vault + bankroll, 1100.0)


if __name__ == "__main__":
    unittest.main()
