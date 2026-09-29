#!/usr/bin/env python3
"""
Script de Simulacao Estocastica e Monte Carlo de Anti-Martingale Expandido.
Avalia a probabilidade real de multiplicar R$ 10 em R$ 10.000 em 365 dias
comparando Flat Stake, Anti-Martingale com Reset, Kelly Fracionario,
Ratchet Vault (Trava de Lucro) e Dimensionamento Adaptativo.
Salva relatorio em data/anti_martingale_report.json.
"""

from __future__ import annotations
import os
import sys
import json
from typing import Dict, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.anti_martingale_engine import (
    AntiMartingaleConfig,
    run_monte_carlo_comparison
)

OUTPUT_PATH = os.path.join(ROOT_DIR, "data", "anti_martingale_report.json")


def _print_mode_stats(mode: str, data: Dict[str, Any]):
    """Imprime sumario estatistico de uma modalidade de dimensionamento."""
    print(f"\n  Modo: {mode.upper()}")
    print(f"    - Saldo Mediano Final: R$ {data['median_final_bankroll']:,.2f}")
    print(f"    - Percentil 25 -> 75 : R$ {data['p25_bankroll']:,.2f} a R$ {data['p75_bankroll']:,.2f}")
    print(f"    - Melhor Caso: R$ {data['best_case_bankroll']:,.2f} | Pior: R$ {data['worst_case_bankroll']:,.2f}")
    print(f"    - Risco de Ruina (< R$ 1,00): {data['ruin_probability_pct']}%")
    print(f"    - Meta de R$ 10.000 Atingida: {data['target_reached_pct']}%")
    print(f"    - Drawdown Medio: {data['average_max_drawdown_pct']}%")
    if data.get("average_vault_locked", 0) > 0:
        print(f"    - Lucro Medio Blindado no Cofre: R$ {data['average_vault_locked']:,.2f}")


def run_scenario(
    name: str,
    cfg: AntiMartingaleConfig,
    simulations: int,
    trades: int
) -> Dict[str, Any]:
    """Executa um cenario completo de Monte Carlo e exibe os resultados."""
    print(f"\n--- {name} ---")
    print(f"Parametros: Win Rate: {cfg.win_rate*100:.0f}% | Payoff: {cfg.payoff_ratio}x | Trades: {trades} | Sims: {simulations}")
    results = run_monte_carlo_comparison(cfg, num_simulations=simulations, trades_per_year=trades)
    for mode, data in results.items():
        _print_mode_stats(mode, data)
    return {
        "scenario_name": name,
        "parameters": {
            "initial_bankroll_brl": cfg.initial_bankroll_brl,
            "target_bankroll_brl": cfg.target_bankroll_brl,
            "win_rate": cfg.win_rate,
            "payoff_ratio": cfg.payoff_ratio,
            "simulations": simulations,
            "trades_per_year": trades
        },
        "results": results
    }


def main():
    print("==================================================================")
    print("SIMULADOR EXPONENCIAL AVANÇADO DE MONTE CARLO (R$ 10 -> R$ 10.000)")
    print("==================================================================")

    # Cenario 1: Micro-Scalping (60% win rate, payoff 1.0, 730 trades/ano)
    cfg1 = AntiMartingaleConfig(
        initial_bankroll_brl=10.0,
        target_bankroll_brl=10000.0,
        win_rate=0.60,
        payoff_ratio=1.0,
        win_expansion_pct=0.25,
        max_streak_expansion=3,
        vault_lock_pct=0.40
    )
    s1 = run_scenario("Cenario 1: Micro-Scalping Padrao (60% acerto, 1:1 payoff, 2 trades/dia)", cfg1, 2000, 730)

    # Cenario 2: Price Action Assimetrico em NY (55% win rate, payoff 1.8, 365 trades/ano)
    cfg2 = AntiMartingaleConfig(
        initial_bankroll_brl=10.0,
        target_bankroll_brl=10000.0,
        win_rate=0.55,
        payoff_ratio=1.8,
        win_expansion_pct=0.20,
        max_streak_expansion=3,
        vault_lock_pct=0.50
    )
    s2 = run_scenario("Cenario 2: Price Action Assimetrico em NY (55% acerto, 1.8:1 payoff, 1 trade/dia)", cfg2, 2000, 365)

    # Cenario 3: Alta Frequencia e Volatilidade (58% win rate, payoff 1.3, 1.000 trades/ano)
    cfg3 = AntiMartingaleConfig(
        initial_bankroll_brl=10.0,
        target_bankroll_brl=10000.0,
        win_rate=0.58,
        payoff_ratio=1.3,
        win_expansion_pct=0.20,
        max_streak_expansion=3,
        vault_lock_pct=0.40
    )
    s3 = run_scenario("Cenario 3: Alta Frequencia Dinamica (58% acerto, 1.3:1 payoff, 1.000 trades/ano)", cfg3, 2000, 1000)

    report = {
        "title": "Analise de Viabilidade: Crescimento Exponencial R$ 10 -> R$ 10.000 (Monte Carlo Multi-Cenario)",
        "total_simulations_executed": 6000,
        "scenarios": [s1, s2, s3],
        "primary_comparison": s1["results"]
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[OK] Relatorio consolidado de 6.000 simulacoes salvo em: {OUTPUT_PATH}")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    main()
