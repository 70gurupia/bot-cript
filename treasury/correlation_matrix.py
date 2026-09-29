"""
Matriz de Covariância e Filtro de Descorrelação de Ativos (Fase 5).
Calcula correlação estatística de Pearson entre pares e impede sobre-exposição
em ativos correlacionados na mesma direção (limiar de corte de 0.70).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


@dataclass
class OrderProposal:
    """Proposta de ordem gerada por um agente para avaliação da Tesouraria."""
    agent_id: str
    symbol: str
    side: str  # "BUY" (Long) ou "SELL" (Short)
    requested_amount_usd: float
    agent_sharpe_ratio: float
    stop_loss_pct: float
    leverage: float = 1.0


def calculate_pearson_correlation(series_a: List[float], series_b: List[float]) -> float:
    """Calcula o coeficiente de correlacao de Pearson entre duas series temporais."""
    n = min(len(series_a), len(series_b))
    if n < 5:
        return 0.0

    sub_a = series_a[-n:]
    sub_b = series_b[-n:]

    mean_a = sum(sub_a) / n
    mean_b = sum(sub_b) / n

    cov = sum((sub_a[i] - mean_a) * (sub_b[i] - mean_b) for i in range(n))
    var_a = sum((sub_a[i] - mean_a) ** 2 for i in range(n))
    var_b = sum((sub_b[i] - mean_b) ** 2 for i in range(n))

    denominator = math.sqrt(var_a * var_b)
    if denominator < 1e-9:
        return 0.0

    r = cov / denominator
    return round(max(-1.0, min(1.0, r)), 4)


class AssetCorrelationTracker:
    """Rastreador e validador de correlacoes entre ativos operados."""

    def __init__(self, correlation_threshold: float = 0.70):
        self.correlation_threshold = correlation_threshold
        self.price_history: Dict[str, List[float]] = {}
        self.returns_history: Dict[str, List[float]] = {}

    def update_history(self, symbol: str, returns_or_prices: List[float], is_returns: bool = True) -> None:
        """Atualiza a serie historica de um ativo."""
        if is_returns:
            self.returns_history[symbol] = list(returns_or_prices)
        else:
            self.price_history[symbol] = list(returns_or_prices)
            # Converte precos em retornos percentuais
            if len(returns_or_prices) >= 2:
                rets = [
                    (returns_or_prices[i] - returns_or_prices[i - 1]) / returns_or_prices[i - 1]
                    for i in range(1, len(returns_or_prices))
                ]
                self.returns_history[symbol] = rets

    def get_correlation(self, symbol_a: str, symbol_b: str) -> float:
        """Obtem a correlacao entre dois simbolos."""
        if symbol_a == symbol_b:
            return 1.0

        hist_a = self.returns_history.get(symbol_a, [])
        hist_b = self.returns_history.get(symbol_b, [])

        if not hist_a or not hist_b:
            return 0.0

        return calculate_pearson_correlation(hist_a, hist_b)

    def is_highly_correlated(self, symbol_a: str, symbol_b: str) -> bool:
        """Verifica se dois ativos excedem o limiar de correlacao."""
        r = self.get_correlation(symbol_a, symbol_b)
        return abs(r) >= self.correlation_threshold

    def filter_concurrent_orders(
        self,
        proposals: List[OrderProposal],
        active_symbols_in_portfolio: List[str]
    ) -> Tuple[List[OrderProposal], List[Tuple[OrderProposal, str]]]:
        """
        Filtra propostas concorrentes. Se uma ordem tiver correlacao > 0.70
        com uma ordem de maior prioridade (Sharpe) ou com ativo ja aberto, eh rejeitada.
        """
        # Ordena propostas pelo Sharpe ratio do agente de forma decrescente
        sorted_proposals = sorted(proposals, key=lambda p: p.agent_sharpe_ratio, reverse=True)

        accepted: List[OrderProposal] = []
        rejected: List[Tuple[OrderProposal, str]] = []
        approved_symbols = list(active_symbols_in_portfolio)

        for prop in sorted_proposals:
            conflict_found = False
            for active_sym in approved_symbols:
                corr = self.get_correlation(prop.symbol, active_sym)
                if abs(corr) >= self.correlation_threshold:
                    rejected.append((
                        prop,
                        f"Correlacao excessiva ({corr:.2f}) com {active_sym} (teto {self.correlation_threshold:.2f})"
                    ))
                    conflict_found = True
                    break

            if not conflict_found:
                accepted.append(prop)
                approved_symbols.append(prop.symbol)

        return accepted, rejected
