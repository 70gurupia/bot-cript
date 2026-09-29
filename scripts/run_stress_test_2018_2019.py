#!/usr/bin/env python3
"""
Suíte de Validação e Teste de Estresse Histórico Pré-2020 (2018 e 2019).
Avalia o comportamento de todas as estratégias do robô no teste de estresse mais severo:
- 2018: O grande Bear Market (Bitcoin de $17.000 para $3.150, -82%).
- 2019: O ano de acumulação e forte rally parabólico ($3.500 para $13.800).
Salva relatório em data/stress_test_2018_2019_report.json.
"""

from __future__ import annotations
import os
import sys
import json
import math
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

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
    update_monthly_vault
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(ROOT_DIR, "data", "stress_test_2018_2019_report.json")

# Períodos de Estresse
TS_2018_START = int(datetime(2018, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
TS_2018_END = int(datetime(2018, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

TS_2019_START = int(datetime(2019, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
TS_2019_END = int(datetime(2019, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)


def load_candles(conn: sqlite3.Connection, sym: str, s_ms: int, e_ms: int) -> List[Dict[str, Any]]:
    """Carrega dados horários do SQLite para determinado intervalo."""
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


def _check_donchian_exit(
    side: str, entry_p: float, c_close: float, d_high: float, d_low: float
) -> Tuple[bool, float]:
    """Testa se a posição de Donchian deve ser encerrada por ruptura de canal oposto."""
    if side == "BUY" and c_close < d_low:
        return True, (c_close - entry_p) / entry_p
    if side == "SELL" and c_close > d_high:
        return True, (entry_p - c_close) / entry_p
    return False, 0.0


def evaluate_donchian_breakout(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Testa Trend Following Donchian 20 no Bitcoin com saídas na banda oposta."""
    if len(candles) < 30:
        return {"trades": 0, "win_rate_pct": 0.0, "net_return_pct": 0.0}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    in_pos = False
    side = ""
    entry_p = 0.0
    wins = 0
    trades = 0
    total_pnl = 0.0

    for i in range(21, len(candles)):
        c_close = closes[i]
        d_high = max(highs[i - 20:i])
        d_low = min(lows[i - 20:i])

        if in_pos:
            closed, pnl = _check_donchian_exit(side, entry_p, c_close, d_high, d_low)
            if closed:
                total_pnl += pnl
                trades += 1
                wins += 1 if pnl > 0 else 0
                in_pos = False
            continue

        if c_close > d_high:
            in_pos, side, entry_p = True, "BUY", c_close
        elif c_close < d_low:
            in_pos, side, entry_p = True, "SELL", c_close

    wr = round((wins / trades * 100.0), 1) if trades else 0.0
    return {
        "trades": trades,
        "wins": wins,
        "win_rate_pct": wr,
        "net_return_pct": round(total_pnl * 100.0, 2)
    }


def evaluate_lead_lag(
    leader_candles: List[Dict[str, Any]],
    follower_candles: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Testa o modelo Lead-Lag (BTC liderando ETH) em janelas de 2 horas."""
    n = min(len(leader_candles), len(follower_candles))
    if n < 30:
        return {"trades": 0, "win_rate_pct": 0.0, "net_return_pct": 0.0}

    l_closes = [c["close"] for c in leader_candles[:n]]
    f_closes = [c["close"] for c in follower_candles[:n]]
    f_highs = [c["high"] for c in follower_candles[:n]]
    f_lows = [c["low"] for c in follower_candles[:n]]

    trades = 0
    wins = 0
    total_pnl = 0.0

    for i in range(5, n - 8):
        l_ret = math.log(l_closes[i] / l_closes[i - 2])
        f_ret = math.log(f_closes[i] / f_closes[i - 2])

        if l_ret > 0.018 and f_ret < 0.006:
            trades += 1
            entry = f_closes[i]
            target = entry * 1.025
            stop = entry * 0.985
            fut_high = max(f_highs[i + 1:i + 9])
            fut_low = min(f_lows[i + 1:i + 9])

            if fut_high >= target:
                wins += 1
                total_pnl += 0.025
            elif fut_low <= stop:
                total_pnl -= 0.015
            else:
                pnl = (f_closes[i + 8] - entry) / entry
                total_pnl += pnl
                wins += 1 if pnl > 0 else 0

    wr = round((wins / trades * 100.0), 1) if trades else 0.0
    return {
        "trades": trades,
        "wins": wins,
        "win_rate_pct": wr,
        "net_return_pct": round(total_pnl * 100.0, 2)
    }


def _evaluate_trade_outcome(
    candles: List[Dict[str, Any]],
    start_idx: int,
    side: str,
    tp: float,
    sl: float
) -> Tuple[bool, float]:
    """Avalia o resultado de um trade num horizonte de até 12 candles futuros."""
    max_idx = min(start_idx + 13, len(candles))
    for f in range(start_idx + 1, max_idx):
        fc = candles[f]
        if side == "BUY":
            if fc["high"] >= tp:
                return True, 0.048
            if fc["low"] <= sl:
                return False, -0.024
        elif side == "SELL":
            if fc["low"] <= tp:
                return True, 0.048
            if fc["high"] >= sl:
                return False, -0.024
    return False, -0.010


def evaluate_entropy_model(
    candles: List[Dict[str, Any]],
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Testa compressão de entropia de Shannon e ruptura com R:R 2:1."""
    if len(candles) < 40:
        return {"trades": 0, "win_rate_pct": 0.0, "net_return_pct": 0.0}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    log_rets = compute_log_returns(closes)
    entropies = compute_rolling_entropy(log_rets, cfg.entropy_window, cfg.entropy_bins)
    atrs = compute_atr(highs, lows, closes, cfg.atr_period)
    ema50 = compute_fast_ema(closes, 50)

    trades = 0
    wins = 0
    total_pnl = 0.0
    i = cfg.entropy_window + 5

    while i < len(candles) - 12:
        w = log_rets[i - cfg.entropy_window:i]
        mean_r = sum(w) / len(w)
        var_r = sum((x - mean_r) ** 2 for x in w) / len(w)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0001
        z_log = (log_rets[i] - mean_r) / std_r

        sig, side, sl, tp = detect_entropy_breakout(
            closes[i], ema50[i], entropies[i], z_log, atrs[i], cfg
        )
        if sig:
            trades += 1
            win, pnl = _evaluate_trade_outcome(candles, i, side, tp, sl)
            total_pnl += pnl
            wins += 1 if win else 0
            i += 6
        i += 1

    wr = round((wins / trades * 100.0), 1) if trades else 0.0
    return {
        "trades": trades,
        "wins": wins,
        "win_rate_pct": wr,
        "net_return_pct": round(total_pnl * 100.0, 2)
    }


def simulate_bankroll_evolution(
    trades_pnl: List[float],
    initial_bankroll: float = 500.0
) -> Dict[str, Any]:
    """Simula a curva de capital com Anti-Martingale e Ratchet Vault."""
    bankroll = initial_bankroll
    vault = 0.0
    streak = 0
    base_stake = 40.0

    for pnl in trades_pnl:
        stake = min(bankroll * 0.35, base_stake * (1.25 ** streak))
        if pnl > 0:
            bankroll += stake * 2.0
            streak += 1
            if streak >= 3:
                streak = 0
        else:
            bankroll = max(10.0, bankroll - stake)
            streak = 0

        tot = bankroll + vault
        vault, bankroll = update_monthly_vault(tot, vault, bankroll)

    return {
        "initial_bankroll_brl": initial_bankroll,
        "final_bankroll_brl": round(bankroll + vault, 2),
        "vault_locked_brl": round(vault, 2),
        "liquid_bankroll_brl": round(bankroll, 2)
    }


def run_year_eval(
    conn: sqlite3.Connection,
    y_label: str,
    s_ms: int,
    e_ms: int,
    symbols: List[str],
    cfg: EntropyEngineConfig
) -> Dict[str, Any]:
    """Executa a bateria de testes de um ano específico."""
    print(f"\n--- REGIME: {y_label} ---")
    y_data: Dict[str, Any] = {}

    # 1. Donchian no BTC
    btc_c = load_candles(conn, "BTCUSDT", s_ms, e_ms)
    donch_res = evaluate_donchian_breakout(btc_c)
    y_data["donchian_btc"] = donch_res
    print(f"  [Donchian BTC] Trades: {donch_res['trades']:>2} | Win Rate: {donch_res['win_rate_pct']:>5.1f}% | Retorno: {donch_res['net_return_pct']:>+6.2f}%")

    # 2. Lead-Lag BTC -> ETH
    eth_c = load_candles(conn, "ETHUSDT", s_ms, e_ms)
    ll_res = evaluate_lead_lag(btc_c, eth_c)
    y_data["lead_lag_eth"] = ll_res
    print(f"  [Lead-Lag ETH] Trades: {ll_res['trades']:>2} | Win Rate: {ll_res['win_rate_pct']:>5.1f}% | Retorno: {ll_res['net_return_pct']:>+6.2f}%")

    # 3. Entropia nos pares disponíveis
    entropy_res = {}
    for sym in symbols:
        c = load_candles(conn, sym, s_ms, e_ms)
        if len(c) > 500:
            res = evaluate_entropy_model(c, cfg)
            entropy_res[sym] = res
            print(f"  [Entropia {sym:<8}] Trades: {res['trades']:>2} | Win Rate: {res['win_rate_pct']:>5.1f}% | Retorno: {res['net_return_pct']:>+6.2f}%")
    y_data["entropy_by_symbol"] = entropy_res

    # 4. Simulação de Banca de R$ 500 no Portfolio Selecionado (Donchian + Lead-Lag + ETH Entropy)
    portfolio_pnl = [0.048] * donch_res["wins"] + [-0.024] * (donch_res["trades"] - donch_res["wins"])
    portfolio_pnl += [0.025] * ll_res["wins"] + [-0.015] * (ll_res["trades"] - ll_res["wins"])
    eth_ent = entropy_res.get("ETHUSDT", {"wins": 0, "trades": 0})
    portfolio_pnl += [0.048] * eth_ent["wins"] + [-0.024] * (eth_ent["trades"] - eth_ent["wins"])

    sim_res = simulate_bankroll_evolution(portfolio_pnl, 500.0)
    y_data["bankroll_simulation"] = sim_res
    print(f"  [Banca R$ 500 Simulada] Final: R$ {sim_res['final_bankroll_brl']:,.2f} | Cofre Travado: R$ {sim_res['vault_locked_brl']:,.2f}")

    return y_data


def main() -> int:
    print("==================================================================")
    print("TESTE DE ESTRESSE HISTÓRICO: VALIDAÇÃO EM 2018 E 2019")
    print("==================================================================")

    conn = sqlite3.connect(DB_PATH)
    cfg = EntropyEngineConfig()
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "LINKUSDT", "DOGEUSDT"]
    years = [("2018 (Bear Market)", TS_2018_START, TS_2018_END), ("2019 (Recuperação)", TS_2019_START, TS_2019_END)]

    report = {
        "title": "Validacao de Estresse Historico nos Anos de 2018 e 2019",
        "tested_symbols": symbols,
        "year_evaluations": {}
    }

    for y_label, s_ms, e_ms in years:
        report["year_evaluations"][y_label] = run_year_eval(
            conn, y_label, s_ms, e_ms, symbols, cfg
        )

    conn.close()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[OK] Relatório de Estresse 2018-2019 salvo em: {REPORT_PATH}")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
