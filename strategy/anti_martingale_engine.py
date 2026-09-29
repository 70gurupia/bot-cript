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
    vault_lock_pct: float = 0.40         # Percentual trancado no cofre nos degraus de lucro
    use_ratchet_vault: bool = False      # Ativa trava de lucro intocavel em degraus


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


def _calculate_stake_for_mode(
    mode: str,
    bankroll: float,
    total_equity: float,
    streak: int,
    last_win: bool,
    config: AntiMartingaleConfig,
    kelly_frac: float
) -> Tuple[float, int]:
    """Determina o tamanho da ordem e a sequencia conforme o modo configurado."""
    if mode == "fixed_fractional":
        stake = max(config.min_trade_brl, bankroll * kelly_frac)
        return stake, streak

    if mode == "flat_linear":
        stake = max(config.min_trade_brl, config.initial_bankroll_brl * config.base_risk_pct)
        return stake, streak

    risk_pct = config.base_risk_pct
    if "adaptive" in mode:
        if total_equity >= 1000.0:
            risk_pct = 0.03
        elif total_equity >= 100.0:
            risk_pct = 0.05
        else:
            risk_pct = 0.06

    cfg_copy = AntiMartingaleConfig(
        min_trade_brl=config.min_trade_brl,
        base_risk_pct=risk_pct,
        win_expansion_pct=config.win_expansion_pct,
        max_streak_expansion=config.max_streak_expansion
    )
    return next_anti_martingale_stake(bankroll, streak, last_win, cfg_copy)


def _update_vault_milestones(
    total_equity: float,
    vault: float,
    active_bankroll: float,
    passed_milestones: set,
    config: AntiMartingaleConfig
) -> Tuple[float, float]:
    """Tranca parte do lucro no cofre sempre que cruza novos marcos de patrimonio."""
    milestones = (50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0)
    for m in milestones:
        if total_equity >= m and m not in passed_milestones:
            passed_milestones.add(m)
            profit_above_base = max(0.0, total_equity - config.initial_bankroll_brl)
            to_lock = (profit_above_base * config.vault_lock_pct) - vault
            if to_lock > 0 and active_bankroll > to_lock + config.min_trade_brl:
                vault += to_lock
                active_bankroll -= to_lock
    return vault, active_bankroll


def _step_simulation_trade(
    active_bankroll: float,
    vault: float,
    streak: int,
    last_win: bool,
    config: AntiMartingaleConfig,
    strategy_mode: str,
    kelly_frac: float
) -> Tuple[float, int, bool]:
    """Executa o despacho e o resultado de um trade individual na trajetoria."""
    total_equity = active_bankroll + vault
    stake, streak = _calculate_stake_for_mode(
        strategy_mode, active_bankroll, total_equity, streak, last_win, config, kelly_frac
    )
    is_win = random.random() < config.win_rate
    new_bankroll, _ = simulate_single_trade(active_bankroll, stake, is_win, config.payoff_ratio)
    new_streak = (streak + 1) if is_win else 0
    return new_bankroll, new_streak, is_win


def _is_vault_enabled(mode: str, config: AntiMartingaleConfig) -> bool:
    """Verifica se o modo operacional utiliza trava de cofre."""
    if config.use_ratchet_vault:
        return True
    return ("vault" in mode) or ("adaptive" in mode)


def _is_trajectory_finished(bankroll: float, equity: float, config: AntiMartingaleConfig) -> bool:
    """Verifica se a trajetoria atingiu condicao de parada (ruina ou meta)."""
    return (bankroll <= config.ruin_threshold_brl) or (equity >= config.target_bankroll_brl)


