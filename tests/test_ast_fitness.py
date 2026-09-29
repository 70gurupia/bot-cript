"""
Suíte de Testes da Gramática AST e Avaliador de Aptidão Estatística (Fase 3).
Valida hermeticidade sem eval/exec, cálculos estatísticos e critérios de graduação.
"""

import math
import sys
import os

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.ast_engine import (
    ASTNode,
    ConstantNode,
    DataNode,
    IndicatorNode,
    ConditionNode,
    LogicalNode,
    StrategyAST,
    SecurityError,
    ASTValidationError,
    node_from_dict
)
from evolution.fitness_evaluator import (
    TradeRecord,
    PerformanceReport,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_calmar_ratio,
    calculate_profit_factor,
    calculate_win_rate,
    calculate_fitness_score,
    evaluate_strategy_performance
)


# ==============================================================================
# TESTES DE SEGURANÇA E NÓS DA AST
# ==============================================================================

def test_ast_security_blocking():
    """Valida bloqueio de tokens perigosos em nos folha e nos compostos."""
    try:
        ConstantNode(value="eval('1+1')")
        assert False, "Deveria ter bloqueado token eval"
    except SecurityError:
        pass

    try:
        DataNode(field_name="__import__('os').system('ls')")
        assert False, "Deveria ter bloqueado token __import__"
    except SecurityError:
        pass

    try:
        IndicatorNode(indicator_name="subprocess_call")
        assert False, "Deveria ter bloqueado token subprocess"
    except SecurityError:
        pass


def test_ast_evaluation_conditions():
    """Testa comparadores basicos, canais e cruzamentos."""
    context = {
        "close": 50000.0,
        "ema_20": 49500.0,
        "ema_50": 48000.0,
        "rsi_14": 28.5,
        "prev_context": {
            "close": 49000.0,
            "ema_20": 48500.0,
            "ema_50": 48600.0,
            "rsi_14": 31.0
        }
    }

    # Condicao 1: close > ema_20
    cond_gt = ConditionNode(
        operator="maior",
        left=DataNode("close"),
        right=IndicatorNode("ema_20")
    )
    assert cond_gt.evaluate(context) is True

    # Condicao 2: rsi dentro do canal [20, 30]
    cond_channel = ConditionNode(
        operator="dentro_canal",
        left=IndicatorNode("rsi_14"),
        right=ConstantNode(20.0),
        extra=ConstantNode(30.0)
    )
    assert cond_channel.evaluate(context) is True

    # Condicao 3: cruzamento de alta ema_20 cruzando para cima da ema_50
    # No anterior: ema_20 (48500) <= ema_50 (48600)
    # No atual: ema_20 (49500) > ema_50 (48000) -> Cruzamento de alta ocorreu
    cond_cross = ConditionNode(
        operator="cruzamento_alta",
        left=IndicatorNode("ema_20"),
        right=IndicatorNode("ema_50")
    )
    assert cond_cross.evaluate(context) is True


def test_ast_logical_and_depth():
    """Testa conectivos logicos e enforcing de profundidade maxima."""
    c1 = ConditionNode(operator="maior", left=ConstantNode(10), right=ConstantNode(5))
    c2 = ConditionNode(operator="menor", left=ConstantNode(2), right=ConstantNode(8))

    and_node = LogicalNode(operator="AND", children=[c1, c2])
    assert and_node.evaluate({}) is True

    not_node = LogicalNode(operator="NOT", children=[and_node])
    assert not_node.evaluate({}) is False

    # Valida profundidade
    assert and_node.depth() == 3


def test_strategy_ast_serialization_roundtrip():
    """Valida serializacao e desserializacao de uma estrategia completa em AST."""
    entry_rule = LogicalNode(
        operator="AND",
        children=[
            ConditionNode(operator="menor", left=IndicatorNode("rsi_14"), right=ConstantNode(30.0)),
            ConditionNode(operator="maior", left=DataNode("close"), right=IndicatorNode("ema_200"))
        ]
    )
    exit_rule = ConditionNode(
        operator="maior",
        left=IndicatorNode("rsi_14"),
        right=ConstantNode(70.0)
    )

    strat = StrategyAST(
        strategy_id="strat_test_001",
        name="RSI Oversold Momentum",
        symbol="BTC/USDT",
        entry_rule=entry_rule,
        exit_rule=exit_rule,
        stop_loss_pct=0.02,
        take_profit_pct=0.05
    )

    data = strat.to_dict()
    restored = StrategyAST.from_dict(data)

    assert restored.strategy_id == "strat_test_001"
    assert restored.name == "RSI Oversold Momentum"
    assert restored.symbol == "BTC/USDT"
    assert restored.stop_loss_pct == 0.02

    # Teste de emissao de sinal
    buy_state = {"close": 60000.0, "ema_200": 55000.0, "rsi_14": 25.0}
    assert restored.evaluate_signals(buy_state, has_open_position=False) == "BUY"
    assert restored.evaluate_signals(buy_state, has_open_position=True) == "HOLD"

    sell_state = {"close": 60000.0, "ema_200": 55000.0, "rsi_14": 75.0}
    assert restored.evaluate_signals(sell_state, has_open_position=True) == "SELL"


