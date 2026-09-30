"""
Alocador de Portfólio Multi-Ativo com Kelly Fracionário e Paridade de Risco (task-032).
Calcula dinamicamente a alocacao ideal de capital entre os grupos da flotilha,
combinando o Critério de Kelly Fracionário com a ponderação pelo inverso da volatilidade:
1. Grupos com maior Win Rate e Sharpe (Lead-Lag e Funding) recebem peso prioritario.
2. Ativos mais voláteis sofrem desconto proporcional (Paridade de Risco).
3. Respeita tetos institucionais: max 25% por grupo, piso de 2.5% e exposicao total <= 70%.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class GroupAllocationInput:
    """Dados de entrada de performance e volatilidade de um grupo ou sub-bot."""
    group_id: str
    name: str
    win_rate: float            # 0.0 a 1.0 (ex: 0.74 para 74%)
    win_loss_ratio: float      # Payoff (ganho medio / perda media)
    realized_volatility: float # Desvio padrao dos retornos (ex: 0.02 para 2%)
    is_active: bool = True


@dataclass
class GroupAllocationResult:
    """Resultado da distribuicao otimizada de capital por grupo."""
    group_id: str
    name: str
    target_weight_pct: float
    allocated_usd: float
    kelly_fraction: float
    risk_parity_weight: float


class RiskParityKellyAllocator:
    """Alocador de carteira que equilibra risco e assimetria estatistica."""

    def __init__(
        self,
        fractional_kelly: float = 0.25,
        max_group_weight_pct: float = 25.0,
        min_group_weight_pct: float = 2.5,
        max_aggregate_exposure_pct: float = 70.0
    ):
        self.fractional_kelly = fractional_kelly
        self.max_group_weight_pct = max_group_weight_pct
        self.min_group_weight_pct = min_group_weight_pct
        self.max_aggregate_exposure_pct = max_aggregate_exposure_pct

    def _calc_raw_kelly(self, win_rate: float, win_loss_ratio: float) -> float:
        """Calcula o Kelly bruto limitado ao fator fracionario de seguranca."""
        if win_rate <= 0.0 or win_rate >= 1.0 or win_loss_ratio <= 0.0:
            return 0.05
        p = win_rate
        q = 1.0 - p
        b = win_loss_ratio
        full_kelly = (p * b - q) / b
        if full_kelly <= 0.0:
            return 0.05
        return min(self.fractional_kelly, full_kelly * self.fractional_kelly)

    def _calc_raw_weights(self, groups: List[GroupAllocationInput]) -> Dict[str, float]:
        """Calcula pesos brutos combinando Kelly e o inverso da volatilidade."""
        raw_weights = {}
        for g in groups:
            if not g.is_active:
                raw_weights[g.group_id] = 0.0
                continue
            k = self._calc_raw_kelly(g.win_rate, g.win_loss_ratio)
            vol = max(0.005, g.realized_volatility)
            # Peso bruto: assimetria de Kelly sobre volatilidade realizada
            raw_weights[g.group_id] = k / vol
        return raw_weights

    def _apply_weight_clamps(
        self,
        raw_weights: Dict[str, float],
        active_count: int
    ) -> Dict[str, float]:
        """Aplica piso minimo e teto maximo por grupo garantindo soma 100%."""
        tot = sum(raw_weights.values())
        if tot <= 0 or active_count <= 0:
            uniform = 100.0 / max(1, len(raw_weights))
            return {gid: uniform for gid in raw_weights}

        # Primeira normalizacao
        norm_weights = {gid: (w / tot) * 100.0 for gid, w in raw_weights.items()}

        # Clamping com teto e piso
        clamped = {}
        for gid, w in norm_weights.items():
            if w <= 0.0:
                clamped[gid] = 0.0
            else:
                c = max(self.min_group_weight_pct, min(self.max_group_weight_pct, w))
                clamped[gid] = c

        # Renormalizacao final para fechar exatamente em 100%
        sum_clamped = sum(clamped.values())
        if sum_clamped > 0:
            return {gid: (w / sum_clamped) * 100.0 for gid, w in clamped.items()}
        return clamped

    def allocate_capital(
        self,
        total_bankroll_usd: float,
        groups: List[GroupAllocationInput]
    ) -> List[GroupAllocationResult]:
        """Distribui o capital ativo entre todos os grupos operacionais."""
        active_count = sum(1 for g in groups if g.is_active)
        raw_weights = self._calc_raw_weights(groups)
        final_weights = self._apply_weight_clamps(raw_weights, active_count)

        # Montante efetivamente alocado respeitando o teto agregado
        active_exposure_usd = total_bankroll_usd * (self.max_aggregate_exposure_pct / 100.0)

        results = []
        for g in groups:
            w_pct = final_weights.get(g.group_id, 0.0)
            allocated = (w_pct / 100.0) * active_exposure_usd
            k = self._calc_raw_kelly(g.win_rate, g.win_loss_ratio)
            results.append(
                GroupAllocationResult(
                    group_id=g.group_id,
                    name=g.name,
                    target_weight_pct=round(w_pct, 2),
                    allocated_usd=round(allocated, 2),
                    kelly_fraction=round(k, 3),
                    risk_parity_weight=round(w_pct, 2)
                )
            )
        return results
