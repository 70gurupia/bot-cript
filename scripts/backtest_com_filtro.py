#!/usr/bin/env python3
"""
Backtest com filtro de constantes (new info) + estratégias existentes (old info).
Caminho: /home/reginato/Projetos/bot-cript/scripts/backtest_com_filtro.py
Base: CSV 1h (BTC, ETH) + filtro de constates (body>0,6, vol_rel>1,3, NY, close>mm20)
"""
import csv, json
from pathlib import Path
from datetime import datetime

CSV_DIR = Path("/home/reginato/Projetos/bot-cript/data/historical")
OUT = Path("/home/reginato/Projetos/bot-cript/analysis/backtest_filtro_resultados.json")

SESSION_MAP = {0:"Tóquio",1:"Tóquio",2:"Tóquio",3:"Tóquio",4:"Tóquio",5:"Tóquio",6:"Londres",7:"Londres",8:"Londres",9:"Londres",10:"Londres",11:"Londres",12:"Londres",13:"NY",14:"NY",15:"NY",16:"NY",17:"NY",18:"Off",19:"Off",20:"Off",21:"Off",22:"Off",23:"Off"}

def load_csv(pair, tf="1h"):
    p = CSV_DIR / f"{pair}_{tf}_2020_2024.csv"
    rows = []
    with open(p, newline="") as f:
        for r in csv.DictReader(f):
            ts = int(r["open_time"])
            dt = datetime.fromtimestamp(ts/1000)
            rows.append({
                "ts": ts, "hour": dt.hour, "dow": dt.strftime("%a"),
                "open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r["volume"]),
            })
    return rows

def calc_indicators(rows):
    for i, r in enumerate(rows):
        range_ = r["high"] - r["low"]
        body = abs(r["close"] - r["open"])
        r["body_pct"] = body / range_ if range_ > 0 else 0.0
        vol_window = [rows[j]["volume"] for j in range(max(0,i-19), i+1)]
        r["vol_rel"] = r["volume"] / (sum(vol_window)/len(vol_window)) if vol_window else 1.0
        # mm20 simples
        closes = [rows[j]["close"] for j in range(max(0,i-19), i+1)]
        r["mm20"] = sum(closes)/len(closes) if closes else r["close"]
        r["pos_mm20"] = (r["close"] - r["mm20"]) / r["mm20"] if r["mm20"] else 0.0
        r["session"] = SESSION_MAP.get(r["hour"], "Off")
    return rows

def _matches_filter(row: dict) -> bool:
    """Verifica se o candle atende às restrições de volatilidade, corpo, sessão e média."""
    return (
        row["body_pct"] > 0.6
        and row["vol_rel"] > 1.3
        and row["session"] == "NY"
        and row["pos_mm20"] > 0.0
    )


def _should_exit(row_next: dict, entry_price: float, use_filter: bool) -> bool:
    """Determina se a posição aberta deve ser encerrada no próximo candle."""
    if not use_filter:
        return True
    if not _matches_filter(row_next):
        return True
    if row_next["close"] < entry_price * 0.98:
        return True
    return False


def _calculate_drawdown(trades: list) -> float:
    """Calcula o drawdown máximo a partir da lista de trades."""
    equity = [100.0]
    cap = 100.0
    for t in trades:
        cap *= (1 + t["pnl_pct"])
        equity.append(cap)
    peak = max(equity)
    return (peak - min(equity)) / peak if peak > 0 else 0.0


def backtest_simple(rows, use_filter=True):
    """Executa a simulação sequencial de trades com ou sem o filtro institucional."""
    capital = 100.0
    in_pos = False
    entry_price = 0.0
    trades = []

    for i in range(len(rows) - 1):
        r = rows[i]
        r_next = rows[i + 1]
        filtro = _matches_filter(r) if use_filter else True

        if filtro and not in_pos:
            in_pos = True
            entry_price = r["close"]
        elif in_pos and _should_exit(r_next, entry_price, use_filter):
            exit_price = r_next["close"]
            pnl_pct = (exit_price - entry_price) / entry_price
            trades.append({"entry": entry_price, "exit": exit_price, "pnl_pct": pnl_pct, "win": pnl_pct > 0})
            capital *= (1 + pnl_pct)
            in_pos = False

    if in_pos:
        exit_price = rows[-1]["close"]
        pnl_pct = (exit_price - entry_price) / entry_price
        trades.append({"entry": entry_price, "exit": exit_price, "pnl_pct": pnl_pct, "win": pnl_pct > 0})
        capital *= (1 + pnl_pct)

    wins = sum(1 for t in trades if t["win"])
    total = len(trades)
    win_rate = wins / total if total > 0 else 0.0
    total_ret = (capital - 100.0) / 100.0
    dd = _calculate_drawdown(trades)

    return {
        "par": rows[0].get("symbol", "N/A"),
        "use_filter": use_filter,
        "trades": total,
        "wins": wins,
        "win_rate": round(win_rate, 3),
        "retorno_pct": round(total_ret * 100, 2),
        "max_drawdown_pct": round(dd * 100, 2),
        "capital_final": round(capital, 2),
        "media_pnl_pos": round(sum(t["pnl_pct"] for t in trades) / max(1, len(trades)), 4)
    }

results = {}
# BTC 1h (Lead-Lag / Donchian / Cash&Carry proxy)
rows = load_csv("BTCUSDT")
rows = calc_indicators(rows)
results["BTC_LeadLag_Donchian_Cash_filtro"] = backtest_simple(rows, use_filter=True)
results["BTC_LeadLag_Donchian_Cash_semfiltro"] = backtest_simple(rows, use_filter=False)
# ETH 1h (Lead-Lag seguidor)
rows_e = load_csv("ETHUSDT")
rows_e = calc_indicators(rows_e)
results["ETH_LeadLag_filtro"] = backtest_simple(rows_e, use_filter=True)
results["ETH_LeadLag_semfiltro"] = backtest_simple(rows_e, use_filter=False)

with open(OUT, "w") as f:
    json.dump(results, f, indent=2, default=str)

with open(str(OUT).replace(".json",".md"), "w") as f:
    f.write("# Backtest com Filtro de Constantes vs Sem Filtro\n")
    f.write("Base: CSV 1h BTC/ETH + filtro (body>0,6, vol_rel>1,3, NY, close>mm20)\n\n")
    for k,v in results.items():
        f.write(f"- **{k}**: trades={v['trades']}, win_rate={v['win_rate']}, ret={v['retorno_pct']}%, DD={v['max_drawdown_pct']}%, cap_final={v['capital_final']}\n")
    f.write("\n**Interpretação:** Se win_rate sob filtro > sem filtro e DD menor, constante é válida.\n")
    f.write("Caminhos: /home/reginato/Projetos/bot-cript/scripts/backtest_com_filtro.py, /home/reginato/Projetos/bot-cript/analysis/backtest_filtro_resultados.json\n")

print("Backtest executado.")
for k,v in results.items():
    print(f"{k}: trades={v['trades']} wins={v['wins']} ret={v['retorno_pct']}% DD={v['max_drawdown_pct']}% cap={v['capital_final']}")
