#!/usr/bin/env python3
"""
Script de download de dados historicos de 1h (2020 a 2024) para o Top 10 criptoativos da Binance.
Utiliza apenas a biblioteca padrao do Python (sem necessidade de chaves de API).
Salva em CSV e SQLite na pasta data/historical/ com suporte a conversao para Parquet.
"""

import os
import sys
import time
import json
import sqlite3
import csv
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Configuracao de pares e limites temporais
TOP_10_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "DOTUSDT",
]

START_DATE_UTC = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DATE_UTC = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

START_TIMESTAMP_MS = int(START_DATE_UTC.timestamp() * 1000)
END_TIMESTAMP_MS = int(END_DATE_UTC.timestamp() * 1000)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "historical")
DB_PATH = os.path.join(OUTPUT_DIR, "market_data.db")

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
REQUEST_LIMIT = 1000
RATE_LIMIT_DELAY = 0.1  # 100ms entre requisicoes


def init_database(db_path: str):
    """Cria a tabela no SQLite para persistencia relacional dos candles."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS klines_1h (
            symbol TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            close_price REAL NOT NULL,
            volume REAL NOT NULL,
            close_time INTEGER NOT NULL,
            quote_volume REAL NOT NULL,
            trades_count INTEGER NOT NULL,
            PRIMARY KEY (symbol, open_time)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_time ON klines_1h(symbol, open_time)")
    conn.commit()
    conn.close()


def fetch_klines_batch(symbol: str, start_time: int, end_time: int, limit: int = 1000):
    """Executa requisicao REST na API publica da Binance com tentativas e backoff."""
    url = (
        f"{BINANCE_KLINES_URL}?symbol={symbol}&interval=1h"
        f"&startTime={start_time}&endTime={end_time}&limit={limit}"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BotCripto-HistoricalDownloader/1.0"}
    )
    
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            wait_time = (attempt + 1) * 2
            print(f"  [Aviso] Falha de rede para {symbol} (tentativa {attempt + 1}/5): {e}. Aguardando {wait_time}s...")
            time.sleep(wait_time)
    
    raise RuntimeError(f"Nao foi possivel baixar lote para {symbol} apos 5 tentativas.")


def download_symbol_history(symbol: str):
    """Baixa todo o historico de 1h de 2020 a 2024 para um determinado simbolo."""
    csv_filename = f"{symbol}_1h_2020_2024.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_filename)
    
    print(f"\n==========================================")
    print(f"Iniciando download: {symbol} (1h) | 2020 a 2024")
    print(f"Destino CSV: {csv_path}")
    print(f"==========================================")
    
    current_start = START_TIMESTAMP_MS
    total_candles = []
    batch_count = 0
    
    while current_start < END_TIMESTAMP_MS:
        data = fetch_klines_batch(symbol, current_start, END_TIMESTAMP_MS, REQUEST_LIMIT)
        if not data:
            # Sem mais dados para este simbolo (ou o ativo ainda nao havia sido listado)
            break
        
        for kline in data:
            # Estrutura do retorno da Binance:
            # 0: Open time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume,
            # 6: Close time, 7: Quote asset volume, 8: Number of trades
            candle = {
                "symbol": symbol,
                "open_time": int(kline[0]),
                "open_price": float(kline[1]),
                "high_price": float(kline[2]),
                "low_price": float(kline[3]),
                "close_price": float(kline[4]),
                "volume": float(kline[5]),
                "close_time": int(kline[6]),
                "quote_volume": float(kline[7]),
                "trades_count": int(kline[8]),
            }
            total_candles.append(candle)
        
        last_close_time = int(data[-1][6])
        current_start = last_close_time + 1
        batch_count += 1
        
        last_date = datetime.fromtimestamp(data[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        sys.stdout.write(f"\rLote {batch_count:03d} | Velas baixadas: {len(total_candles):05d} | Ultima data: {last_date}")
        sys.stdout.flush()
        
        if len(data) < REQUEST_LIMIT:
            # Chegou ao fim do intervalo disponivel
            break
            
        time.sleep(RATE_LIMIT_DELAY)
        
    print(f"\nConcluido {symbol}: {len(total_candles)} candles coletados.")
    
    # Salvar no arquivo CSV
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "symbol", "open_time", "open", "high", "low", "close",
            "volume", "close_time", "quote_volume", "trades_count"
        ])
        for c in total_candles:
            writer.writerow([
                c["symbol"], c["open_time"], c["open_price"], c["high_price"],
                c["low_price"], c["close_price"], c["volume"], c["close_time"],
                c["quote_volume"], c["trades_count"]
            ])
            
    # Salvar no SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO klines_1h (
            symbol, open_time, open_price, high_price, low_price,
            close_price, volume, close_time, quote_volume, trades_count
        ) VALUES (
            :symbol, :open_time, :open_price, :high_price, :low_price,
            :close_price, :volume, :close_time, :quote_volume, :trades_count
        )
    """, total_candles)
    conn.commit()
    conn.close()
    
    # Se pyarrow/pandas estiverem presentes, gera tambem o parquet
    try:
        import pandas as pd
        parquet_path = os.path.join(OUTPUT_DIR, f"{symbol}_1h_2020_2024.parquet")
        df = pd.DataFrame(total_candles)
        df.to_parquet(parquet_path, index=False, compression="snappy")
        print(f"Parquet salvo: {parquet_path}")
    except ImportError:
        pass

    return len(total_candles)


def main():
    print("Iniciando Pipeline de Download Historico Top 10 (2020 a 2024)")
    print(f"Diretorio de Armazenamento: {OUTPUT_DIR}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    init_database(DB_PATH)
    
    start_total_time = time.time()
    summary = {}
    
    for symbol in TOP_10_SYMBOLS:
        try:
            count = download_symbol_history(symbol)
            summary[symbol] = count
        except Exception as e:
            print(f"\n[ERRO] Falha ao processar {symbol}: {e}")
            summary[symbol] = 0
            
    total_elapsed = time.time() - start_total_time
    total_candles = sum(summary.values())
    
    print("\n==========================================")
    print("RESUMO CONSOLIDADO DO DOWNLOAD")
    print("==========================================")
    for sym, count in summary.items():
        print(f"  - {sym:<10}: {count:>6} candles")
    print(f"Total acumulado: {total_candles} candles em {total_elapsed:.1f} segundos.")
    print(f"Banco SQLite atualizado em: {DB_PATH}")


if __name__ == "__main__":
    main()
