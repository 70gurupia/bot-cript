"""
Motor Quântico de Entropia de Shannon e Retornos Logarítmicos (Entropy Compounding Engine).
Projetado para aceleração determinística de micro-banca (R$ 500 para R$ 3.000 em 30 dias).
Implementa:
1. Retornos Logarítmicos Aditivos e Desvio Móvel.
2. Entropia Normalizada de Shannon em janela deslizante (SES - Shannon Entropy Squeeze).
3. Transição de Fase e Ruptura Direcional Logarítmica.
4. Relação Risco/Retorno Determinística (Payoff 2.0x a 2.4x).
5. Progressão Geométrica Anti-Martingale com Ratchet Vault nos degraus de R$ 500 a R$ 3.000.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class EntropyEngineConfig:
    """Configuração matemática determinística do motor de entropia."""
    initial_bankroll_brl: float = 500.0
    target_bankroll_brl: float = 3000.0
    days_horizon: int = 30
    entropy_window: int = 24             # Janela deslizante de 24 candles de 1h
    entropy_bins: int = 10               # Discretização da distribuição empírica
    entropy_threshold: float = 0.72      # Limiar de compressão (máximo 1.0)
    z_score_threshold: float = 1.75      # Limiar de choque de volatilidade
    base_risk_pct: float = 0.08          # 8% de risco base da banca por trade
    win_expansion_pct: float = 0.25      # Expansão de +25% no lote após vitória
    max_streak_expansion: int = 3        # Trava de ciclo: realiza lucro na 3ª vitória
    payoff_multiplier: float = 2.0       # Take profit 2x o stop loss
    atr_period: int = 14
    funding_rate_8h: float = 0.0003      # 0,03% de funding médio a cada 8h
    funding_allocation_pct: float = 0.40 # 40% em funding neutro, 60% em trades direcionais


def compute_log_returns(prices: List[float]) -> List[float]:
    """Calcula os retornos logarítmicos estacionários: r_t = ln(P_t / P_{t-1})."""
    if len(prices) < 2:
        return [0.0] * len(prices)
    returns = [0.0]
    for i in range(1, len(prices)):
        p_prev = prices[i - 1]
        p_curr = prices[i]
        r = math.log(p_curr / p_prev) if p_prev > 0 and p_curr > 0 else 0.0
        returns.append(r)
    return returns


def compute_shannon_entropy(returns: List[float], bins_count: int = 10) -> float:
    """Calcula a Entropia de Shannon Normalizada [0, 1] de uma janela de retornos."""
    if len(returns) < bins_count:
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
    ent = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            ent -= p * math.log2(p)

    max_entropy = math.log2(bins_count)
    return ent / max_entropy if max_entropy > 0 else 1.0


def compute_rolling_entropy(
    log_returns: List[float],
    window: int = 24,
    bins_count: int = 10
) -> List[float]:
    """Calcula o vetor de entropia normalizada móvel para toda a série temporal."""
    entropies: List[float] = []
    for i in range(len(log_returns)):
        if i < window:
            entropies.append(1.0)
        else:
            w_slice = log_returns[i - window:i]
            entropies.append(round(compute_shannon_entropy(w_slice, bins_count), 4))
    return entropies


def compute_atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14
) -> List[float]:
    """Calcula o Average True Range (ATR) para balizamento de volatilidade."""
    if not highs or not lows or not closes:
        return []
    atrs = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        atrs.append((atrs[-1] * (period - 1) + tr) / period)
    return atrs


def compute_fast_ema(values: List[float], period: int) -> List[float]:
    """Calcula Média Móvel Exponencial (EMA) rápida."""
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    ema = [values[0]]
    for v in values[1:]:
        ema.append((v * k) + (ema[-1] * (1.0 - k)))
    return ema


def detect_entropy_breakout(
    close_p: float,
    ema50_p: float,
    h_norm: float,
    z_log: float,
    atr: float,
    cfg: EntropyEngineConfig
) -> Tuple[bool, str, float, float]:
    """Identifica gatilho determinístico de entrada após compressão entrópica."""
    if h_norm >= cfg.entropy_threshold:
        return False, "", 0.0, 0.0

    sl_dist = 1.2 * atr
    tp_dist = sl_dist * cfg.payoff_multiplier

    if z_log > cfg.z_score_threshold and close_p > ema50_p:
        return True, "BUY", close_p - sl_dist, close_p + tp_dist

    if z_log < -cfg.z_score_threshold and close_p < ema50_p:
        return True, "SELL", close_p + sl_dist, close_p - tp_dist

    return False, "", 0.0, 0.0


def calculate_compounding_stake(
    bankroll: float,
    streak: int,
    cfg: EntropyEngineConfig
) -> float:
    """Calcula tamanho de lote no Anti-Martingale com expansão geométrica."""
    base_stake = bankroll * cfg.base_risk_pct
    if streak <= 0:
        return max(5.0, base_stake)

    multiplier = (1.0 + cfg.win_expansion_pct) ** streak
    expanded = base_stake * multiplier
    max_cap = bankroll * 0.35
    return max(5.0, min(max_cap, expanded))


def update_monthly_vault(
    total_equity: float,
    vault: float,
    active_bankroll: float
) -> Tuple[float, float]:
    """Aplica o Ratchet Vault para a escalada de R$ 500 a R$ 3.000."""
    milestones = (
        (1000.0, 200.0),
        (1500.0, 450.0),
        (2000.0, 800.0),
        (2500.0, 1250.0)
    )
    for m_target, target_vault in milestones:
        if total_equity >= m_target and vault < target_vault:
            to_add = target_vault - vault
            if active_bankroll > to_add + 20.0:
                vault += to_add
                active_bankroll -= to_add
    return vault, active_bankroll
