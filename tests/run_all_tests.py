#!/usr/bin/env python3
"""
Orquestrador central de execucao de todos os testes do bot-cript.
Executa as 3 camadas obrigatorias:
1. Camada Atomica (test_atomic_invariants.py)
2. Camada Empirica (test_sdd_behavioral.py, test_odd_telemetry.py)
3. Camada Massiva e Evals (test_llm_evals.py, test_massive_stress.py)
"""

import sys
import subprocess
import os

TEST_FILES = [
    ("Atômica / TDD", "tests/test_atomic_invariants.py"),
    ("Empírica / SDD", "tests/test_sdd_behavioral.py"),
    ("Empírica / ODD", "tests/test_odd_telemetry.py"),
    ("Evals de LLM", "tests/test_llm_evals.py"),
    ("Massiva / Estresse", "tests/test_massive_stress.py"),
    ("Fase 1 / Fundação", "tests/test_phase1_foundation.py"),
    ("Fase 2 / Paper Exchange", "tests/test_paper_exchange.py"),
    ("Fase 2 / CCXT Adapter", "tests/test_exchange_adapter.py"),
    ("Fase 3 / AST & Fitness", "tests/test_ast_fitness.py"),
    ("Fase 4 / Crossover Genético", "tests/test_crossover.py"),
    ("Fase 4 / Incubadora Quarentena", "tests/test_incubator.py"),
    ("Fase 5 / Tesouraria Central", "tests/test_treasury.py"),
    ("Fase 6 / Supervisor OpenCode", "tests/test_supervisor_loop.py"),
    ("Fase 6 / Dashboard & Telegram", "tests/test_monitoring.py"),
    ("Fase 6 / Walk-Forward Backtest", "tests/test_walk_forward.py"),
    ("Fase 7 / Ingestão 15m", "tests/test_data_15m.py"),
    ("Fase 7 / Motor Day Trade", "tests/test_daytrade_engine.py"),
    ("Fase 7 / Walk-Forward Mensal", "tests/test_monthly_walk_forward.py"),
    ("Fase 7 / Motor Híbrido Alpha", "tests/test_hybrid_alpha.py"),
    ("Fase 7 / Micro-Scalper Centavos", "tests/test_cent_scalper.py"),
    ("Fase 7 / Anti-Martingale Sizing", "tests/test_anti_martingale.py"),
    ("Fase 7 / Motor Híbrido Misto", "tests/test_mixed_portfolio.py"),
    ("Fase 7 / Benchmark Catálogo", "tests/test_strategy_catalog_tester.py"),
    ("Fase 7 / Avaliador Laia", "tests/test_laia_entry_evaluator.py"),
    ("Segurança / AST Engine", "tests/test_ast_security.py"),
    ("Fase 6/7 / Loop Assíncrono", "tests/test_event_loop.py"),
    ("Fase 7 / Entropia & Log-Returns", "tests/test_entropy_compounding.py"),
    ("Fase 7 / Trigonometria Adaptativa", "tests/test_trigonometric_adaptive.py"),
    ("Fase 7 / Roteador Maker & OBI", "tests/test_smart_order_router.py"),
    ("Fase 7 / Alertas Operacionais", "tests/test_operational_alerts.py"),
    ("Fase 7 / Pipeline Alfa Unificado", "tests/test_unified_alpha_pipeline.py"),
    ("Fase 7 / Motor Matricial Alpha", "tests/test_cross_sectional_matrix.py"),
    ("Fase 7 / Flotilha 40 Bots & Paper", "tests/test_swarm_paper_trading.py"),
    ("Fase 7 / Motores de Alto Win Rate", "tests/test_high_winrate_engines.py"),
    ("Fase 7 / Alocador Kelly & Streamer L2", "tests/test_portfolio_allocator_and_streamer.py"),
]








BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.init_test_db import ensure_test_database


def main():
    ensure_test_database()
    print("\n==================================================================")
    print("ORQUESTRADOR DE TESTES: BOT CRIPTO (SUÍTE COMPLETA)")
    print("==================================================================")
    
    passed_count = 0
    total_count = len(TEST_FILES)
    
    for category, rel_path in TEST_FILES:
        full_path = os.path.join(BASE_DIR, rel_path)
        cmd = [sys.executable, full_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        status_label = "✅ PASSOU" if res.returncode == 0 else "❌ FALHOU"
        print(f"[{status_label}] {category:<20}: {rel_path}")
        
        if res.returncode != 0:
            print(f"       Erro: {res.stderr.strip() or res.stdout.strip()}")
        else:
            passed_count += 1
            
    print("\n==================================================================")
    print(f"RESULTADO FINAL: {passed_count}/{total_count} SUÍTES APROVADAS")
    print("==================================================================")
    
    if passed_count == total_count:
        print("TODOS OS GATES DE TESTE FORAM SUPERADOS COM SUCESSO.\n")
        sys.exit(0)
    else:
        print("FALHA EM UMA OU MAIS SUÍTES DE TESTE.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
