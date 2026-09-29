"""
Mecanismo Central de Kill Switch e Circuit Breakers em 3 Níveis.
Gerencia a integridade patrimonial, persistência atômica de estado em disco
e recuperação de estado após falhas (Crash Recovery com cooling-off de 24h).
"""

import os
import time
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from config.settings import settings
from core.logger import telemetry


class CircuitBreakerManager:
    """Controlador determinístico dos freios de emergência (Kill Switch)."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or settings.circuit_breaker_state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Estado interno em memória
        self.is_global_locked: bool = False
        self.active_level: str = "NORMAL"  # NORMAL, L1, L2, L3
        self.locked_at_utc: int = 0
        self.lock_expires_at_utc: int = 0
        self.lock_reason: str = ""
        self.paused_agents: set[str] = set()
        
        # Recuperação obrigatória de estado no boot
        self.verify_boot_state()

    def _persist_state_atomically(self):
        """Grava o estado em disco de forma atômica para evitar corrupção em caso de queda de energia."""
        state_data = {
            "is_global_locked": self.is_global_locked,
            "active_level": self.active_level,
            "locked_at_utc": self.locked_at_utc,
            "lock_expires_at_utc": self.lock_expires_at_utc,
            "lock_reason": self.lock_reason,
            "paused_agents": list(self.paused_agents),
            "updated_at_utc": int(time.time() * 1000)
        }
        
        # Padrão atômico: escreve em arquivo temporário no mesmo sistema de arquivos e renomeia
        temp_dir = self.state_file.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(state_data, tf, indent=2)
            temp_name = tf.name
            
        os.replace(temp_name, self.state_file)

    def verify_boot_state(self):
        """Verifica se o sistema foi reiniciado durante um período de quarentena ativo."""
        if not self.state_file.exists():
            self._persist_state_atomically()
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            now_ms = int(time.time() * 1000)
            expires_at = data.get("lock_expires_at_utc", 0)
            
            # Se havia um bloqueio L2 ativo e o prazo de cooling-off ainda não expirou
            if data.get("is_global_locked", False) and now_ms < expires_at:
                self.is_global_locked = True
                self.active_level = data.get("active_level", "L2")
                self.locked_at_utc = data.get("locked_at_utc", now_ms)
                self.lock_expires_at_utc = expires_at
                self.lock_reason = data.get("lock_reason", "Bloqueio de segurança herdado do boot.")
                self.paused_agents = set(data.get("paused_agents", []))
                
                remaining_hours = (expires_at - now_ms) / (1000 * 3600)
                telemetry.emit_event(
                    event="BOOT_COOLING_OFF_RESTORED",
                    level="CRITICAL",
                    agent_id="SYSTEM",
                    payload={
                        "motivo": self.lock_reason,
                        "horas_restantes": round(remaining_hours, 2),
                        "expira_em_ms": expires_at
                    }
                )
            else:
                # Período já expirou ou estado estava limpo
                self.paused_agents = set(data.get("paused_agents", []))
                self.is_global_locked = False
                self.active_level = "NORMAL"
                self._persist_state_atomically()
        except Exception as e:
            telemetry.error(f"Erro ao ler arquivo de estado do Circuit Breaker: {e}. Inicializando seguro.")
            self.is_global_locked = True
            self.lock_reason = "Falha de integridade no arquivo de estado."

    def trip_level_1_agent(self, agent_id: str, daily_loss_usd: float, allocated_capital: float) -> bool:
        """
        Aciona Nível 1: Pausa um agente individual que atingiu o limite diário de perda (2.0%).
        """
        loss_pct = (daily_loss_usd / allocated_capital) * 100.0 if allocated_capital > 0 else 100.0
        if loss_pct >= settings.risk_limits.max_agent_daily_loss_pct:
            self.paused_agents.add(agent_id)
            self._persist_state_atomically()
            
            telemetry.emit_event(
                event="CIRCUIT_BREAKER_L1_TRIGGERED",
                level="WARN",
                agent_id=agent_id,
                payload={
                    "perda_diaria_usd": daily_loss_usd,
                    "perda_diaria_pct": round(loss_pct, 2),
                    "limite_pct": settings.risk_limits.max_agent_daily_loss_pct,
                    "acao": "PAUSE_AGENT"
                }
            )
            return True
        return False

    def trip_level_2_portfolio(self, current_equity_usd: float, baseline_equity_usd: float, reason: str = "") -> bool:
        """
        Aciona Nível 2: Circuit Breaker Global de Carteira (Drawdown >= 4.0% em 24h).
        Cancela ordens, fecha posições a mercado e bloqueia por 24h.
        """
        dd_pct = ((baseline_equity_usd - current_equity_usd) / baseline_equity_usd) * 100.0 if baseline_equity_usd > 0 else 0.0
        if dd_pct >= settings.risk_limits.max_portfolio_daily_drawdown_pct or reason == "MANUAL_PANIC":
            now_ms = int(time.time() * 1000)
            cooling_off_ms = settings.risk_limits.circuit_breaker_l2_cooling_off_hours * 3600 * 1000
            
            self.is_global_locked = True
            self.active_level = "L2"
            self.locked_at_utc = now_ms
            self.lock_expires_at_utc = now_ms + cooling_off_ms
            self.lock_reason = reason or f"Drawdown global atingiu {dd_pct:.2f}% (limite: {settings.risk_limits.max_portfolio_daily_drawdown_pct}%)."
            self._persist_state_atomically()
            
            telemetry.emit_event(
                event="CIRCUIT_BREAKER_L2_TRIGGERED",
                level="CRITICAL",
                agent_id="SYSTEM",
                payload={
                    "drawdown_pct": round(dd_pct, 2),
                    "patrimonio_atual": current_equity_usd,
                    "patrimonio_base": baseline_equity_usd,
                    "motivo": self.lock_reason,
                    "bloqueio_horas": settings.risk_limits.circuit_breaker_l2_cooling_off_hours,
                    "acao": "CLOSE_ALL_MARKET_AND_LOCK_SYSTEM"
                }
            )
            return True
        return False

    def is_trading_allowed(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Consulta central para verificar se uma ordem pode ser enviada."""
        now_ms = int(time.time() * 1000)
        
        # Checa se o bloqueio L2 expirou naturalmente pelo tempo
        if self.is_global_locked and now_ms >= self.lock_expires_at_utc:
            self.is_global_locked = False
            self.active_level = "NORMAL"
            self.lock_reason = "Quarentena de 24h expirada com sucesso."
            self._persist_state_atomically()
            
        if self.is_global_locked:
            return {
                "allowed": False,
                "reason": f"Sistema travado pelo Circuit Breaker L2. {self.lock_reason}"
            }
            
        if agent_id and agent_id in self.paused_agents:
            return {
                "allowed": False,
                "reason": f"Agente {agent_id} está pausado pelo Circuit Breaker L1."
            }
            
        return {"allowed": True, "reason": "Negociação autorizada."}

    def reset_lock(self, force_override: bool = False) -> bool:
        """Destrava o sistema (apenas com autorização explícita)."""
        if not force_override:
            return False
        self.is_global_locked = False
        self.active_level = "NORMAL"
        self.lock_expires_at_utc = 0
        self.lock_reason = "Destravamento manual autorizado."
        self.paused_agents.clear()
        self._persist_state_atomically()
        telemetry.warning("Circuit Breaker destravado manualmente por comando autorizado.")
        return True


# Instância global do gerenciador de Kill Switch
circuit_breaker = CircuitBreakerManager()
