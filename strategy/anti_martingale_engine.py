"""
Motor de Dimensionamento Exponencial e Anti-Martingale (Compounding Engine).
Implementa modelos de progressao geometrica para micro-capital:
- Anti-Martingale (Paroli): Expansao do lote em vitorias, retorno imediato à base na perda.
- Kelly Fracionario: Alocacao otima baseada em probabilidade e payoff.
- Simulacao de Monte Carlo e trajetoria historica para avaliacao de risco de ruina vs crescimento 1.000x.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class AntiMartingaleConfig:
    """Configuracao do modelo de dimensionamento progressivo."""
    initial_bankroll_brl: float = 10.0
    target_bankroll_brl: float = 10000.0
    base_risk_pct: float = 0.05          # 5% de risco base da banca por trade
    win_expansion_pct: float = 0.20      # Aumenta 20% do lote ou do lucro apos vitoria
    max_streak_expansion: int = 4        # Trava de seguranca: apos 4 vitorias seguidas, realiza lucro e volta à base
    min_trade_brl: float = 0.50          # Lote minimo operacional
    ruin_threshold_brl: float = 1.00     # Considerado quebrado se saldo cair abaixo de R$ 1,00
    win_rate: float = 0.60               # Probabilidade estimada de vitoria
    payoff_ratio: float = 1.0            # Relacao Ganho / Perda media
    kelly_multiplier: float = 0.25       # Fracao de seguranca do criterio de Kelly


def calculate_kelly_fraction(
    win_rate: float,
    payoff_ratio: float,
    multiplier: float = 0.25
) -> float:
    """Calcula a fracao otima de Kelly com multiplicador conservador."""
    if payoff_ratio <= 0.0:
        return 0.0
    q = 1.0 - win_rate
    full_kelly = (win_rate * payoff_ratio - q) / payoff_ratio
    if full_kelly <= 0.0:
        return 0.0
    return min(0.20, full_kelly * multiplier)


def next_anti_martingale_stake(
    bankroll: float,
    current_streak: int,
    last_was_win: bool,
    config: AntiMartingaleConfig
) -> Tuple[float, int]:
    """Calcula o tamanho do proximo trade seguindo Anti-Martingale com reset em perda."""
    base_stake = max(config.min_trade_brl, bankroll * config.base_risk_pct)
    if not last_was_win or current_streak <= 0:
        return base_stake, 0

    if current_streak >= config.max_streak_expansion:
        # Atingiu o teto da sequencia vitoriosa: realiza lucros e reseta
        return base_stake, 0

    multiplier = (1.0 + config.win_expansion_pct) ** current_streak
    expanded_stake = min(bankroll * 0.40, base_stake * multiplier)
    return max(config.min_trade_brl, expanded_stake), current_streak


def simulate_single_trade(
    bankroll: float,
    stake: float,
    is_win: bool,
    payoff_ratio: float,
    fee_rate: float = 0.0004
) -> Tuple[float, float]:
    """Simula o resultado financeiro liquido de uma operacao individual."""
    gross_pnl = (stake * payoff_ratio) if is_win else -stake
    fee = (stake * fee_rate * 2.0)
    net_pnl = gross_pnl - fee
    new_bankroll = max(0.0, bankroll + net_pnl)
    return new_bankroll, net_pnl


def _run_single_trajectory(
    config: AntiMartingaleConfig,
    num_trades: int,
    strategy_mode: str,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """Executa uma trajetoria estocastica de N trades para um modo de dimensionamento."""
    if seed is not None:
        random.seed(seed)

    bankroll = config.initial_bankroll_brl
    streak = 0
    last_win = False
    max_equity = bankroll
    min_equity = bankroll
    wins = 0

    kelly_frac = calculate_kelly_fraction(config.win_rate, config.payoff_ratio, config.kelly_multiplier)

    for _ in range(num_trades):
        if bankroll <= config.ruin_threshold_brl or bankroll >= config.target_bankroll_brl:
            break

        if strategy_mode == "fixed_fractional":
            stake = max(config.min_trade_brl, bankroll * kelly_frac)
        elif strategy_mode == "anti_martingale":
            stake, streak = next_anti_martingale_stake(bankroll, streak, last_win, config)
        else:  # flat_linear
            stake = max(config.min_trade_brl, config.initial_bankroll_brl * config.base_risk_pct)

        is_win = random.random() < config.win_rate
        bankroll, _ = simulate_single_trade(bankroll, stake, is_win, config.payoff_ratio)

        if is_win:
            wins += 1
            streak += 1
            last_win = True
        else:
            streak = 0
            last_win = False

        max_equity = max(max_equity, bankroll)
        min_equity = min(min_equity, bankroll)

    drawdown = (max_equity - min_equity) / max_equity if max_equity > 0 else 1.0

    return {
        "final_bankroll": round(bankroll, 2),
        "reached_target": bankroll >= config.target_bankroll_brl,
        "is_ruined": bankroll <= config.ruin_threshold_brl,
        "max_equity": round(max_equity, 2),
        "max_drawdown_pct": round(drawdown * 100.0, 1),
        "total_trades": num_trades,
        "wins": wins
    }


def run_monte_carlo_comparison(
    config: AntiMartingaleConfig,
    num_simulations: int = 1000,
    trades_per_year: int = 730
) -> Dict[str, Any]:
    """Executa simulacoes de Monte Carlo comparando Flat, Anti-Martingale e Kelly."""
    modes = ["flat_linear", "anti_martingale", "fixed_fractional"]
    results = {}

    for mode in modes:
        final_balances = []
        ruin_count = 0
        target_count = 0
        drawdowns = []

        for i in range(num_simulations):
            traj = _run_single_trajectory(config, trades_per_year, mode, seed=(i + 42))
            final_balances.append(traj["final_bankroll"])
            if traj["is_ruined"]:
                ruin_count += 1
            if traj["reached_target"]:
                target_count += 1
            drawdowns.append(traj["max_drawdown_pct"])

        median_bal = sorted(final_balances)[len(final_balances) // 2]
        avg_dd = sum(drawdowns) / len(drawdowns)

        results[mode] = {
            "mode": mode,
            "simulations": num_simulations,
            "ruin_probability_pct": round((ruin_count / num_simulations) * 100.0, 2),
            "target_reached_pct": round((target_count / num_simulations) * 100.0, 2),
            "median_final_bankroll": round(median_bal, 2),
            "average_max_drawdown_pct": round(avg_dd, 1),
            "best_case_bankroll": round(max(final_balances), 2),
            "worst_case_bankroll": round(min(final_balances), 2)
        }

    return results
