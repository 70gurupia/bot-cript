"""
Motor Geométrico e Trigonométrico Adaptativo no Plano Cartesiano Avançado.
Converte velas e séries temporais em coordenadas vetoriais adimensionais (x=tempo, y=preço/ATR),
aplicando física newtoniana e geometria diferencial:
1. Vetor de Tendência Trigonométrica (TVT): ângulo theta, velocidade tan(theta), força sin(theta), inércia cos(theta).
2. Massa de Volume e Força de Momento Linear de Newton: F_y = sin(theta) * m, onde m = V / SMA(V, 20).
3. Geometria Diferencial: Curvatura kappa = |y''| / (1 + y'^2)^(3/2) e Raio de Curvatura R = 1 / kappa.
4. Entropia Não-Extensiva de Tsallis (q = 1.5) para detecção de anomalias em caudas pesadas (fat tails).
5. Entropia Multiescala Fractal (MSE) em janelas rápida, média e lenta.
6. Trailing Stop Dinâmico modularizado pelo cosseno: Stop = ATR * cos(theta).
7. Média Móvel Adaptativa Trigonométrica (TAMA): adapta alfa em função de sin^2(theta).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class TrigonometricVector:
    """Decomposição trigonométrica e newtoniana do vetor de preço no plano cartesiano."""
    time_idx: int
    delta_x: float          # Variação no eixo temporal (barras)
    delta_y_norm: float     # Variação de preço normalizada pelo ATR (adimensional)
    angle_rad: float        # Ângulo theta em radianos [-pi/2, pi/2]
    angle_deg: float        # Ângulo theta em graus [-90, +90]
    sin_theta: float        # Força direcional vertical [-1.0, +1.0]
    cos_theta: float        # Inércia temporal horizontal [0.0, +1.0]
    tan_theta: float        # Velocidade / Inclinação linear (slope = dy/dx)
    angular_accel: float    # Aceleração angular: d_theta / dt
    volume_mass: float      # Massa normalizada: V / SMA(V, 20)
    momentum_force: float   # Força de Momento: F_y = sin(theta) * volume_mass
    curvature: float        # Curvatura diferencial kappa
    radius_of_curvature: float # Raio de curvatura R = 1 / kappa


@dataclass
class TrigonometricSignal:
    """Sinal analítico gerado pela fusão geométrica, newtoniana e entrópica."""
    time_idx: int
    has_signal: bool
    side: str               # "BUY", "SELL" ou "NONE"
    angle_deg: float
    sin_theta: float
    cos_theta: float
    angular_accel: float
    momentum_force: float
    curvature: float
    regime: str             # "TREND_EXPANSION", "ANGULAR_EXHAUSTION", "CHOP_FLAT"
    confidence: float


def compute_tsallis_entropy(
    returns: List[float],
    q: float = 1.5,
    bins_count: int = 10
) -> float:
    """
    Calcula a Entropia de Tsallis Normalizada [0, 1] com índice não-extensivo q.
    S_q = (1 - sum(p_i^q)) / (q - 1)
    """
    if len(returns) < bins_count or math.isclose(q, 1.0, abs_tol=1e-5):
        return 1.0
    min_r = min(returns)
    max_r = max(returns)
    if math.isclose(max_r, min_r, abs_tol=1e-9):
        return 0.0

    bin_width = (max_r - min_r) / bins_count
    counts = [0] * bins_count
    for r in returns:
        idx = min(int((r - min_r) / bin_width), bins_count - 1)
        counts[idx] += 1

    total = len(returns)
    sum_pq = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            sum_pq += p ** q

    sq = (1.0 - sum_pq) / (q - 1.0)
    # Valor máximo teórico com probabilidades uniformes (1/k)
    max_sq = (1.0 - (bins_count ** (1.0 - q))) / (q - 1.0)
    return round(min(1.0, max(0.0, sq / max_sq)), 4) if max_sq > 0 else 1.0


def compute_multiscale_entropy(
    returns: List[float],
    windows: Tuple[int, int, int] = (6, 12, 24)
) -> Dict[str, float]:
    """Calcula a entropia em três escalas temporais fractais (rápida, média e lenta)."""
    scales: Dict[str, float] = {}
    names = ["fast", "medium", "slow"]
    for name, w in zip(names, windows):
        if len(returns) >= w:
            slice_ret = returns[-w:]
            scales[name] = compute_tsallis_entropy(slice_ret, q=1.5)
        else:
            scales[name] = 1.0
    return scales


def compute_dynamic_cosine_stop(
    atr_val: float,
    angle_rad: float,
    base_multiplier: float = 1.5
) -> float:
    """
    Calcula a distância do Stop Loss dinâmico modularizado pelo cosseno:
    StopDistance = ATR * base_multiplier * max(0.40, cos(theta))
    Conforme o ângulo sobe verticalmente, o stop se aproxima da vela, protegendo lucros.
    """
    cos_val = math.cos(angle_rad)
    effective_cos = max(0.40, abs(cos_val))
    return round(atr_val * base_multiplier * effective_cos, 4)


def _compute_curvature(slope: float, prev_slope: float, delta_t: float) -> Tuple[float, float]:
    """Calcula a curvatura kappa e o raio de curvatura da trajetória do preço."""
    y_second_deriv = (slope - prev_slope) / delta_t
    denominator = (1.0 + slope ** 2) ** 1.5
    kappa = abs(y_second_deriv) / denominator if denominator > 0 else 0.0
    radius = 1.0 / max(kappa, 1e-6)
    return round(kappa, 6), round(radius, 2)


def compute_normalized_cartesian_vector(
    p_curr: float,
    p_prev: float,
    atr_val: float,
    delta_t: int = 14,
    prev_angle_rad: float = 0.0,
    prev_slope: float = 0.0,
    volume_mass: float = 1.0,
    time_idx: int = 0
) -> TrigonometricVector:
    """Mapeia o vetor de preço no plano cartesiano normalizado com momento newtoniano."""
    safe_atr = max(atr_val, 1e-6)
    safe_dx = max(delta_t, 1)

    dy_norm = (p_curr - p_prev) / safe_atr
    slope = dy_norm / float(safe_dx)

    angle_rad = math.atan(slope)
    angle_deg = math.degrees(angle_rad)

    sin_t = math.sin(angle_rad)
    cos_t = math.cos(angle_rad)
    accel = angle_rad - prev_angle_rad
    momentum = sin_t * volume_mass
    kappa, radius = _compute_curvature(slope, prev_slope, float(safe_dx))

    return TrigonometricVector(
        time_idx=time_idx,
        delta_x=float(safe_dx),
        delta_y_norm=round(dy_norm, 4),
        angle_rad=round(angle_rad, 5),
        angle_deg=round(angle_deg, 2),
        sin_theta=round(sin_t, 4),
        cos_theta=round(cos_t, 4),
        tan_theta=round(slope, 4),
        angular_accel=round(accel, 5),
        volume_mass=round(volume_mass, 3),
        momentum_force=round(momentum, 4),
        curvature=kappa,
        radius_of_curvature=radius
    )


def compute_series_trigonometric_vectors(
    closes: List[float],
    atrs: List[float],
    volumes: Optional[List[float]] = None,
    window: int = 14
) -> List[TrigonometricVector]:
    """Calcula a evolução dos vetores trigonométricos e newtonianos para toda a série."""
    if len(closes) != len(atrs) or len(closes) < window:
        return []

    # Se volumes forem fornecidos, calcula a média móvel de 20 períodos para massa m
    v_mass = [1.0] * len(closes)
    if volumes and len(volumes) == len(closes):
        sma_vol = closes[0]
        for i in range(len(volumes)):
            if i >= 20:
                v_slice = volumes[i - 20:i]
                mean_v = sum(v_slice) / 20.0
                v_mass[i] = (volumes[i] / mean_v) if mean_v > 0 else 1.0

    vectors: List[TrigonometricVector] = []
    prev_angle = 0.0
    prev_slope = 0.0

    for i in range(len(closes)):
        if i < window:
            vec = TrigonometricVector(
                time_idx=i, delta_x=float(window), delta_y_norm=0.0,
                angle_rad=0.0, angle_deg=0.0, sin_theta=0.0,
                cos_theta=1.0, tan_theta=0.0, angular_accel=0.0,
                volume_mass=1.0, momentum_force=0.0, curvature=0.0,
                radius_of_curvature=10000.0
            )
        else:
            vec = compute_normalized_cartesian_vector(
                p_curr=closes[i],
                p_prev=closes[i - window],
                atr_val=atrs[i],
                delta_t=window,
                prev_angle_rad=prev_angle,
                prev_slope=prev_slope,
                volume_mass=v_mass[i],
                time_idx=i
            )
            prev_angle = vec.angle_rad
            prev_slope = vec.tan_theta
        vectors.append(vec)

    return vectors


def compute_trigonometric_adaptive_ma(
    closes: List[float],
    vectors: List[TrigonometricVector],
    fast_period: int = 4,
    slow_period: int = 30
) -> List[float]:
    """Média Móvel Adaptativa Trigonométrica (TAMA) ponderada por sin^2(theta)."""
    n = min(len(closes), len(vectors))
    if n == 0:
        return []

    alpha_fast = 2.0 / (fast_period + 1)
    alpha_slow = 2.0 / (slow_period + 1)

    tama = [closes[0]]
    for i in range(1, n):
        sin_sq = vectors[i].sin_theta ** 2
        alpha_t = alpha_slow + (alpha_fast - alpha_slow) * sin_sq
        val = alpha_t * closes[i] + (1.0 - alpha_t) * tama[-1]
        tama.append(round(val, 6))

    return tama


def _classify_angular_regime(
    angle_deg: float,
    accel: float,
    sin_t: float,
    momentum: float
) -> Tuple[str, str, float]:
    """Classifica o regime direcional considerando momentum newtoniano e exaustão."""
    # Ruptura de Alta com Força Real de Momento
    if angle_deg > 28.0 and sin_t > 0.45:
        if accel < -0.08:
            return "BUY", "ANGULAR_EXHAUSTION", 0.60
        conf = 0.95 if momentum > 0.65 else 0.80
        return "BUY", "TREND_EXPANSION", conf

    # Ruptura de Baixa com Força Real de Momento
    if angle_deg < -28.0 and sin_t < -0.45:
        if accel > 0.08:
            return "SELL", "ANGULAR_EXHAUSTION", 0.60
        conf = 0.95 if momentum < -0.65 else 0.80
        return "SELL", "TREND_EXPANSION", conf

    return "NONE", "CHOP_FLAT", 0.30


def evaluate_trigonometric_signal(
    vector: TrigonometricVector,
    entropy_val: float,
    tama_val: float,
    close_price: float,
    entropy_thresh: float = 0.75
) -> TrigonometricSignal:
    """Avalia o sinal integrando geometria analítica, volume newtoniano e entropia."""
    side, regime, base_conf = _classify_angular_regime(
        vector.angle_deg, vector.angular_accel, vector.sin_theta, vector.momentum_force
    )

    # Congruência com a TAMA e Entropia Comprimida
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
        momentum_force=vector.momentum_force,
        curvature=vector.curvature,
        regime=regime,
        confidence=conf
    )
