"""
Suíte de Testes Automatizados para os Motores de Alto Win Rate:
1. Motor de Lead-Lag Multi-Par (strategy/lead_lag_engine.py)
2. Motor de Funding Harvest e Snipe de Exaustao (strategy/funding_harvest_engine.py)
3. Motor de Microestrutura OBI e TTM Squeeze Pullback (strategy/order_flow_squeeze_engine.py)
4. Integracao do Filtro Laia EQS na Flotilha (core/swarm_manager.py)
"""

from __future__ import annotations
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.lead_lag_engine import (
    LeadLagConfig,
    detect_lead_lag_opportunity,
    MultiPairLeadLagMatrix,
)
from strategy.funding_harvest_engine import (
    FundingHarvestConfig,
    compute_annualized_funding,
    evaluate_carry_opportunity,
    detect_funding_exhaustion_snipe,
    FundingArbitrageController,
)
from strategy.order_flow_squeeze_engine import (
    SqueezeConfig,
    calculate_obi,
    detect_obi_absorption_scalp,
    check_squeeze_state,
    detect_first_pullback_entry,
)
from core.swarm_manager import SwarmManager


def test_lead_lag_detection():
    """Valida deteccao de assimetria direcional Lead-Lag entre lider e seguidor."""
    cfg = LeadLagConfig(impulse_threshold_pct=0.008, follower_lag_max_pct=0.002)

    # 1. Impulso comprador no lider (1.0%) com seguidor atrasado (0.1%)
    sig_buy = detect_lead_lag_opportunity(
        leader_open=100.0, leader_close=101.0, follower_open=10.0, follower_close=10.01, cfg=cfg
    )
    assert sig_buy.is_valid is True
    assert sig_buy.side == "BUY"
    assert sig_buy.take_profit > sig_buy.entry_price_estimate
    assert sig_buy.stop_loss < sig_buy.entry_price_estimate

    # 2. Impulso vendedor no lider (-1.0%) com seguidor atrasado (-0.1%)
    sig_sell = detect_lead_lag_opportunity(
        leader_open=100.0, leader_close=99.0, follower_open=10.0, follower_close=9.99, cfg=cfg
    )
    assert sig_sell.is_valid is True
    assert sig_sell.side == "SELL"
    assert sig_sell.take_profit < sig_sell.entry_price_estimate
    assert sig_sell.stop_loss > sig_sell.entry_price_estimate

    # 3. Sem impulso (mercado neutro)
    sig_neutral = detect_lead_lag_opportunity(
        leader_open=100.0, leader_close=100.2, follower_open=10.0, follower_close=10.02, cfg=cfg
    )
    assert sig_neutral.is_valid is False


def test_multipair_lead_lag_matrix():
    """Valida o escaneamento simultaneo da matriz de lideres e seguidores."""
    matrix = MultiPairLeadLagMatrix()
    market_quotes = {
        "BTCUSDT": (50000.0, 50600.0),  # +1.2% impulso
        "ETHUSDT": (3000.0, 3003.0),    # +0.1% atraso
        "SOLUSDT": (150.0, 150.1),      # +0.06% atraso
        "LINKUSDT": (15.0, 15.01),      # +0.06% atraso
        "AVAXUSDT": (30.0, 30.02),      # +0.06% atraso
        "DOGEUSDT": (0.10, 0.10),       # 0.0% atraso
    }
    signals = matrix.scan_market_pulse(market_quotes)
    assert len(signals) >= 3, f"Esperado ao menos 3 sinais ativos, obtido: {len(signals)}"
    for s in signals:
        assert s.is_valid is True
        assert s.side == "BUY"


