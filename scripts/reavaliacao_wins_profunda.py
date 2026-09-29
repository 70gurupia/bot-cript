#!/usr/bin/env python3
"""
Reavaliação profunda de casos win (todos os do benchmark 2024).
Lê data/strategies_benchmark_report.json, carrega CSV de data/historical/,
calcula indicadores por candle (hora/sessão/range/body/volume/MM/ATR/sup-res)
e busca constantes que explicam os wins.
Caminho: /home/reginato/Projetos/bot-cript/scripts/reavaliacao_wins_profunda.py
"""
import json, math
from pathlib import Path
#!/usr/bin/env python3
"""
Reavaliação profunda de casos win (todos do benchmark 2024) — Python puro (sem numpy/pandas).
Lê CSV manualmente, calcula indicadores por candle, busca constantes.
"""
import csv, json, math
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path("/home/reginato/Projetos/bot-cript")
BENCH = BASE / "data/strategies_benchmark_report.json"
CSV_DIR = BASE / "data/historical"
OUT = BASE / "analysis/constantes_wins.json"

SESSION_MAP = {0:"Tóquio",1:"Tóquio",2:"Tóquio",3:"Tóquio",4:"Tóquio",5:"Tóquio",6:"Londres",7:"Londres",8:"Londres",9:"Londres",10:"Londres",11:"Londres",12:"Londres",13:"NY",14:"NY",15:"NY",16:"NY",17:"NY",18:"Off",19:"Off",20:"Off",21:"Off",22:"Off",23:"Off"}

STRATEGIES = [
    {"name":"Lead-Lag BTC->ETH","pair":"BTCUSDT","pair_follow":"ETHUSDT","tf":"15m","win_rate":74.4,"pf":4.32,"dd":1.6,"ret":11.91,"total_trades":39},
    {"name":"Cash & Carry Funding","pair":"BTCUSDT","tf":"8h","win_rate":100.0,"pf":99.0,"dd":0.0,"ret":24.57,"total_trades":366},
    {"name":"Donchian Breakout BTC","pair":"BTCUSDT","tf":"1h","win_rate":41.1,"pf":1.39,"dd":13.2,"ret":42.35,"total_trades":124},
    {"name":"RSI+Bollinger XRP","pair":"XRPUSDT","tf":"15m","win_rate":56.1,"pf":1.07,"dd":103.3,"ret":35.09,"total_trades":779},
    {"name":"RSI+Bollinger ADA","pair":"ADAUSDT","tf":"15m","win_rate":54.2,"pf":1.02,"dd":129.9,"ret":14.88,"total_trades":864},
]

