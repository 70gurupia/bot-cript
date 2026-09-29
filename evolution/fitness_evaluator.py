"""
Avaliador Estatístico de Aptidão Multi-Objetivo (Fitness Evaluator).
Implementa métricas de risco e retorno (Sharpe, Sortino, Calmar, Drawdown, Profit Factor)
e calcula a nota de aptidão para a incubadora evolutiva.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import List, Optional


HOURLY_ANNUALIZATION_FACTOR = math.sqrt(365 * 24)  # ~93.59487
FIFTEEN_MIN_ANNUALIZATION_FACTOR = math.sqrt(365 * 24 * 4)  # ~187.18974


@dataclass
class TradeRecord:
    """Registro individual de operacao concluida."""
    entry_time: float
    exit_time: float
    entry_price: float
    exit_price: float
    side: str
    size: float
    pnl_abs: float
    pnl_pct: float
    fee_paid: float = 0.0


@dataclass
class PerformanceReport:
    """Relatorio consolidado de metricas estatisticas e nota de aptidao."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    total_return_pct: float
    fitness_score: float
    passed_graduation: bool


# ==============================================================================
# FUNÇÕES DE CÁLCULO ESTATÍSTICO PURO
# ==============================================================================

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    annualization_factor: Optional[float] = None
) -> float:
    """Calcula o Sharpe Ratio anualizado a partir dos retornos periodicos."""
    if not returns or len(returns) < 2:
        return 0.0
    factor = annualization_factor if annualization_factor is not None else HOURLY_ANNUALIZATION_FACTOR
    if HAS_NUMPY:
        arr = np.asarray(returns, dtype=float)
        mean_ret = float(np.mean(arr))
        std_dev = float(np.std(arr, ddof=1))
    else:
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
    if std_dev < 1e-9:
        return 0.0
    return ((mean_ret - risk_free_rate) / std_dev) * factor


def calculate_sortino_ratio(
    returns: List[float],
    target_return: float = 0.0,
    annualization_factor: Optional[float] = None
) -> float:
    """Calcula o Sortino Ratio anualizado considerando apenas volatilidade negativa."""
    if not returns or len(returns) < 2:
        return 0.0
    factor = annualization_factor if annualization_factor is not None else HOURLY_ANNUALIZATION_FACTOR
    if HAS_NUMPY:
        arr = np.asarray(returns, dtype=float)
        mean_ret = float(np.mean(arr))
        downside = np.minimum(0.0, arr - target_return)
        downside_std = float(np.sqrt(np.mean(downside ** 2)))
    else:
        mean_ret = sum(returns) / len(returns)
        negative_deviations = [min(0.0, r - target_return) ** 2 for r in returns]
        downside_variance = sum(negative_deviations) / len(returns)
        downside_std = math.sqrt(downside_variance)
    if downside_std < 1e-9:
        return 0.0
    return ((mean_ret - target_return) / downside_std) * factor


