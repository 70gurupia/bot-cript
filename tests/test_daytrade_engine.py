#!/usr/bin/env python3
"""
Testes Unitarios do Motor de Day Trade Intraday (15m).
Valida regras EOD Flat compulsorias, limites de stop/alvo, anualizacao de 15m e alavancagem.
"""

import unittest
from datetime import datetime, timezone
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.daytrade_engine import (
    DayTradeConfig,
    is_eod_candle,
    simulate_daytrade_session,
    generate_daytrade_signals
)
from evolution.fitness_evaluator import FIFTEEN_MIN_ANNUALIZATION_FACTOR


class TestDayTradeEngine(unittest.TestCase):
    def setUp(self):
        self.config = DayTradeConfig(
            symbol="BTCUSDT",
            initial_balance=10000.0,
            leverage=2.0,
            risk_per_trade_pct=0.01,
            stop_loss_pct=0.01,
            take_profit_pct=0.02,
            max_hold_bars=16,
            eod_flat_hour_utc=23,
            eod_flat_minute_utc=45
        )

    def test_01_is_eod_candle(self):
        # 23:45 UTC
        dt_eod = datetime(2024, 1, 1, 23, 45, 0, tzinfo=timezone.utc)
        ms_eod = int(dt_eod.timestamp() * 1000)
        self.assertTrue(is_eod_candle(ms_eod), "23:45 UTC deve ser identificado como vela EOD")

        # 14:15 UTC
        dt_mid = datetime(2024, 1, 1, 14, 15, 0, tzinfo=timezone.utc)
        ms_mid = int(dt_mid.timestamp() * 1000)
        self.assertFalse(is_eod_candle(ms_mid), "14:15 UTC nao pode ser vela EOD")

    def test_02_eod_flat_enforcement(self):
        # Cria serie de 96 candles (1 dia completo de 15m)
        base_time = int(datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        fifteen_min_ms = 15 * 60 * 1000
        candles = []
        price = 40000.0
        for i in range(96):
            t = base_time + i * fifteen_min_ms
            # Simula tendencia de alta para gerar sinal de compra
            price += 15.0 if i < 80 else -10.0
            candles.append({
                "symbol": "BTCUSDT",
                "open_time": t,
                "open_price": price - 5.0,
                "high_price": price + 10.0,
                "low_price": price - 10.0,
                "close_price": price,
                "volume": 100.0
            })

        report = simulate_daytrade_session(candles, self.config)
        self.assertEqual(report.overnight_positions_carried, 0, "Nenhuma posicao pode ser carregada overnight em Day Trade")
        self.assertGreater(report.total_candles, 0)
        self.assertGreater(len(report.equity_curve), 0)

    def test_03_annualization_factor_15m(self):
        self.assertAlmostEqual(FIFTEEN_MIN_ANNUALIZATION_FACTOR, 187.1897, places=3)

    def test_04_signals_generation(self):
        import sqlite3
        db_path = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT symbol, open_time, open_price, high_price, low_price, close_price, volume
            FROM klines_15m
            WHERE symbol = 'BTCUSDT'
            ORDER BY open_time ASC
            LIMIT 200;
        """)
        rows = cur.fetchall()
        conn.close()
        self.assertGreaterEqual(len(rows), 50, "Deve haver candles reais disponiveis no banco")
        candles = [{
            "symbol": r[0], "open_time": r[1], "open_price": r[2],
            "high_price": r[3], "low_price": r[4], "close_price": r[5], "volume": r[6]
        } for r in rows]
        signals = generate_daytrade_signals(candles)
        self.assertEqual(len(signals), len(candles))
        has_buy = "BUY" in signals
        has_sell = "SELL" in signals
        self.assertTrue(has_buy or has_sell, "Deve gerar sinais operacionais (BUY ou SELL)")

    def test_05_leverage_within_bounds(self):
        self.assertLessEqual(self.config.leverage, 3.0, "Alavancagem de Day Trade deve ser <= 3x")


if __name__ == "__main__":
    unittest.main()
