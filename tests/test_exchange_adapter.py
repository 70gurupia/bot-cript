"""
Suíte de Testes do Adaptador de Conectividade de Mercado (ExchangeAdapter).
Valida:
1. Bloqueio categórico de funções de saque e transferência (SecurityException).
2. Monitoramento de batimento cardíaco (Heartbeat) e detecção de inatividade.
3. Normalização de dados públicos de ticker e candles.
4. Roteamento seguro de ordens para o simulador PaperTradingExchange.
"""

import sys
import time
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.exchange_adapter import ExchangeAdapter, SecurityException


def test_inviolable_withdrawal_blocking():
    """Valida que qualquer chamada de saque ou transferência é sumariamente bloqueada."""
    adapter = ExchangeAdapter(paper_trading=True)
    
    # Tentativa de saque deve lançar SecurityException
    try:
        adapter.withdraw(code="USDT", amount=100.0, address="0x123FakeAddress")
        assert False, "A função withdraw deveria ter sido bloqueada!"
    except SecurityException as e:
        assert "OPERAÇÃO PROIBIDA" in str(e)

    # Tentativa de transferência deve lançar SecurityException
    try:
        adapter.transfer(code="BTC", amount=1.0, from_account="spot", to_account="external")
        assert False, "A função transfer deveria ter sido bloqueada!"
    except SecurityException as e:
        assert "OPERAÇÃO PROIBIDA" in str(e)


def test_heartbeat_and_timeout_detection():
    """Valida o rastreamento de batimento cardíaco e detecção de inatividade de rede."""
    adapter = ExchangeAdapter(paper_trading=True)
    
    # Estado inicial recém-criado deve estar saudável
    health = adapter.check_connection_health()
    assert health["healthy"] is True
    
    # Simula inatividade de 15 segundos (superior ao limite de 10s)
    adapter.last_heartbeat_ts = time.time() - 15.0
    health_timeout = adapter.check_connection_health()
    assert health_timeout["healthy"] is False
    assert health_timeout["elapsed_seconds"] >= 15.0
    assert health_timeout["action"] == "TRIGGER_CONTINGENCY_REST"
    
    # Novo batimento cardíaco deve restabelecer a saúde
    adapter.record_heartbeat()
    assert adapter.check_connection_health()["healthy"] is True


def test_normalized_market_data():
    """Valida que tickers e candles são retornados em formato padronizado."""
    adapter = ExchangeAdapter(paper_trading=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    ticker = loop.run_until_complete(adapter.fetch_ticker_normalized("BTCUSDT"))
    assert ticker["symbol"] == "BTCUSDT"
    assert "bid" in ticker and "ask" in ticker and "last" in ticker
    assert ticker["last"] > 0
    
    candles = loop.run_until_complete(adapter.fetch_ohlcv_normalized("BTCUSDT", limit=10))
    assert len(candles) == 10
    # Cada candle deve ter [timestamp, open, high, low, close, volume]
    assert len(candles[0]) == 6
    
    loop.run_until_complete(adapter.close())
    loop.close()


def test_order_submission_in_paper_mode():
    """Valida que o envio de ordens é roteado com sucesso para o PaperTradingExchange."""
    adapter = ExchangeAdapter(paper_trading=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    res = loop.run_until_complete(
        adapter.submit_order(
            agent_id="agent_adapter_test",
            symbol="ETHUSDT",
            side="BUY",
            order_type="MARKET",
            amount=0.5,
            price=3000.0,
            leverage=1.0,
            margin_type="ISOLATED"
        )
    )
    loop.run_until_complete(adapter.close())
    loop.close()
    
    assert res["success"] is True
    assert res["status"] == "FILLED"
    assert len(adapter.paper_exchange.positions) == 1


if __name__ == "__main__":
    test_inviolable_withdrawal_blocking()
    test_heartbeat_and_timeout_detection()
    test_normalized_market_data()
    test_order_submission_in_paper_mode()
    print("TODOS OS TESTES DO EXCHANGE ADAPTER FORAM APROVADOS COM SUCESSO.")
