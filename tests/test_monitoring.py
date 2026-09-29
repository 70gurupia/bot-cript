"""
Suíte de Testes do Sistema de Monitoramento e Bot Telegram (Fase 6).
Valida rotas REST do FastAPI, segurança de Chat ID e acionamento/destravamento de emergência L2.
"""

import sys
import os
from fastapi.testclient import TestClient

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from monitoring.telegram_service import TelegramRemoteService
from monitoring.web_app import app
from core.kill_switch import circuit_breaker


def test_telegram_unauthorized_rejection():
    """Valida rejeicao de comandos vindos de remetentes nao autorizados."""
    circuit_breaker.reset_lock(force_override=True)
    bot = TelegramRemoteService(authorized_chat_ids=[123456789])

    # Tentativa de acesso por invasor
    resp = bot.process_command(chat_id=987654321, text="/panic")
    assert "ACESSO NEGADO" in resp
    # Circuit breaker nao deve ser acionado
    assert circuit_breaker.is_global_locked is False


def test_telegram_panic_and_resume_flow():
    """Valida acionamento do botao de panico e destravamento via confirmacao no Telegram."""
    circuit_breaker.reset_lock(force_override=True)
    bot = TelegramRemoteService(authorized_chat_ids=[123456789])

    # 1. Comando /panic aciona Circuit Breaker L2
    resp_panic = bot.process_command(chat_id=123456789, text="/panic")
    assert "EMERGENCIA ACIONADA" in resp_panic
    assert circuit_breaker.is_global_locked is True

    # 2. Comando /status reflete o travamento
    resp_status = bot.process_command(chat_id=123456789, text="/status")
    assert "TRAVADO" in resp_status

    # 3. Solicitacao de destravamento /resume
    resp_resume = bot.process_command(chat_id=123456789, text="/resume")
    assert "Para confirmar formalmente, digite: /confirm" in resp_resume
    assert circuit_breaker.is_global_locked is True  # Ainda travado ate confirmacao

    # 4. Confirmacao formal /confirm
    resp_confirm = bot.process_command(chat_id=123456789, text="/confirm")
    assert "SUCESSO: Circuit Breaker L2 resetado" in resp_confirm
    assert circuit_breaker.is_global_locked is False  # Destravado com sucesso


def test_fastapi_endpoints():
    """Valida funcionamento das rotas REST e retorno do dashboard HTML."""
    circuit_breaker.reset_lock(force_override=True)
    client = TestClient(app)

    # 1. GET /api/status
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert "circuit_breaker_allowed" in data_status
    assert "total_equity_usd" in data_status

    # 2. GET /api/incubator
    res_inc = client.get("/api/incubator")
    assert res_inc.status_code == 200
    data_inc = res_inc.json()
    assert "quarantine_count" in data_inc
    assert "graduated_count" in data_inc

    # 3. POST /api/panic e POST /api/resume (Segurança: 401 sem chave, 200 com chave)
    # Tentativa sem chave deve ser rejeitada com 401
    res_unauth = client.post("/api/panic")
    assert res_unauth.status_code == 401
    assert "ACESSO NEGADO" in res_unauth.json()["detail"]

    # Tentativa com chave invalida deve ser rejeitada com 401
    res_bad_key = client.post("/api/panic", headers={"X-API-Key": "WRONG_KEY"})
    assert res_bad_key.status_code == 401

    # Execucao autorizada com chave valida
    auth_headers = {"X-API-Key": "BOT_CRIPTO_SECURE_KEY_2026"}
    res_panic = client.post("/api/panic", headers=auth_headers)
    assert res_panic.status_code == 200
    assert circuit_breaker.is_global_locked is True

    res_resume = client.post("/api/resume", headers=auth_headers)
    assert res_resume.status_code == 200
    assert circuit_breaker.is_global_locked is False


    # 4. GET / (Dashboard HTML)
    res_html = client.get("/")
    assert res_html.status_code == 200
    assert "Bot Cripto Autoevolutivo" in res_html.text
    assert "<!DOCTYPE html>" in res_html.text


if __name__ == "__main__":
    test_telegram_unauthorized_rejection()
    test_telegram_panic_and_resume_flow()
    test_fastapi_endpoints()
    print("SUÍTE DE TESTES DE MONITORAMENTO E DASHBOARD APROVADA COM SUCESSO (3/3 TESTES PASSARAM).")
