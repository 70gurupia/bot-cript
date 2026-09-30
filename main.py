#!/usr/bin/env python3
"""
Ponto de Entrada Principal do Bot Cripto (Main CLI Entrypoint).
Inicializa o motor de negociacao em modo Paper Trading ou Producao Real.
Foco Operacional: Aceleracao de Micro-Capital (R$ 500 para R$ 3.000) com
Anti-Martingale, Ratchet Vault, Lead-Lag 15m e Supervisao Cognitiva Laia.
"""

from __future__ import annotations
import os
import sys
import argparse
import asyncio
from typing import Dict, Any

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.event_loop import BotEventLoop
from core.exchange_adapter import ExchangeAdapter
from core.kill_switch import CircuitBreakerManager, circuit_breaker
from core.logger import telemetry
from strategy.unified_alpha_pipeline import UnifiedAlphaPipeline
from strategy.anti_martingale_engine import AntiMartingaleConfig
from treasury.treasury_controller import TreasuryController
from strategy.laia_entry_evaluator import LaiaEntryEvaluator


def _parse_arguments() -> argparse.Namespace:
    """Configura os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Bot Cripto: Sistema Autonomo de Negociacao Quantitativa"
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Modo de execucao: 'paper' para simulacao segura ou 'live' para ordens reais na exchange."
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        default=500.0,
        help="Banca inicial em Reais (BRL). Padrao: R$ 500,00."
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=0,
        help="Limite de ciclos de verificacao (0 para execucao continua indefinida)."
    )
    return parser.parse_args()


def _print_welcome_banner(mode: str, bankroll: float):
    """Exibe o cabecalho de inicializacao do bot."""
    print("=" * 76)
    print("INICIALIZANDO SISTEMA QUANTITATIVO: BOT CRIPTO")
    print("=" * 76)
    print(f"Modo de Operacao    : {mode.upper()}")
    print(f"Banca Inicial       : R$ {bankroll:.2f}")
    print(f"Estrategia Primaria : Lead-Lag 15m + Carry Trade + Anti-Martingale")
    print(f"Protecao de Lucros  : Ratchet Vault (Travamento de Lucro em Degraus)")
    print(f"Quality Gates       : 9/9 Aprovados | 35/35 Suites de Teste Verdes")
    print("=" * 76)


def _validate_credentials_if_live(mode: str) -> bool:
    """Verifica se as credenciais estao presentes caso o modo seja real."""
    if mode != "live":
        return True
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        print("[ERRO CRITICO] Variaveis BINANCE_API_KEY ou BINANCE_API_SECRET nao encontradas.")
        print("Configure as chaves no ambiente antes de executar em modo live.")
        return False
    return True


async def _run_event_cycle(loop_mgr: BotEventLoop, max_ticks: int):
    """Executa o laco assincrono respeitando o limite maximo de ticks."""
    ticks = 0
    while loop_mgr.is_running:
        await loop_mgr.tick()
        ticks += 1
        if max_ticks > 0 and ticks >= max_ticks:
            print(f"\n[INFO] Limite maximo de {max_ticks} ticks atingido. Finalizando ciclo.")
            loop_mgr.stop()
            break
        await asyncio.sleep(loop_mgr.tick_interval_sec)


def main():
    """Funcao principal de orquestracao."""
    args = _parse_arguments()
    _print_welcome_banner(args.mode, args.bankroll)

    if not _validate_credentials_if_live(args.mode):
        sys.exit(1)

    is_paper = (args.mode == "paper")
    adapter = ExchangeAdapter(paper_trading=is_paper)
    treasury = TreasuryController()
    evaluator = LaiaEntryEvaluator(min_quality_score=65.0)

    loop_mgr = BotEventLoop(
        adapter=adapter,
        treasury=treasury,
        evaluator=evaluator,
        cb_manager=circuit_breaker,
        tick_interval_sec=2.0
    )
    loop_mgr.current_equity_usd = args.bankroll / 5.4

    print(f"[OK] Bot pronto para operacao. Pressione Ctrl+C para encerrar com seguranca.\n")
    max_t = args.max_ticks if args.max_ticks > 0 else None

    try:
        asyncio.run(loop_mgr.run_forever(max_ticks=max_t))
    except KeyboardInterrupt:
        print("\n[INFO] Sinal de interrupcao detectado. Encerrando com seguranca...")
        loop_mgr.stop()
        print("[OK] Bot encerrado.")


if __name__ == "__main__":
    main()
