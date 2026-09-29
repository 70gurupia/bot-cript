#!/usr/bin/env python3
"""
Script de Simulacao Estocastica e Monte Carlo de Anti-Martingale.
Avalia a probabilidade real de multiplicar R$ 10 em R$ 10.000 em 365 dias
comparando Flat Stake, Anti-Martingale com Reset e Kelly Fracionario.
Salva relatorio em data/anti_martingale_report.json.
"""

from __future__ import annotations
import os
import sys
import json

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.anti_martingale_engine import (
    AntiMartingaleConfig,
    run_monte_carlo_comparison
)

OUTPUT_PATH = os.path.join(ROOT_DIR, "data", "anti_martingale_report.json")


def main():
    print("==================================================================")
    print("SIMULADOR DE CRESCIMENTO EXPONENCIAL (R$ 10 -> R$ 10.000)")
    print("==================================================================")

    # Cenario 1: Micro-Scalping (60% win rate, 1:1 payoff, 2 trades/dia = 730 trades/ano)
    cfg_base = AntiMartingaleConfig(
        initial_bankroll_brl=10.0,
        target_bankroll_brl=10000.0,
        win_rate=0.60,
        payoff_ratio=1.0,
        win_expansion_pct=0.25,
        max_streak_expansion=3
    )

    print("\nExecutando Monte Carlo (1.000 simulacoes por modalidade)...")
    results = run_monte_carlo_comparison(cfg_base, num_simulations=1000, trades_per_year=730)

    report = {
        "title": "Analise de Viabilidade: Crescimento Exponencial R$ 10 -> R$ 10.000 em 365 Dias",
        "parameters": {
            "initial_bankroll_brl": cfg_base.initial_bankroll_brl,
            "target_bankroll_brl": cfg_base.target_bankroll_brl,
            "win_rate": cfg_base.win_rate,
            "payoff_ratio": cfg_base.payoff_ratio,
            "simulations_count": 1000,
            "trades_per_year": 730
        },
        "comparison": results
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[OK] Relatorio salvo em: {OUTPUT_PATH}")
    print("\nRESULTADOS DA COMPARACAO:")
    for mode, data in results.items():
        print(f"\n  Modo: {mode.upper()}")
        print(f"    - Saldo Mediano Final: R$ {data['median_final_bankroll']:,.2f}")
        print(f"    - Melhor Caso: R$ {data['best_case_bankroll']:,.2f}")
        print(f"    - Pior Caso: R$ {data['worst_case_bankroll']:,.2f}")
        print(f"    - Risco de Ruina (< R$ 1,00): {data['ruin_probability_pct']}%")
        print(f"    - Meta de R$ 10.000 Atingida: {data['target_reached_pct']}%")
        print(f"    - Drawdown Medio: {data['average_max_drawdown_pct']}%")

    print("\n==================================================================")


if __name__ == "__main__":
    main()