def calculate_max_drawdown(equity_curve: List[float]) -> float:
    """Calcula o rebaixamento maximo percentual (pico a vale)."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    if HAS_NUMPY:
        arr = np.asarray(equity_curve, dtype=float)
        peaks = np.maximum.accumulate(arr)
        valid_mask = peaks > 0
        if not np.any(valid_mask):
            return 0.0
        drawdowns = np.where(valid_mask, (peaks - arr) / peaks, 0.0)
        return float(np.max(drawdowns)) * 100.0

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd * 100.0


def calculate_calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
    """Calcula o Calmar Ratio (Retorno Anualizado / Max Drawdown)."""
    if max_drawdown <= 1e-6:
        return 0.0
    return annualized_return / max_drawdown


def _sum_profits_and_losses(trades: List[TradeRecord]) -> tuple[float, float, int, int]:
    """Calcula somatorio de lucros, perdas e contagem de trades vencedores e perdedores."""
    gross_profit = 0.0
    gross_loss = 0.0
    wins = 0
    losses = 0
    for t in trades:
        net_pnl = t.pnl_abs - t.fee_paid
        if net_pnl > 0:
            gross_profit += net_pnl
            wins += 1
        elif net_pnl < 0:
            gross_loss += abs(net_pnl)
            losses += 1
    return gross_profit, gross_loss, wins, losses


def calculate_profit_factor(trades: List[TradeRecord]) -> float:
    """Calcula a razao entre lucro bruto e prejuizo bruto (Profit Factor)."""
    if not trades:
        return 0.0
    gross_profit, gross_loss, _, _ = _sum_profits_and_losses(trades)
    if gross_loss == 0.0:
        return 10.0 if gross_profit > 0 else 0.0
    return min(10.0, gross_profit / gross_loss)


def calculate_win_rate(trades: List[TradeRecord]) -> float:
    """Calcula a taxa de acerto percentual (de 0.0 a 1.0)."""
    if not trades:
        return 0.0
    _, _, wins, _ = _sum_profits_and_losses(trades)
    return wins / len(trades)


# ==============================================================================
# NORMALIZAÇÕES E FUNÇÃO DE APTIDÃO MULTI-OBJETIVO
# ==============================================================================

def _normalize_sharpe(sharpe: float) -> float:
    """Normaliza o Sharpe Ratio para escala entre 0.0 e 1.0 (saturando em 3.0)."""
    return max(0.0, min(1.0, sharpe / 3.0))


def _normalize_sortino(sortino: float) -> float:
    """Normaliza o Sortino Ratio para escala entre 0.0 e 1.0 (saturando em 4.0)."""
    return max(0.0, min(1.0, sortino / 4.0))


def _normalize_drawdown_score(max_drawdown: float) -> float:
    """Calcula a pontuacao de drawdown. Acima de 8% zera imediatamente."""
    if max_drawdown > 8.0:
        return 0.0
    return max(0.0, (8.0 - max_drawdown) / 8.0)


def _normalize_profit_factor(pf: float) -> float:
    """Normaliza o Profit Factor para escala entre 0.0 e 1.0 (neutro em 1.0, maximo em 3.0)."""
    if pf <= 1.0:
        return 0.0
    return min(1.0, (pf - 1.0) / 2.0)


def calculate_fitness_score(
    sharpe: float,
    sortino: float,
    max_drawdown: float,
    profit_factor: float
) -> float:
    """
    Calcula a pontuacao composta de aptidao segundo a especificacao:
    Fitness = (0.35 * Sharpe_norm) + (0.25 * Sortino_norm) +
              (0.20 * DrawdownScore) + (0.20 * ProfitFactor_norm)
    Regra invariante: Drawdown superior a 8% resulta em fitness zero.
    """
    if max_drawdown > 8.0:
        return 0.0

    s_norm = _normalize_sharpe(sharpe)
    so_norm = _normalize_sortino(sortino)
    dd_score = _normalize_drawdown_score(max_drawdown)
    pf_norm = _normalize_profit_factor(profit_factor)

    fitness = (0.35 * s_norm) + (0.25 * so_norm) + (0.20 * dd_score) + (0.20 * pf_norm)
    return round(max(0.0, min(1.0, fitness)), 6)


# ==============================================================================
# AVALIADOR COMPLETO DE PERFORMANCE
# ==============================================================================

def evaluate_strategy_performance(
    trades: List[TradeRecord],
    returns: List[float],
    equity_curve: List[float],
    annualization_factor: Optional[float] = None
) -> PerformanceReport:
    """Gera o relatorio completo de performance e verifica criterios de graduacao."""
    gross_profit, gross_loss, wins, losses = _sum_profits_and_losses(trades)
    total_trades = len(trades)
    win_rate = wins / total_trades if total_trades > 0 else 0.0

    if gross_loss == 0.0:
        profit_factor = 10.0 if gross_profit > 0 else 0.0
    else:
        profit_factor = min(10.0, gross_profit / gross_loss)

    sharpe = calculate_sharpe_ratio(returns, annualization_factor=annualization_factor)
    sortino = calculate_sortino_ratio(returns, annualization_factor=annualization_factor)
    max_dd = calculate_max_drawdown(equity_curve)

    initial_capital = equity_curve[0] if (equity_curve and equity_curve[0] > 0.0) else 1.0
    final_capital = equity_curve[-1] if equity_curve else initial_capital
    total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100.0

    calmar = calculate_calmar_ratio(total_return_pct, max_dd)
    fitness = calculate_fitness_score(sharpe, sortino, max_dd, profit_factor)

    # Criterios de graduacao da incubadora:
    # 1. Minimo de 30 trades fechados
    # 2. Sharpe Ratio >= 1.25
    # 3. Drawdown maximo <= 4.5%
    passed = (total_trades >= 30) and (sharpe >= 1.25) and (max_dd <= 4.5)

    return PerformanceReport(
        total_trades=total_trades,
        winning_trades=wins,
        losing_trades=losses,
        win_rate=win_rate,
        profit_factor=profit_factor,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=max_dd,
        total_return_pct=total_return_pct,
        fitness_score=fitness,
        passed_graduation=passed
    )
