"""
Suíte de Testes da Fase 1: Fundação de Segurança, Configurações e Circuit Breakers.
Valida:
1. Imutabilidade dos esquemas Pydantic v2 (frozen=True).
2. Sanitização automática de chaves e segredos no logger ODD.
3. Persistência atômica e recuperação de bloqueio no boot (Crash Recovery).
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path
from pydantic import ValidationError

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.settings import RiskLimits, SystemSettings
from core.logger import BotTelemetryLogger, sanitize_text, sanitize_payload
from core.kill_switch import CircuitBreakerManager


def test_pydantic_frozen_immutability():
    """Valida que nenhum código ou agente consegue alterar os limites de risco em memória."""
    limits = RiskLimits()
    try:
        limits.max_leverage_ceiling = 10.0
        assert False, "Deveria ter lançado ValidationError ao tentar alterar limite congelado."
    except (ValidationError, TypeError):
        pass

    try:
        limits.max_agent_daily_loss_pct = 50.0
        assert False, "Deveria ter lançado ValidationError ao tentar alterar perda máxima."
    except (ValidationError, TypeError):
        pass


def test_logger_secret_sanitization():
    """Valida que chaves de API e tokens confidenciais são mascarados como ***REDACTED***."""
    leaked_msg = "Enviando ordem com api_key=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6 e secret=999888777666555444333222111000"
    sanitized = sanitize_text(leaked_msg)
    assert "a1b2c3d4e5f6g7h8" not in sanitized, "Chave de API vazou no log sem sanitização!"
    assert "***REDACTED***" in sanitized, "Substituição por REDACTED não ocorreu!"

    payload_with_keys = {
        "symbol": "BTCUSDT",
        "api_secret": "my_super_secret_private_key_xyz123",
        "amount": 0.5
    }
    clean_payload = sanitize_payload(payload_with_keys)
    assert clean_payload["api_secret"] == "***REDACTED***"
    assert clean_payload["symbol"] == "BTCUSDT"


def test_circuit_breaker_atomic_persistence_and_crash_recovery():
    """Valida que um bloqueio L2 ativo persiste após reinicialização simulada do sistema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "test_cb_state.json"
        
        # Instância 1: Dispara o Circuit Breaker L2
        cb1 = CircuitBreakerManager(state_file=state_file)
        assert cb1.is_trading_allowed()["allowed"] is True
        
        # Dispara queda de 5% (superior ao limite de 4%)
        triggered = cb1.trip_level_2_portfolio(
            current_equity_usd=9500.0,
            baseline_equity_usd=10000.0,
            reason="Crash test"
        )
        assert triggered is True
        assert cb1.is_trading_allowed()["allowed"] is False
        assert state_file.exists(), "Arquivo de estado não foi gravado em disco!"
        
        # Simula reinicialização do processo: cria uma nova instância lendo o arquivo
        cb2 = CircuitBreakerManager(state_file=state_file)
        
        # Deve acordar travado e recusar qualquer trade
        check = cb2.is_trading_allowed()
        assert check["allowed"] is False, "O sistema liberou trades indevidamente após reinicialização!"
        assert cb2.active_level == "L2"
        assert "L2" in check["reason"]
        
        # Valida que apenas reset explícito autorizado destrava
        cb2.reset_lock(force_override=True)
        assert cb2.is_trading_allowed()["allowed"] is True


def test_circuit_breaker_l1_agent_pause():
    """Valida que o Circuit Breaker L1 pausa o agente infrator mas permite outros agentes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "test_cb_l1.json"
        cb = CircuitBreakerManager(state_file=state_file)
        
        # Agente A perde $25 em $1000 (2.5% > 2.0%)
        tripped = cb.trip_level_1_agent("agent_A", daily_loss_usd=25.0, allocated_capital=1000.0)
        assert tripped is True
        
        # Agente A deve estar bloqueado
        assert cb.is_trading_allowed("agent_A")["allowed"] is False
        # Agente B deve continuar liberado
        assert cb.is_trading_allowed("agent_B")["allowed"] is True


if __name__ == "__main__":
    test_pydantic_frozen_immutability()
    test_logger_secret_sanitization()
    test_circuit_breaker_atomic_persistence_and_crash_recovery()
    test_circuit_breaker_l1_agent_pause()
    print("TODOS OS TESTES DA FASE 1 FORAM APROVADOS COM SUCESSO.")
