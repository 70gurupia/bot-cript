"""
Motor de Matrizes Cross-Sectional, Extremos e Sazonalidade Temporal (Matrix Alpha Engine).
Implementa:
1. Estimador de Volatilidade de Garman-Klass e Eficiência Direcional de Vela (Body/Wick Ratio).
2. Matriz de Sazonalidade Temporal Intradiária (Horas UTC e Dias da Semana).
3. Matriz de Força Relativa Cross-Sectional contra o Bitcoin (Seleção de Top Quantile).
4. Detector de Regime de Turbulência e Chicotada Estocástica (Markov Whipsaw Risk).
"""

from __future__ import annotations
import math
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class MatrixAlphaSignal:
    """Sinal quantitativo gerado pela matriz de filtros combinados."""
    symbol: str
    allow_entry: bool
    candle_efficiency: float
    garman_klass_vol: float
    session_name: str
    liquidity_weight: float
    relative_strength_zscore: float
    whipsaw_risk: bool
    confidence_score: float
    rejection_reason: str


def compute_garman_klass_volatility(
    high: float, low: float, open_p: float, close_p: float
) -> float:
    """Calcula a volatilidade de Garman-Klass baseada em extremos e abertura/fechamento."""
    if low <= 0.0 or open_p <= 0.0 or high <= 0.0 or close_p <= 0.0:
        return 0.0
    hl_ratio = high / low
    co_ratio = close_p / open_p
    if hl_ratio <= 0.0 or co_ratio <= 0.0:
        return 0.0

    log_hl = math.log(hl_ratio)
    log_co = math.log(co_ratio)
    term1 = 0.5 * (log_hl ** 2)
    term2 = (2.0 * math.log(2.0) - 1.0) * (log_co ** 2)
    variance = max(0.0, term1 - term2)
    return round(math.sqrt(variance), 6)


def compute_candle_efficiency(
    open_p: float, high: float, low: float, close_p: float
) -> float:
    """Calcula a relação entre corpo direcional e amplitude total do candle."""
    spread = high - low
    if spread <= 1e-12:
        return 0.0
    body = abs(close_p - open_p)
    return round(min(1.0, max(0.0, body / spread)), 4)


def evaluate_temporal_session(open_time_ms: int) -> Dict[str, Any]:
    """Determina a sessão global de liquidez e o peso de continuidade estatística."""
    dt = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)
    hour = dt.hour
    weekday = dt.weekday()
    is_weekend = weekday in (5, 6)

    if 13 <= hour <= 17:
        session = "US_EXPANSION"
        weight = 1.30 if not is_weekend else 0.70
        is_high = not is_weekend
    elif 8 <= hour <= 12:
        session = "EUROPE_MOMENTUM"
        weight = 1.10 if not is_weekend else 0.60
        is_high = not is_weekend
    elif 0 <= hour <= 7:
        session = "ASIA_RANGING"
        weight = 0.65 if not is_weekend else 0.40
        is_high = False
    elif 18 <= hour <= 20:
        session = "US_CLOSE"
        weight = 0.85 if not is_weekend else 0.50
        is_high = False
    else:
        session = "PACIFIC_LOW_LIQ"
        weight = 0.50 if not is_weekend else 0.30
        is_high = False

    return {
        "session_name": session,
        "is_weekend": is_weekend,
        "liquidity_weight": round(weight, 2),
        "is_high_liquidity_window": is_high,
        "hour_utc": hour,
        "weekday": weekday
    }


def compute_cross_sectional_zscores(
    pair_returns: Dict[str, float]
) -> Dict[str, float]:
    """Calcula o Z-score de momento relativo entre todos os ativos do portfólio."""
    if not pair_returns:
        return {}
    vals = list(pair_returns.values())
    n = len(vals)
    if n <= 1:
        return {sym: 0.0 for sym in pair_returns}

    mean_val = sum(vals) / float(n)
    variance = sum((v - mean_val) ** 2 for v in vals) / float(n)
    std_dev = math.sqrt(variance)

    if std_dev < 1e-9:
        return {sym: 0.0 for sym in pair_returns}

    return {
        sym: round((ret - mean_val) / std_dev, 4)
        for sym, ret in pair_returns.items()
    }


