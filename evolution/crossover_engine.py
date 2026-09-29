"""
Motor de Recombinação Genética (Crossover e Mutação de AST).
Implementa seleção por torneio entre os melhores indivíduos, permuta de subárvores
e mutações gaussianas de parâmetros numéricos mantendo invariantes de risco.
"""

from __future__ import annotations
import copy
import random
from typing import List, Tuple, Optional

from strategy.ast_engine import (
    ASTNode,
    ConstantNode,
    DataNode,
    IndicatorNode,
    ConditionNode,
    LogicalNode,
    StrategyAST,
    MAX_AST_DEPTH
)
from evolution.fitness_evaluator import PerformanceReport


# Limites seguros de calibracao numerica
MIN_STOP_LOSS_PCT = 0.005   # 0.5%
MAX_STOP_LOSS_PCT = 0.05    # 5.0%
MIN_TAKE_PROFIT_PCT = 0.01  # 1.0%
MAX_TAKE_PROFIT_PCT = 0.15  # 15.0%
MIN_ATR_STOP_MULT = 1.0
MAX_ATR_STOP_MULT = 4.0


# ==============================================================================
# 1. SELEÇÃO DE PAIS POR TORNEIO (TOP 20%)
# ==============================================================================

def select_parents_tournament(
    population: List[Tuple[StrategyAST, PerformanceReport]],
    tournament_size: int = 3
) -> Tuple[StrategyAST, StrategyAST]:
    """Seleciona dois genitores usando selecao por torneio restrita aos melhores."""
    if len(population) < 2:
        raise ValueError("Populacao deve ter ao menos 2 individuos para cruzamento.")

    # Ordena pelo score de aptidao decrescente
    sorted_pop = sorted(population, key=lambda item: item[1].fitness_score, reverse=True)

    # Restringe aos 20% melhores (minimo de 2 individuos)
    top_limit = max(2, int(len(sorted_pop) * 0.20))
    elite_pool = [item[0] for item in sorted_pop[:top_limit]]

    def _pick_one() -> StrategyAST:
        k = min(tournament_size, len(elite_pool))
        candidates = random.sample(elite_pool, k)
        # Retorna o primeiro sorted (pois a lista ja esta ordenada por fitness)
        candidates.sort(key=lambda s: next(p[1].fitness_score for p in sorted_pop if p[0] is s), reverse=True)
        return candidates[0]

    parent_a = _pick_one()
    # Garante genitores distintos se houver mais de 1 no pool
    attempts = 0
    parent_b = _pick_one()
    while parent_b.strategy_id == parent_a.strategy_id and attempts < 5 and len(elite_pool) > 1:
        parent_b = _pick_one()
        attempts += 1

    return parent_a, parent_b


# ==============================================================================
# 2. MUTAÇÃO PARAMÉTRICA GAUSSIANA
# ==============================================================================

def _clamp(val: float, min_v: float, max_v: float) -> float:
    """Aplica delimitador estrito de faixa segura."""
    return max(min_v, min(max_v, val))


def mutate_constant_value(
    val: float,
    mutation_rate: float = 0.08,
    seed: Optional[int] = None
) -> float:
    """Perturba valor numerico atraves de distribuicao normal com seed deterministica opcional."""
    rnd = random.Random(seed) if seed is not None else random
    delta = rnd.gauss(0.0, mutation_rate)
    new_val = val * (1.0 + delta)
    return round(new_val, 4)


def validate_ast_semantics(node: ASTNode) -> bool:
    """Verifica a coerencia semantica para evitar comparacoes invalidas (ex: numerico com booleano)."""
    if isinstance(node, ConditionNode):
        if isinstance(node.right, ConstantNode) and isinstance(node.right.value, bool):
            if node.operator in {"maior", "menor", "maior_igual", "menor_igual"}:
                return False
        return validate_ast_semantics(node.left) and validate_ast_semantics(node.right)
    if isinstance(node, LogicalNode):
        return all(validate_ast_semantics(c) for c in node.children)
    return True


