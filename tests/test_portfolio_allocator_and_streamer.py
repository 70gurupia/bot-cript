"""
Suíte de Testes para o Alocador de Portfólio, Calibrador Walk-Forward e Streamer L2:
1. Alocador de Portfólio Multi-Ativo (treasury/risk_parity_kelly_allocator.py)
2. Calibrador Walk-Forward por Par (strategy/walk_forward_calibrator.py)
3. Streamer L2 de Livro de Ofertas e OBI (core/ws_depth_streamer.py)
"""

from __future__ import annotations
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from treasury.risk_parity_kelly_allocator import (
    RiskParityKellyAllocator,
    GroupAllocationInput,
)
from strategy.walk_forward_calibrator import (
    WalkForwardCalibrator,
)
from core.ws_depth_streamer import (
    WSDepthStreamer,
    OrderBookSnapshot,
)


def test_risk_parity_kelly_allocation():
    """Valida a alocacao equilibrada de capital com preferencia para alto win rate."""
    allocator = RiskParityKellyAllocator(
        fractional_kelly=0.25,
        max_group_weight_pct=25.0,
        min_group_weight_pct=2.5,
        max_aggregate_exposure_pct=70.0
    )

    # 4 grupos com perfis contrastantes
    groups = [
        GroupAllocationInput("G1", "Lead-Lag Alto Win", win_rate=0.75, win_loss_ratio=2.0, realized_volatility=0.015),
        GroupAllocationInput("G2", "Funding Rate 100%", win_rate=0.99, win_loss_ratio=1.5, realized_volatility=0.005),
        GroupAllocationInput("G3", "Donchian 35%", win_rate=0.35, win_loss_ratio=2.5, realized_volatility=0.035),
        GroupAllocationInput("G4", "Inativo", win_rate=0.50, win_loss_ratio=1.0, realized_volatility=0.020, is_active=False),
    ]

    results = allocator.allocate_capital(total_bankroll_usd=10000.0, groups=groups)
    assert len(results) == 4

    res_map = {r.group_id: r for r in results}
    # G2 (Funding 100% com baixa volatilidade) e G1 (Lead-Lag 75%) devem receber maior alocacao
    assert res_map["G2"].target_weight_pct >= res_map["G3"].target_weight_pct
    assert res_map["G1"].target_weight_pct >= res_map["G3"].target_weight_pct
    assert res_map["G4"].target_weight_pct == 0.0

    # Soma dos pesos dos grupos ativos deve ser exatamente 100%
    active_weights_sum = sum(r.target_weight_pct for r in results)
    assert abs(active_weights_sum - 100.0) < 0.1

    # Montante total alocado deve respeitar o teto de 70% (7000 USD de 10000 USD)
    tot_allocated = sum(r.allocated_usd for r in results)
    assert abs(tot_allocated - 7000.0) < 2.0


def test_walk_forward_calibrator():
    """Valida a calibracao adaptativa de limiares por volatilidade historica."""
    calibrator = WalkForwardCalibrator(window_size=30)

    # Ativo calmo (baixa variacao percentual)
    calm_closes = [100.0 + (i * 0.05) for i in range(50)]
    params_calm = calibrator.calibrate_pair("CALMUSDT", calm_closes, base_asset_volatility=0.01)

    # Ativo altamente volatil (flutuacoes grandes)
    wild_closes = [100.0 * (1.0 + ((-1) ** i * 0.05)) for i in range(50)]
    params_wild = calibrator.calibrate_pair("WILDUSDT", wild_closes, base_asset_volatility=0.01)

    # Ativo volatil deve ter limiar de Lead-Lag maior para filtrar falsos rompimentos
    assert params_wild.lead_lag_impulse_threshold > params_calm.lead_lag_impulse_threshold
    assert params_wild.target_volatility_pct > params_calm.target_volatility_pct


def test_ws_depth_streamer_and_obi():
    """Valida snapshot de depth, calculo de OBI e spread relativo."""
    streamer = WSDepthStreamer(["BTCUSDT"])
    snap = streamer.get_snapshot("BTCUSDT")
    assert snap is not None

    # Simula livro com pressao compradora macica (bids > asks)
    bids = [(50000.0, 10.0), (49990.0, 5.0), (49980.0, 2.0)]
    asks = [(50010.0, 2.0), (50020.0, 1.0), (50030.0, 1.0)]
    streamer.process_depth_payload("BTCUSDT", {"bids": bids, "asks": asks})

    assert snap.best_bid == 50000.0
    assert snap.best_ask == 50010.0
    assert snap.obi > 0.50 # Pressao compradora
    assert snap.get_spread_pct() > 0.0

    # Teste de simulacao local de feed
    streamer.simulate_feed_update("BTCUSDT", mid_price=50000.0, bids_pressure_ratio=2.5)
    assert snap.obi > 0.0


def run_all_tests():
    test_risk_parity_kelly_allocation()
    test_walk_forward_calibrator()
    test_ws_depth_streamer_and_obi()
    print("TODOS OS TESTES DE ALOCADOR, CALIBRADOR E STREAMER FORAM APROVADOS.")


if __name__ == "__main__":
    run_all_tests()
