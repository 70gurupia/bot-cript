"""
Suíte de Testes do Loop Assíncrono Central (BotEventLoop).
Valida:
1. Ciclo de decisão, validação de tesouraria e envio de ordens.
2. Pausa automática quando o Circuit Breaker estiver travado.
3. Modo de espera (HOLD) quando a Laia filtrar a entrada.
4. Execução contínua com encerramento determinístico.
"""

from __future__ import annotations
import os
import sys
import asyncio
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.event_loop import BotEventLoop
from core.kill_switch import CircuitBreakerManager
from core.exchange_adapter import ExchangeAdapter
from treasury.treasury_controller import TreasuryController


import tempfile
from pathlib import Path


class TestBotEventLoop(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmpdir.name) / "cb_test.json"
        self.cb = CircuitBreakerManager(state_file=self.state_file)
        self.adapter = ExchangeAdapter(paper_trading=True)
        self.treasury = TreasuryController()
        self.loop = BotEventLoop(
            adapter=self.adapter,
            treasury=self.treasury,
            cb_manager=self.cb,
            tick_interval_sec=0.01
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_step_order_processed_when_signal_is_high_quality(self):
        """Valida despacho de ordem quando há descompasso de Lead-Lag na sessão de NY."""
        res = asyncio.run(self.loop.step(
            symbol="ETHUSDT",
            btc_ret_15m=0.015,
            alt_ret_15m=0.001,
            hour_utc=15,
            funding=-0.0002
        ))
        self.assertEqual(res["status"], "ORDER_PROCESSED")
        self.assertEqual(res["action"], "LONG")
        self.assertEqual(res["execution"]["status"], "SUBMITTED")

    def test_step_paused_when_circuit_breaker_is_locked(self):
        """Valida que o loop não opera quando o circuit breaker L2 estiver travado."""
        self.cb.trip_level_2_portfolio(current_equity_usd=9000.0, baseline_equity_usd=10000.0, reason="TEST_LOCK")
        res = asyncio.run(self.loop.step(symbol="ETHUSDT"))
        self.assertEqual(res["status"], "PAUSED")
        self.assertIn("CIRCUIT_BREAKER_LOCKED", res["reason"])

    def test_step_hold_when_laia_filters_entry(self):
        """Valida modo HOLD quando a confluência for insuficiente (Ásia + funding esticado)."""
        res = asyncio.run(self.loop.step(
            symbol="ETHUSDT",
            btc_ret_15m=0.001,
            alt_ret_15m=0.001,
            hour_utc=3,
            funding=0.0008
        ))
        self.assertEqual(res["status"], "HOLD")

    def test_run_forever_max_ticks(self):
        """Valida execução contínua com limite de ticks."""
        asyncio.run(self.loop.run_forever(max_ticks=3))
        self.assertEqual(self.loop.total_ticks, 3)
        self.assertFalse(self.loop.is_running)


if __name__ == "__main__":
    unittest.main()
