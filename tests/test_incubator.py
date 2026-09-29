"""
Suíte de Testes da Incubadora em Paper Trading e Ciclo Probatório (Fase 4).
Valida admissão em quarentena, processamento de candles com taxas, critérios de graduação e eliminação.
"""

import sys
import os

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.ast_engine import (
    ConstantNode,
    DataNode,
    IndicatorNode,
    ConditionNode,
    LogicalNode,
    StrategyAST
)
from evolution.incubator_manager import IncubatorManager, CandidateAgent


import uuid

def _create_sample_strategy(strat_id: str, symbol: str = "BTC/USDT") -> StrategyAST:
    """Cria estrategia simples de teste com ID unico."""
    unique_id = f"{strat_id}_{uuid.uuid4().hex[:6]}"
    return StrategyAST(
        strategy_id=unique_id,
        name=f"Test Strat {unique_id}",
        symbol=symbol,
        entry_rule=ConditionNode("maior", DataNode("close"), ConstantNode(50000.0)),
        exit_rule=ConditionNode("menor", DataNode("close"), ConstantNode(49000.0)),
        stop_loss_pct=0.02,
        take_profit_pct=0.04
    )



def test_incubator_admission_and_capacity():
    """Valida admissao de candidatos e respeito ao teto maximo de clones em quarentena."""
    incubator = IncubatorManager(initial_balance_usd=5000.0, max_clones_in_quarantine=3)

    s1 = _create_sample_strategy("strat_1")
    s2 = _create_sample_strategy("strat_2")
    s3 = _create_sample_strategy("strat_3")
    s4 = _create_sample_strategy("strat_4")

    c1 = incubator.admit_strategy(s1)
    c2 = incubator.admit_strategy(s2)
    c3 = incubator.admit_strategy(s3)

    assert len(incubator.get_quarantine_candidates()) == 3
    assert c1.paper_exchange.cash_balance_usd == 5000.0

    # Tenta admitir o quarto candidato acima da capacidade
    try:
        incubator.admit_strategy(s4)
        assert False, "Deveria ter bloqueado admissao por exceder capacidade"
    except ValueError as e:
        assert "Capacidade maxima da incubadora atingida" in str(e)


def test_quarantine_execution_and_elimination():
    """Valida que queda brusca de mercado elimina o candidato por violar teto de drawdown de 8%."""
    incubator = IncubatorManager(
        initial_balance_usd=10000.0,
        rejection_drawdown_limit=1.0
    )

    strat = _create_sample_strategy("bad_strat", symbol="ETH/USDT")
    # Regra de stop loss permissiva para permitir drawdown
    strat.stop_loss_pct = 0.20
    candidate = incubator.admit_strategy(strat)

    # 1. Vela de entrada (preco acima de 50.000)
    candle_buy = {"close": 51000.0, "high": 51500.0, "low": 50500.0, "open": 50000.0, "volume": 100.0}
    incubator.process_candle("ETH/USDT", candle_buy)

    assert candidate.last_position_id is not None
    assert candidate.status == "QUARANTINE"

    # 2. Despenco de mercado que causa queda de mais de 10% no saldo
    candle_crash = {"close": 44000.0, "high": 45000.0, "low": 43500.0, "open": 51000.0, "volume": 500.0}
    incubator.process_candle("ETH/USDT", candle_crash)

    # O candidato deve ter sido eliminado
    assert candidate.status == "ELIMINATED"
    assert "Drawdown maximo" in candidate.elimination_reason
    assert len(incubator.get_eliminated_candidates()) == 1


def test_quarantine_graduation_cycle():
    """Valida o ciclo completo de quarentena com graduacao para candidato de alta performance."""
    incubator = IncubatorManager(
        initial_balance_usd=10000.0,
        min_quarantine_trades=30,
        min_graduation_sharpe=1.25,
        max_graduation_drawdown=4.5
    )
    strat = _create_sample_strategy("winner_strat", symbol="BTC/USDT")
    strat.stop_loss_pct = 0.01
    strat.take_profit_pct = 0.02
    candidate = incubator.admit_strategy(strat)

    base_price = 50000.0
    # Simula 35 ciclos consecutivos de entrada lucrativa e realizacao de lucro (TP atingido)
    for i in range(35):
        # Vela de compra: preco 50100 -> dispara compra
        entry_price = base_price + 100.0 + (i * 10)
        c_entry = {"close": entry_price, "high": entry_price + 50, "low": entry_price - 50, "open": entry_price - 20, "volume": 100.0}
        incubator.process_candle("BTC/USDT", c_entry)

        # Vela de saida lucrativa (+2.5% de alta -> atinge take profit de 2%)
        exit_price = entry_price * 1.025
        c_exit = {"close": exit_price, "high": exit_price + 50, "low": exit_price - 50, "open": entry_price, "volume": 120.0}
        incubator.process_candle("BTC/USDT", c_exit)

    # Apos 35 operacoes lucrativas consistentes, deve estar graduado
    assert len(candidate.trades) >= 30
    assert candidate.status == "GRADUATED"
    assert candidate.graduation_report is not None
    assert candidate.graduation_report.passed_graduation is True
    assert len(incubator.get_graduated_candidates()) == 1


if __name__ == "__main__":
    test_incubator_admission_and_capacity()
    test_quarantine_execution_and_elimination()
    test_quarantine_graduation_cycle()
    print("SUÍTE DE TESTES DA INCUBADORA APROVADA COM SUCESSO (3/3 TESTES PASSARAM).")
