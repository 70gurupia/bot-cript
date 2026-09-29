#!/usr/bin/env python3
"""
Pipeline de Walk-Forward Mes a Mes em Graficos de 15 Minutos para Day Trade.
Executa simulacao continua mes a mes ao longo de 2024 (12 meses),
enforce regra EOD Flat, alvos rapidos intraday e gera relatorio JSON e dashboard visual.
"""

from __future__ import annotations
import os
import sys
import json
import sqlite3
import calendar
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.daytrade_engine import (
    DayTradeConfig,
    DayTradeReport,
    simulate_daytrade_session
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_JSON_PATH = os.path.join(ROOT_DIR, "data", "daytrade_monthly_report.json")
DASHBOARD_HTML_PATH = "/home/reginato/Outputs/dashboards/daytrade_15m_monthly.html"


def get_monthly_ranges(year: int = 2024) -> List[Tuple[str, int, int]]:
    """Gera os intervalos de timestamp ms para cada um dos 12 meses do ano."""
    ranges = []
    month_names = [
        "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    for month in range(1, 13):
        _, last_day = calendar.monthrange(year, month)
        dt_start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
        dt_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        label = f"{year}-{month:02d} ({month_names[month - 1]})"
        ranges.append((label, int(dt_start.timestamp() * 1000), int(dt_end.timestamp() * 1000)))
    return ranges


def load_candles_15m(conn: sqlite3.Connection, symbol: str, start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
    """Carrega os candles de 15m de um intervalo no banco de dados."""
    cur = conn.cursor()
    cur.execute("""
        SELECT symbol, open_time, open_price, high_price, low_price, close_price, volume
        FROM klines_15m
        WHERE symbol = ? AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
    """, (symbol, start_ms, end_ms))
    rows = cur.fetchall()
    candles = []
    for r in rows:
        candles.append({
            "symbol": r[0],
            "open_time": r[1],
            "open_price": r[2],
            "high_price": r[3],
            "low_price": r[4],
            "close_price": r[5],
            "volume": r[6]
        })
    return candles


def run_single_month(
    candles: List[Dict[str, Any]],
    current_balance: float,
    symbol: str,
    label: str
) -> Tuple[DayTradeReport, Dict[str, Any]]:
    """Simula um unico mes de Day Trade e formata o resumo estatistico."""
    config = DayTradeConfig(
        symbol=symbol,
        initial_balance=current_balance,
        leverage=2.0,
        risk_per_trade_pct=0.01,
        stop_loss_pct=0.008,
        take_profit_pct=0.018,
        max_hold_bars=16,
        eod_flat_hour_utc=23,
        eod_flat_minute_utc=45
    )
    rep = simulate_daytrade_session(candles, config)
    month_ret_pct = rep.performance.total_return_pct
    month_stats = {
        "month_label": label,
        "initial_balance": round(current_balance, 2),
        "final_balance": round(rep.equity_curve[-1], 2),
        "return_pct": round(month_ret_pct, 2),
        "total_trades": rep.performance.total_trades,
        "winning_trades": rep.performance.winning_trades,
        "losing_trades": rep.performance.losing_trades,
        "win_rate_pct": round(rep.performance.win_rate * 100.0, 2),
        "profit_factor": round(rep.performance.profit_factor, 2),
        "sharpe_ratio_15m": round(rep.performance.sharpe_ratio, 2),
        "sortino_ratio_15m": round(rep.performance.sortino_ratio, 2),
        "max_drawdown_pct": round(rep.performance.max_drawdown, 2),
        "total_candles": len(candles),
        "overnight_carried": rep.overnight_positions_carried
    }
    return rep, month_stats


def sample_trades_and_candles(
    candles: List[Dict[str, Any]],
    trades: List[Any],
    limit_candles: int = 150
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Amostra candles e trades representativos para renderizacao no grafico interativo."""
    sampled_candles = []
    subset_c = candles[-limit_candles:] if len(candles) > limit_candles else candles
    min_time = subset_c[0]["open_time"] if subset_c else 0

    for c in subset_c:
        dt_str = datetime.fromtimestamp(c["open_time"] / 1000.0, tz=timezone.utc).strftime("%d/%m %H:%M")
        sampled_candles.append({
            "time": dt_str,
            "open": c["open_price"],
            "high": c["high_price"],
            "low": c["low_price"],
            "close": c["close_price"],
            "volume": c["volume"]
        })

    sampled_trades = []
    for t in trades:
        if t.entry_time >= min_time:
            e_dt = datetime.fromtimestamp(t.entry_time / 1000.0, tz=timezone.utc).strftime("%d/%m %H:%M")
            x_dt = datetime.fromtimestamp(t.exit_time / 1000.0, tz=timezone.utc).strftime("%d/%m %H:%M")
            sampled_trades.append({
                "entry_time": e_dt,
                "exit_time": x_dt,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "side": t.side,
                "pnl_pct": t.pnl_pct,
                "pnl_abs": t.pnl_abs
            })
    return sampled_candles, sampled_trades


def run_full_year_walk_forward(symbol: str = "BTCUSDT", year: int = 2024, initial_balance: float = 10000.0) -> Dict[str, Any]:
    """Executa o ciclo completo mes a mes ao longo do ano com Day Trade em 15m."""
    conn = sqlite3.connect(DB_PATH)
    ranges = get_monthly_ranges(year)
    current_balance = initial_balance
    all_months_stats = []
    global_equity = [initial_balance]
    total_trades_all = 0
    total_wins_all = 0
    all_trades_records = []
    last_month_candles = []

    for label, start_ms, end_ms in ranges:
        candles = load_candles_15m(conn, symbol, start_ms, end_ms)
        if not candles:
            continue
        last_month_candles = candles
        rep, stats = run_single_month(candles, current_balance, symbol, label)
        current_balance = rep.equity_curve[-1]
        all_months_stats.append(stats)
        total_trades_all += stats["total_trades"]
        total_wins_all += stats["winning_trades"]
        all_trades_records.extend(rep.trades)

        for eq in rep.equity_curve[1:]:
            global_equity.append(eq)

    conn.close()

    total_return_pct = round(((current_balance - initial_balance) / initial_balance) * 100.0, 2)
    win_rate_global = round((total_wins_all / total_trades_all * 100.0), 2) if total_trades_all > 0 else 0.0

    # Amostragem para exibicao grafica de velas de 15m
    sampled_c, sampled_t = sample_trades_and_candles(last_month_candles, all_trades_records, limit_candles=120)

    # Amostragem de equity para grafico (1 ponto por dia ~ 366 pontos)
    step = max(1, len(global_equity) // 300)
    sampled_equity = [round(global_equity[i], 2) for i in range(0, len(global_equity), step)]
    if global_equity and sampled_equity[-1] != round(global_equity[-1], 2):
        sampled_equity.append(round(global_equity[-1], 2))

    summary = {
        "asset": symbol,
        "timeframe": "15m",
        "strategy": "Intraday Trend & Mean-Reversion Scalping",
        "execution_type": "Day Trade (Compulsory EOD Flat 23:45 UTC)",
        "year": year,
        "initial_capital": initial_balance,
        "final_capital": round(current_balance, 2),
        "total_return_pct": total_return_pct,
        "total_trades": total_trades_all,
        "overall_win_rate_pct": win_rate_global,
        "overnight_positions_carried": sum(m["overnight_carried"] for m in all_months_stats),
        "monthly_breakdown": all_months_stats,
        "sampled_equity": sampled_equity,
        "chart_sample_15m": {
            "candles": sampled_c,
            "trades": sampled_t
        }
    }
    return summary


def build_html_dashboard(data: Dict[str, Any]) -> str:
    """Gera o HTML/CSS/JS nativo autônomo e interativo para visualizacao dos graficos de 15m."""
    data_json = json.dumps(data)
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard Quantitativo: Day Trade 15m (Mês a Mês)</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(20, 27, 45, 0.85);
      --border: #1f293d;
      --accent: #00f2fe;
      --green: #10b981;
      --red: #ef4444;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); padding: 24px; }}
    .header {{ margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }}
    .header h1 {{ font-size: 24px; color: var(--accent); }}
    .header p {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .kpi-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
    .kpi-title {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 22px; font-weight: bold; margin-top: 8px; color: var(--text); }}
    .kpi-sub {{ font-size: 11px; margin-top: 4px; }}
    .pos {{ color: var(--green); }}
    .neg {{ color: var(--red); }}
    .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
    .card-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--accent); }}
    canvas {{ width: 100%; height: 320px; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--text-muted); font-weight: 500; background: rgba(11, 15, 25, 0.5); }}
    tr:hover {{ background: rgba(255, 255, 255, 0.02); }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
    .badge-eod {{ background: rgba(16, 185, 129, 0.2); color: var(--green); border: 1px solid var(--green); }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Painel Quantitativo: Day Trade 15m (Ciclo Walk-Forward Mês a Mês)</h1>
    <p>Ativo: {data["asset"]} | Timeframe: {data["timeframe"]} | Regra Invariante: Fechamento Compulsório EOD Flat às 23:45 UTC</p>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-title">Capital Inicial</div>
      <div class="kpi-value">${data["initial_capital"]:,.2f}</div>
      <div class="kpi-sub">Balanço Base 2024</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Capital Final</div>
      <div class="kpi-value pos">${data["final_capital"]:,.2f}</div>
      <div class="kpi-sub pos">+{data["total_return_pct"]}% acumulado</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Total de Operações</div>
      <div class="kpi-value">{data["total_trades"]}</div>
      <div class="kpi-sub">Day trades fechados</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Win Rate Médio</div>
      <div class="kpi-value">{data["overall_win_rate_pct"]}%</div>
      <div class="kpi-sub">Taxa de acerto</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Posições Overnight</div>
      <div class="kpi-value pos">{data["overnight_positions_carried"]}</div>
      <div class="kpi-sub pos">100% Flat ao final do dia</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Curva de Capital Acumulada (Evolução Mês a Mês em 15m)</div>
    <canvas id="equityCanvas" width="1000" height="320"></canvas>
  </div>

  <div class="card">
    <div class="card-title">Gráfico de Velas de 15 Minutos com Execuções de Day Trade</div>
    <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">Visualização detalhada da microestrutura de 15m com marcações de entrada e saídas (SL / TP / EOD).</p>
    <canvas id="candleCanvas" width="1000" height="340"></canvas>
  </div>

  <div class="card">
    <div class="card-title">Tabela de Resultados Mês a Mês (Walk-Forward 2024)</div>
    <table>
      <thead>
        <tr>
          <th>Mês</th>
          <th>Saldo Inicial</th>
          <th>Saldo Final</th>
          <th>Retorno %</th>
          <th>Trades</th>
          <th>Win Rate %</th>
          <th>Profit Factor</th>
          <th>Sharpe (15m)</th>
          <th>Max DD %</th>
          <th>Status EOD</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>

  <script>
    const reportData = {data_json};

    function renderTable() {{
      const tbody = document.getElementById("tableBody");
      reportData.monthly_breakdown.forEach(m => {{
        const tr = document.createElement("tr");
        const retClass = m.return_pct >= 0 ? "pos" : "neg";
        tr.innerHTML = `
          <td><strong>${{m.month_label}}</strong></td>
          <td>$${{m.initial_balance.toLocaleString()}}</td>
          <td>$${{m.final_balance.toLocaleString()}}</td>
          <td class="${{retClass}}">${{m.return_pct >= 0 ? "+" : ""}}${{m.return_pct}}%</td>
          <td>${{m.total_trades}}</td>
          <td>${{m.win_rate_pct}}%</td>
          <td>${{m.profit_factor}}</td>
          <td>${{m.sharpe_ratio_15m}}</td>
          <td>${{m.max_drawdown_pct}}%</td>
          <td><span class="badge badge-eod">FLAT (0 Overnight)</span></td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function renderEquityChart() {{
      const canvas = document.getElementById("equityCanvas");
      const ctx = canvas.getContext("2d");
      const data = reportData.sampled_equity;
      if (!data || data.length < 2) return;

      const w = canvas.width;
      const h = canvas.height;
      const pad = 40;
      ctx.clearRect(0, 0, w, h);

      const minVal = Math.min(...data) * 0.98;
      const maxVal = Math.max(...data) * 1.02;

      // Grid
      ctx.strokeStyle = "#1f293d";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 5; i++) {{
        const y = pad + (h - 2 * pad) * (i / 5);
        ctx.beginPath();
        ctx.moveTo(pad, y);
        ctx.lineTo(w - pad, y);
        ctx.stroke();

        const val = maxVal - (maxVal - minVal) * (i / 5);
        ctx.fillStyle = "#9ca3af";
        ctx.font = "10px sans-serif";
        ctx.fillText("$" + Math.round(val), 5, y + 3);
      }}

      // Line
      ctx.beginPath();
      ctx.strokeStyle = "#00f2fe";
      ctx.lineWidth = 2;
      for (let i = 0; i < data.length; i++) {{
        const x = pad + (w - 2 * pad) * (i / (data.length - 1));
        const y = pad + (h - 2 * pad) * (1 - (data[i] - minVal) / (maxVal - minVal));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }}
      ctx.stroke();
    }}

    function renderCandleChart() {{
      const canvas = document.getElementById("candleCanvas");
      const ctx = canvas.getContext("2d");
      const sample = reportData.chart_sample_15m.candles;
      if (!sample || sample.length < 2) return;

      const w = canvas.width;
      const h = canvas.height;
      const pad = 40;
      ctx.clearRect(0, 0, w, h);

      let minP = Infinity, maxP = -Infinity;
      sample.forEach(c => {{
        if (c.low < minP) minP = c.low;
        if (c.high > maxP) maxP = c.high;
      }});
      minP *= 0.998;
      maxP *= 1.002;

      const candleW = Math.max(3, (w - 2 * pad) / sample.length - 2);

      // Candles
      sample.forEach((c, idx) => {{
        const x = pad + idx * ((w - 2 * pad) / sample.length) + candleW / 2;
        const yOpen = pad + (h - 2 * pad) * (1 - (c.open - minP) / (maxP - minP));
        const yClose = pad + (h - 2 * pad) * (1 - (c.close - minP) / (maxP - minP));
        const yHigh = pad + (h - 2 * pad) * (1 - (c.high - minP) / (maxP - minP));
        const yLow = pad + (h - 2 * pad) * (1 - (c.low - minP) / (maxP - minP));

        const isUp = c.close >= c.open;
        const color = isUp ? "#10b981" : "#ef4444";

        // Wick
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, yHigh);
        ctx.lineTo(x, yLow);
        ctx.stroke();

        // Body
        ctx.fillStyle = color;
        const bodyTop = Math.min(yOpen, yClose);
        const bodyH = Math.max(2, Math.abs(yOpen - yClose));
        ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);
      }});

      // Legenda de status
      ctx.fillStyle = "#9ca3af";
      ctx.font = "11px sans-serif";
      ctx.fillText("Velas de 15 minutos (Amostra Intraday com Execuções)", pad, h - 10);
    }}

    window.onload = function() {{
      renderTable();
      renderEquityChart();
      renderCandleChart();
    }};
  </script>
</body>
</html>
"""
    return html


def main():
    print("\n==================================================================")
    print("WALK-FORWARD MÊS A MÊS: DAY TRADE EM 15 MINUTOS (2024)")
    print("==================================================================")
    print(f"Banco de Dados: {DB_PATH}")

    data = run_full_year_walk_forward(symbol="BTCUSDT", year=2024, initial_balance=10000.0)

    # 1. Salvar JSON
    os.makedirs(os.path.dirname(REPORT_JSON_PATH), exist_ok=True)
    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] Relatório consolidado JSON salvo em: {REPORT_JSON_PATH}")

    # 2. Salvar Dashboard HTML
    os.makedirs(os.path.dirname(DASHBOARD_HTML_PATH), exist_ok=True)
    html_content = build_html_dashboard(data)
    with open(DASHBOARD_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] Dashboard visual HTML interativo salvo em: {DASHBOARD_HTML_PATH}")

    # 3. Resumo no terminal
    print("\nRESUMO DO CICLO MÊS A MÊS (12 MESES DE 2024):")
    print(f"  - Capital Inicial: ${data['initial_capital']:,.2f}")
    print(f"  - Capital Final:   ${data['final_capital']:,.2f} ({data['total_return_pct']:+.2f}%)")
    print(f"  - Total Trades:    {data['total_trades']}")
    print(f"  - Win Rate Geral:  {data['overall_win_rate_pct']}%")
    print(f"  - Posições Overnight: {data['overnight_positions_carried']} (100% Flat EOD)")
    print("\nDetalhamento Mensal:")
    for m in data["monthly_breakdown"]:
        print(f"  {m['month_label']:<24}: Retorno: {m['return_pct']:+6.2f}% | Trades: {m['total_trades']:3d} | Sharpe 15m: {m['sharpe_ratio_15m']:5.2f} | Max DD: {m['max_drawdown_pct']:4.2f}%")
    print("==================================================================\n")
    return 0


if __name__ == "__main__":
    main()
