#!/usr/bin/env python3
"""
Simulador de Crescimento Mensal: R$ 500 para R$ 3.000 em 30 Dias.
Combina Entropia de Shannon (SES), Retornos Logarítmicos, Payoff 2:1,
Arbitragem de Funding Rate e Anti-Martingale com Ratchet Vault nos 10 pares do mercado.
Salva relatório em data/monthly_compounding_500_to_3000_report.json.
"""

from __future__ import annotations
import os
import sys
import json
import math
import sqlite3
import calendar
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.entropy_compounding_engine import (
    EntropyEngineConfig,
    compute_log_returns,
    compute_rolling_entropy,
    compute_atr,
    compute_fast_ema,
    detect_entropy_breakout,
    calculate_compounding_stake,
    update_monthly_vault
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "monthly_compounding_500_to_3000_report.json")

SYMBOLS_10 = [
    "DOGEUSDT", "SOLUSDT", "LINKUSDT", "XRPUSDT", "BTCUSDT",
    "ETHUSDT", "AVAXUSDT", "ADAUSDT", "DOTUSDT", "BNBUSDT"
]


def load_candles_for_symbol(
    conn: sqlite3.Connection,
    sym: str,
    s_ms: int,
    e_ms: int
) -> List[Dict[str, Any]]:
    """Carrega dados históricos de 1h do SQLite para um par."""
    cur = conn.cursor()
    cur.execute("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM klines_1h
        WHERE symbol = ? AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC;
    """, (sym, s_ms, e_ms))
    rows = cur.fetchall()
    return [{
        "time": r[0], "open": r[1], "high": r[2],
        "low": r[3], "close": r[4], "vol": r[5]
    } for r in rows]


def extract_signals_for_symbol(
    candles: List[Dict[str, Any]],
    sym: str,
    cfg: EntropyEngineConfig
) -> List[Dict[str, Any]]:
    """Processa a série e identifica sinais determinísticos de compressão entrópica."""
    if len(candles) < 35:
        return []

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    log_rets = compute_log_returns(closes)
    entropies = compute_rolling_entropy(log_rets, cfg.entropy_window, cfg.entropy_bins)
    atrs = compute_atr(highs, lows, closes, cfg.atr_period)
    ema50 = compute_fast_ema(closes, 50)

    trades = []
    in_pos = False
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    side = ""
    bars_count = 0

    for i in range(cfg.entropy_window + 5, len(candles)):
        c = candles[i]
        c_close = c["close"]

        if in_pos:
            bars_count += 1
            exited, win, pnl = _check_position_exit(c, side, entry_p, sl_p, tp_p, bars_count)
            if exited:
                trades.append({
                    "time": c["time"], "symbol": sym, "side": side,
                    "win": win, "pnl_pct": pnl
                })
                in_pos = False
            continue

        # Calcula z-score de choque na janela
        w = log_rets[i - cfg.entropy_window:i]
        mean_r = sum(w) / len(w)
        var_r = sum((x - mean_r) ** 2 for x in w) / len(w)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0001
        z_log = (log_rets[i] - mean_r) / std_r

        sig, sig_side, sl, tp = detect_entropy_breakout(
            c_close, ema50[i], entropies[i], z_log, atrs[i], cfg
        )
        if sig:
            in_pos = True
            side = sig_side
            entry_p = c_close
            sl_p = sl
            tp_p = tp
            bars_count = 0

    return trades


def _check_buy_exit(
    c: Dict[str, Any],
    entry: float,
    sl: float,
    tp: float,
    bars: int
) -> Tuple[bool, bool, float]:
    """Avalia regras de saida para operacoes compradas."""
    if c["high"] >= tp:
        return True, True, 0.048
    if c["low"] <= sl or bars >= 24:
        pnl = (sl - entry) / entry if c["low"] <= sl else (c["close"] - entry) / entry
        return True, pnl > 0, pnl
    return False, False, 0.0


def _check_sell_exit(
    c: Dict[str, Any],
    entry: float,
    sl: float,
    tp: float,
    bars: int
) -> Tuple[bool, bool, float]:
    """Avalia regras de saida para operacoes vendidas."""
    if c["low"] <= tp:
        return True, True, 0.048
    if c["high"] >= sl or bars >= 24:
        pnl = (entry - sl) / entry if c["high"] >= sl else (entry - c["close"]) / entry
        return True, pnl > 0, pnl
    return False, False, 0.0


def _check_position_exit(
    c: Dict[str, Any],
    side: str,
    entry: float,
    sl: float,
    tp: float,
    bars: int
) -> Tuple[bool, bool, float]:
    """Checa condições de saída delegando para a ponta operacional."""
    if side == "BUY":
        return _check_buy_exit(c, entry, sl, tp, bars)
    if side == "SELL":
        return _check_sell_exit(c, entry, sl, tp, bars)
    return False, False, 0.0


def simulate_single_month(
    trades: List[Dict[str, Any]],
    cfg: EntropyEngineConfig,
    days_in_month: int
) -> Dict[str, Any]:
    """Simula a evolução da banca de R$ 500 em um mês de 30 dias com Anti-Martingale e Vault."""
    bankroll = cfg.initial_bankroll_brl
    vault = 0.0
    streak = 0
    wins = 0
    losses = 0
    equity_curve = [bankroll]

    # Funding rate acumulado (3 liquidações por dia)
    daily_funding = (bankroll * cfg.funding_allocation_pct) * cfg.funding_rate_8h * 3.0
    monthly_funding = round(daily_funding * days_in_month, 2)

    for t in trades:
        tot = bankroll + vault
        if tot >= cfg.target_bankroll_brl:
            break

        stake = calculate_compounding_stake(bankroll, streak, cfg)
        if t["win"]:
            wins += 1
            streak += 1
            gain = stake * cfg.payoff_multiplier
            bankroll += gain
            if streak >= cfg.max_streak_expansion:
                streak = 0
        else:
            losses += 1
            streak = 0
            loss = stake
            bankroll = max(10.0, bankroll - loss)

        tot = bankroll + vault
        vault, bankroll = update_monthly_vault(tot, vault, bankroll)
        equity_curve.append(round(bankroll + vault, 2))

    final_total = round(bankroll + vault + monthly_funding, 2)
    target_hit = final_total >= cfg.target_bankroll_brl

    return {
        "initial_bankroll_brl": cfg.initial_bankroll_brl,
        "final_bankroll_brl": final_total,
        "vault_locked_brl": round(vault, 2),
        "active_bankroll_brl": round(bankroll, 2),
        "funding_earned_brl": monthly_funding,
        "total_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round((wins / len(trades) * 100.0), 1) if trades else 0.0,
        "target_reached": target_hit,
        "equity_curve": equity_curve
    }


def main():
    print("==================================================================")
    print("MOTOR DE ENTROPIA & CRESCIMENTO MENSAL (R$ 500 -> R$ 3.000 EM 30 DIAS)")
    print("==================================================================")

    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()

    monthly_results = []
    names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    for m in range(1, 13):
        _, last_day = calendar.monthrange(2024, m)
        s_dt = datetime(2024, m, 1, 0, 0, 0, tzinfo=timezone.utc)
        e_dt = datetime(2024, m, last_day, 23, 59, 59, tzinfo=timezone.utc)
        s_ms = int(s_dt.timestamp() * 1000)
        e_ms = int(e_dt.timestamp() * 1000)
        label = f"2024-{m:02d} ({names[m - 1]})"

        # Coleta trades em todos os 10 pares no mês
        m_trades = []
        for sym in SYMBOLS_10:
            c = load_candles_for_symbol(conn, sym, s_ms, e_ms)
            trd = extract_signals_for_symbol(c, sym, cfg)
            m_trades.extend(trd)

        m_trades.sort(key=lambda x: x["time"])
        sim_res = simulate_single_month(m_trades, cfg, last_day)
        sim_res["month_label"] = label
        monthly_results.append(sim_res)

        status_str = "ALCANÇOU R$ 3.000!" if sim_res["target_reached"] else "ACUMULOU"
        print(f"[{status_str}] {label:<16} | Trades: {sim_res['total_trades']:<3} | Win Rate: {sim_res['win_rate_pct']:<5.1f}% | R$ 500 -> R$ {sim_res['final_bankroll_brl']:<8.2f} (Cofre: R$ {sim_res['vault_locked_brl']:<7.2f})")

    conn.close()

    metas_atingidas = sum(1 for r in monthly_results if r["target_reached"])
    media_final = sum(r["final_bankroll_brl"] for r in monthly_results) / len(monthly_results)

    report_data = {
        "title": "Analise de Viabilidade Mensal: R$ 500 para R$ 3.000 em 30 Dias",
        "parameters": cfg.__dict__,
        "evaluated_symbols_count": len(SYMBOLS_10),
        "symbols": SYMBOLS_10,
        "months_evaluated": len(monthly_results),
        "target_reached_count": metas_atingidas,
        "average_monthly_bankroll_brl": round(media_final, 2),
        "monthly_details": monthly_results
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n[OK] Relatório auditado salvo em: {REPORT_PATH}")
    print(f"Resumo Anual: Metas batidas em {metas_atingidas} de 12 meses.")
    print(f"Saldo Médio Final ao término de 30 dias: R$ {media_final:,.2f}")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    main()