# ==============================================================================
# TESTES DO AVALIADOR DE APTIDÃO (FITNESS EVALUATOR)
# ==============================================================================

def test_fitness_metrics_accuracy():
    """Valida calculos de Sharpe, Sortino, Drawdown e Profit Factor."""
    # Retornos horarios constantes positivos
    returns = [0.001, 0.0015, 0.0008, 0.0012, 0.0011, 0.0009]
    sharpe = calculate_sharpe_ratio(returns)
    assert sharpe > 0.0

    # Sortino sem desvios negativos deve ser zero ou muito alto
    sortino = calculate_sortino_ratio(returns)
    assert sortino == 0.0  # Nao ha variancia negativa abaixo do target 0.0

    # Retornos mistos
    mixed_returns = [0.01, -0.005, 0.015, -0.008, 0.02, -0.002]
    mixed_sortino = calculate_sortino_ratio(mixed_returns)
    assert mixed_sortino > 0.0

    # Max Drawdown
    equity = [1000.0, 1050.0, 1100.0, 990.0, 1020.0, 1200.0]
    # Pico 1100 -> vale 990 = queda de 110 / 1100 = 10.0%
    dd = calculate_max_drawdown(equity)
    assert math.isclose(dd, 10.0, rel_tol=1e-5)


def test_profit_factor_and_win_rate():
    """Valida calculo de Win Rate e Profit Factor com taxas de corretagem."""
    trades = [
        TradeRecord(1, 2, 100, 105, "BUY", 1.0, pnl_abs=5.0, pnl_pct=0.05, fee_paid=0.5),   # Net +4.5
        TradeRecord(3, 4, 105, 102, "BUY", 1.0, pnl_abs=-3.0, pnl_pct=-0.03, fee_paid=0.5), # Net -3.5
        TradeRecord(5, 6, 102, 108, "BUY", 1.0, pnl_abs=6.0, pnl_pct=0.06, fee_paid=0.5),   # Net +5.5
    ]
    # Gross profit = 4.5 + 5.5 = 10.0
    # Gross loss = 3.5
    # Profit factor = 10.0 / 3.5 = 2.8571
    pf = calculate_profit_factor(trades)
    assert math.isclose(pf, 10.0 / 3.5, rel_tol=1e-4)

    # Win rate = 2 / 3 = 0.6666
    wr = calculate_win_rate(trades)
    assert math.isclose(wr, 2.0 / 3.0, rel_tol=1e-4)


def test_fitness_score_cutoff_at_8_percent_drawdown():
    """Valida a regra invariante que zera o fitness para rebaixamento superior a 8%."""
    # Cenário com Sharpe alto mas Drawdown de 8.5%
    score_zero = calculate_fitness_score(sharpe=2.5, sortino=3.0, max_drawdown=8.5, profit_factor=2.0)
    assert score_zero == 0.0, f"Fitness deveria ser zero com DD > 8%, obtido: {score_zero}"

    # Cenário com Drawdown seguro de 3.0%
    score_safe = calculate_fitness_score(sharpe=2.0, sortino=2.5, max_drawdown=3.0, profit_factor=2.0)
    assert score_safe > 0.0, "Fitness deveria ser positivo para DD seguro"
    assert 0.0 <= score_safe <= 1.0, "Fitness deve estar estritamente normalizado entre 0 e 1"


def test_graduation_criteria_in_incubator():
    """Valida que apenas agentes que cumpram todos os 3 criterios graduam."""
    # Agente A: Aprovado (35 trades, Sharpe alto > 1.25, DD baixo <= 4.5%)
    trades_35 = [TradeRecord(i, i+1, 100, 102, "BUY", 1.0, 2.0, 0.02, 0.1) for i in range(35)]
    returns = [0.003 + (i % 5) * 0.001 for i in range(100)]
    equity = [100.0 + i * 0.5 for i in range(100)]
    report_a = evaluate_strategy_performance(trades_35, returns, equity)
    assert report_a.passed_graduation is True


    # Agente B: Reprovado por poucos trades (25 trades, Sharpe 2.0, DD 2.0%)
    trades_25 = [TradeRecord(i, i+1, 100, 102, "BUY", 1.0, 2.0, 0.02, 0.1) for i in range(25)]
    report_b = evaluate_strategy_performance(trades_25, returns, equity)
    assert report_b.passed_graduation is False

    # Agente C: Reprovado por Drawdown alto (35 trades, Sharpe 2.0, DD 5.5% > 4.5%)
    equity_bad = [100.0, 120.0, 112.0, 130.0]  # Queda de (120 - 112)/120 = 6.66%
    report_c = evaluate_strategy_performance(trades_35, returns, equity_bad)
    assert report_c.passed_graduation is False


if __name__ == "__main__":
    test_ast_security_blocking()
    test_ast_evaluation_conditions()
    test_ast_logical_and_depth()
    test_strategy_ast_serialization_roundtrip()
    test_fitness_metrics_accuracy()
    test_profit_factor_and_win_rate()
    test_fitness_score_cutoff_at_8_percent_drawdown()
    test_graduation_criteria_in_incubator()
    print("SUÍTE DE TESTES AST E FITNESS APROVADA COM SUCESSO (8/8 TESTES PASSARAM).")
