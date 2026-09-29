"""
Suíte de Testes da Tesouraria Central e Gestão de Risco (Fase 5).
Valida dimensionamento por Kelly Fracionário (20%), trava de 1% de risco,
teto de alavancagem de 3x, margem isolada obrigatória e filtro de correlação.
"""

import sys
import os

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from treasury.correlation_matrix import (
    AssetCorrelationTracker,
    OrderProposal,
    calculate_pearson_correlation
)
from treasury.treasury_controller import TreasuryController, OrderValidationResult


def test_fractional_kelly_and_position_sizing():
    """Valida dimensionamento fracionario de Kelly (20%) e trava de risco de 1%."""
    treasury = TreasuryController(fractional_kelly=0.20)

    # 1. Cenario lucrativo: 60% win rate, payoff 2:1
    k_frac = treasury.calculate_fractional_kelly(win_rate=0.60, win_loss_ratio=2.0)
    assert 0.0 < k_frac <= 0.20, f"Kelly fracionario fora do limite seguro: {k_frac}"

    # 2. Cenario com expectativa negativa: 30% win rate, payoff 1:1 -> Kelly deve ser zero
    k_zero = treasury.calculate_fractional_kelly(win_rate=0.30, win_loss_ratio=1.0)
    assert k_zero == 0.0, "Kelly deve ser zero para expectativa negativa"

    # 3. Calculo de tamanho de posicao com trava de 1% de risco
    # Saldo total: $10.000, capital alocado ao agente: $2.000
    # Stop Loss de 2% (0.02)
    # Risco maximo em $ = $2.000 * 0.01 = $20.0
    # Tamanho maximo permitido pelo risco = $20.0 / 0.02 = $1.000
    size = treasury.calculate_position_size(
        total_equity=10000.0,
        agent_allocated_capital=2000.0,
        win_rate=0.60,
        win_loss_ratio=2.0,
        stop_loss_pct=0.02
    )
    assert size <= 1000.0, f"Tamanho da posicao excedeu trava de 1% de risco: {size}"
    assert size > 0.0


def test_leverage_and_margin_invariants():
    """Valida rejeicao de alavancagem acima de 3x e bloqueio de margem CROSS."""
    treasury = TreasuryController(max_leverage=3.0)

    # 1. Proposta com alavancagem 5x (acima de 3x) -> REJEITADA
    prop_high_lev = OrderProposal(
        agent_id="agent_1",
        symbol="BTC/USDT",
        side="BUY",
        requested_amount_usd=500.0,
        agent_sharpe_ratio=1.5,
        stop_loss_pct=0.02,
        leverage=5.0
    )
    res_lev = treasury.evaluate_order(
        proposal=prop_high_lev,
        total_equity=10000.0,
        current_aggregate_exposure=1000.0,
        current_symbol_exposure=0.0,
        active_portfolio_symbols=[],
        margin_type="ISOLATED"
    )
    assert res_lev.approved is False
    assert "excede teto maximo permitido" in res_lev.rejection_reason

    # 2. Proposta com margem CROSS -> REJEITADA
    prop_cross = OrderProposal(
        agent_id="agent_1",
        symbol="BTC/USDT",
        side="BUY",
        requested_amount_usd=500.0,
        agent_sharpe_ratio=1.5,
        stop_loss_pct=0.02,
        leverage=2.0
    )
    res_cross = treasury.evaluate_order(
        proposal=prop_cross,
        total_equity=10000.0,
        current_aggregate_exposure=1000.0,
        current_symbol_exposure=0.0,
        active_portfolio_symbols=[],
        margin_type="CROSS"
    )
    assert res_cross.approved is False
    assert "apenas modalidade ISOLATED" in res_cross.rejection_reason

    # 3. Proposta sem Stop Loss -> REJEITADA
    prop_no_sl = OrderProposal(
        agent_id="agent_1",
        symbol="BTC/USDT",
        side="BUY",
        requested_amount_usd=500.0,
        agent_sharpe_ratio=1.5,
        stop_loss_pct=0.0,
        leverage=2.0
    )
    res_no_sl = treasury.evaluate_order(
        proposal=prop_no_sl,
        total_equity=10000.0,
        current_aggregate_exposure=1000.0,
        current_symbol_exposure=0.0,
        active_portfolio_symbols=[],
        margin_type="ISOLATED"
    )
    assert res_no_sl.approved is False
    assert "Stop Loss" in res_no_sl.rejection_reason


