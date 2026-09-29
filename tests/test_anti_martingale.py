"""
Testes Unitarios do Motor de Dimensionamento Exponencial e Anti-Martingale.
Valida o calculo de Kelly Fracionario, expansao de lote em vitorias,
retorno imediato à base na perda e simulacao de Monte Carlo.
"""

from __future__ import annotations
import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.anti_martingale_engine import (
    AntiMartingaleConfig,
    calculate_kelly_fraction,
    next_anti_martingale_stake,
    simulate_single_trade,
    run_monte_carlo_comparison
)


class TestAntiMartingaleEngine(unittest.TestCase):
    """Suíte de validação da matemática de progressão geométrica."""

    def setUp(self):
        self.config = AntiMartingaleConfig(
            initial_bankroll_brl=10.0,
            target_bankroll_brl=100.0,
            base_risk_pct=0.05,
            win_expansion_pct=0.20,
            max_streak_expansion=3,
            min_trade_brl=0.50
        )

    def test_calculate_kelly_fraction(self):
        # 60% win rate com 1:1 payoff -> full kelly = (0.6*1 - 0.4)/1 = 0.20
        # Multiplicador 0.25 -> 0.05
        k = calculate_kelly_fraction(0.60, 1.0, multiplier=0.25)
        self.assertAlmostEqual(k, 0.05, places=3)

        # Sem vantagem matematica (win rate 40%, 1:1) -> 0.0
        k_neg = calculate_kelly_fraction(0.40, 1.0)
        self.assertEqual(k_neg, 0.0)

    def test_next_anti_martingale_stake_win_and_loss(self):
        bankroll = 100.0
        # Apos derrota: deve voltar à base (5% de 100 = 5.0)
        stake_loss, streak_loss = next_anti_martingale_stake(bankroll, current_streak=2, last_was_win=False, config=self.config)
        self.assertEqual(stake_loss, 5.0)
        self.assertEqual(streak_loss, 0)

        # Apos 1 vitoria: expande 20%
        stake_w1, streak_w1 = next_anti_martingale_stake(bankroll, current_streak=1, last_was_win=True, config=self.config)
        self.assertGreater(stake_w1, 5.0)
        self.assertEqual(streak_w1, 1)

        # Apos atingir o teto de streak (3): deve realizar lucro e voltar à base
        stake_max, streak_max = next_anti_martingale_stake(bankroll, current_streak=3, last_was_win=True, config=self.config)
        self.assertEqual(stake_max, 5.0)
        self.assertEqual(streak_max, 0)

    def test_simulate_single_trade(self):
        bankroll = 50.0
        stake = 10.0

        # Vitoria com payoff 1.0 e taxa
        new_b, net_pnl = simulate_single_trade(bankroll, stake, is_win=True, payoff_ratio=1.0, fee_rate=0.0002)
        self.assertGreater(new_b, bankroll)
        self.assertAlmostEqual(net_pnl, 10.0 - (10.0 * 0.0004), places=3)

        # Derrota
        new_b_loss, net_pnl_loss = simulate_single_trade(bankroll, stake, is_win=False, payoff_ratio=1.0, fee_rate=0.0002)
        self.assertLess(new_b_loss, bankroll)
        self.assertLess(net_pnl_loss, -10.0)

    def test_monte_carlo_mini_comparison(self):
        cfg = AntiMartingaleConfig(initial_bankroll_brl=10.0, target_bankroll_brl=20.0)
        results = run_monte_carlo_comparison(cfg, num_simulations=10, trades_per_year=20)
        self.assertIn("flat_linear", results)
        self.assertIn("anti_martingale", results)
        self.assertIn("fixed_fractional", results)
        self.assertIn("anti_martingale_vault", results)
        self.assertIn("anti_martingale_adaptive", results)
        self.assertIn("ruin_probability_pct", results["anti_martingale"])
        self.assertIn("average_vault_locked", results["anti_martingale_vault"])

    def test_ratchet_vault_protection(self):
        cfg = AntiMartingaleConfig(initial_bankroll_brl=10.0, target_bankroll_brl=500.0, vault_lock_pct=0.40)
        results = run_monte_carlo_comparison(
            cfg, num_simulations=20, trades_per_year=50, modes=["anti_martingale_vault"]
        )
        self.assertIn("anti_martingale_vault", results)
        self.assertGreaterEqual(results["anti_martingale_vault"]["average_vault_locked"], 0.0)


if __name__ == "__main__":
    unittest.main()