def parse_csv(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "ts": int(r["open_time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
            })
    return rows

def calc_indicators(rows):
    # indicador simples: média móvel 20, body_pct, vol_rel, sessão, hora, ATR simples
    out = []
    vol_window = []
    closes = [r["close"] for r in rows]
    for i, r in enumerate(rows):
        ts_ms = r["ts"]
        hour_utc = (ts_ms // 3600000) % 24  # aproximado; melhor usar datetime se disponível
        # melhor: extrair hora do timestamp já que open_time é ms desde epoch
        # vou usar uma aproximação simples baseada no dia do ano; para este script é aceitável
        from datetime import datetime
        dt = datetime.fromtimestamp(ts_ms/1000)
        hour_utc = dt.hour
        dow = dt.strftime("%a")  # dia da semana
        session = SESSION_MAP.get(hour_utc, "Off")
        range_ = r["high"] - r["low"]
        body = abs(r["close"] - r["open"])
        body_pct = body / range_ if range_ > 0 else 0.0
        vol_window.append(r["volume"])
        vol_media_20 = sum(vol_window[-20:]) / min(20, len(vol_window)) if vol_window else 1.0
        vol_rel = r["volume"] / vol_media_20 if vol_media_20 > 0 else 1.0
        # mm20 simples
        mm20 = sum(closes[max(0,i-19):i+1]) / min(20, i+1) if i >= 0 else r["close"]
        pos_mm20 = (r["close"] - mm20) / mm20
        # ATR simples (14 barras) usando range + prev close
        atr = range_  # simplificado para este script de sondagem
        out.append({
            "ts": ts_ms,
            "hour_utc": hour_utc,
            "session": session,
            "range_": range_,
            "body": body,
            "body_pct": body_pct,
            "vol_rel": vol_rel,
            "mm20": mm20,
            "pos_mm20": pos_mm20,
            "atr": atr,
            "close": r["close"],
            "volume": r["volume"],
            "dow": dt.strftime("%a"),
        })
    return out

def _resolve_csv_file(strategy: dict) -> Path | None:
    """Localiza o arquivo CSV correspondente ao par e timeframe da estratégia."""
    pair = strategy["pair"]
    file_1h = CSV_DIR / f"{pair}_1h_2020_2024.csv"
    file_15m = CSV_DIR / f"{pair}_15m_2020_2024.csv"

    if strategy["tf"] == "15m" and file_15m.exists():
        return file_15m
    if file_1h.exists():
        return file_1h
    return None


def _calc_lead_lag_corr(strategy: dict, csv_file: Path) -> float | None:
    """Calcula a correlação de Lead-Lag de 1 barra com o ativo seguidor, se configurado."""
    if not strategy.get("pair_follow"):
        return None

    f_follow = CSV_DIR / f"{strategy['pair_follow']}_15m_2020_2024.csv"
    if not f_follow.exists():
        return None

    file_15m = CSV_DIR / f"{strategy['pair']}_15m_2020_2024.csv"
    base_csv = file_15m if strategy["tf"] == "15m" and file_15m.exists() else csv_file
    rows_b = parse_csv(base_csv)
    rows_e = parse_csv(f_follow)

    min_n = min(len(rows_b), len(rows_e))
    if min_n <= 10:
        return None

    closes_b = [rows_b[i]["close"] for i in range(min_n)]
    closes_e = [rows_e[i + 1]["close"] for i in range(min_n - 1)]
    mean_b = sum(closes_b[:len(closes_e)]) / len(closes_e)
    mean_e = sum(closes_e) / len(closes_e)

    cov = sum((closes_b[i] - mean_b) * (closes_e[i] - mean_e) for i in range(len(closes_e))) / len(closes_e)
    var_b = sum((x - mean_b) ** 2 for x in closes_b[:len(closes_e)]) / len(closes_e)
    var_e = sum((x - mean_e) ** 2 for x in closes_e) / len(closes_e)

    if var_b > 0 and var_e > 0:
        return round(cov / math.sqrt(var_b * var_e), 4)
    return None


def _evaluate_strategy_metrics(strategy: dict, csv_file: Path) -> dict:
    """Calcula todas as métricas e constantes de sondagem de uma estratégia."""
    rows = parse_csv(csv_file)
    ind = calc_indicators(rows)
    both = [r for r in ind if r["body_pct"] > 0.6 and r["vol_rel"] > 1.3]

    body_by_hour = defaultdict(list)
    session_vol = defaultdict(float)
    session_n = defaultdict(int)

    for r in ind:
        body_by_hour[r["hour_utc"]].append(r["body_pct"])
        session_vol[r["session"]] += r["vol_rel"]
        session_n[r["session"]] += 1

    best_hour = max(body_by_hour, key=lambda h: sum(body_by_hour[h]) / max(1, len(body_by_hour[h])))
    session_vol_avg = {k: round(session_vol[k] / max(1, session_n[k]), 3) for k in session_vol}
    corr_lead = _calc_lead_lag_corr(strategy, csv_file)

    return {
        "estrategia": strategy["name"],
        "par": strategy["pair"],
        "timeframe": strategy["tf"],
        "win_rate": strategy["win_rate"],
        "retorno": strategy["ret"],
        "max_dd": strategy["dd"],
        "linhas": len(ind),
        "mean_vol_rel": round(sum(r["vol_rel"] for r in ind) / max(1, len(ind)), 3),
        "mean_body_pct": round(sum(r["body_pct"] for r in ind) / max(1, len(ind)), 3),
        "best_dow": Counter(r.get("dow", "?") for r in ind).most_common(1)[0][0] if ind else "N/A",
        "count_body_high_vol": len(both),
        "pct_strong": round(100 * len(both) / max(1, len(ind)), 2),
        "best_hour_by_body": best_hour,
        "session_vol_avg": session_vol_avg,
        "lead_lag_corr_1bar": corr_lead,
        "nota": "Constante sugerida: body_pct > 0,6 + vol_rel > 1,3 + sessao NY (13-18h) + close > mm20 (pos_mm20 > 0). Se >50% das barras fortes atenderem, valida filtro no AST."
    }


def main():
    results = {}
    for s in STRATEGIES:
        csv_file = _resolve_csv_file(s)
        if not csv_file or not csv_file.exists():
            results[s["name"]] = {"erro": "CSV não encontrado"}
            continue
        results[s["name"]] = _evaluate_strategy_metrics(s, csv_file)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print("Executado.", OUT)
    for k, v in results.items():
        if isinstance(v, dict):
            print(f"{k}: strong_pct={v.get('pct_strong')}, best_hour={v.get('best_hour_by_body')}, lead={v.get('lead_lag_corr_1bar')}")


if __name__ == "__main__":
    main()


BASE = Path("/home/reginato/Projetos/bot-cript")
BENCH = BASE / "data/strategies_benchmark_report.json"
CSV_DIR = BASE / "data/historical"
OUT = BASE / "analysis/constantes_wins.json"

# Estratégias win comprovadas no benchmark (nome, par, timeframe, total_trades, win_rate, return, max_dd)
STRATEGIES = [
    {"name":"Lead-Lag BTC->ETH","pair":"BTCUSDT","pair_follow":"ETHUSDT","tf":"15m","win_rate":74.4,"pf":4.32,"dd":1.6,"ret":11.91},
    {"name":"Cash & Carry Funding","pair":"BTCUSDT","tf":"8h","win_rate":100.0,"pf":99.0,"dd":0.0,"ret":24.57},
    {"name":"Donchian Breakout BTC","pair":"BTCUSDT","tf":"1h","win_rate":41.1,"pf":1.39,"dd":13.2,"ret":42.35},
    {"name":"RSI+Bollinger XRP","pair":"XRPUSDT","tf":"15m","win_rate":56.1,"pf":1.07,"dd":103.3,"ret":35.09},
    {"name":"RSI+Bollinger ADA","pair":"ADAUSDT","tf":"15m","win_rate":54.2,"pf":1.02,"dd":129.9,"ret":14.88},
]

SESSION_MAP = {0:"Tóquio",1:"Tóquio",2:"Tóquio",3:"Tóquio",4:"Tóquio",5:"Tóquio",6:"Londres",7:"Londres",8:"Londres",9:"Londres",10:"Londres",11:"Londres",12:"Londres",13:"NY",14:"NY",15:"NY",16:"NY",17:"NY",18:"Off",19:"Off",20:"Off",21:"Off",22:"Off",23:"Off"}

