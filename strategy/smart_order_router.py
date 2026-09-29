"""
Roteador Inteligente de Execução Passiva (Smart Order Router),
Microestrutura de Livro de Ofertas (Order Book Imbalance - OBI),
Filtro de Sentimento por Taxa de Financiamento (Funding Sentiment) e
Calibração Walk-Forward Adaptativa.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class OrderBookLevel:
    """Nível de preço e volume no livro de ofertas."""
    price: float
    volume: float


@dataclass
class OrderBookSnapshot:
    """Instantâneo dos primeiros níveis do livro de ofertas."""
    symbol: str
    timestamp_ms: int
    bids: List[OrderBookLevel]  # Compras ordenadas de maior para menor preço
    asks: List[OrderBookLevel]  # Vendas ordenadas de menor para maior preço


@dataclass
class ExecutionPlan:
    """Plano determinístico de execução com garantia Maker (Post-Only)."""
    symbol: str
    side: str
    target_price: float
    order_type: str            # "LIMIT_MAKER_POST_ONLY"
    size: float
    expected_fee_pct: float    # 0.02% para Maker vs 0.04% para Taker
    estimated_fee_savings_brl: float
    max_slippage_tolerance: float
    cancel_threshold_price: float


def compute_order_book_imbalance(
    snapshot: OrderBookSnapshot,
    depth_levels: int = 10
) -> float:
    """
    Calcula o Desequilíbrio do Livro de Ofertas (Order Book Imbalance - OBI):
    OBI = (Sum(BidVol) - Sum(AskVol)) / (Sum(BidVol) + Sum(AskVol))
    Retorna valor no intervalo [-1.0, +1.0]:
    - OBI > +0.30: Pressão compradora forte.
    - OBI < -0.30: Pressão vendedora forte.
    """
    safe_depth = max(1, depth_levels)
    bid_vol = sum(lvl.volume for lvl in snapshot.bids[:safe_depth])
    ask_vol = sum(lvl.volume for lvl in snapshot.asks[:safe_depth])
    tot_vol = bid_vol + ask_vol

    if tot_vol <= 0.0:
        return 0.0
    return round((bid_vol - ask_vol) / tot_vol, 4)


def evaluate_funding_sentiment(
    funding_rate_8h: float,
    threshold: float = 0.0005  # 0.05% por 8h (aprox 54% ao ano)
) -> Tuple[str, bool, bool]:
    """
    Analisa o sentimento do mercado derivado da taxa de financiamento dos perpétuos:
    Retorna: (regime, can_buy, can_sell)
    """
    if funding_rate_8h >= threshold:
        # Longs pagam shorts excessivamente -> Risco de Long Squeeze
        return "BULLISH_OVERHEATED", False, True

    if funding_rate_8h <= -threshold:
        # Shorts pagam longs excessivamente -> Risco de Short Squeeze
        return "BEARISH_OVERHEATED", True, False

    return "NEUTRAL_BALANCED", True, True


def calculate_maker_execution_price(
    side: str,
    best_bid: float,
    best_ask: float,
    tick_size: float = 0.01
) -> float:
    """Calcula o preço limite ótimo para garantir execução passiva (Maker Post-Only)."""
    spread = best_ask - best_bid
    if spread <= tick_size:
        return best_bid if side == "BUY" else best_ask

    # Entra um tick acima do best bid ou um tick abaixo do best ask para prioridade na fila
    if side == "BUY":
        return round(best_bid + tick_size, 4)
    return round(best_ask - tick_size, 4)


def create_smart_execution_plan(
    symbol: str,
    side: str,
    size: float,
    best_bid: float,
    best_ask: float,
    atr_val: float,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0004
) -> ExecutionPlan:
    """Gera um plano de execução inteligente com economia de taxas e trava de slippage."""
    target_p = calculate_maker_execution_price(side, best_bid, best_ask)
    order_val = size * target_p
    fee_savings = order_val * (taker_fee - maker_fee)

    # Tolerância máxima de fuga de preço: 0.20 ATR
    cancel_offset = max(0.20 * atr_val, target_p * 0.002)
    cancel_p = target_p + cancel_offset if side == "BUY" else target_p - cancel_offset

    return ExecutionPlan(
        symbol=symbol,
        side=side,
        target_price=target_p,
        order_type="LIMIT_MAKER_POST_ONLY",
        size=size,
        expected_fee_pct=round(maker_fee * 100.0, 3),
        estimated_fee_savings_brl=round(fee_savings, 4),
        max_slippage_tolerance=round(cancel_offset, 4),
        cancel_threshold_price=round(cancel_p, 4)
    )


def calibrate_walk_forward_thresholds(
    recent_log_returns: List[float],
    base_angle_deg: float = 28.0,
    base_entropy_thresh: float = 0.75
) -> Tuple[float, float]:
    """
    Calibra dinamicamente os limiares com base na volatilidade realizada recente:
    - Alta volatilidade recente -> Aumenta ângulo (mais exigente para filtrar ruído).
    - Baixa volatilidade recente -> Diminui ligeiramente o ângulo para não perder alinhamento.
    """
    if len(recent_log_returns) < 20:
        return base_angle_deg, base_entropy_thresh

    mean_r = sum(recent_log_returns) / len(recent_log_returns)
    var_r = sum((x - mean_r) ** 2 for x in recent_log_returns) / len(recent_log_returns)
    realized_vol = math.sqrt(var_r)

    # Volatilidade de referência normal: ~0.008 (0.8% por barra)
    vol_ratio = realized_vol / 0.008 if realized_vol > 0 else 1.0
    vol_ratio = max(0.70, min(1.40, vol_ratio))

    calibrated_angle = round(base_angle_deg * vol_ratio, 1)
    calibrated_entropy = round(base_entropy_thresh / (vol_ratio ** 0.5), 2)

    return calibrated_angle, min(0.85, max(0.65, calibrated_entropy))
