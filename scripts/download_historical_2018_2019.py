#!/usr/bin/env python3
"""
Script de Download de Dados Históricos de 1h (2018 a 2019) da Binance.
Baixa o período de 2 anos anteriores a 2020 para estresse máximo:
- 2018: O grande Bear Market (queda de 84% no BTC e 95% nas altcoins).
- 2019: O ano de acumulação e recuperação pré-halving.
Salva em data/historical/ e insere no SQLite market_data.db.
"""

from __future__ import annotations
import os
import sys
import time
import json
import sqlite3
import csv
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Dict, Any

SYMBOLS_AVAILABLE_2018_2019 = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "LINKUSDT",
    "DOGEUSDT"
]

START_DATE_UTC = datetime(2018, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DATE_UTC = datetime(2019, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

START_TIMESTAMP_MS = int(START_DATE_UTC.timestamp() * 1000)
END_TIMESTAMP_MS = int(END_DATE_UTC.timestamp() * 1000)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "historical")
DB_PATH = os.path.join(OUTPUT_DIR, "market_data.db")

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
REQUEST_LIMIT = 1000
RATE_LIMIT_DELAY = 0.05  # 50ms


def fetch_klines_batch(symbol: str, start_time: int, end_time: int, limit: int = 1000):
    """Executa requisição à API pública da Binance com retries e backoff exponencial."""
    url = (
        f"{BINANCE_KLINES_URL}?symbol={symbol}&interval=1h"
        f"&startTime={start_time}&endTime={end_time}&limit={limit}"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BotCripto-HistoricalDownloader-2018-2019/1.0"}
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            wait_sec = (attempt + 1) * 2
            print(f"  [Aviso] Falha de rede ({symbol} tent {attempt + 1}/5): {e}. Aguardando {wait_sec}s...")
            time.sleep(wait_sec)
    raise RuntimeError(f"Falha definitiva ao baixar {symbol} de {start_time} a {end_time}.")


def save_candles_to_csv(csv_path: str, candles: List[Dict[str, Any]]):
    """Grava as velas em formato CSV padronizado."""
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "symbol", "open_time", "open", "high", "low", "close",
            "volume", "close_time", "quote_volume", "trades_count"
        ])
        for c in candles:
            writer.writerow([
                c["symbol"], c["open_time"], c["open_price"], c["high_price"],
                c["low_price"], c["close_price"], c["volume"], c["close_time"],
                c["quote_volume"], c["trades_count"]
            ])


def insert_candles_to_sqlite(candles: List[Dict[str, Any]]):
    """Insere velas no banco de dados SQLite sem duplicar registros."""
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
    """, candles)
    conn.commit()
    conn.close()


def download_symbol_history_2018_2019(symbol: str) -> int:
    """Coleta os dados de 1h entre 2018 e 2019 para um símbolo."""
    csv_filename = f"{symbol}_1h_2018_2019.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_filename)

    print(f"\nIniciando download: {symbol} (1h) | 2018 a 2019")
    current_start = START_TIMESTAMP_MS
    total_candles = []
    batch_count = 0

    while current_start < END_TIMESTAMP_MS:
        data = fetch_klines_batch(symbol, current_start, END_TIMESTAMP_MS, REQUEST_LIMIT)
        if not data:
            break

        for kline in data:
            total_candles.append({
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
            })

        last_close_time = int(data[-1][6])
        current_start = last_close_time + 1
        batch_count += 1

        last_date = datetime.fromtimestamp(data[-1][0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        sys.stdout.write(f"\r  Lote {batch_count:02d} | Candles: {len(total_candles):05d} | Ultima Data: {last_date}")
        sys.stdout.flush()

        if len(data) < REQUEST_LIMIT:
            break
        time.sleep(RATE_LIMIT_DELAY)

    if total_candles:
        save_candles_to_csv(csv_path, total_candles)
        insert_candles_to_sqlite(total_candles)
        print(f"\n[OK] {symbol}: {len(total_candles)} candles inseridos e salvos em {csv_path}")
    else:
        print(f"\n[Aviso] {symbol} não possuía pares listados antes de 2020.")

    return len(total_candles)


def main():
    print("==================================================================")
    print("DOWNLOAD DE DADOS HISTÓRICOS DE 2018 E 2019 (2 ANOS PRÉ-2020)")
    print("==================================================================")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    start_time = time.time()
    summary = {}

    for sym in SYMBOLS_AVAILABLE_2018_2019:
        try:
            cnt = download_symbol_history_2018_2019(sym)
            summary[sym] = cnt
        except Exception as e:
            print(f"\n[ERRO] Falha ao processar {sym}: {e}")
            summary[sym] = 0

    elapsed = time.time() - start_time
    total = sum(summary.values())

    print("\n==================================================================")
    print(f"DOWNLOAD CONCLUÍDO: {total} candles de 2018-2019 em {elapsed:.1f}s")
    for sym, cnt in summary.items():
        print(f"  - {sym:<10}: {cnt:>5} candles")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    main()
