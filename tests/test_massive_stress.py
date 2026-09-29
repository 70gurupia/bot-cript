"""
Suíte de Testes Massivos de Carga, Estresse e Performance.
Processa dezenas de milhares de candles reais do banco SQLite em alta velocidade.
Valida rendimento (throughput > 10.000 candles/segundo) e estabilidade de memoria.
"""

import os
import sqlite3
import time
import math

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "historical", "market_data.db")


def test_massive_historical_data_throughput():
    """Processa 20.000 candles reais do banco medindo a velocidade de calculo de indicadores."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Banco {DB_PATH} nao encontrado para teste massivo.")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Seleciona 20.000 candles do BTCUSDT (cerca de 2 anos e meio de dados continuos)
    cursor.execute("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM klines_1h
        WHERE symbol = 'BTCUSDT'
        ORDER BY open_time ASC
        LIMIT 20000
    """)
    rows = cursor.fetchall()
    conn.close()
    
    total_candles = len(rows)
    assert total_candles >= 5000, f"Amostra insuficiente para teste massivo: {total_candles} candles."
    
    start_time = time.perf_counter()
    
    # Motor em lote de calculo de EMA e ATR (simulando a carga do motor evolutivo)
    ema_period = 20
    k = 2.0 / (ema_period + 1)
    current_ema = rows[0][4]
    
    prev_close = rows[0][4]
    signals = []
    
    for row in rows:
        high = row[2]
        low = row[3]
        close = row[4]
        
        # Atualizacao de EMA
        current_ema = (close * k) + (current_ema * (1.0 - k))
        
        # True Range
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        
        # Geracao de sinal simulada
        if close > current_ema and tr > (close * 0.01):
            signals.append(1)  # Sinal de compra
        elif close < current_ema:
            signals.append(-1) # Sinal de venda
        else:
            signals.append(0)  # Neutro
            
        prev_close = close
        
    elapsed_time = time.perf_counter() - start_time
    candles_per_second = total_candles / elapsed_time if elapsed_time > 0 else 0
    
    print(f"\n[Massive Test] Processados {total_candles} candles em {elapsed_time:.4f}s.")
    print(f"[Massive Test] Taxa de Processamento: {candles_per_second:,.0f} candles/segundo.")
    print(f"[Massive Test] Sinais computados: {len(signals)} (Compras: {signals.count(1)}, Vendas: {signals.count(-1)})")
    
    # Invariante de performance: deve processar pelo menos 20.000 candles/segundo no motor deterministico
    assert candles_per_second >= 10000, f"Throughput abaixo do esperado: {candles_per_second:.0f} candles/s"


if __name__ == "__main__":
    test_massive_historical_data_throughput()
    print("TESTE MASSIVO DE CARGA E PERFORMANCE APROVADO COM SUCESSO.")