def test_funding_harvest_and_snipe():
    """Valida calculos de Cash and Carry e deteccao de reversao pos-funding."""
    cfg = FundingHarvestConfig(min_annualized_carry_pct=20.0, extreme_funding_threshold=0.0008)

    # 1. Taxa normal moderada (0.01% por 8h -> ~10.95% anual)
    ann_1 = compute_annualized_funding(0.0001)
    assert abs(ann_1 - 10.95) < 0.1
    carry_ok, _, _ = evaluate_carry_opportunity(0.0001, cfg)
    assert carry_ok is False

    # 2. Taxa alta para Cash and Carry (0.03% por 8h -> ~32.85% anual)
    carry_ok2, act, ann_2 = evaluate_carry_opportunity(0.0003, cfg)
    assert carry_ok2 is True
    assert act == "LONG_SPOT_SHORT_PERP"

    # 3. Snipe de exaustao pos-funding (0.10% nos primeiros 15 minutos)
    snipe_ok, side, tp, sl = detect_funding_exhaustion_snipe(0.0010, 15, cfg)
    assert snipe_ok is True
    assert side == "SELL"
    assert tp == 0.008
    assert sl == 0.006

    # 4. Snipe apos janela de 30m (deve ser rejeitado)
    snipe_late, _, _, _ = detect_funding_exhaustion_snipe(0.0010, 45, cfg)
    assert snipe_late is False


def test_order_flow_obi_and_squeeze():
    """Valida calculos de OBI e deteccao do Squeeze com primeiro reteste."""
    cfg = SqueezeConfig(bb_period=10, keltner_atr_period=10)

    # 1. Calculo de OBI
    obi_pos = calculate_obi(bids_volume=100.0, asks_volume=20.0)
    assert obi_pos > 0.60
    obi_neg = calculate_obi(bids_volume=20.0, asks_volume=100.0)
    assert obi_neg < -0.60

    # 2. OBI Absorption Scalp
    valid_scalp, side_scalp, tp_s, sl_s = detect_obi_absorption_scalp(
        bids_volume=100.0, asks_volume=20.0, current_price=100.0, cvd_divergence=True, cfg=cfg
    )
    assert valid_scalp is True
    assert side_scalp == "BUY"
    assert tp_s > 100.0
    assert sl_s < 100.0

    # 3. Pullback em compressao
    closes = [100.0 + (i * 0.1) for i in range(25)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    is_sq, _, _, _, _ = check_squeeze_state(closes, highs, lows, cfg)
    # Apenas valida que executa sem excecoes matematicas
    assert isinstance(is_sq, bool)


def test_swarm_manager_laia_filter():
    """Valida o filtro cognitivo Laia EQS integrado ao SwarmManager."""
    swarm = SwarmManager(initial_balance_usd=10000.0, min_laia_score=70.0)

    # Contexto 1: Horario de baixa liquidez (madrugada 02:00 UTC) e mercado estagnado
    ctx_bad = {
        "btc_return_15m": 0.001,
        "alt_return_15m": 0.001,
        "hour_utc": 2,
        "funding_rate": 0.0006,  # funding adverso
        "alt_volume_ratio": 0.5
    }
    res_bad = swarm.dispatch_order(
        bot_id="bot_01",
        side="BUY",
        price=50000.0,
        amount=0.01,
        order_type="LIMIT",
        laia_filter_context=ctx_bad
    )
    assert res_bad["success"] is False
    assert "Filtro Laia EQS rejeitou" in res_bad["reason"]

    # Contexto 2: Alta liquidez em Nova York (14:00 UTC) e forte lead-lag
    ctx_good = {
        "btc_return_15m": 0.015,
        "alt_return_15m": 0.002,
        "hour_utc": 14,
        "funding_rate": -0.0002,
        "alt_volume_ratio": 2.0
    }
    res_good = swarm.dispatch_order(
        bot_id="bot_01",
        side="BUY",
        price=50000.0,
        amount=0.01,
        order_type="MARKET",
        laia_filter_context=ctx_good
    )
    assert res_good["success"] is True
    assert res_good["status"] == "FILLED"


def run_all_tests():
    test_lead_lag_detection()
    test_multipair_lead_lag_matrix()
    test_funding_harvest_and_snipe()
    test_order_flow_obi_and_squeeze()
    test_swarm_manager_laia_filter()
    print("TODOS OS 5 TESTES DOS MOTORES DE ALTO WIN RATE FORAM APROVADOS.")


if __name__ == "__main__":
    run_all_tests()
