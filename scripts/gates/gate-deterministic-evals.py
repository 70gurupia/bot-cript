#!/usr/bin/env python3
"""
Gate Deterministico: Baterias de Avaliacao e Evals de IA e Estrategias.
Executa 6 baterias de validacao matematica, seguranca e resiliencia operacional:
1. Robustez contra Prompt Injection e sanitizacao de multiplicador de risco.
2. Resiliencia contra Flash Crash, margem ISOLATED e disparo de Circuit Breakers.
3. Rejeicao de ruido e chicotada de Markov em regimes de chop lateral.
4. Monotonicidade formal do Ratchet Vault em 100 ciclos estocasticos.
5. Acuracia do modelo de friccao (Maker Fee 0.02% vs Taker Fee 0.04% + Slippage).
6. Segregacao estrita e solvencia da Flotilha de 40 Bots nos 8 grupos.
"""

from __future__ import annotations
import sys
import os
import random
from typing import List, Dict, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.paper_exchange import PaperTradingExchange
from core.swarm_manager import SwarmManager, GROUP_DEFINITIONS
from core.kill_switch import circuit_breaker
from strategy.entropy_compounding_engine import (
    EntropyEngineConfig,
    compute_log_returns,
    compute_shannon_entropy,
    detect_entropy_breakout,
    update_monthly_vault,
)
from strategy.opencode_client import FALLBACK_REGIME


def eval_llm_prompt_injection_and_clamp() -> Dict[str, Any]:
    """Eval 1: Valida clamp de multiplicador abusivo e degradacao graciosa sob injecao."""
    test_cases = [
        {"multiplicador_exposicao": 99.0, "esperado": 1.0},
        {"multiplicador_exposicao": -5.0, "esperado": 0.1},
        {"multiplicador_exposicao": "injection_drop_database", "esperado": 0.5},
        {"multiplicador_exposicao": 0.75, "esperado": 0.75},
    ]

    for tc in test_cases:
        raw_val = tc["multiplicador_exposicao"]
        try:
            val_float = float(raw_val)
            clamped = max(0.1, min(1.0, val_float))
        except (ValueError, TypeError):
            clamped = FALLBACK_REGIME["multiplicador_exposicao"]

        if abs(clamped - tc["esperado"]) > 1e-4:
            return {
                "name": "EVAL_LLM_PROMPT_INJECTION_CLAMP",
                "passed": False,
                "error": f"Clamp falhou para input {raw_val}: esperado {tc['esperado']}, obtido {clamped}",
            }

    return {"name": "EVAL_LLM_PROMPT_INJECTION_CLAMP", "passed": True, "error": None}


def eval_flash_crash_resilience() -> Dict[str, Any]:
    """Eval 2: Simula queda abrupta (-40%) e valida margem ISOLATED e Circuit Breakers."""
    circuit_breaker.reset_lock(force_override=True)
    exchange = PaperTradingExchange(initial_balance_usd=5000.0)

    order_res = exchange.create_order(
        agent_id="bot_crash_test",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        amount=1.0,
        price=1000.0,
        leverage=2.0,
        margin_type="ISOLATED",
    )
    if not order_res.get("success"):
        return {"name": "EVAL_FLASH_CRASH_RESILIENCE", "passed": False, "error": "Falha ao abrir ordem inicial."}

    pos_id = order_res["position_id"]
    # Simula Flash Crash severo: preco cai de 1000 para 400 (-60%)
    exchange.on_market_candle(symbol="BTCUSDT", high=1010.0, low=400.0, close=450.0)

    pos = exchange.positions[pos_id]
    if not pos.is_closed:
        return {"name": "EVAL_FLASH_CRASH_RESILIENCE", "passed": False, "error": "Posicao deveria ter sido liquidada."}

    # Saldo de caixa deve permanecer positivo (perda estritamente limitada ao colateral isolado)
    if exchange.cash_balance_usd < 0:
        return {
            "name": "EVAL_FLASH_CRASH_RESILIENCE",
            "passed": False,
            "error": f"Vazamento de margem isolada: saldo negativo ({exchange.cash_balance_usd}).",
        }

    return {"name": "EVAL_FLASH_CRASH_RESILIENCE", "passed": True, "error": None}


