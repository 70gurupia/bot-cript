"""
Suíte de Testes Atômicos e Invariantes Algébricas (TDD).
Testa matemática de risco (Kelly, Sharpe, Drawdown) e segurança da AST contra RCE.
Executável via pytest ou python3 nativo.
"""

import math
try:
    import pytest
except ImportError:
    class _PytestMock:
        @staticmethod
        def raises(expected_exception, match=None):
            class _Context:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    if exc_type is None:
                        raise AssertionError(f"Excecao esperada {expected_exception.__name__} nao foi levantada.")
                    return issubclass(exc_type, expected_exception)
            return _Context()
    pytest = _PytestMock()


# ==============================================================================
# 1. FUNÇÕES PURAS DE MATEMÁTICA E INVARIANTES DE RISCO
# ==============================================================================

def calculate_fractional_kelly(win_rate: float, win_loss_ratio: float, fraction: float = 0.25) -> float:
    """Calcula o dimensionamento fracionario pelo Criterio de Kelly com teto seguro."""
    if win_loss_ratio <= 0 or win_rate <= 0 or win_rate >= 1.0:
        return 0.0
    p = win_rate
    q = 1.0 - p
    b = win_loss_ratio
    kelly_full = (p * b - q) / b
    if kelly_full <= 0:
        return 0.0
    # Impõe teto estrito de no maximo 25% de Kelly (fator de seguranca contra ruina)
    return min(fraction, kelly_full * fraction)


def calculate_sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Calcula o Sharpe Ratio anualizado a partir de retornos horarios."""
    if not returns or len(returns) < 2:
        return 0.0
    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance)
    if std_dev == 0.0:
        return 0.0
    # Anualizacao para dados de 1h (sqrt(365 * 24))
    annualization_factor = math.sqrt(365 * 24)
    return ((mean_ret - risk_free_rate) / std_dev) * annualization_factor


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    """Calcula a queda maxima de pico a vale (Max Drawdown percentual)."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd * 100.0


# ==============================================================================
# 2. VALIDADOR DE SEGURANÇA DA AST (PREVENÇÃO DE RCE)
# ==============================================================================

FORBIDDEN_TOKENS = {
    "eval", "exec", "__import__", "os", "sys", "subprocess",
    "open", "compile", "globals", "locals", "builtins", "getattr"
}

ALLOWED_OPERATORS = {
    "maior", "menor", "maior_igual", "menor_igual",
    "cruzamento_alta", "cruzamento_baixa", "dentro_canal"
}


def _check_string_tokens(val: str):
    """Verifica presenca de tokens proibidos em strings da AST."""
    lower_val = val.lower()
    for token in FORBIDDEN_TOKENS:
        if token in lower_val:
            raise SecurityError(f"Token perigoso detectado na AST: {val}")


def validate_rule_ast(node: dict, current_depth: int = 1, max_depth: int = 8) -> bool:
    """Valida que uma arvore de regras nao contem tokens proibidos e respeita a profundidade maxima."""
    if current_depth > max_depth:
        raise ValueError(f"Profundidade de AST excedida: {current_depth} > {max_depth}")
        
    operator = node.get("operador")
    if operator and operator not in ALLOWED_OPERATORS:
        raise ValueError(f"Operador nao autorizado na AST: {operator}")
        
    for val in node.values():
        if isinstance(val, str):
            _check_string_tokens(val)
        elif isinstance(val, dict):
            validate_rule_ast(val, current_depth + 1, max_depth)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    validate_rule_ast(item, current_depth + 1, max_depth)
    return True


# ==============================================================================
# 3. CASOS DE TESTE ATÔMICOS (PYTEST / ASSERTIONS)
# ==============================================================================

def test_fractional_kelly_invariant():
    """Valida que o Kelly Fracionario nunca excede o teto de seguranca de 0.25."""
    # Cenário hiper-lucrativo (99% de acerto e 10x de payoff)
    size = calculate_fractional_kelly(win_rate=0.99, win_loss_ratio=10.0, fraction=0.25)
    assert size <= 0.25, "Kelly fracionario ultrapassou o teto maximo permitido"
    assert size > 0.0, "Kelly deveria ser positivo para cenario lucrativo"

    # Cenário de expectativa matematica negativa (30% de acerto e 1:1)
    size_neg = calculate_fractional_kelly(win_rate=0.30, win_loss_ratio=1.0, fraction=0.25)
    assert size_neg == 0.0, "Kelly deve ser zero quando a expectativa for negativa"


def test_max_drawdown_calculation():
    """Valida a precisao do calculo de drawdown historico."""
    equity = [100.0, 110.0, 120.0, 90.0, 95.0, 60.0, 80.0, 130.0]
    # Pico maximo foi 120.0, vale mais profundo foi 60.0 -> queda de 50.0%
    dd = calculate_max_drawdown(equity)
    assert math.isclose(dd, 50.0, rel_tol=1e-5), f"Drawdown esperado 50.0%, obtido {dd}%"


def test_sharpe_ratio_invariants():
    """Valida retornos constantes (volatilidade zero) e retornos simetricos."""
    constant_returns = [0.01, 0.01, 0.01, 0.01]
    assert calculate_sharpe_ratio(constant_returns) == 0.0, "Volatilidade zero deve retornar Sharpe 0.0"

    positive_returns = [0.02, 0.01, 0.03, 0.02, 0.01, 0.02]
    assert calculate_sharpe_ratio(positive_returns) > 0.0, "Serie lucrativa consistente deve ter Sharpe positivo"


def test_ast_rce_security_blocking():
    """Valida que tentativas de injecao de codigo arbitrario sao bloqueadas pelo validador da AST."""
    malicious_ast = {
        "operador": "cruzamento_alta",
        "expressao": "__import__('os').system('touch /tmp/hacked')",
        "filhos": []
    }
    with pytest.raises(SecurityError):
        validate_rule_ast(malicious_ast)


def test_ast_depth_limit_blocking():
    """Valida que arvores recursivas profundas sao bloqueadas contra estouro de pilha."""
    deep_ast = {"operador": "cruzamento_alta"}
    current = deep_ast
    for _ in range(12):
        child = {"operador": "cruzamento_alta"}
        current["filho"] = child
        current = child

    with pytest.raises(ValueError, match="Profundidade de AST excedida"):
        validate_rule_ast(deep_ast)


class SecurityError(Exception):
    pass


if __name__ == "__main__":
    test_fractional_kelly_invariant()
    test_max_drawdown_calculation()
    test_sharpe_ratio_invariants()
    test_ast_rce_security_blocking()
    test_ast_depth_limit_blocking()
    print("TODOS OS TESTES ATÔMICOS FORAM APROVADOS COM SUCESSO.")