def mutate_ast_constants(node: ASTNode, mutation_rate: float = 0.08) -> ASTNode:
    """Percorre recursivamente a arvore aplicando mutacao gaussiana em constantes numericas."""
    if isinstance(node, ConstantNode):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            mutated_val = mutate_constant_value(float(node.value), mutation_rate)
            return ConstantNode(value=mutated_val)
        return copy.deepcopy(node)

    if isinstance(node, ConditionNode):
        new_left = mutate_ast_constants(node.left, mutation_rate)
        new_right = mutate_ast_constants(node.right, mutation_rate)
        new_extra = mutate_ast_constants(node.extra, mutation_rate) if node.extra else None
        return ConditionNode(
            operator=node.operator,
            left=new_left,
            right=new_right,
            extra=new_extra
        )

    if isinstance(node, LogicalNode):
        new_children = [mutate_ast_constants(c, mutation_rate) for c in node.children]
        return LogicalNode(operator=node.operator, children=new_children)

    return copy.deepcopy(node)


def _mutate_risk_parameters(
    stop_loss: float,
    take_profit: float,
    atr_mult: float,
    rate: float
) -> Tuple[float, float, float]:
    """Aplica mutacao gaussiana e truncamento seguro nos parametros de risco."""
    new_sl = _clamp(mutate_constant_value(stop_loss, rate), MIN_STOP_LOSS_PCT, MAX_STOP_LOSS_PCT)
    new_tp = _clamp(mutate_constant_value(take_profit, rate), MIN_TAKE_PROFIT_PCT, MAX_TAKE_PROFIT_PCT)
    new_atr = _clamp(mutate_constant_value(atr_mult, rate), MIN_ATR_STOP_MULT, MAX_ATR_STOP_MULT)
    return round(new_sl, 4), round(new_tp, 4), round(new_atr, 2)


# ==============================================================================
# 3. CROSSOVER ESTATÍSTICO DE SUBÁRVORES
# ==============================================================================

def _crossover_subtrees(rule_a: ASTNode, rule_b: ASTNode) -> ASTNode:
    """
    Executa crossover entre duas subarvores de regras.
    Se ambos forem nos logicos, combina filhos respeitando profundidade maxima.
    """
    if isinstance(rule_a, LogicalNode) and isinstance(rule_b, LogicalNode):
        # Permuta combinando filhos selecionados
        chosen_children = []
        if rule_a.children:
            chosen_children.append(copy.deepcopy(random.choice(rule_a.children)))
        if rule_b.children:
            chosen_children.append(copy.deepcopy(random.choice(rule_b.children)))

        candidate = LogicalNode(operator=rule_a.operator, children=chosen_children)
        if candidate.depth() <= MAX_AST_DEPTH:
            return candidate

    # Fallback: heranca direta de um dos pais com menor profundidade
    return copy.deepcopy(rule_a if rule_a.depth() <= rule_b.depth() else rule_b)


def recombine_strategies(
    parent_a: StrategyAST,
    parent_b: StrategyAST,
    child_id: str,
    mutation_rate: float = 0.08
) -> StrategyAST:
    """
    Realiza o cruzamento estrutural entre genitores e aplica mutacao gaussiana.
    Garante que o novo individuo respeita todos os limites de profundidade e risco.
    """
    # 1. Heranca estrutural de subarvores (crossover)
    # Por padrao: herda entrada de um e saida de outro, ou cruza subarvores
    if random.random() < 0.5:
        child_entry = _crossover_subtrees(parent_a.entry_rule, parent_b.entry_rule)
        child_exit = copy.deepcopy(parent_b.exit_rule)
    else:
        child_entry = copy.deepcopy(parent_a.entry_rule)
        child_exit = _crossover_subtrees(parent_b.exit_rule, parent_a.exit_rule)

    # 2. Mutacao gaussiana de constantes nas regras
    child_entry = mutate_ast_constants(child_entry, mutation_rate)
    child_exit = mutate_ast_constants(child_exit, mutation_rate)

    # 3. Mutacao nos parametros de risco da estrategia
    base_sl = (parent_a.stop_loss_pct + parent_b.stop_loss_pct) / 2.0
    base_tp = (parent_a.take_profit_pct + parent_b.take_profit_pct) / 2.0
    base_atr = (parent_a.atr_stop_mult + parent_b.atr_stop_mult) / 2.0

    new_sl, new_tp, new_atr = _mutate_risk_parameters(base_sl, base_tp, base_atr, mutation_rate)

    child_name = f"Clone-{child_id[:8]}"
    symbol = parent_a.symbol

    return StrategyAST(
        strategy_id=child_id,
        name=child_name,
        symbol=symbol,
        entry_rule=child_entry,
        exit_rule=child_exit,
        stop_loss_pct=new_sl,
        take_profit_pct=new_tp,
        atr_stop_mult=new_atr
    )
