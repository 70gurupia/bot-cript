#!/usr/bin/env python3
"""
Download Resiliente de Dados Historicos do Primeiro Semestre de 2026 (2026-H1).
Periodo: 01/01/2026 00:00:00 UTC a 30/06/2026 23:59:59 UTC.
Pares: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, DOGEUSDT, XRPUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, DOTUSDT.
Timeframes: 1h e 15m.
Gravacao incremental idempotente no SQLite market_data.db.
"""

from __future__ import annotations
import os
import sys
import time
import json
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

SYMBOLS_10 = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "DOTUSDT"
]

START_DATE_2026_UTC = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DATE_2026_UTC = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

START_MS = int(START_DATE_2026_UTC.timestamp() * 1000)
END_MS = int(END_DATE_2026_UTC.timestamp() * 1000)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "historical")
DB_PATH = os.path.join(OUTPUT_DIR, "market_data.db")
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


def fetch_batch_with_retry(
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int
) -> List[Any]:
    """Busca lote de candles na Binance com backoff exponencial."""
    url = (
        f"{BINANCE_KLINES_URL}?symbol={symbol}&interval={interval}"
        f"&startTime={start_time}&endTime={end_time}&limit=1000"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BotCripto-2026Downloader/2.0"}
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                if res.status == 200:
                    return json.loads(res.read().decode("utf-8"))
        except Exception as exc:
            backoff = 1.0 + attempt * 1.5
            time.sleep(backoff)
    return []


def parse_raw_row(symbol: str, row: List[Any]) -> Dict[str, Any]:
    """Mapeia linha bruta para dicionario padronizado."""
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


def save_batch_to_sqlite(table: str, batch_dict: List[Dict[str, Any]], db_path: str):
    """Grava lote imediatamente no SQLite para persistencia incremental."""
    if not batch_dict:
        return
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    cur.executemany(f"""
        INSERT OR REPLACE INTO {table} (
            symbol, open_time, open_price, high_price, low_price,
            close_price, volume, close_time, quote_volume, trades_count
        ) VALUES (
            :symbol, :open_time, :open_price, :high_price, :low_price,
            :close_price, :volume, :close_time, :quote_volume, :trades_count
        );
    """, batch_dict)
    conn.commit()
    conn.close()


def get_latest_downloaded_ms(table: str, symbol: str, db_path: str) -> Optional[int]:
    """Descobre o ultimo candle gravado para retomar sem duplicar requisicoes."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    cur.execute(f"""
        SELECT MAX(close_time) FROM {table}
        WHERE symbol = ? AND open_time >= ? AND open_time <= ?;
    """, (symbol, START_MS, END_MS))
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if (row and row[0]) else None


def download_interval_for_symbol(
    table: str,
    symbol: str,
    interval: str,
    db_path: str
) -> int:
    """Baixa o intervalo especificado para o par de forma incremental."""
    last_ms = get_latest_downloaded_ms(table, symbol, db_path)
    curr_time = (last_ms + 1) if last_ms else START_MS

    if curr_time >= END_MS:
        print(f"    [{symbol} {interval}] Ja completo ate o fim de 2026-H1.")
        return 0

    total_added = 0
    while curr_time < END_MS:
        raw_batch = fetch_batch_with_retry(symbol, interval, curr_time, END_MS)
        if not raw_batch:
            print(f"    [!] Falha persistente no lote de {symbol} {interval} em {curr_time}.")
            break

        parsed = [parse_raw_row(symbol, r) for r in raw_batch]
        save_batch_to_sqlite(table, parsed, db_path)
        total_added += len(parsed)

        last_close = int(raw_batch[-1][6])
        if last_close <= curr_time:
            break
        curr_time = last_close + 1
        time.sleep(0.04)

    return total_added


def run_pipeline_2026_h1(db_path: str = DB_PATH):
    """Executa o pipeline de ingestao para todos os 10 pares."""
    print("=" * 72)
    print("INGESTAO INCREMENTAL DETERMINISTICA 2026-H1 (01/01 a 30/06)")
    print("=" * 72)

    for sym in SYMBOLS_10:
        print(f"\n[Sincronizando {sym}]")
        n_1h = download_interval_for_symbol("klines_1h", sym, "1h", db_path)
        print(f"  -> 1h: +{n_1h} novos candles.")
        n_15m = download_interval_for_symbol("klines_15m", sym, "15m", db_path)
        print(f"  -> 15m: +{n_15m} novos candles.")

    print("\n" + "=" * 72)
    print("SINCRONIZACAO 2026-H1 CONCLUIDA COM SUCESSO!")
    print("=" * 72)


if __name__ == "__main__":
    run_pipeline_2026_h1()