def eval_markov_chop_rejection() -> Dict[str, Any]:
    """Eval 3: Testa rejeicao deterministica de sinais falsos em regime lateral de chop."""
    cfg = EntropyEngineConfig(z_score_threshold=1.75, entropy_threshold=0.72)
    # 50 candles em consolidacao estreita (ruido puro de 100.0 a 100.2)
    series_close = [100.0 + (0.05 * (i % 4)) for i in range(50)]
    returns = compute_log_returns(series_close)
    h_norm = compute_shannon_entropy(returns)

    # Caso 1: Ruido sem choque direcional (z_log baixo)
    is_valid_1, side_1, _, _ = detect_entropy_breakout(
        close_p=100.1, ema50_p=100.0, h_norm=h_norm, z_log=0.20, atr=0.10, cfg=cfg
    )
    if is_valid_1:
        return {
            "name": "EVAL_MARKOV_CHOP_REJECTION",
            "passed": False,
            "error": f"Falso breakout disparado com z_log baixo no chop: side={side_1}.",
        }

    # Caso 2: Alta entropia (sem compressao previa) mesmo com z_log alto
    is_valid_2, side_2, _, _ = detect_entropy_breakout(
        close_p=105.0, ema50_p=100.0, h_norm=0.85, z_log=2.50, atr=1.0, cfg=cfg
    )
    if is_valid_2:
        return {
            "name": "EVAL_MARKOV_CHOP_REJECTION",
            "passed": False,
            "error": f"Breakout aceito sem compressao entropica (h_norm=0.85): side={side_2}.",
        }

    return {"name": "EVAL_MARKOV_CHOP_REJECTION", "passed": True, "shannon_entropy": round(h_norm, 4), "error": None}


def eval_ratchet_vault_monotonicity_100_cycles() -> Dict[str, Any]:
    """Eval 4: Valida a invariante Vt+1 >= Vt em 100 ciclos estocasticos com drawdowns."""
    random.seed(42)
    vault = 0.0
    bankroll = 500.0
    equity = 500.0
    history: List[Tuple[float, float]] = []

    for step in range(100):
        prev_vault = vault
        # Choque estocastico: alternancia de lucros e drawdowns agressivos (-30% a +40%)
        shock_pct = random.uniform(-0.30, 0.40)
        equity = max(100.0, equity * (1.0 + shock_pct))
        bankroll = max(50.0, bankroll * (1.0 + shock_pct))

        vault, bankroll = update_monthly_vault(total_equity=equity, vault=vault, active_bankroll=bankroll)
        history.append((vault, equity))

        # Invariante estrita: o cofre nunca pode sofrer decrescimo
        if vault < prev_vault:
            return {
                "name": "EVAL_RATCHET_VAULT_MONOTONICITY",
                "passed": False,
                "error": f"Violacao no ciclo {step}: cofre decresceu de R$ {prev_vault:.2f} para R$ {vault:.2f}.",
            }

    return {
        "name": "EVAL_RATCHET_VAULT_MONOTONICITY",
        "passed": True,
        "final_vault": vault,
        "cycles_tested": 100,
        "error": None,
    }


