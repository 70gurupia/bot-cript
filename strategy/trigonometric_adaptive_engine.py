"""
Motor Geométrico e Trigonométrico Adaptativo no Plano Cartesiano.
Converte velas e séries temporais em coordenadas vetoriais adimensionais (x=tempo, y=preço/ATR),
aplicando trigonometria (seno, cosseno, tangente, arco-tangente) e derivadas angulares:
1. Vetor de Tendência Trigonométrica (TVT): ângulo theta, velocidade tan(theta), força sin(theta), inércia cos(theta).
2. Aceleração Angular (d_theta/dt) para antecipação de exaustão e topos/fundos.
3. Média Móvel Adaptativa Trigonométrica (TAMA): adapta alfa em função de sin^2(theta).
4. Indicador Híbrido Entropia-Trigonométrico (ASTF) para detecção de rupturas com alta tração angular.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class TrigonometricVector:
    """Decomposição trigonométrica do vetor de preço no plano cartesiano normalizado."""
    time_idx: int
    delta_x: float          # Variação no eixo temporal (barras)
    delta_y_norm: float     # Variação de preço normalizada pelo ATR (adimensional)
    angle_rad: float        # Ângulo theta em radianos [-pi/2, pi/2]
    angle_deg: float        # Ângulo theta em graus [-90, +90]
    sin_theta: float        # Força direcional vertical [-1.0, +1.0]
    cos_theta: float        # Inércia temporal horizontal [0.0, +1.0]
    tan_theta: float        # Velocidade / Inclinação linear (slope = dy/dx)
    angular_accel: float    # Aceleração angular: d_theta / dt


@dataclass
class TrigonometricSignal:
    """Sinal analítico gerado pela fusão geométrica e entrópica."""
    time_idx: int
    has_signal: bool
    side: str               # "BUY", "SELL" ou "NONE"
    angle_deg: float
    sin_theta: float
    cos_theta: float
    angular_accel: float
    regime: str             # "TREND_EXPANSION", "ANGULAR_EXHAUSTION", "CHOP_FLAT"
    confidence: float


def compute_normalized_cartesian_vector(
    p_curr: float,
    p_prev: float,
    atr_val: float,
    delta_t: int = 14,
    prev_angle_rad: float = 0.0,
    time_idx: int = 0
) -> TrigonometricVector:
    """
    Mapeia dois pontos de preço no plano cartesiano normalizado:
    dx = delta_t (passos de tempo)
    dy = (P_curr - P_prev) / ATR (deslocamento normalizado por volatilidade)
    """
    safe_atr = max(atr_val, 1e-6)
    safe_dx = max(delta_t, 1)

    dy_norm = (p_curr - p_prev) / safe_atr
    slope = dy_norm / float(safe_dx)

    angle_rad = math.atan(slope)
    angle_deg = math.degrees(angle_rad)

    sin_t = math.sin(angle_rad)
    cos_t = math.cos(angle_rad)
    tan_t = slope
    accel = angle_rad - prev_angle_rad

    return TrigonometricVector(
        time_idx=time_idx,
        delta_x=float(safe_dx),
        delta_y_norm=round(dy_norm, 4),
        angle_rad=round(angle_rad, 5),
        angle_deg=round(angle_deg, 2),
        sin_theta=round(sin_t, 4),
        cos_theta=round(cos_t, 4),
        tan_theta=round(tan_t, 4),
        angular_accel=round(accel, 5)
    )


def compute_series_trigonometric_vectors(
    closes: List[float],
    atrs: List[float],
    window: int = 14
) -> List[TrigonometricVector]:
    """Calcula a evolução dos vetores trigonométricos para toda a série temporal."""
    if len(closes) != len(atrs) or len(closes) < window:
        return []

    vectors: List[TrigonometricVector] = []
    prev_angle = 0.0

    for i in range(len(closes)):
        if i < window:
            vec = TrigonometricVector(
                time_idx=i, delta_x=float(window), delta_y_norm=0.0,
                angle_rad=0.0, angle_deg=0.0, sin_theta=0.0,
                cos_theta=1.0, tan_theta=0.0, angular_accel=0.0
            )
        else:
            vec = compute_normalized_cartesian_vector(
                p_curr=closes[i],
                p_prev=closes[i - window],
                atr_val=atrs[i],
                delta_t=window,
                prev_angle_rad=prev_angle,
                time_idx=i
            )
            prev_angle = vec.angle_rad
        vectors.append(vec)

    return vectors


def compute_trigonometric_adaptive_ma(
    closes: List[float],
    vectors: List[TrigonometricVector],
    fast_period: int = 4,
    slow_period: int = 30
) -> List[float]:
    """
    Média Móvel Adaptativa Trigonométrica (TAMA).
    Modula a constante de suavização alpha com base em sin^2(theta):
    - Mercado lateral (theta ~ 0): sin^2 ~ 0 => alpha lento (filtra ruído).
    - Mercado direcional forte (|theta| > 45 graus): sin^2 > 0.5 => alpha rápido (zero-lag).
    """
    n = min(len(closes), len(vectors))
    if n == 0:
        return []

    alpha_fast = 2.0 / (fast_period + 1)
    alpha_slow = 2.0 / (slow_period + 1)

    tama = [closes[0]]
    for i in range(1, n):
        # A força de aceleração usa o seno ao quadrado (paridade simétrica para alta e baixa)
        sin_sq = vectors[i].sin_theta ** 2
        alpha_t = alpha_slow + (alpha_fast - alpha_slow) * sin_sq
        val = alpha_t * closes[i] + (1.0 - alpha_t) * tama[-1]
        tama.append(round(val, 6))

    return tama


def _classify_angular_regime(
    angle_deg: float,
    accel: float,
    sin_t: float
) -> Tuple[str, str, float]:
    """Classifica o regime direcional e se há exaustão angular."""
    # Ruptura e tendência forte
    if angle_deg > 30.0 and sin_t > 0.50:
        if accel < -0.08:
            return "BUY", "ANGULAR_EXHAUSTION", 0.65  # Subindo mas perdendo ângulo
        return "BUY", "TREND_EXPANSION", 0.90

    if angle_deg < -30.0 and sin_t < -0.50:
        if accel > 0.08:
            return "SELL", "ANGULAR_EXHAUSTION", 0.65 # Caindo mas perdendo inclinação
        return "SELL", "TREND_EXPANSION", 0.90

    return "NONE", "CHOP_FLAT", 0.30


def evaluate_trigonometric_signal(
    vector: TrigonometricVector,
    entropy_val: float,
    tama_val: float,
    close_price: float,
    entropy_thresh: float = 0.75
) -> TrigonometricSignal:
    """
    Avalia se a combinação de geometria trigonométrica cartesiana com entropia
    configura uma oportunidade de alta probabilidade.
    """
    side, regime, base_conf = _classify_angular_regime(
        vector.angle_deg, vector.angular_accel, vector.sin_theta
    )

    # Filtro de congruência com a TAMA e Entropia comprimida
    is_valid_buy = (side == "BUY" and close_price > tama_val and entropy_val <= entropy_thresh)
    is_valid_sell = (side == "SELL" and close_price < tama_val and entropy_val <= entropy_thresh)

    has_sig = is_valid_buy or is_valid_sell
    conf = base_conf if has_sig else 0.0

    return TrigonometricSignal(
        time_idx=vector.time_idx,
        has_signal=has_sig,
        side=side if has_sig else "NONE",
        angle_deg=vector.angle_deg,
        sin_theta=vector.sin_theta,
        cos_theta=vector.cos_theta,
        angular_accel=vector.angular_accel,
        regime=regime,
        confidence=conf
    )
