"""
Suite de Testes Unitarios e de Integracao: Flotilha de 40 Bots e Paper Trading.
Valida a inicializacao dos 8 grupos de 5 bots, o ciclo de despacho de ordens Maker,
a execucao assincrona de candles de mercado, atualizacao de PnL e endpoints REST do painel.
"""

import sys
import os
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.paper_exchange import PaperTradingExchange
from core.swarm_manager import SwarmManager, GROUP_DEFINITIONS
from monitoring.web_app import app


def test_swarm_initialization():
    """Valida a composicao formal dos 40 bots e 8 grupos na inicializacao."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    swarm = SwarmManager(exchange=exchange, initial_balance_usd=10000.0)

    # 1. Total de bots e grupos
    assert len(swarm.bots) == 40
    assert len(GROUP_DEFINITIONS) == 8

    # 2. Validacao de identificadores e grupos de 5
    for i in range(1, 41):
        b_id = f"bot_{i:02d}"
        assert b_id in swarm.bots
        bot = swarm.bots[b_id]
        assert bot.is_active is True
        assert bot.trades_count == 0
        assert bot.wins_count == 0
        assert bot.realized_pnl_usd == 0.0

    # 3. Resumo inicial da flotilha
    summary = swarm.get_swarm_summary()
    assert summary["total_bots"] == 40
    assert summary["active_bots"] == 40
    assert summary["total_groups"] == 8
    assert summary["cash_balance_usd"] == 10000.0
    assert summary["total_equity_usd"] == 10000.0
    assert summary["net_return_pct"] == 0.0
    assert summary["open_positions_count"] == 0


def test_swarm_order_dispatch_and_limit_fill():
    """Testa o despacho de ordem limite por um sub-bot e sua execucao via candle de mercado."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    swarm = SwarmManager(exchange=exchange, initial_balance_usd=10000.0)

    # Bot 1 (Grupo 1: BTCUSDT) despacha ordem limite de compra abaixo do preco de mercado
    order_res = swarm.dispatch_order(
        bot_id="bot_01",
        side="BUY",
        price=59000.0,
        amount=0.05,
        order_type="LIMIT",
        leverage=1.0
    )
    assert order_res["success"] is True
    assert order_res["status"] == "OPEN"
    order_id = order_res["order_id"]
    assert order_id in exchange.open_orders

    # Candle que nao atinge o preco limite: ordem continua OPEN
    swarm.process_market_candle("BTCUSDT", high=60500.0, low=59500.0, close=60000.0)
    assert order_id in exchange.open_orders

    # Candle que fura a minima (58800 <= 59000): ordem limite deve ser preenchida como Maker
    swarm.process_market_candle("BTCUSDT", high=59800.0, low=58800.0, close=59200.0)
    assert order_id not in exchange.open_orders
    assert len(exchange.positions) == 1

    # Localiza a posicao criada e vincula ao bot
    pos = list(exchange.positions.values())[0]
    assert pos.agent_id == "bot_01"
    assert pos.entry_price == 59000.0
    assert pos.amount == 0.05
    assert not pos.is_closed

    bot_01 = swarm.get_bot("bot_01")
    bot_01.active_position_id = pos.position_id

    # Verifica o resumo de posicoes abertas
    open_pos = swarm.get_open_positions()
    assert len(open_pos) == 1
    assert open_pos[0]["agent_id"] == "bot_01"
    assert open_pos[0]["symbol"] == "BTCUSDT"


