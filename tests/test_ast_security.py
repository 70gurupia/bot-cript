"""
Suíte de Testes de Segurança em Profundidade para a Árvore de Sintaxe Abstrata (AST Engine).
Executa 22 vetores de ataque adversarial contra a gramática de execução hermética:
- Injeção de RCE (eval, exec, __import__, compile, subprocess, os, sys)
- Manipulação de introspecção (globals, locals, builtins, getattr, setattr)
- Evasão de caracteres especiais (; \\ \n \r ( ))
- Injeção de campos não autorizados fora da allowlist
- Excesso de profundidade para proteção contra DoS recursivo (MAX_AST_DEPTH = 8)
"""

from __future__ import annotations
import os
import sys
import unittest

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
    SecurityError,
    ASTValidationError,
    _check_string_safety,
    FORBIDDEN_CALL_PATTERN
)


class TestASTSecurityVectors(unittest.TestCase):
    """Bateria de testes adversariais para garantir a inviolabilidade da AST."""

    def test_rce_eval_injection_blocked(self):
        """1. Bloqueio de eval direto."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="eval")

    def test_rce_exec_injection_blocked(self):
        """2. Bloqueio de exec direto."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="exec")

    def test_rce_import_injection_blocked(self):
        """3. Bloqueio de __import__."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="__import__")

    def test_rce_compile_injection_blocked(self):
        """4. Bloqueio de compile."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="compile")

    def test_rce_subprocess_injection_blocked(self):
        """5. Bloqueio de subprocess."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="subprocess")

    def test_rce_os_system_injection_blocked(self):
        """6. Bloqueio de os."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="os")

    def test_rce_sys_exit_injection_blocked(self):
        """7. Bloqueio de sys."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="sys")

    def test_introspection_globals_blocked(self):
        """8. Bloqueio de globals."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="globals")

    def test_introspection_locals_blocked(self):
        """9. Bloqueio de locals."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="locals")

    def test_introspection_builtins_blocked(self):
        """10. Bloqueio de builtins e __builtins__."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="builtins")
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="__builtins__")

    def test_introspection_getattr_blocked(self):
        """11. Bloqueio de getattr."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="getattr")

    def test_introspection_setattr_blocked(self):
        """12. Bloqueio de setattr."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="setattr")

    def test_introspection_delattr_blocked(self):
        """13. Bloqueio de delattr."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="delattr")

    def test_module_shutil_blocked(self):
        """14. Bloqueio de shutil."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="shutil")

    def test_module_socket_blocked(self):
        """15. Bloqueio de socket."""
        with self.assertRaises((SecurityError, ASTValidationError)):
            DataNode(field_name="socket")

    def test_newline_escape_in_string_safety(self):
        """16. Bloqueio de quebra de linha em strings."""
        with self.assertRaises(SecurityError):
            _check_string_safety("open\n")
        with self.assertRaises(SecurityError):
            _check_string_safety("open\r")

    def test_semicolon_command_chaining_blocked(self):
        """17. Bloqueio de ponto e virgula em strings."""
        with self.assertRaises(SecurityError):
            _check_string_safety("close; rm -rf /")

    def test_parentheses_call_syntax_blocked(self):
        """18. Bloqueio de parenteses em strings para impedir chamadas de funcao."""
        with self.assertRaises(SecurityError):
            _check_string_safety("hack()")

    def test_backslash_escape_blocked(self):
        """19. Bloqueio de barras invertidas para impedir evasao de unicode/escapes."""
        with self.assertRaises(SecurityError):
            _check_string_safety("test\\escape")

    def test_unauthorized_data_field_blocked(self):
        """20. Bloqueio de campos fora da allowlist estrita."""
        with self.assertRaises(ASTValidationError):
            DataNode(field_name="secret_api_key")
        with self.assertRaises(ASTValidationError):
            DataNode(field_name="database_password")

    def test_unauthorized_comparison_operator_blocked(self):
        """21. Bloqueio de operador de comparacao invalido ou malicioso."""
        with self.assertRaises((ASTValidationError, SecurityError)):
            ConditionNode(
                left=DataNode(field_name="close"),
                operator="<script>alert(1)</script>",
                right=ConstantNode(value=100.0)
            )

    def test_dos_max_depth_exceeded_raises_validation_error(self):
        """22. Protecao contra DoS por profundidade excessiva na arvore AST (profundidade > 8)."""
        curr = ConditionNode(
            left=DataNode(field_name="close"),
            operator="maior",
            right=ConstantNode(value=50000.0)
        )
        for _ in range(9):
            curr = LogicalNode(
                operator="AND",
                children=[curr, ConditionNode(
                    left=DataNode(field_name="volume"),
                    operator="maior",
                    right=ConstantNode(value=10.0)
                )]
            )
        with self.assertRaises(ASTValidationError):
            StrategyAST(
                strategy_id="deep_strategy",
                name="Deep Strategy Test",
                symbol="BTCUSDT",
                entry_rule=curr,
                exit_rule=ConditionNode(
                    left=DataNode(field_name="close"),
                    operator="menor",
                    right=ConstantNode(value=1000.0)
                )
            )


if __name__ == "__main__":
    unittest.main()
