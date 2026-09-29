"""
Gramática de Regras em Árvore de Sintaxe Abstrata (AST) Tipada.
Execução determinística e hermética sem uso de eval, exec ou importação dinâmica.
Projetado para evolução genética com restrição estrita de segurança e profundidade.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# ==============================================================================
# SEGURANÇA E CONSTANTES INVARIANTES
# ==============================================================================

import re

# ==============================================================================
# SEGURANÇA E CONSTANTES INVARIANTES (ALLOWLISTS E TOKENS PROIBIDOS)
# ==============================================================================

FORBIDDEN_CALL_PATTERN = re.compile(
    r"\b(eval|exec|__import__|os|sys|subprocess|compile|globals|locals|builtins|getattr|setattr|delattr|__builtins__|shutil|socket)\b",
    re.IGNORECASE
)

ALLOWED_DATA_FIELDS = {
    "open", "high", "low", "close", "volume", "quote_volume", "timestamp", "trades",
    "prev_open", "prev_high", "prev_low", "prev_close", "prev_volume"
}

ALLOWED_COMPARISON_OPERATORS = {
    "maior", "menor", "maior_igual", "menor_igual", "igual", "diferente",
    "cruzamento_alta", "cruzamento_baixa", "dentro_canal", "fora_canal"
}

ALLOWED_LOGICAL_OPERATORS = {"AND", "OR", "NOT"}

MAX_AST_DEPTH = 8


class SecurityError(Exception):
    """Excecao levantada quando um token perigoso ou proibido for detectado."""
    pass


class ASTValidationError(Exception):
    """Excecao para falhas de sintaxe, tipos invalidos ou profundidade excessiva."""
    pass


LONG_FORBIDDEN_TOKENS = {
    "eval", "exec", "__import__", "subprocess", "compile",
    "globals", "locals", "builtins", "getattr", "setattr",
    "delattr", "__builtins__", "shutil", "socket"
}

SHORT_FORBIDDEN_PATTERN = re.compile(r"(^|_|\W)(os|sys|open)($|_|\W)", re.IGNORECASE)


def _check_string_safety(text: str) -> None:
    """Verifica se o texto contem tokens proibidos ou caracteres de injecao de codigo."""
    lower_text = text.lower()
    for token in LONG_FORBIDDEN_TOKENS:
        if token in lower_text:
            raise SecurityError(f"Token proibido detectado na AST: {text}")

    if SHORT_FORBIDDEN_PATTERN.search(lower_text):
        raise SecurityError(f"Identificador de sistema proibido detectado na AST: {text}")

    if any(ch in text for ch in ("(", ")", ";", "\n", "\r", "\\")):
        raise SecurityError(f"Caractere proibido detectado na AST: {text}")




# ==============================================================================
# NÓS FUNDAMENTAIS DA AST
# ==============================================================================

class ASTNode:
    """Classe base para todos os nos da arvore sintatica de regras."""

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Executa a avaliacao pura recebendo o estado de mercado."""
        raise NotImplementedError("Subclasses devem implementar evaluate().")

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o no para dicionario seguro e tipado."""
        raise NotImplementedError("Subclasses devem implementar to_dict().")

    def depth(self) -> int:
        """Calcula a profundidade maxima do no."""
        return 1


@dataclass
class ConstantNode(ASTNode):
    """No contendo valor numerico ou literal estatico."""
    value: Union[float, int, bool, str]

    def __post_init__(self):
        if isinstance(self.value, str):
            _check_string_safety(self.value)

    def evaluate(self, context: Dict[str, Any]) -> Any:
        return self.value

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "constant", "value": self.value}


@dataclass
class DataNode(ASTNode):
    """No extrator de variavel de mercado (open, high, low, close, volume)."""
    field_name: str

    def __post_init__(self):
        _check_string_safety(self.field_name)
        if self.field_name not in ALLOWED_DATA_FIELDS:
            raise ASTValidationError(f"Campo de dados nao permitido na AST: {self.field_name}")

    def evaluate(self, context: Dict[str, Any]) -> float:
        val = context.get(self.field_name, 0.0)
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "data", "field_name": self.field_name}


@dataclass
class IndicatorNode(ASTNode):
    """No extrator de indicador tecnico pre-calculado (rsi, ema, atr)."""
    indicator_name: str

    def __post_init__(self):
        _check_string_safety(self.indicator_name)

    def evaluate(self, context: Dict[str, Any]) -> float:
        val = context.get(self.indicator_name, 0.0)
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "indicator", "indicator_name": self.indicator_name}


# ==============================================================================
# NÓS DE CONDIÇÃO E COMPARAÇÃO
# ==============================================================================

def _eval_comparison(op: str, l_val: float, r_val: float) -> bool:
    """Executa comparacoes basicas entre dois valores escalares."""
    if op == "maior":
        return l_val > r_val
    if op == "menor":
        return l_val < r_val
    if op == "maior_igual":
        return l_val >= r_val
    if op == "menor_igual":
        return l_val <= r_val
    if op == "igual":
        return abs(l_val - r_val) < 1e-9
    if op == "diferente":
        return abs(l_val - r_val) >= 1e-9
    return False


def _eval_crossover(op: str, left_node: ASTNode, right_node: ASTNode, context: Dict[str, Any]) -> bool:
    """Avalia condicoes de cruzamento considerando valores anteriores e atuais."""
    curr_l = float(left_node.evaluate(context))
    curr_r = float(right_node.evaluate(context))
    prev_context = context.get("prev_context", {})
    prev_l = float(left_node.evaluate(prev_context)) if prev_context else curr_l
    prev_r = float(right_node.evaluate(prev_context)) if prev_context else curr_r

    if op == "cruzamento_alta":
        return prev_l <= prev_r and curr_l > curr_r
    if op == "cruzamento_baixa":
        return prev_l >= prev_r and curr_l < curr_r
    return False


def _eval_channel(op: str, val: float, lower: float, upper: float) -> bool:
    """Avalia se um valor esta dentro ou fora de uma faixa canal."""
    if op == "dentro_canal":
        return lower <= val <= upper
    if op == "fora_canal":
        return val < lower or val > upper
    return False


@dataclass
class ConditionNode(ASTNode):
    """No de avaliacao de condicao relacional entre nos."""
    operator: str
    left: ASTNode
    right: ASTNode
    extra: Optional[ASTNode] = None

    def __post_init__(self):
        _check_string_safety(self.operator)
        if self.operator not in ALLOWED_COMPARISON_OPERATORS:
            raise ASTValidationError(f"Operador nao autorizado: {self.operator}")

    def evaluate(self, context: Dict[str, Any]) -> bool:
        if self.operator in {"cruzamento_alta", "cruzamento_baixa"}:
            return _eval_crossover(self.operator, self.left, self.right, context)

        l_val = float(self.left.evaluate(context))
        r_val = float(self.right.evaluate(context))

        if self.operator in {"dentro_canal", "fora_canal"}:
            extra_val = float(self.extra.evaluate(context)) if self.extra else r_val
            return _eval_channel(self.operator, l_val, r_val, extra_val)

        return _eval_comparison(self.operator, l_val, r_val)

    def depth(self) -> int:
        child_depths = [self.left.depth(), self.right.depth()]
        if self.extra:
            child_depths.append(self.extra.depth())
        return 1 + max(child_depths)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "type": "condition",
            "operator": self.operator,
            "left": self.left.to_dict(),
            "right": self.right.to_dict()
        }
        if self.extra:
            data["extra"] = self.extra.to_dict()
        return data


# ==============================================================================
# NÓS LÓGICOS BOOLEANOS
# ==============================================================================

@dataclass
class LogicalNode(ASTNode):
    """No logico conector de regras (AND, OR, NOT)."""
    operator: str
    children: List[ASTNode]

    def __post_init__(self):
        _check_string_safety(self.operator)
        op_upper = self.operator.upper()
        if op_upper not in ALLOWED_LOGICAL_OPERATORS:
            raise ASTValidationError(f"Operador logico nao autorizado: {self.operator}")
        self.operator = op_upper
        if self.operator == "NOT" and len(self.children) != 1:
            raise ASTValidationError("Operador NOT exige exatamente 1 filho.")
        if self.operator in {"AND", "OR"} and len(self.children) < 1:
            raise ASTValidationError(f"Operador {self.operator} exige ao menos 1 filho.")

    def evaluate(self, context: Dict[str, Any]) -> bool:
        if self.operator == "NOT":
            return not bool(self.children[0].evaluate(context))
        if self.operator == "AND":
            for child in self.children:
                if not bool(child.evaluate(context)):
                    return False
            return True
        if self.operator == "OR":
            for child in self.children:
                if bool(child.evaluate(context)):
                    return True
            return False
        return False

    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth() for c in self.children)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "logical",
            "operator": self.operator,
            "children": [c.to_dict() for c in self.children]
        }


# ==============================================================================
# PARSER E RECONSTRUTOR SEGURO DE AST
# ==============================================================================

def _parse_leaf_node(node_type: str, data: Dict[str, Any]) -> Optional[ASTNode]:
    """Processa criacao de nos folha (constant, data, indicator)."""
    if node_type == "constant":
        return ConstantNode(value=data["value"])
    if node_type == "data":
        return DataNode(field_name=str(data["field_name"]))
    if node_type == "indicator":
        return IndicatorNode(indicator_name=str(data["indicator_name"]))
    return None


def _parse_composite_node(node_type: str, data: Dict[str, Any], current_depth: int) -> ASTNode:
    """Processa criacao de nos compostos (condition, logical)."""
    if node_type == "condition":
        left_node = node_from_dict(data["left"], current_depth + 1)
        right_node = node_from_dict(data["right"], current_depth + 1)
        extra_node = node_from_dict(data["extra"], current_depth + 1) if "extra" in data else None
        return ConditionNode(
            operator=str(data["operator"]),
            left=left_node,
            right=right_node,
            extra=extra_node
        )
    if node_type == "logical":
        children = [node_from_dict(c, current_depth + 1) for c in data.get("children", [])]
        return LogicalNode(operator=str(data["operator"]), children=children)
    raise ASTValidationError(f"Tipo de no desconhecido: {node_type}")


def node_from_dict(data: Dict[str, Any], current_depth: int = 1) -> ASTNode:
    """Reconstroi de forma tipada e segura um no a partir de um dicionario."""
    if current_depth > MAX_AST_DEPTH:
        raise ASTValidationError(f"Profundidade de AST excedida: {current_depth} > {MAX_AST_DEPTH}")

    if not isinstance(data, dict):
        raise ASTValidationError(f"No invalido, esperado dicionario, recebido: {type(data)}")

    node_type = data.get("type")
    if not node_type or not isinstance(node_type, str):
        raise ASTValidationError("Campo 'type' obrigatorio no no da AST.")

    _check_string_safety(node_type)

    leaf = _parse_leaf_node(node_type, data)
    if leaf is not None:
        return leaf

    return _parse_composite_node(node_type, data, current_depth)



# ==============================================================================
# ESTRATÉGIA INTEGRADA EM AST
# ==============================================================================

@dataclass
class StrategyAST:
    """Representa a estrategia completa com subarvores de entrada e saida."""
    strategy_id: str
    name: str
    symbol: str
    entry_rule: ASTNode
    exit_rule: ASTNode
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    atr_stop_mult: float = 2.0

    def __post_init__(self):
        _check_string_safety(self.strategy_id)
        _check_string_safety(self.name)
        _check_string_safety(self.symbol)
        if self.entry_rule.depth() > MAX_AST_DEPTH:
            raise ASTValidationError(f"Subarvore de entrada excede profundidade maxima de {MAX_AST_DEPTH}")
        if self.exit_rule.depth() > MAX_AST_DEPTH:
            raise ASTValidationError(f"Subarvore de saida excede profundidade maxima de {MAX_AST_DEPTH}")

    def evaluate_signals(self, market_state: Dict[str, Any], has_open_position: bool = False) -> str:
        """Determina o sinal gerado (BUY, SELL, HOLD) para o estado de mercado atual."""
        if has_open_position:
            should_exit = bool(self.exit_rule.evaluate(market_state))
            if should_exit:
                return "SELL"
            return "HOLD"
        else:
            should_enter = bool(self.entry_rule.evaluate(market_state))
            if should_enter:
                return "BUY"
            return "HOLD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "symbol": self.symbol,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "atr_stop_mult": self.atr_stop_mult,
            "entry_rule": self.entry_rule.to_dict(),
            "exit_rule": self.exit_rule.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyAST:
        return cls(
            strategy_id=str(data["strategy_id"]),
            name=str(data["name"]),
            symbol=str(data["symbol"]),
            stop_loss_pct=float(data.get("stop_loss_pct", 0.02)),
            take_profit_pct=float(data.get("take_profit_pct", 0.04)),
            atr_stop_mult=float(data.get("atr_stop_mult", 2.0)),
            entry_rule=node_from_dict(data["entry_rule"]),
            exit_rule=node_from_dict(data["exit_rule"])
        )