def test_swarm_position_close_and_pnl_accounting():
    """Testa o encerramento de posicao com apuracao contabil de PnL e metricas do grupo."""
    exchange = PaperTradingExchange(initial_balance_usd=10000.0)
    swarm = SwarmManager(exchange=exchange, initial_balance_usd=10000.0)

    # Abre ordem a mercado direta para o Bot 6 (Grupo 2: ETHUSDT)
    mkt_res = swarm.dispatch_order(
        bot_id="bot_06",
        side="BUY",
        price=3000.0,
        amount=1.0,
        order_type="MARKET",
        leverage=1.0
    )
    assert mkt_res["success"] is True
    assert mkt_res["status"] == "FILLED"
    pos_id = mkt_res["position_id"]

    bot_06 = swarm.get_bot("bot_06")
    assert bot_06.active_position_id == pos_id

    # Fecha a posicao com lucro em $3.200
    close_res = swarm.close_bot_position(bot_id="bot_06", exit_price=3200.0)
    assert close_res["success"] is True
    assert close_res["realized_pnl_usd"] > 0.0

    # Verifica os contadores do Bot 6
    assert bot_06.trades_count == 1
    assert bot_06.wins_count == 1
    assert bot_06.realized_pnl_usd > 190.0  # ~200 USD bruto menos taxas
    assert bot_06.active_position_id is None

    # Verifica as metricas agregadas do Grupo 2
    groups = swarm.get_groups_summary()
    g2 = next(g for g in groups if g["group_id"] == "G2")
    assert g2["total_trades"] == 1
    assert g2["wins_count"] == 1
    assert g2["win_rate_pct"] == 100.0
    assert g2["realized_pnl_usd"] > 190.0


def test_swarm_multi_bot_concurrency():
    """Testa operacoes simultaneas de bots de grupos distintos em paralelo."""
    exchange = PaperTradingExchange(initial_balance_usd=20000.0)
    swarm = SwarmManager(exchange=exchange, initial_balance_usd=20000.0)

    # Dispara operacoes para bots de 4 grupos diferentes
    symbols_and_bots = [
        ("bot_01", "BUY", 60000.0, 0.02),
        ("bot_06", "BUY", 3000.0, 0.5),
        ("bot_16", "BUY", 0.15, 5000.0),
        ("bot_21", "BUY", 140.0, 5.0)
    ]

    for b_id, side, price, amount in symbols_and_bots:
        res = swarm.dispatch_order(
            bot_id=b_id,
            side=side,
            price=price,
            amount=amount,
            order_type="MARKET",
            leverage=1.0
        )
        assert res["success"] is True

    # Quatro posicoes devem estar ativas
    open_pos = swarm.get_open_positions()
    assert len(open_pos) == 4

    summary = swarm.get_swarm_summary()
    assert summary["open_positions_count"] == 4
    assert summary["cash_balance_usd"] < 20000.0

    # Fecha duas posicoes
    swarm.close_bot_position("bot_01", 61000.0)
    swarm.close_bot_position("bot_16", 0.14)

    summary_after = swarm.get_swarm_summary()
    assert summary_after["open_positions_count"] == 2
    assert summary_after["total_trades"] == 2


def test_swarm_api_endpoints():
    """Valida a integracao dos endpoints REST do FastAPI para a flotilha."""
    client = TestClient(app)

    # 1. GET /api/swarm/status
    res_status = client.get("/api/swarm/status")
    assert res_status.status_code == 200
    st_data = res_status.json()
    assert st_data["total_bots"] == 40
    assert st_data["total_groups"] == 8
    assert "total_equity_usd" in st_data
    assert "cash_balance_usd" in st_data

    # 2. GET /api/swarm/groups
    res_groups = client.get("/api/swarm/groups")
    assert res_groups.status_code == 200
    gr_data = res_groups.json()
    assert len(gr_data) == 8
    assert gr_data[0]["group_id"] == "G1"
    assert gr_data[7]["group_id"] == "G8"

    # 3. GET /api/swarm/bots
    res_bots = client.get("/api/swarm/bots")
    assert res_bots.status_code == 200
    bt_data = res_bots.json()
    assert len(bt_data) == 40
    assert bt_data[0]["bot_id"] == "bot_01"
    assert bt_data[39]["bot_id"] == "bot_40"

    # 4. GET /api/swarm/positions
    res_pos = client.get("/api/swarm/positions")
    assert res_pos.status_code == 200
    assert isinstance(res_pos.json(), list)


if __name__ == "__main__":
    test_swarm_initialization()
    test_swarm_order_dispatch_and_limit_fill()
    test_swarm_position_close_and_pnl_accounting()
    test_swarm_multi_bot_concurrency()
    test_swarm_api_endpoints()
    print("SUITE DA FLOTILHA DE 40 BOTS E PAPER TRADING APROVADA COM SUCESSO (5/5 TESTES PASSARAM).")
