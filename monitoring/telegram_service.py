"""
Serviço de Alertas e Comandos Remotos via Telegram (Fase 6).
Implementa os comandos de emergência /status, /panic, /kill e /resume com autenticação
estrita por Chat ID e acionamento determinístico do Circuit Breaker L2.
"""

from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from core.kill_switch import circuit_breaker
from core.logger import telemetry


import os


class TelegramRemoteService:
    """Controlador de comandos e notificacoes remotas via Telegram Bot."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        authorized_chat_ids: Optional[List[int]] = None
    ):
        env_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.bot_token = bot_token or env_token
        self.is_live = bool(self.bot_token and len(self.bot_token) >= 30 and ":" in self.bot_token)

        env_chats = os.getenv("TELEGRAM_AUTHORIZED_CHAT_IDS")
        if authorized_chat_ids:
            self.authorized_chat_ids = set(authorized_chat_ids)
        elif env_chats:
            self.authorized_chat_ids = {int(cid.strip()) for cid in env_chats.split(",") if cid.strip().isdigit()}
        else:
            self.authorized_chat_ids = {123456789}

        if not self.is_live:
            telemetry.emit_event(
                event="TELEGRAM_SIMULATION_MODE",
                level="INFO",
                agent_id="TELEGRAM_BOT",
                payload={"status": "Servico Telegram em modo de simulacao local (sem token real configurado)."}
            )
        self.pending_confirmation: Dict[int, str] = {}

    def is_authorized(self, chat_id: int) -> bool:
        """Valida se o remetente pertence a allowlist autorizada."""
        return chat_id in self.authorized_chat_ids

    def process_command(self, chat_id: int, text: str, state_provider: Optional[Any] = None) -> str:
        """Processa comando de texto recebido e retorna mensagem de resposta."""
        if not self.is_authorized(chat_id):
            telemetry.emit_event(
                event="TELEGRAM_UNAUTHORIZED_ACCESS",
                level="WARNING",
                agent_id="TELEGRAM_BOT",
                payload={"chat_id": chat_id, "attempted_text": text[:30]}
            )
            return "ACESSO NEGADO: Chat ID nao autorizado para operacoes da Tesouraria."

        cmd = text.strip().split()[0].lower() if text.strip() else ""

        if cmd in {"/panic", "/kill"}:
            return self._handle_panic(chat_id)

        if cmd == "/resume":
            return self._handle_resume(chat_id)

        if cmd == "/confirm":
            return self._handle_confirm(chat_id)

        if cmd == "/status":
            return self._handle_status(state_provider)

        return "Comando desconhecido. Comandos disponiveis: /status, /panic, /kill, /resume"

    def _handle_panic(self, chat_id: int) -> str:
        """Aciona imediatamente o Circuit Breaker L2 (congelamento total por 24h)."""
        circuit_breaker.trip_level_2_portfolio(
            current_equity_usd=0.0,
            baseline_equity_usd=10000.0,
            reason="MANUAL_PANIC"
        )
        telemetry.emit_event(
            event="CIRCUIT_BREAKER_MANUAL_PANIC",
            level="CRITICAL",
            agent_id="TELEGRAM_BOT",
            payload={"requested_by_chat_id": chat_id}
        )
        return (
            "EMERGENCIA ACIONADA VIA TELEGRAM: Circuit Breaker Nivel 2 DISPARADO.\n"
            "Todas as ordens foram canceladas e o sistema esta travado em quarentena de 24h.\n"
            "Para destravar apos inspecao, utilize o comando /resume."
        )

    def _handle_resume(self, chat_id: int) -> str:
        """Inicia processo de destravamento com confirmacao de dois passos."""
        self.pending_confirmation[chat_id] = "RESUME"
        return (
            "ATENCAO: Destravamento do sistema solicitado.\n"
            "Isto cancelara a quarentena do Circuit Breaker L2 e reativara as negociacoes.\n"
            "Para confirmar formalmente, digite: /confirm"
        )

    def _handle_confirm(self, chat_id: int) -> str:
        """Executa a acao pendente confirmada."""
        pending_action = self.pending_confirmation.pop(chat_id, None)
        if pending_action == "RESUME":
            circuit_breaker.reset_lock(force_override=True)
            telemetry.emit_event(
                event="CIRCUIT_BREAKER_MANUAL_RESET",
                level="WARNING",
                agent_id="TELEGRAM_BOT",
                payload={"resumed_by_chat_id": chat_id}
            )
            return "SUCESSO: Circuit Breaker L2 resetado. Negociacoes liberadas pela Tesouraria."
        return "Nenhuma acao pendente de confirmacao."

    def _handle_status(self, state_provider: Optional[Any] = None) -> str:
        """Gera sumario operacional de status."""
        cb_status = circuit_breaker.is_trading_allowed("STATUS_CHECK")
        status_text = "OPERACIONAL (LIBERADO)" if cb_status["allowed"] else f"TRAVADO ({cb_status['reason']})"

        lines = [
            "RELATORIO DE STATUS DA TESOURARIA:",
            f"- Status Circuit Breaker: {status_text}",
            f"- Quarentena L2 Ativa: {circuit_breaker.is_global_locked}"
        ]
        if state_provider and hasattr(state_provider, "get_status_summary"):
            extra = state_provider.get_status_summary()
            lines.append(f"- Detalhes Extras: {json.dumps(extra)}")

        return "\n".join(lines)

