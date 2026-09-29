"""
Orquestrador do Supervisor OpenCode e Controle de Regime de Mercado (Fase 6).
Executa recalibração periódica a cada 4h/24h, ajusta multiplicadores de risco
e garante fallback automático e resiliente em caso de indisponibilidade do modelo.
"""

from __future__ import annotations
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from strategy.opencode_client import OpenCodeSupervisorClient, FALLBACK_REGIME
from treasury.treasury_controller import TreasuryController
from core.logger import telemetry


@dataclass
class MarketRegimeState:
    """Estado consolidado do regime macro de mercado avaliado pelo supervisor."""
    timestamp: float
    regime: str
    multiplicador_exposicao: float
    permitir_novas_entradas: bool
    foco_estrategico: str
    justificativa_curta: str
    is_fallback: bool


class MarketSupervisorLoop:
    """Gerenciador do ciclo de supervisao macro de mercado com o OpenCode."""

    def __init__(
        self,
        treasury: TreasuryController,
        opencode_client: Optional[OpenCodeSupervisorClient] = None,
        evaluation_interval_hours: int = 4
    ):
        self.treasury = treasury
        self.client = opencode_client or OpenCodeSupervisorClient()
        self.evaluation_interval_hours = evaluation_interval_hours
        self.last_evaluation_time: float = 0.0
        self.current_state: MarketRegimeState = MarketRegimeState(
            timestamp=time.time(),
            regime="NEUTRO_INICIAL",
            multiplicador_exposicao=1.0,
            permitir_novas_entradas=True,
            foco_estrategico="EQUILIBRADO",
            justificativa_curta="Inicializacao do sistema em modo padrao.",
            is_fallback=False
        )
        self.regime_history: List[MarketRegimeState] = []

    def should_evaluate(self, current_time: float) -> bool:
        """Determina se o intervalo minimo de recalibracao foi atingido."""
        elapsed_seconds = current_time - self.last_evaluation_time
        interval_seconds = self.evaluation_interval_hours * 3600
        return elapsed_seconds >= interval_seconds

    def _build_market_summary(self, symbol_candles: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Agrega estatisticas basicas dos pares para envio ao OpenCode."""
        summary: Dict[str, Any] = {
            "timestamp": time.time(),
            "total_symbols": len(symbol_candles),
            "symbols_data": {}
        }
        for sym, candles in symbol_candles.items():
            if not candles:
                continue
            last_c = candles[-1]
            first_c = candles[0]
            price_change_pct = ((last_c["close"] - first_c["close"]) / first_c["close"]) * 100.0 if first_c["close"] > 0 else 0.0
            avg_volume = sum(c.get("volume", 0.0) for c in candles) / len(candles)
            summary["symbols_data"][sym] = {
                "current_price": last_c["close"],
                "price_change_pct": round(price_change_pct, 2),
                "avg_volume": round(avg_volume, 2),
                "candles_count": len(candles)
            }
        return summary

    def _apply_regime_to_treasury(self, regime_data: Dict[str, Any], is_fallback: bool) -> MarketRegimeState:
        """Aplica as diretrizes do regime na Tesouraria Central."""
        mult = float(regime_data.get("multiplicador_exposicao", 0.5))
        mult = max(0.1, min(1.0, mult))

        # Ajusta exposicao agregada da tesouraria
        base_exposure = 0.70  # Teto nominal de 70%
        self.treasury.max_portfolio_exposure_pct = base_exposure * mult

        state = MarketRegimeState(
            timestamp=time.time(),
            regime=str(regime_data.get("regime", "NEUTRO")),
            multiplicador_exposicao=mult,
            permitir_novas_entradas=bool(regime_data.get("permitir_novas_entradas", True)),
            foco_estrategico=str(regime_data.get("foco_estrategico", "PRESERVACAO")),
            justificativa_curta=str(regime_data.get("justificativa_curta", "")),
            is_fallback=is_fallback
        )
        self.current_state = state
        self.regime_history.append(state)

        telemetry.emit_event(
            event="MARKET_REGIME_UPDATED",
            level="INFO",
            agent_id="SUPERVISOR_OPENCODE",
            payload={
                "regime": state.regime,
                "multiplicador": state.multiplicador_exposicao,
                "permitir_entradas": state.permitir_novas_entradas,
                "foco": state.foco_estrategico,
                "is_fallback": is_fallback,
                "teto_exposicao_ajustado": self.treasury.max_portfolio_exposure_pct
            }
        )

        return state

    async def update_market_regime(
        self,
        symbol_candles: Dict[str, List[Dict[str, Any]]],
        force: bool = False
    ) -> MarketRegimeState:
        """
        Executa uma rodada de avaliacao de regime de mercado consultando o OpenCode.
        Aciona fallback imediatamente se o OpenCode estiver inacessivel.
        """
        now = time.time()
        if not force and not self.should_evaluate(now):
            return self.current_state

        market_summary = self._build_market_summary(symbol_candles)
        
        # Consulta assincrona ao OpenCode
        regime_response = await self.client.evaluate_market_regime(market_summary)
        is_fallback = (regime_response == FALLBACK_REGIME)

        self.last_evaluation_time = now
        return self._apply_regime_to_treasury(regime_response, is_fallback=is_fallback)