def test_portfolio_aggregate_exposure_ceiling():
    """Valida que a exposicao agregada nunca ultrapassa o teto de 70%."""
    treasury = TreasuryController(max_portfolio_exposure_pct=0.70)

    # Carteira de $10.000, ja exposta em $6.500 (65%)
    # Restam apenas $500 para atingir o teto de $7.000 (70%)
    prop = OrderProposal(
        agent_id="agent_1",
        symbol="SOL/USDT",
        side="BUY",
        requested_amount_usd=1000.0,  # Pede $1000
        agent_sharpe_ratio=1.5,
        stop_loss_pct=0.02,
        leverage=1.0
    )
    res = treasury.evaluate_order(
        proposal=prop,
        total_equity=10000.0,
        current_aggregate_exposure=6500.0,
        current_symbol_exposure=0.0,
        active_portfolio_symbols=[],
        margin_type="ISOLATED"
    )
    assert res.approved is True
    # O valor aprovado deve ter sido ajustado para o limite restante de $500
    assert res.adjusted_amount_usd == 500.0

    # Quando ja esta em 70% ($7.000) -> Proxima ordem deve ser rejeitada
    res_full = treasury.evaluate_order(
        proposal=prop,
        total_equity=10000.0,
        current_aggregate_exposure=7000.0,
        current_symbol_exposure=0.0,
        active_portfolio_symbols=[],
        margin_type="ISOLATED"
    )
    assert res_full.approved is False
    assert "Exposicao agregada excedeu teto" in res_full.rejection_reason


def test_correlation_matrix_blocks_highly_correlated_assets():
    """Valida bloqueio de ordens em ativos com correlacao > 0.70."""
    tracker = AssetCorrelationTracker(correlation_threshold=0.70)

    # Cria series fortemente correlacionadas para BTC e ETH (r ~ 0.98)
    btc_rets = [0.01 * (i % 5) for i in range(50)]
    eth_rets = [0.01 * (i % 5) * 1.05 + 0.001 for i in range(50)]
    # Serie descorrelacionada para DOGE
    doge_rets = [0.02 * ((50 - i) % 7) - 0.01 for i in range(50)]

    tracker.update_history("BTC/USDT", btc_rets)
    tracker.update_history("ETH/USDT", eth_rets)
    tracker.update_history("DOGE/USDT", doge_rets)

    corr_btc_eth = tracker.get_correlation("BTC/USDT", "ETH/USDT")
    assert corr_btc_eth > 0.80, f"Correlacao esperada > 0.80, obtido {corr_btc_eth}"

    treasury = TreasuryController(correlation_tracker=tracker)

    # Carteira ja tem posicao ativa em BTC/USDT
    active_symbols = ["BTC/USDT"]

    # Tentativa de abrir ETH/USDT -> BLOQUEADA por alta correlacao
    prop_eth = OrderProposal("a2", "ETH/USDT", "BUY", 500.0, 1.4, 0.02)
    res_eth = treasury.evaluate_order(
        proposal=prop_eth,
        total_equity=10000.0,
        current_aggregate_exposure=1000.0,
        current_symbol_exposure=0.0,
        active_portfolio_symbols=active_symbols
    )
    assert res_eth.approved is False
    assert "correlacao excessiva" in res_eth.rejection_reason

    # Tentativa de abrir DOGE/USDT (descorrelacionado) -> APROVADA
    prop_doge = OrderProposal("a3", "DOGE/USDT", "BUY", 500.0, 1.4, 0.02)
    res_doge = treasury.evaluate_order(
        proposal=prop_doge,
        total_equity=10000.0,
        current_aggregate_exposure=1000.0,
        current_symbol_exposure=0.0,
        active_portfolio_symbols=active_symbols
    )
    assert res_doge.approved is True


if __name__ == "__main__":
    test_fractional_kelly_and_position_sizing()
    test_leverage_and_margin_invariants()
    test_portfolio_aggregate_exposure_ceiling()
    test_correlation_matrix_blocks_highly_correlated_assets()
    print("SUÍTE DE TESTES DA TESOURARIA CENTRAL APROVADA COM SUCESSO (4/4 TESTES PASSARAM).")