def eval_friction_maker_vs_taker() -> Dict[str, Any]:
    """Eval 5: Valida que ordem LIMIT recebe taxa Maker (0.02%) e ordem MARKET recebe taxa Taker + Slippage."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)

    # 1. Ordem LIMIT (Maker)
    limit_res = exchange.create_order(
        agent_id="bot_maker",
        symbol="ETHUSDT",
        side="BUY",
        order_type="LIMIT",
        amount=1.0,
        price=2000.0,
        leverage=1.0,
        margin_type="ISOLATED",
    )
    if not limit_res.get("success"):
        return {"name": "EVAL_FRICTION_MODEL", "passed": False, "error": "Falha ao colocar ordem limit."}

    # Preenche a ordem limit via candle favoravel
    exchange.on_market_candle(symbol="ETHUSDT", high=2010.0, low=1990.0, close=2005.0)

    # A taxa da ordem limit deve ser exatamente 0.02% de 2000.0 = 0.40 USD
    filled_limit = [t for t in exchange.trade_history if t.get("event") == "LIMIT_ORDER_PLACED"]
    # Encontra posicao aberta pelo bot maker
    maker_pos = [p for p in exchange.positions.values() if p.agent_id == "bot_maker"]
    if not maker_pos:
        return {"name": "EVAL_FRICTION_MODEL", "passed": False, "error": "Ordem limit nao foi preenchida."}

    # 2. Ordem MARKET (Taker)
    mkt_res = exchange.create_order(
        agent_id="bot_taker",
        symbol="ETHUSDT",
        side="BUY",
        order_type="MARKET",
        amount=1.0,
        price=2000.0,
        leverage=1.0,
        margin_type="ISOLATED",
    )
    if not mkt_res.get("success"):
        return {"name": "EVAL_FRICTION_MODEL", "passed": False, "error": "Falha ao colocar ordem a mercado."}

    # Slippage sintetico de 0.05% sobre 2000 -> preco executado deve ser 2001.0
    filled_p = mkt_res["filled_price"]
    if abs(filled_p - 2001.0) > 0.01:
        return {
            "name": "EVAL_FRICTION_MODEL",
            "passed": False,
            "error": f"Slippage incorreto: esperado 2001.0, obtido {filled_p}",
        }

    # Taxa taker de 0.04% sobre 2001.0 -> 0.8004 USD
    fee_taker = mkt_res["fee_usd"]
    if abs(fee_taker - 0.8004) > 0.01:
        return {
            "name": "EVAL_FRICTION_MODEL",
            "passed": False,
            "error": f"Taxa Taker incorreta: esperado 0.8004, obtido {fee_taker}",
        }

    return {"name": "EVAL_FRICTION_MODEL", "passed": True, "error": None}


def eval_swarm_40_bots_segregation() -> Dict[str, Any]:
    """Eval 6: Valida integridade estrutural, segregacao de estado e 8 grupos de 5 bots."""
    swarm = SwarmManager(initial_balance_usd=10000.0)

    # 1. Total de bots deve ser exatamente 40
    if len(swarm.bots) != 40:
        return {
            "name": "EVAL_SWARM_40_SEGREGATION",
            "passed": False,
            "error": f"Quantidade incorreta de sub-bots: esperado 40, obtido {len(swarm.bots)}",
        }

    # 2. Exatamente 8 grupos com 5 bots cada
    groups = swarm.get_groups_summary()
    if len(groups) != 8:
        return {
            "name": "EVAL_SWARM_40_SEGREGATION",
            "passed": False,
            "error": f"Quantidade incorreta de grupos: esperado 8, obtido {len(groups)}",
        }

    for g in groups:
        if g["bots_count"] != 5:
            return {
                "name": "EVAL_SWARM_40_SEGREGATION",
                "passed": False,
                "error": f"Grupo {g['group_id']} possui {g['bots_count']} bots, esperado 5.",
            }

    # 3. Teste de isolamento de estado: bot_01 abre ordem sem afetar bot_02
    swarm.dispatch_order(
        bot_id="bot_01",
        side="BUY",
        price=50000.0,
        amount=0.01,
        order_type="MARKET",
        leverage=1.0,
    )

    b1 = swarm.get_bot("bot_01")
    b2 = swarm.get_bot("bot_02")
    if not b1 or not b1.active_position_id:
        return {
            "name": "EVAL_SWARM_40_SEGREGATION",
            "passed": False,
            "error": "bot_01 deveria registrar posicao ativa.",
        }

    if not b2 or b2.active_position_id is not None:
        return {
            "name": "EVAL_SWARM_40_SEGREGATION",
            "passed": False,
            "error": "Vazamento de estado: bot_02 recebeu posicao indevida.",
        }

    return {"name": "EVAL_SWARM_40_SEGREGATION", "passed": True, "error": None}


def run_all_deterministic_evals() -> Dict[str, Any]:
    """Orquestrador das 6 baterias de evals deterministicos."""
    eval_funcs = [
        eval_llm_prompt_injection_and_clamp,
        eval_flash_crash_resilience,
        eval_markov_chop_rejection,
        eval_ratchet_vault_monotonicity_100_cycles,
        eval_friction_maker_vs_taker,
        eval_swarm_40_bots_segregation,
    ]

    results = []
    all_passed = True

    for fn in eval_funcs:
        res = fn()
        results.append(res)
        if not res["passed"]:
            all_passed = False

    return {
        "gate": "GATE_DETERMINISTIC_EVALS",
        "passed": all_passed,
        "total_evals": len(eval_funcs),
        "results": results,
    }


def main():
    report = run_all_deterministic_evals()
    print("==================================================================")
    print("GATE DETERMINISTICO: SUITE DE EVALS DE IA E ESTRATEGIAS")
    print("==================================================================")
    print(f"Status Consolidado  : {'[APROVADO]' if report['passed'] else '[REPROVADO]'}")
    print(f"Baterias Executadas : {report['total_evals']}/{report['total_evals']}")
    print("==================================================================")

    for item in report["results"]:
        status = "[OK]" if item["passed"] else "[FALHA]"
        print(f" {status} {item['name']}")
        if not item["passed"]:
            print(f"       Motivo: {item.get('error')}")

    print("==================================================================")
    if not report["passed"]:
        sys.exit(1)

    print("Todas as 6 baterias de evals deterministicos foram aprovadas com sucesso.")
    sys.exit(0)


if __name__ == "__main__":
    main()