def evaluate_markov_whipsaw_risk(
    closes: List[float],
    window: int = 24
) -> Tuple[bool, float]:
    """Estima a probabilidade de transição para o estado de chicotada / turbulência."""
    if len(closes) < window + 2:
        return False, 0.0

    recent_closes = closes[-(window + 1):]
    changes = []
    for i in range(1, len(recent_closes)):
        diff = recent_closes[i] - recent_closes[i - 1]
        changes.append(1 if diff > 0 else (-1 if diff < 0 else 0))

    if len(changes) < 2:
        return False, 0.0

    reversals = 0
    for i in range(1, len(changes)):
        if changes[i] != 0 and changes[i - 1] != 0 and changes[i] != changes[i - 1]:
            reversals += 1

    reversal_rate = reversals / float(len(changes) - 1)
    is_whipsaw = reversal_rate >= 0.58
    return is_whipsaw, round(reversal_rate, 4)


def _check_matrix_rejection(
    eff: float,
    sess: Dict[str, Any],
    z_score: float,
    whipsaw: bool,
    side: str
) -> Optional[str]:
    """Avalia individualmente os critérios de rejeição matriciais."""
    if whipsaw:
        return "WHIPSAW_REGIME_DETECTED: Mercado em alternância estocástica de chicotada"
    if eff < 0.28:
        return f"LOW_CANDLE_EFFICIENCY: Vela dominada por pavios de ruído ({eff:.2f} < 0.28)"
    if sess["is_weekend"] and sess["liquidity_weight"] < 0.55:
        return "WEEKEND_LOW_LIQUIDITY: Fim de semana com dispersão e baixo volume"
    if side == "BUY" and z_score < -0.80:
        return f"CROSS_SECTIONAL_UNDERPERFORMER: Altcoin no quintil inferior de força relativa ({z_score:.2f})"
    return None


def evaluate_matrix_alpha(
    symbol: str,
    open_p: float,
    high: float,
    low: float,
    close_p: float,
    open_time_ms: int,
    closes_history: List[float],
    relative_strength_zscore: float = 0.0,
    side: str = "BUY"
) -> MatrixAlphaSignal:
    """Avalia o filtro matricial multidimensional completo para uma decisão operacional."""
    gk_vol = compute_garman_klass_volatility(high, low, open_p, close_p)
    eff = compute_candle_efficiency(open_p, high, low, close_p)
    sess = evaluate_temporal_session(open_time_ms)
    whipsaw, w_rate = evaluate_markov_whipsaw_risk(closes_history, window=24)

    rejection = _check_matrix_rejection(eff, sess, relative_strength_zscore, whipsaw, side)

    if rejection is not None:
        return MatrixAlphaSignal(
            symbol=symbol,
            allow_entry=False,
            candle_efficiency=eff,
            garman_klass_vol=gk_vol,
            session_name=sess["session_name"],
            liquidity_weight=sess["liquidity_weight"],
            relative_strength_zscore=relative_strength_zscore,
            whipsaw_risk=whipsaw,
            confidence_score=0.0,
            rejection_reason=rejection
        )

    base_score = 0.50
    eff_bonus = (eff - 0.30) * 0.40
    session_bonus = (sess["liquidity_weight"] - 1.0) * 0.25
    rs_bonus = max(-0.20, min(0.30, relative_strength_zscore * 0.15))
    whipsaw_penalty = w_rate * 0.20

    conf = round(min(1.0, max(0.1, base_score + eff_bonus + session_bonus + rs_bonus - whipsaw_penalty)), 4)

    return MatrixAlphaSignal(
        symbol=symbol,
        allow_entry=True,
        candle_efficiency=eff,
        garman_klass_vol=gk_vol,
        session_name=sess["session_name"],
        liquidity_weight=sess["liquidity_weight"],
        relative_strength_zscore=relative_strength_zscore,
        whipsaw_risk=False,
        confidence_score=conf,
        rejection_reason=""
    )