def _run_single_trajectory(
    config: AntiMartingaleConfig,
    num_trades: int,
    strategy_mode: str,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """Executa uma trajetoria estocastica de N trades para um modo de dimensionamento."""
    if seed is not None:
        random.seed(seed)

    active_bankroll = config.initial_bankroll_brl
    vault = 0.0
    streak = 0
    last_win = False
    passed_milestones = set()
    use_vault = _is_vault_enabled(strategy_mode, config)

    max_equity = active_bankroll
    min_equity = active_bankroll
    wins = 0
    trades_done = 0

    kelly_frac = calculate_kelly_fraction(config.win_rate, config.payoff_ratio, config.kelly_multiplier)

    for _ in range(num_trades):
        total_equity = active_bankroll + vault
        if _is_trajectory_finished(active_bankroll, total_equity, config):
            break

        trades_done += 1
        active_bankroll, streak, is_win = _step_simulation_trade(
            active_bankroll, vault, streak, last_win, config, strategy_mode, kelly_frac
        )
        last_win = is_win
        if is_win:
            wins += 1

        total_equity = active_bankroll + vault
        if use_vault:
            vault, active_bankroll = _update_vault_milestones(
                total_equity, vault, active_bankroll, passed_milestones, config
            )
            total_equity = active_bankroll + vault

        max_equity = max(max_equity, total_equity)
        min_equity = min(min_equity, total_equity)

    final_total = round(active_bankroll + vault, 2)
    drawdown = (max_equity - min_equity) / max_equity if max_equity > 0 else 1.0
    is_ruined = (active_bankroll <= config.ruin_threshold_brl) and (vault < config.min_trade_brl)

    return {
        "final_bankroll": final_total,
        "vault_locked": round(vault, 2),
        "active_bankroll": round(active_bankroll, 2),
        "reached_target": final_total >= config.target_bankroll_brl,
        "is_ruined": is_ruined,
        "max_equity": round(max_equity, 2),
        "max_drawdown_pct": round(drawdown * 100.0, 1),
        "total_trades": trades_done,
        "wins": wins
    }


def run_monte_carlo_comparison(
    config: AntiMartingaleConfig,
    num_simulations: int = 1000,
    trades_per_year: int = 730,
    modes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Executa simulacoes de Monte Carlo comparando Flat, Anti-Martingale, Kelly e Vault."""
    target_modes = modes or [
        "flat_linear",
        "fixed_fractional",
        "anti_martingale",
        "anti_martingale_vault",
        "anti_martingale_adaptive"
    ]
    results = {}

    for mode in target_modes:
        final_balances = []
        vaults = []
        ruin_count = 0
        target_count = 0
        drawdowns = []

        for i in range(num_simulations):
            traj = _run_single_trajectory(config, trades_per_year, mode, seed=(i + 42))
            final_balances.append(traj["final_bankroll"])
            vaults.append(traj["vault_locked"])
            if traj["is_ruined"]:
                ruin_count += 1
            if traj["reached_target"]:
                target_count += 1
            drawdowns.append(traj["max_drawdown_pct"])

        sorted_bal = sorted(final_balances)
        n = len(sorted_bal)
        p10 = sorted_bal[int(n * 0.10)]
        p25 = sorted_bal[int(n * 0.25)]
        median_bal = sorted_bal[n // 2]
        p75 = sorted_bal[int(n * 0.75)]
        p90 = sorted_bal[int(n * 0.90)]
        avg_dd = sum(drawdowns) / len(drawdowns)
        avg_vault = sum(vaults) / len(vaults)

        results[mode] = {
            "mode": mode,
            "simulations": num_simulations,
            "ruin_probability_pct": round((ruin_count / num_simulations) * 100.0, 2),
            "target_reached_pct": round((target_count / num_simulations) * 100.0, 2),
            "median_final_bankroll": round(median_bal, 2),
            "p10_bankroll": round(p10, 2),
            "p25_bankroll": round(p25, 2),
            "p75_bankroll": round(p75, 2),
            "p90_bankroll": round(p90, 2),
            "average_vault_locked": round(avg_vault, 2),
            "average_max_drawdown_pct": round(avg_dd, 1),
            "best_case_bankroll": round(max(final_balances), 2),
            "worst_case_bankroll": round(min(final_balances), 2)
        }

    return results
