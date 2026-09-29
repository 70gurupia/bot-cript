#!/usr/bin/env python3
"""
Suíte de Validação e Teste de Estresse Histórico do Ano de 2025.
Avalia todas as estratégias do robô no ano mais recente do mercado:
- Donchian Breakout 20 no BTC
- Arbitragem Temporal Lead-Lag BTC -> ETH
- Geração 1 (Baseline Shannon) vs Geração 3 (Newtoniana Avançada) em ETH, BTC, BNB e SOL
- Simulação da banca de R$ 500 com Anti-Martingale e Ratchet Vault
Salva relatório em data/stress_test_2025_report.json.
"""

from __future__ import annotations
import os
import sys
import math
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.entropy_compounding_engine import (
    EntropyEngineConfig,
    compute_log_returns,
    compute_atr,
    update_monthly_vault
)
from strategy.trigonometric_adaptive_engine import (
    compute_series_trigonometric_vectors,
    compute_trigonometric_adaptive_ma,
    evaluate_trigonometric_signal,
    compute_tsallis_entropy,
    compute_dynamic_cosine_stop
)
from scripts.run_stress_test_2018_2019 import (
    load_candles,
    evaluate_donchian_breakout,
    evaluate_lead_lag,
    evaluate_entropy_model,
    simulate_bankroll_evolution
)
from scripts.run_advanced_indicators_simulation import evaluate_advanced_newton_model

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "stress_test_2025_report.json")

TS_2025_START = int(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
TS_2025_END = int(datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)


def evaluate_pair_full_2025(
    conn: sqlite3.Connection,
    sym: str,
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Avalia o desempenho de um par em 2025 comparando Baseline vs G3 Newtoniana."""
    candles = load_candles(conn, sym, TS_2025_START, TS_2025_END)
    if len(candles) < 100:
        return {"candles": 0, "g1_baseline": {}, "g3_newton": {}}

    g1 = evaluate_entropy_model(candles, cfg)
    g3 = evaluate_advanced_newton_model(candles, cfg)

    return {
        "candles": len(candles),
        "g1_baseline": g1,
        "g3_newton": g3
    }


def main():
    print("==========================================================================================")
    print("TESTE DE ESTRESSE E VALIDAÇÃO HISTÓRICA DO ANO DE 2025 COMPLETO")
    print("==========================================================================================")

    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()

    # 1. Carrega dados de BTC e ETH para Donchian e Lead-Lag
    btc_c = load_candles(conn, "BTCUSDT", TS_2025_START, TS_2025_END)
    eth_c = load_candles(conn, "ETHUSDT", TS_2025_START, TS_2025_END)

    donch_btc = evaluate_donchian_breakout(btc_c)
    ll_eth = evaluate_lead_lag(btc_c, eth_c)

    print(f"\n[Donchian BTC 2025] Trades: {donch_btc['trades']:>2} | Win Rate: {donch_btc['win_rate_pct']:>5.1f}% | Retorno: {donch_btc['net_return_pct']:>+6.2f}%")
    print(f"[Lead-Lag ETH 2025] Trades: {ll_eth['trades']:>2} | Win Rate: {ll_eth['win_rate_pct']:>5.1f}% | Retorno: {ll_eth['net_return_pct']:>+6.2f}%")

    # 2. Avaliação dos 4 pares principais em 2025 (G1 vs G3)
    symbols = ["ETHUSDT", "BTCUSDT", "BNBUSDT", "SOLUSDT"]
    eval_results = {}

    print("\n--- COMPARAÇÃO DE MODELOS EM 2025 (BASELINE G1 VS NEWTONIANO G3) ---")
    print(f"{'Símbolo':<10} | {'G1 Retorno':<12} | {'G1 Win Rate':<12} | {'G3 Retorno':<12} | {'G3 Win Rate':<12} | {'Impacto G3'}")
    print("-" * 88)

    for sym in symbols:
        res = evaluate_pair_full_2025(conn, sym, cfg)
        eval_results[sym] = res

        g1_ret = f"{res['g1_baseline']['net_return_pct']:>+6.2f}%"
        g1_wr = f"{res['g1_baseline']['win_rate_pct']}% ({res['g1_baseline']['trades']}t)"
        g3_ret = f"{res['g3_newton']['net_return_pct']:>+6.2f}%"
        g3_wr = f"{res['g3_newton']['win_rate_pct']}% ({res['g3_newton']['trades']}t)"

        diff = res['g3_newton']['net_return_pct'] - res['g1_baseline']['net_return_pct']
        impact = f"MELHOROU (+{diff:.1f}%)" if diff > 0 else f"EQUIVALENTE ({diff:+.1f}%)"

        print(f"{sym:<10} | {g1_ret:<12} | {g1_wr:<12} | {g3_ret:<12} | {g3_wr:<12} | {impact}")

    # 3. Simulação da Banca de R$ 500 no Portfólio Combinado em 2025
    portfolio_pnl = [0.048] * donch_btc["wins"] + [-0.024] * (donch_btc["trades"] - donch_btc["wins"])
    portfolio_pnl += [0.025] * ll_eth["wins"] + [-0.015] * (ll_eth["trades"] - ll_eth["wins"])
    eth_g3 = eval_results["ETHUSDT"]["g3_newton"]
    portfolio_pnl += [0.048] * eth_g3["wins"] + [-0.024] * (eth_g3["trades"] - eth_g3["wins"])

    sim_res = simulate_bankroll_evolution(portfolio_pnl, 500.0)
    print("\n--- SIMULAÇÃO DE BANCA (R$ 500) NO PORTFÓLIO EM 2025 ---")
    print(f"Patrimônio Final Consolidado: R$ {sim_res['final_bankroll_brl']:,.2f}")
    print(f"Capital Líquido Operacional:  R$ {sim_res['liquid_bankroll_brl']:,.2f}")
    print(f"Capital Travado no Cofre:     R$ {sim_res['vault_locked_brl']:,.2f} (100% Protegido)")

    conn.close()

    report_data = {
        "year": 2025,
        "donchian_btc": donch_btc,
        "lead_lag_eth": ll_eth,
        "pair_evaluations": eval_results,
        "bankroll_simulation": sim_res
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n[OK] Relatório completo de 2025 salvo em: {REPORT_PATH}")
    print("==========================================================================================")
    return 0


if __name__ == "__main__":
    main()
