#!/usr/bin/env python3
"""
Utilitário para inicializar o banco de dados SQLite local de testes (market_data.db)
a partir dos arquivos CSV históricos incluídos no repositório.
Garante que pipelines de CI/CD em runners efêmeros tenham os dados necessários para os testes.
"""

import csv
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "historical"
DB_PATH = DATA_DIR / "market_data.db"


def _create_tables(cursor: sqlite3.Cursor):
    """Cria as tabelas relacionais de candles klines_1h e klines_15m."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS klines_1h (
            symbol TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            close_price REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (symbol, open_time)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS klines_15m (
            symbol TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            close_price REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (symbol, open_time)
        );
    """)


def _extract_row_tuple(row: dict, symbol: str) -> tuple | None:
    """Extrai uma tupla tipada de candle de uma linha de CSV."""
    try:
        open_time = int(row.get("open_time") or row.get("timestamp") or 0)
        open_p = float(row.get("open") or 0.0)
        high_p = float(row.get("high") or 0.0)
        low_p = float(row.get("low") or 0.0)
        close_p = float(row.get("close") or 0.0)
        vol = float(row.get("volume") or 0.0)
        return (symbol, open_time, open_p, high_p, low_p, close_p, vol)
    except (ValueError, TypeError):
        return None


def _load_csv_records(csv_path: Path, symbol: str, limit: int = 3000) -> list:
    """Lê registros válidos de um arquivo CSV até o limite especificado."""
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if idx >= limit:
                break
            record = _extract_row_tuple(row, symbol)
            if record:
                records.append(record)
    return records


def _seed_csv_data(cursor: sqlite3.Cursor):
    """Insere dados de candles a partir dos CSVs existentes."""
    csv_files = list(DATA_DIR.glob("*_1h_2020_2024.csv"))
    insert_sql_1h = """
        INSERT OR IGNORE INTO klines_1h (symbol, open_time, open_price, high_price, low_price, close_price, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    insert_sql_15m = """
        INSERT OR IGNORE INTO klines_15m (symbol, open_time, open_price, high_price, low_price, close_price, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    for csv_path in csv_files:
        symbol = csv_path.name.split("_")[0]
        records = _load_csv_records(csv_path, symbol)
        cursor.executemany(insert_sql_1h, records)
        cursor.executemany(insert_sql_15m, records)


def ensure_test_database():
    """Inicializa as tabelas klines_1h e klines_15m caso não existam ou estejam vazias."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    _create_tables(cursor)

    cursor.execute("SELECT COUNT(*) FROM klines_1h;")
    count_1h = cursor.fetchone()[0]

    if count_1h == 0:
        _seed_csv_data(cursor)
        conn.commit()

    conn.close()


if __name__ == "__main__":
    ensure_test_database()
    print(f"Banco de dados de teste validado em {DB_PATH}")
