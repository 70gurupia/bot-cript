#!/usr/bin/env python3
"""
Testes Unitários dos Alertas Operacionais de Telemetria (monitoring/operational_alerts.py).
"""

import unittest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from monitoring.operational_alerts import (
    format_trade_entry_alert,
    format_streak_milestone_alert,
    format_vault_ratchet_alert,
    format_eod_summary_alert
)


class TestOperationalAlerts(unittest.TestCase):

    def test_trade_entry_alert_formatting(self):
        msg = format_trade_entry_alert(
            symbol="ETHUSDT",
            side="BUY",
            entry_price=3000.5,
            take_profit=3120.0,
            stop_loss=2940.0,
            angle_deg=34.2,
            momentum_force=0.85,
            order_book_imbalance=0.42
        )
        self.assertIn("ETHUSDT", msg)
        self.assertIn("COMPRA", msg)
        self.assertIn("Theta", msg)
        self.assertIn("LIMIT MAKER", msg)

    def test_streak_milestone_alert(self):
        msg = format_streak_milestone_alert(
            streak_count=2,
            current_stake=62.5,
            current_bankroll=750.0
        )
        self.assertIn("2/3", msg)
        self.assertIn("R$ 62.50", msg)

    def test_vault_ratchet_alert(self):
        msg = format_vault_ratchet_alert(
            total_locked=500.0,
            transferred_amount=250.0,
            liquid_bankroll=1000.0
        )
        self.assertIn("R$ 500.00", msg)
        self.assertIn("R$ 1,500.00", msg)
        self.assertIn("Invariante de Segurança", msg)

    def test_eod_summary_alert(self):
        msg = format_eod_summary_alert(
            date_str="29/09/2026",
            daily_pnl_brl=125.40,
            daily_trades=3,
            win_rate_pct=66.7,
            total_equity=1250.0,
            vault_locked=500.0
        )
        self.assertIn("29/09/2026", msg)
        self.assertIn("+R$ 125.40", msg)
        self.assertIn("Posições Overnight Abertas: 0", msg)


if __name__ == "__main__":
    unittest.main()
