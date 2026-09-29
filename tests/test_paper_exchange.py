"""
Suíte de Testes do Simulador PaperTradingExchange.
Valida:
1. Execução de ordens a mercado com slippage sintético e taxa taker.
2. Enfileiramento e preenchimento de ordens limite via candles.
3. Encerramento de posições com cálculo de PnL realizado.
4. Rejeição de margem cruzada e alavancagem abusiva.
5. Liquidação forçada teórica sob movimento adverso de preço.
"""

import sys
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.paper_exchange import PaperTradingExchange


def test_initial_state_and_equity():
    """Valida saldo inicial e cálculo correto de patrimônio líquido."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    assert exchange.cash_balance_usd == 10000.0
    assert exchange.get_equity() == 10000.0
    assert len(exchange.positions) == 0
    assert len(exchange.open_orders) == 0


def test_market_order_execution_and_slippage():
    """Valida que ordem a mercado sofre penalidade de slippage (0.05%) e taxa taker (0.04%)."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    
    # Compra a mercado de 0.1 BTC a $60.000,00 com alavancagem 2x
    nominal_price = 60000.0
    res = exchange.create_order(
        agent_id="test_agent_1",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        amount=0.1,
        price=nominal_price,
        leverage=2.0,
        margin_type="ISOLATED"
    )
    
    assert res["success"] is True
    # Preço preenchido com slippage de +0.05%
    expected_price = nominal_price * 1.0005
    assert math.isclose(res["filled_price"], expected_price, rel_tol=1e-5)
    
    # Saldo deve ter deduzido o colateral ($3.001,50) + taxa taker ($2,4012)
    expected_notional = 0.1 * expected_price
    expected_collateral = expected_notional / 2.0
    expected_fee = expected_notional * 0.0004
    expected_cash = 10000.0 - (expected_collateral + expected_fee)
    
    assert math.isclose(exchange.cash_balance_usd, expected_cash, rel_tol=1e-4)
    assert len(exchange.positions) == 1


def test_close_position_profit():
    """Valida o encerramento de uma posição lucrativa e crédito correto ao saldo."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    
    # Compra 0.1 BTC a $60.000
    res_open = exchange.create_order(
        agent_id="test_agent_1",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        amount=0.1,
        price=60000.0,
        leverage=1.0,
        margin_type="ISOLATED"
    )
    pos_id = res_open["position_id"]
    entry_price = res_open["filled_price"]
    
    # O preço sobe para $66.000 (+10%) e encerramos a posição
    exit_price = 66000.0
    res_close = exchange.close_position(pos_id, exit_price=exit_price)
    
    assert res_close["success"] is True
    # PnL bruto deve ser (66000 - entry_price) * 0.1
    expected_gross_pnl = (exit_price - entry_price) * 0.1
    assert math.isclose(res_close["realized_pnl_usd"], expected_gross_pnl, rel_tol=1e-4)
    # Saldo final deve ser maior que o inicial de $10.000
    assert exchange.cash_balance_usd > 10000.0


def test_limit_order_matching_via_candle():
    """Valida o enfileiramento de ordem limite e preenchimento ao ser atingida por candle."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    
    # Ordem limite de compra de ETH a $3.000 (preço atual $3.100)
    res = exchange.create_order(
        agent_id="test_agent_2",
        symbol="ETHUSDT",
        side="BUY",
        order_type="LIMIT",
        amount=1.0,
        price=3000.0,
        leverage=1.0,
        margin_type="ISOLATED"
    )
    assert res["success"] is True
    assert res["status"] == "OPEN"
    assert len(exchange.open_orders) == 1
    
    # Candle 1: High 3150, Low 3050 (não atinge 3000) -> ordem permanece aberta
    exchange.on_market_candle("ETHUSDT", high=3150.0, low=3050.0, close=3100.0)
    assert len(exchange.open_orders) == 1
    
    # Candle 2: High 3080, Low 2980 (atinge 3000) -> ordem preenchida!
    exchange.on_market_candle("ETHUSDT", high=3080.0, low=2980.0, close=3020.0)
    assert len(exchange.open_orders) == 0
    assert len(exchange.positions) == 1
    
    pos = list(exchange.positions.values())[0]
    assert pos.entry_price == 3000.0  # Ordem limite preenche no preco exato (sem slippage)


def test_invariants_rejection():
    """Valida a recusa estrita de ordens que violam regras de segurança."""
    exchange = PaperTradingExchange(initial_balance_usd=500.0)
    
    # Rejeição de margem cruzada (CROSS)
    res_cross = exchange.create_order(
        agent_id="a1", symbol="BTCUSDT", side="BUY", order_type="MARKET",
        amount=0.01, price=60000.0, leverage=1.0, margin_type="CROSS"
    )
    assert res_cross["success"] is False
    assert "ISOLATED" in res_cross["reason"]
    
    # Rejeição de alavancagem superior a 3.0x
    res_lev = exchange.create_order(
        agent_id="a1", symbol="BTCUSDT", side="BUY", order_type="MARKET",
        amount=0.01, price=60000.0, leverage=10.0, margin_type="ISOLATED"
    )
    assert res_lev["success"] is False
    assert "excede o teto" in res_lev["reason"]
    
    # Rejeição de saldo insuficiente
    res_funds = exchange.create_order(
        agent_id="a1", symbol="BTCUSDT", side="BUY", order_type="MARKET",
        amount=1.0, price=60000.0, leverage=1.0, margin_type="ISOLATED"
    )
    assert res_funds["success"] is False
    assert "Saldo insuficiente" in res_funds["reason"]


def test_theoretical_liquidation():
    """Valida a liquidação forçada quando o preço atinge o patamar de liquidação."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    
    # Compra 1 BTC a $60.000 com alavancagem 3x (colateral = $20.000, mas vamos comprar 0.1 BTC para caber no saldo)
    res = exchange.create_order(
        agent_id="test_agent_liq",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        amount=0.1,
        price=60000.0,
        leverage=3.0,
        margin_type="ISOLATED"
    )
    pos_id = res["position_id"]
    pos = exchange.positions[pos_id]
    
    # Preço de liquidação para alavancagem 3x com margem de manutenção de 90%
    # Entrada ~$60.030,00 -> Liquidação ocorre em torno de $42.000
    assert pos.liquidation_price < 50000.0
    
    # Candle com queda abrupta para $35.000 (abaixo do preço de liquidação)
    exchange.on_market_candle("BTCUSDT", high=55000.0, low=35000.0, close=36000.0)
    
    assert pos.is_closed is True
    assert pos.realized_pnl_usd == -pos.collateral_usd  # Perdeu o colateral isolado da posição


if __name__ == "__main__":
    test_initial_state_and_equity()
    test_market_order_execution_and_slippage()
    test_close_position_profit()
    test_limit_order_matching_via_candle()
    test_invariants_rejection()
    test_theoretical_liquidation()
    print("TODOS OS TESTES DO PAPER TRADING EXCHANGE FORAM APROVADOS COM SUCESSO.")
