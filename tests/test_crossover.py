"""
Suíte de Testes do Motor Genético de Recombinação e Mutação (Fase 4).
Valida seleção por torneio, crossover estrutural de subárvores e mutações gaussianas com clamping.
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
    StrategyAST,
    MAX_AST_DEPTH
)
from evolution.fitness_evaluator import PerformanceReport
from evolution.crossover_engine import (
    select_parents_tournament,
    mutate_constant_value,
    mutate_ast_constants,
    recombine_strategies,
    MIN_STOP_LOSS_PCT,
    MAX_STOP_LOSS_PCT,
    MIN_TAKE_PROFIT_PCT,
    MAX_TAKE_PROFIT_PCT,
    MIN_ATR_STOP_MULT,
    MAX_ATR_STOP_MULT
)


def _build_dummy_report(fitness: float) -> PerformanceReport:
    """Gera um relatorio ficticio com score de fitness especifico."""
    return PerformanceReport(
        total_trades=50,
        winning_trades=30,
        losing_trades=20,
        win_rate=0.6,
        profit_factor=2.0,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        calmar_ratio=1.2,
        max_drawdown=3.0,
        total_return_pct=15.0,
        fitness_score=fitness,
        passed_graduation=True
    )


def test_tournament_selection_top_20():
    """Valida que o torneio seleciona genitores apenas do grupo elite (top 20%)."""
    # Cria populacao de 10 agentes com fitness de 0.1 a 1.0
    population = []
    for i in range(1, 11):
        strat = StrategyAST(
            strategy_id=f"strat_{i}",
            name=f"Agent {i}",
            symbol="BTC/USDT",
            entry_rule=ConditionNode("maior", DataNode("close"), ConstantNode(100.0)),
            exit_rule=ConditionNode("menor", DataNode("close"), ConstantNode(90.0))
        )
        report = _build_dummy_report(fitness=i / 10.0)
        population.append((strat, report))

    # Top 20% de 10 agentes sao os 2 melhores: strat_10 (fitness 1.0) e strat_9 (fitness 0.9)
    p_a, p_b = select_parents_tournament(population, tournament_size=3)
    assert p_a.strategy_id in {"strat_10", "strat_9"}
    assert p_b.strategy_id in {"strat_10", "strat_9"}


def test_gaussian_mutation_and_clamping():
    """Valida mutacao gaussiana e limites de truncamento seguros."""
    # Testa clamping de stop loss
    for _ in range(50):
        mut_val = mutate_constant_value(0.02, mutation_rate=0.10)
        assert mut_val > 0.0

    # Testa mutacao de constantes na AST
    cond = ConditionNode("menor", IndicatorNode("rsi_14"), ConstantNode(30.0))
    mut_cond = mutate_ast_constants(cond, mutation_rate=0.10)
    assert isinstance(mut_cond, ConditionNode)
    # Valor da constante deve ter sofrido mutacao leve
    assert isinstance(mut_cond.right, ConstantNode)
    assert 20.0 <= float(mut_cond.right.value) <= 40.0


def test_recombine_strategies_generates_valid_child():
    """Valida recombinacao gerando filho valido e funcional."""
    parent_a = StrategyAST(
        strategy_id="parent_rsi",
        name="Parent RSI",
        symbol="ETH/USDT",
        entry_rule=LogicalNode("AND", [
            ConditionNode("menor", IndicatorNode("rsi_14"), ConstantNode(30.0)),
            ConditionNode("maior", DataNode("close"), ConstantNode(3000.0))
        ]),
        exit_rule=ConditionNode("maior", IndicatorNode("rsi_14"), ConstantNode(70.0)),
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        atr_stop_mult=2.0
    )

    parent_b = StrategyAST(
        strategy_id="parent_ema",
        name="Parent EMA",
        symbol="ETH/USDT",
        entry_rule=LogicalNode("AND", [
            ConditionNode("cruzamento_alta", IndicatorNode("ema_20"), IndicatorNode("ema_50")),
            ConditionNode("maior", DataNode("volume"), ConstantNode(1000.0))
        ]),
        exit_rule=ConditionNode("menor", DataNode("close"), IndicatorNode("ema_50")),
        stop_loss_pct=0.03,
        take_profit_pct=0.06,
        atr_stop_mult=2.5
    )

    child = recombine_strategies(parent_a, parent_b, child_id="clone_001_gen1", mutation_rate=0.08)

    assert child.strategy_id == "clone_001_gen1"
    assert child.symbol == "ETH/USDT"
    assert MIN_STOP_LOSS_PCT <= child.stop_loss_pct <= MAX_STOP_LOSS_PCT
    assert MIN_TAKE_PROFIT_PCT <= child.take_profit_pct <= MAX_TAKE_PROFIT_PCT
    assert MIN_ATR_STOP_MULT <= child.atr_stop_mult <= MAX_ATR_STOP_MULT
    assert child.entry_rule.depth() <= MAX_AST_DEPTH
    assert child.exit_rule.depth() <= MAX_AST_DEPTH

    # Valida avaliacao sem excecoes
    market_context = {
        "close": 3100.0,
        "volume": 1500.0,
        "rsi_14": 25.0,
        "ema_20": 3050.0,
        "ema_50": 3020.0,
        "prev_context": {"ema_20": 3010.0, "ema_50": 3015.0}
    }
    signal = child.evaluate_signals(market_context, has_open_position=False)
    assert signal in {"BUY", "HOLD", "SELL"}


def test_genetic_diversity_multiple_children():
    """Valida que filhos gerados possuem variabilidade estocastica (diversidade genetica)."""
    parent_a = StrategyAST(
        strategy_id="p1",
        name="P1",
        symbol="SOL/USDT",
        entry_rule=ConditionNode("maior", DataNode("close"), ConstantNode(150.0)),
        exit_rule=ConditionNode("menor", DataNode("close"), ConstantNode(140.0)),
        stop_loss_pct=0.02,
        take_profit_pct=0.04
    )
    parent_b = StrategyAST(
        strategy_id="p2",
        name="P2",
        symbol="SOL/USDT",
        entry_rule=ConditionNode("menor", IndicatorNode("rsi_14"), ConstantNode(35.0)),
        exit_rule=ConditionNode("maior", IndicatorNode("rsi_14"), ConstantNode(65.0)),
        stop_loss_pct=0.025,
        take_profit_pct=0.05
    )

    children_sl = set()
    for i in range(10):
        child = recombine_strategies(parent_a, parent_b, child_id=f"c_{i}", mutation_rate=0.10)
        children_sl.add(child.stop_loss_pct)

    # Devido a mutacao gaussiana, deve haver diversidade de valores de stop loss
    assert len(children_sl) >= 3, "Mutacao gaussiana deve gerar diversidade genetica entre clones"


if __name__ == "__main__":
    test_tournament_selection_top_20()
    test_gaussian_mutation_and_clamping()
    test_recombine_strategies_generates_valid_child()
    test_genetic_diversity_multiple_children()
    print("SUÍTE DE TESTES DE RECOMBINAÇÃO GENÉTICA APROVADA COM SUCESSO (4/4 TESTES PASSARAM).")
