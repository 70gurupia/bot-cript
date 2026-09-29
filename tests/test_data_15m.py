#!/usr/bin/env python3
"""
Teste de Integridade e Estrutura de Dados 15m para Day Trade.
Valida o schema da tabela klines_15m, presenca de dados e consistencia dos candles.
"""

import os
import sys
import sqlite3
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "historical", "market_data.db")


class TestHistoricalData15m(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(DB_PATH), f"Banco SQLite nao encontrado em {DB_PATH}")
        self.conn = sqlite3.connect(DB_PATH)
        self.cur = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def test_01_table_exists(self):
        self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='klines_15m';")
        res = self.cur.fetchone()
        self.assertIsNotNone(res, "Tabela klines_15m deve existir no banco de dados.")

    def test_02_symbol_counts(self):
        self.cur.execute("SELECT symbol, COUNT(*) FROM klines_15m GROUP BY symbol;")
        rows = dict(self.cur.fetchall())
        self.assertIn("BTCUSDT", rows, "BTCUSDT deve possuir candles na tabela klines_15m.")
        self.assertIn("ETHUSDT", rows, "ETHUSDT deve possuir candles na tabela klines_15m.")
        self.assertGreater(rows["BTCUSDT"], 1000, "Deve haver mais de 1000 candles de 15m para BTCUSDT.")
        self.assertGreater(rows["ETHUSDT"], 1000, "Deve haver mais de 1000 candles de 15m para ETHUSDT.")

    def test_03_price_consistency(self):
        self.cur.execute("""
            SELECT symbol, open_time, open_price, high_price, low_price, close_price
            FROM klines_15m
            WHERE symbol='BTCUSDT'
            LIMIT 100;
        """)
        rows = self.cur.fetchall()
        for sym, ot, o, h, l, c in rows:
            self.assertGreaterEqual(h, min(o, c), f"High {h} deve ser maior ou igual ao corpo em {ot}")
            self.assertLessEqual(l, max(o, c), f"Low {l} deve ser menor ou igual ao corpo em {ot}")
            self.assertGreater(o, 0, "Preco de abertura deve ser positivo")
            self.assertGreater(c, 0, "Preco de fechamento deve ser positivo")

    def test_04_time_interval_15m(self):
        self.cur.execute("""
            SELECT open_time
            FROM klines_15m
            WHERE symbol='BTCUSDT'
            ORDER BY open_time ASC
            LIMIT 10;
        """)
        times = [r[0] for r in self.cur.fetchall()]
        fifteen_min_ms = 15 * 60 * 1000
        for i in range(1, len(times)):
            diff = times[i] - times[i - 1]
            self.assertEqual(diff, fifteen_min_ms, f"Intervalo entre candles adjacentes deve ser de 15 minutos (900000ms), obtido {diff}")


if __name__ == "__main__":
    unittest.main()
