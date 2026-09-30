"""
Calibrador Dinamico de Limiares Walk-Forward por Par (WalkForwardCalibrator).
Ajusta os parametros operacionais (limiar de impulso de Lead-Lag e multiplicador
de Squeeze) conforme a volatilidade e o beta especifico de cada ativo,
evitando parametros engessados e sobreajuste (overfitting).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class CalibratedPairParams:
    """Parametros calibrados para um par especifico."""
    symbol: str
    lead_lag_impulse_threshold: float
    follower_lag_tolerance: float
    obi_sensitivity_threshold: float
    target_volatility_pct: float
    updated_at_candles: int


class WalkForwardCalibrator:
    """Calibra parametros operacionais usando janela historica deslizante."""

    def __init__(self, window_size: int = 96): # 96 candles de 15m = 24 horas
        self.window_size = window_size
        self.cache: Dict[str, CalibratedPairParams] = {}

    def _compute_realized_volatility(self, closes: List[float]) -> float:
        """Calcula o desvio padrao dos retornos percentuais."""
        if len(closes) < 2:
            return 0.01
        rets = []
        for i in range(1, len(closes)):
            p0 = closes[i - 1]
            if p0 > 0:
                rets.append((closes[i] - p0) / p0)
        if not rets:
            return 0.01
        mean_r = sum(rets) / float(len(rets))
        variance = sum((r - mean_r) ** 2 for r in rets) / float(len(rets))
        return max(0.002, math.sqrt(variance))

    def calibrate_pair(
        self,
        symbol: str,
        recent_closes: List[float],
        base_asset_volatility: Optional[float] = None
    ) -> CalibratedPairParams:
        """Calcula os limiares adaptativos ideais para o par com base na volatilidade recente."""
        vol = self._compute_realized_volatility(recent_closes[-self.window_size:])
        base_vol = base_asset_volatility or 0.008

        # Razao de beta relativo entre o ativo e o mercado
        vol_ratio = vol / base_vol
        clamped_ratio = max(0.6, min(2.5, vol_ratio))

        # Ativos mais volateis (DOGE, SOL) exigem limiar maior para evitar ruido
        calibrated_impulse = round(0.008 * clamped_ratio, 4)
        calibrated_tolerance = round(0.0025 * clamped_ratio, 4)

        # OBI: em ativos mais lentos, menor desbalanceamento ja e suficiente
        calibrated_obi = round(max(0.45, min(0.65, 0.55 * (1.0 / clamped_ratio))), 3)

        params = CalibratedPairParams(
            symbol=symbol,
            lead_lag_impulse_threshold=calibrated_impulse,
            follower_lag_tolerance=calibrated_tolerance,
            obi_sensitivity_threshold=calibrated_obi,
            target_volatility_pct=round(vol * 100.0, 3),
            updated_at_candles=len(recent_closes)
        )
        self.cache[symbol] = params
        return params

    def get_params(self, symbol: str) -> Optional[CalibratedPairParams]:
        """Retorna os parametros mais recentes armazenados em cache."""
        return self.cache.get(symbol)
