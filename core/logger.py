"""
Subsistema de Logging Estruturado ODD (Observability-Driven Development) e Sanitização de Segredos.
Formata todos os eventos em JSON e mascara automaticamente chaves de API, senhas e tokens via regex.
"""

import re
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

# Padroes regex para deteccao de segredos e chaves de API
SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret[_-]?key|token|password|auth|bearer)[\s:=]+["\']?([a-zA-Z0-9_\-\.]{16,128})["\']?'),
    re.compile(r'\b[a-fA-F0-9]{32,64}\b'),  # Strings hexadecimais longas (hashes de chaves de API)
    re.compile(r'(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{20,}'),
]


def sanitize_text(text: str) -> str:
    """Substitui qualquer ocorrencia de chaves de API ou segredos por ***REDACTED***."""
    sanitized = text
    for pattern in SECRET_PATTERNS:
        # Substitui o valor sensivel preservando o identificador do campo quando aplicavel
        sanitized = pattern.sub(r'\1: "***REDACTED***"', sanitized) if "\\1" in pattern.pattern else pattern.sub('***REDACTED***', sanitized)
    return sanitized


def sanitize_payload(obj: Any) -> Any:
    """Sanitiza recursivamente dicionarios e listas antes da serializacao de log."""
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            if any(term in k.lower() for term in ["key", "secret", "token", "password", "auth"]):
                new_dict[k] = "***REDACTED***"
            else:
                new_dict[k] = sanitize_payload(v)
        return new_dict
    elif isinstance(obj, list):
        return [sanitize_payload(item) for item in obj]
    elif isinstance(obj, str):
        return sanitize_text(obj)
    return obj


class StructuredJsonFormatter(logging.Formatter):
    """Formatador customizado para emitir logs estritamente no contrato ODD JSON."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp_utc": int(time.time() * 1000),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_text(record.getMessage()),
        }
        
        # Incorpora dados extras caso presentes
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        if hasattr(record, "agent_id"):
            log_entry["agent_id"] = record.agent_id
        if hasattr(record, "payload"):
            log_entry["payload"] = sanitize_payload(record.payload)
            
        return json.dumps(log_entry, ensure_ascii=False)


class BotTelemetryLogger:
    """Logger principal com sink para console e arquivo JSON Lines estruturado."""
    def __init__(self, log_dir: Optional[Path] = None):
        if log_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
            log_dir = base_dir / "data" / "logs"
            
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / "bot_audit.jsonl"
        
        self.logger = logging.getLogger("bot_cripto")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        
        # Evita duplicacao de handlers
        if not self.logger.handlers:
            # File Handler com Rotacao Automatica (JSONL, max 10MB, 5 backups)
            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setFormatter(StructuredJsonFormatter())
            self.logger.addHandler(file_handler)
            
            # Stream Handler (Console)
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(StructuredJsonFormatter())
            self.logger.addHandler(stream_handler)

    def emit_event(self, event: str, level: str, agent_id: str, payload: dict):
        """Emite um log estruturado conforme o contrato ODD."""
        extra = {
            "event": event,
            "agent_id": agent_id,
            "payload": payload
        }
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"[{event}] Agente: {agent_id}", extra=extra)

    def info(self, msg: str, **kwargs):
        self.logger.info(sanitize_text(msg), **kwargs)

    def warning(self, msg: str, **kwargs):
        self.logger.warning(sanitize_text(msg), **kwargs)

    def error(self, msg: str, **kwargs):
        self.logger.error(sanitize_text(msg), **kwargs)

    def critical(self, msg: str, **kwargs):
        self.logger.critical(sanitize_text(msg), **kwargs)


# Instância global do logger
telemetry = BotTelemetryLogger()
