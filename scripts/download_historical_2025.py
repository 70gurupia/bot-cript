#!/usr/bin/env python3
"""
Download de Dados Históricos de 1h do Ano de 2025 da Binance.
Baixa o período de 01/01/2025 a 31/12/2025 para os 4 pares principais:
BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT.
Insere no SQLite market_data.db e salva CSVs correspondentes.
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

SYMBOLS_2025 = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT"
]

START_DATE_UTC = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DATE_UTC = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

START_TIMESTAMP_MS = int(START_DATE_UTC.timestamp() * 1000)
END_TIMESTAMP_MS = int(END_DATE_UTC.timestamp() * 1000)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "historical")
DB_PATH = os.path.join(OUTPUT_DIR, "market_data.db")
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


def fetch_batch_2025(symbol: str, start_time: int, end_time: int) -> List[Any]:
    """Busca lote de até 1000 candles na Binance com retries seguros."""
    url = f"{BINANCE_KLINES_URL}?symbol={symbol}&interval=1h&startTime={start_time}&endTime={end_time}&limit=1000"
    req = urllib.request.Request(url, headers={"User-Agent": "BotCripto-2025Downloader/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                if res.status == 200:
                    return json.loads(res.read().decode("utf-8"))
        except Exception:
            time.sleep(1 + attempt)
    return []


def parse_kline_row(symbol: str, row: List[Any]) -> Dict[str, Any]:
    """Converte linha bruta da Binance em dicionário padronizado."""
    return {
        "symbol": symbol,
        "open_time": int(row[0]),
        "open_price": float(row[1]),
        "high_price": float(row[2]),
        "low_price": float(row[3]),
        "close_price": float(row[4]),
        "volume": float(row[5]),
        "close_time": int(row[6]),
        "quote_volume": float(row[7]),
        "trades_count": int(row[8])
    }


def download_symbol_2025(symbol: str) -> List[Dict[str, Any]]:
    """Baixa o histórico completo de 2025 para um símbolo."""
    print(f"-> Baixando {symbol} (Ano de 2025)...")
    curr_time = START_TIMESTAMP_MS
    all_candles = []
    while curr_time < END_TIMESTAMP_MS:
        data = fetch_batch_2025(symbol, curr_time, END_TIMESTAMP_MS)
        if not data:
            break
        for row in data:
            all_candles.append(parse_kline_row(symbol, row))
        last_close = int(data[-1][6])
        if last_close <= curr_time:
            break
        curr_time = last_close + 1
        time.sleep(0.04)
    print(f"   Total coletado {symbol} em 2025: {len(all_candles)} candles.")
    return all_candles


def insert_candles_to_sqlite(candles: List[Dict[str, Any]], db_path: str):
    """Insere ou atualiza os candles no SQLite."""
    if not candles:
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany("""
        INSERT OR REPLACE INTO klines_1h (
            symbol, open_time, open_price, high_price, low_price,
            close_price, volume, close_time, quote_volume, trades_count
        ) VALUES (
            :symbol, :open_time, :open_price, :high_price, :low_price,
            :close_price, :volume, :close_time, :quote_volume, :trades_count
        );
    """, candles)
    conn.commit()
    conn.close()


def save_csv(candles: List[Dict[str, Any]], csv_path: str):
    """Salva candles em arquivo CSV."""
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades_count"])
        for c in candles:
            writer.writerow([c["symbol"], c["open_time"], c["open_price"], c["high_price"], c["low_price"], c["close_price"], c["volume"], c["close_time"], c["quote_volume"], c["trades_count"]])


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for sym in SYMBOLS_2025:
        candles = download_symbol_2025(sym)
        if candles:
            insert_candles_to_sqlite(candles, DB_PATH)
            csv_path = os.path.join(OUTPUT_DIR, f"{sym}_1h_2025.csv")
            save_csv(candles, csv_path)
    print("[OK] Concluido download e ingestao do ano de 2025.")


if __name__ == "__main__":
    main()
