"""
Controlador da Tesouraria Central (Fase 5).
Gerencia a alocação de capital da carteira, dimensionamento fracionário de Kelly (20%),
teto de alavancagem de 3x, margem isolada inviolável e teto agregado de 70% de exposição.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from config.settings import settings
from treasury.correlation_matrix import AssetCorrelationTracker, OrderProposal


@dataclass
class OrderValidationResult:
    """Resultado detalhado da auditoria de risco da ordem pela Tesouraria."""
    approved: bool
    adjusted_amount_usd: float
    adjusted_leverage: float
    rejection_reason: Optional[str] = None
    risk_metrics: Optional[Dict[str, Any]] = None


class TreasuryController:
    """Banco central interno do ecossistema de trading."""

    def __init__(
        self,
        fractional_kelly: float = 0.20,
        max_leverage: float = 3.0,
        max_portfolio_exposure_pct: float = 0.70,
        max_single_asset_exposure_pct: float = 0.25,
        max_single_trade_risk_pct: float = 0.01,
        correlation_tracker: Optional[AssetCorrelationTracker] = None
    ):
        self.fractional_kelly = fractional_kelly
        self.max_leverage = min(max_leverage, settings.risk_limits.max_leverage_ceiling)
        self.max_portfolio_exposure_pct = max_portfolio_exposure_pct
        self.max_single_asset_exposure_pct = max_single_asset_exposure_pct
        self.max_single_trade_risk_pct = max_single_trade_risk_pct
        self.correlation_tracker = correlation_tracker or AssetCorrelationTracker()

    def calculate_fractional_kelly(
        self,
        win_rate: float,
        win_loss_ratio: float
    ) -> float:
        """Calcula o dimensionamento fracionario pelo Criterio de Kelly (20%)."""
        if win_loss_ratio <= 0.0 or win_rate <= 0.0 or win_rate >= 1.0:
            return 0.0
        p = win_rate
        q = 1.0 - p
        b = win_loss_ratio
        kelly_full = (p * b - q) / b
        if kelly_full <= 0.0:
            return 0.0
        # Impõe teto estrito de no maximo fractional_kelly (fator de seguranca contra ruina)
        return min(self.fractional_kelly, kelly_full * self.fractional_kelly)

    def calculate_position_size(
        self,
        total_equity: float,
        agent_allocated_capital: float,
        win_rate: float,
        win_loss_ratio: float,
        stop_loss_pct: float
    ) -> float:
        """Calcula tamanho de lote seguro combinando Kelly, trava de risco de 1% e teto por ativo."""
        # 1. Dimensionamento por Kelly fracionario
        k_frac = self.calculate_fractional_kelly(win_rate, win_loss_ratio)
        kelly_notional = agent_allocated_capital * k_frac

        # 2. Trava de risco maximo: perda monetaria no stop loss <= 1% do capital do agente
        max_risk_usd = agent_allocated_capital * self.max_single_trade_risk_pct
        effective_sl = max(0.005, stop_loss_pct)
        risk_limited_notional = max_risk_usd / effective_sl

        # 3. Teto maximo em ativo individual (25% do saldo total da carteira)
        asset_ceiling = total_equity * self.max_single_asset_exposure_pct

        # Seleciona o mais conservador
        selected_size = min(kelly_notional, risk_limited_notional, asset_ceiling)
        return round(max(0.0, selected_size), 2)

    def _check_invariants(
        self,
        margin_type: str,
        leverage: float,
        stop_loss_pct: float
    ) -> Optional[str]:
        """Valida invariantes de seguranca de margem, alavancagem e protecao de stop."""
        if margin_type.upper() != "ISOLATED":
            return "Margem rejeitada: apenas modalidade ISOLATED e permitida."
        if leverage > self.max_leverage:
            return f"Alavancagem ({leverage}x) excede teto maximo permitido ({self.max_leverage}x)."
        if stop_loss_pct <= 0.001:
            return "Ordem rejeitada: presenca de Stop Loss obrigatorio nao informada."
        return None

    def _check_portfolio_capacity(
        self,
        requested_notional: float,
        total_equity: float,
        current_aggregate_exposure: float,
        symbol: str,
        current_symbol_exposure: float
    ) -> Tuple[bool, float, Optional[str]]:
        """Verifica e ajusta capacidade agregada e por ativo individual."""
        max_aggregate_usd = total_equity * self.max_portfolio_exposure_pct
        available_aggregate = max_aggregate_usd - current_aggregate_exposure
        if available_aggregate <= 0.0:
            return False, 0.0, f"Exposicao agregada excedeu teto de {self.max_portfolio_exposure_pct * 100:.0f}% da carteira."

        max_asset_usd = total_equity * self.max_single_asset_exposure_pct
        available_asset = max_asset_usd - current_symbol_exposure
        if available_asset <= 0.0:
            return False, 0.0, f"Exposicao no ativo {symbol} excedeu teto de {self.max_single_asset_exposure_pct * 100:.0f}%."

        adjusted_amount = min(requested_notional, available_aggregate, available_asset)
        if adjusted_amount < 10.0:
            return False, 0.0, "Saldo disponivel insuficiente para tamanho minimo de ordem ($10)."

        return True, round(adjusted_amount, 2), None

    def evaluate_order(
        self,
        proposal: OrderProposal,
        total_equity: float,
        current_aggregate_exposure: float,
        current_symbol_exposure: float,
        active_portfolio_symbols: List[str],
        margin_type: str = "ISOLATED"
    ) -> OrderValidationResult:
        """Audita uma proposta de ordem contra todas as politicas de risco da Tesouraria."""
        # 1. Checagem de invariantes estruturais
        inv_error = self._check_invariants(margin_type, proposal.leverage, proposal.stop_loss_pct)
        if inv_error:
            return OrderValidationResult(False, 0.0, 1.0, rejection_reason=inv_error)

        # 2. Checagem de filtro de descorrelacao
        for active_sym in active_portfolio_symbols:
            if active_sym != proposal.symbol and self.correlation_tracker.is_highly_correlated(proposal.symbol, active_sym):
                corr = self.correlation_tracker.get_correlation(proposal.symbol, active_sym)
                return OrderValidationResult(
                    False, 0.0, 1.0,
                    rejection_reason=f"Ordem bloqueada: correlacao excessiva ({corr:.2f}) com ativo ativo {active_sym}."
                )

        # 3. Checagem de capacidade de exposicao
        allowed, adj_amount, cap_error = self._check_portfolio_capacity(
            proposal.requested_amount_usd,
            total_equity,
            current_aggregate_exposure,
            proposal.symbol,
            current_symbol_exposure
        )
        if not allowed:
            return OrderValidationResult(False, 0.0, 1.0, rejection_reason=cap_error)

        safe_leverage = min(proposal.leverage, self.max_leverage)
        metrics = {
            "requested_usd": proposal.requested_amount_usd,
            "approved_usd": adj_amount,
            "leverage": safe_leverage,
            "aggregate_exposure_after": current_aggregate_exposure + adj_amount
        }
        return OrderValidationResult(
            approved=True,
            adjusted_amount_usd=adj_amount,
            adjusted_leverage=safe_leverage,
            risk_metrics=metrics
        )
