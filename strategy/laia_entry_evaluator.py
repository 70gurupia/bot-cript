"""
Avaliador e Descobridor de Entradas Qualificadas com o Modelo Laia (Alpha Discovery).
Combina confluência multi-par, filtro de falsos rompimentos, análise de funding rate
e horários bancários para selecionar entradas com assimetria superior às regras mecânicas.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class EntryEvaluationResult:
    """Resultado da avaliação cognitiva de uma oportunidade de entrada."""
    symbol: str
    action: str  # "LONG", "SHORT", "HOLD_WAIT", "FILTERED_NO_TRADE"
    entry_quality_score: float  # 0 a 100
    risk_mode: str  # "ANTI_MARTINGALE_EXPAND", "BASE_RISK", "NO_TRADE"
    confidence: float  # 0.0 a 1.0
    reasons: List[str]
    is_superior_to_mechanical: bool


class LaiaEntryEvaluator:
    """Avaliador cognitivo de entradas para Day Trade baseado no modelo Laia."""

    def __init__(self, min_quality_score: float = 70.0):
        self.min_quality_score = min_quality_score

    def _calc_session_score(self, hour_utc: int) -> float:
        """Calcula o peso de liquidez institucional da sessao bancaria."""
        if 8 <= hour_utc <= 11:
            return 25.0  # Sessao de Londres (alta liquidez)
        if 13 <= hour_utc <= 17:
            return 30.0  # Sessao de Nova York (maior volume e expansao)
        if 0 <= hour_utc <= 4:
            return 10.0  # Sessao da Asia (range estreito e falsos breakouts)
        return 15.0

    def _calc_lead_lag_score(self, btc_ret: float, alt_ret: float) -> tuple[float, bool]:
        """Avalia a assimetria e o atraso entre o lider BTC e a altcoin seguidora."""
        spread = btc_ret - alt_ret
        if btc_ret > 0.010 and alt_ret < 0.003:
            return 35.0, True  # Descompasso classico de alta assimetria
        if btc_ret < -0.010 and alt_ret > -0.003:
            return 35.0, True  # Descompasso de baixa
        if abs(spread) >= 0.005:
            return 20.0, False
        return 5.0, False

    def _calc_funding_safety_score(self, funding_rate: float, side: str) -> float:
        """Pontua a seguranca contra armadilhas de liquidacao baseadas em funding."""
        if side == "LONG":
            if funding_rate <= -0.0001:
                return 25.0  # Short squeeze provavel (excelente para compra)
            if funding_rate > 0.0005:
                return -15.0  # Mercado excessivamente comprado (risco de dump)
            return 15.0
        if side == "SHORT":
            if funding_rate >= 0.0005:
                return 25.0  # Long squeeze provavel (excelente para venda)
            if funding_rate < -0.0001:
                return -15.0
            return 15.0
        return 0.0

    def _detect_hidden_accumulation(
        self,
        btc_ret: float,
        alt_ret: float,
        alt_volume_ratio: float
    ) -> bool:
        """Detecta acumulacao institucional oculta (altcoin forte enquanto BTC cai)."""
        return btc_ret < -0.008 and alt_ret >= 0.001 and alt_volume_ratio >= 1.4

    def _determine_decision(
        self,
        score: float,
        side: str,
        is_mechanical_signal_active: bool,
        reasons: List[str]
    ) -> tuple[str, str, bool]:
        """Calcula a ação, modo de risco e superioridade com base no score."""
        if score >= self.min_quality_score:
            action = side
            risk_mode = "ANTI_MARTINGALE_EXPAND" if score >= 85.0 else "BASE_RISK"
            is_superior = not is_mechanical_signal_active or (score >= 85.0)
            return action, risk_mode, is_superior

        action = "FILTERED_NO_TRADE" if is_mechanical_signal_active else "HOLD_WAIT"
        risk_mode = "NO_TRADE"
        is_superior = is_mechanical_signal_active
        reasons.append("Filtro cognitivo ativo: confluencia insuficiente para arriscar capital.")
        return action, risk_mode, is_superior

    def evaluate_entry(
        self,
        symbol: str,
        btc_return_15m: float,
        alt_return_15m: float,
        hour_utc: int,
        funding_rate: float,
        alt_volume_ratio: float = 1.0,
        is_mechanical_signal_active: bool = False
    ) -> EntryEvaluationResult:
        """
        Avalia se a entrada proposta possui confluencia real ou se deve ser vetada.
        Identifica tambem entradas de acumulacao oculta mesmo sem sinal mecanico puro.
        """
        reasons: List[str] = []
        is_hidden_acc = self._detect_hidden_accumulation(btc_return_15m, alt_return_15m, alt_volume_ratio)

        # 1. Definir direcao primaria
        side = "LONG" if (btc_return_15m > 0 or is_hidden_acc) else "SHORT"

        # 2. Calcular componentes do Score de Qualidade (EQS)
        session_pts = self._calc_session_score(hour_utc)
        lead_lag_pts, is_strong_lead = self._calc_lead_lag_score(btc_return_15m, alt_return_15m)
        funding_pts = self._calc_funding_safety_score(funding_rate, side)

        score = session_pts + lead_lag_pts + funding_pts
        if is_hidden_acc:
            score += 20.0
            reasons.append("Acumulacao institucional oculta: Altcoin descorrelacionou em alta com volume.")

        if is_strong_lead:
            reasons.append("Descompasso temporal Lead-Lag de alta probabilidade.")

        if funding_pts >= 20.0:
            reasons.append("Funding rate favoravel a squeeze direcional.")
        elif funding_pts < 0.0:
            reasons.append("Funding rate perigoso: alto risco de liquidacao contra a posicao.")

        score = max(0.0, min(100.0, score))
        confidence = score / 100.0

        # 3. Decisao final via helper
        action, risk_mode, is_superior = self._determine_decision(
            score, side, is_mechanical_signal_active, reasons
        )

        return EntryEvaluationResult(
            symbol=symbol,
            action=action,
            entry_quality_score=round(score, 2),
            risk_mode=risk_mode,
            confidence=round(confidence, 2),
            reasons=reasons,
            is_superior_to_mechanical=is_superior
        )

    def filter_opportunity_batch(
        self,
        opportunities: List[Dict[str, Any]]
    ) -> List[EntryEvaluationResult]:
        """Processa um lote de oportunidades e retorna apenas as aprovadas pelo filtro Laia."""
        results: List[EntryEvaluationResult] = []
        for opp in opportunities:
            eval_res = self.evaluate_entry(
                symbol=opp.get("symbol", "UNKNOWN"),
                btc_return_15m=opp.get("btc_return_15m", 0.0),
                alt_return_15m=opp.get("alt_return_15m", 0.0),
                hour_utc=opp.get("hour_utc", 14),
                funding_rate=opp.get("funding_rate", 0.0001),
                alt_volume_ratio=opp.get("alt_volume_ratio", 1.0),
                is_mechanical_signal_active=opp.get("is_mechanical_signal_active", False)
            )
            results.append(eval_res)
        return results
