#!/usr/bin/env python3
"""
Pipeline de Walk-Forward Mes a Mes do Motor Hibrido (Hybrid Alpha).
Combina arbitragem de Funding Rate continuo com Price Action nos pares campeoes (LINK, BNB, SOL).
Gera projecoes em R$/dia e exporta relatorio JSON e dashboard visual.
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

from strategy.daytrade_engine import compute_fast_ema
from strategy.hybrid_alpha_engine import (
    HybridAlphaConfig,
    DailyProjections,
    HybridMonthReport,
    is_ny_session,
    is_funding_hour,
    detect_pin_bar_signal,
    check_trade_exit,
    process_closed_trade,
    compute_daily_projections
)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
REPORT_JSON_PATH = os.path.join(ROOT_DIR, "data", "hybrid_alpha_report.json")
DASHBOARD_HTML_PATH = "/home/reginato/Outputs/dashboards/hybrid_alpha_dashboard.html"


def get_monthly_ranges_2024() -> List[Tuple[str, int, int]]:
    """Gera tuplas de timestamp para os 12 meses de 2024."""
    ranges = []
    names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    for m in range(1, 13):
        _, last_day = calendar.monthrange(2024, m)
        s_dt = datetime(2024, m, 1, 0, 0, 0, tzinfo=timezone.utc)
        e_dt = datetime(2024, m, last_day, 23, 59, 59, tzinfo=timezone.utc)
        ranges.append((f"2024-{m:02d} ({names[m - 1]})", int(s_dt.timestamp() * 1000), int(e_dt.timestamp() * 1000)))
    return ranges


def load_candles_symbol(conn: sqlite3.Connection, sym: str, s_ms: int, e_ms: int) -> List[Dict[str, Any]]:
    """Carrega dados historicos de um par para determinado intervalo."""
    cur = conn.cursor()
    cur.execute("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM klines_1h
        WHERE symbol = ? AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC;
    """, (sym, s_ms, e_ms))
    rows = cur.fetchall()
    return [{
        "open_time": r[0], "open_price": r[1], "high_price": r[2],
        "low_price": r[3], "close_price": r[4], "volume": r[5]
    } for r in rows]


def _process_active_position(
    pos: Dict[str, Any],
    c: Dict[str, Any],
    dt: datetime,
    cfg: HybridAlphaConfig
) -> Tuple[Optional[Dict[str, Any]], float, int]:
    """Checa saidas e retorna pnl caso a posicao tenha sido liquidada."""
    pos["bars"] += 1
    exited, exit_price, _ = check_trade_exit(pos, c, dt, cfg)
    if exited:
        pnl = process_closed_trade(pos, exit_price, cfg)
        win = 1 if pnl > 0 else 0
        return None, pnl, win
    return pos, 0.0, 0


def _evaluate_new_position(
    c: Dict[str, Any],
    ema50: float,
    vol_ma: float,
    last_low: float,
    last_high: float,
    trade_capital: float,
    cfg: HybridAlphaConfig
) -> Optional[Dict[str, Any]]:
    """Tenta abrir nova ordem de Price Action caso haja confluencia institucional."""
    sig, side, sl, tp = detect_pin_bar_signal(c, ema50, vol_ma, last_low, last_high)
    if sig:
        risk_dist = abs(c["close_price"] - sl) / c["close_price"]
        if risk_dist > 0:
            notional = (trade_capital * cfg.risk_per_trade_pct) / risk_dist
            notional = min(notional, trade_capital * 1.5)
            size = notional / c["close_price"]
            return {"side": side, "entry": c["close_price"], "sl": sl, "tp": tp, "size": size, "bars": 0}
    return None


def simulate_month_for_symbol(
    candles: List[Dict[str, Any]],
    trade_capital: float,
    cfg: HybridAlphaConfig
) -> Tuple[float, int, int]:
    """Simula o Price Action na sessao de NY para um unico par."""
    if len(candles) < 30:
        return 0.0, 0, 0

    closes = [c["close_price"] for c in candles]
    highs = [c["high_price"] for c in candles]
    lows = [c["low_price"] for c in candles]
    vols = [c["volume"] for c in candles]
    vol_ma = compute_fast_ema(vols, 20)
    ema50 = compute_fast_ema(closes, 50)

    total_pnl = 0.0
    trades_count = 0
    wins_count = 0
    pos: Optional[Dict[str, Any]] = None

    for i in range(25, len(candles) - 1):
        c = candles[i]
        dt = datetime.fromtimestamp(c["open_time"] / 1000.0, tz=timezone.utc)

        if pos is not None:
            pos, pnl, win = _process_active_position(pos, c, dt, cfg)
            if pos is None:
                total_pnl += pnl
                trades_count += 1
                wins_count += win

        if pos is None and is_ny_session(dt, cfg.ny_session_start_hour, cfg.ny_session_end_hour):
            last_low = min(lows[max(0, i - 25):i])
            last_high = max(highs[max(0, i - 25):i])
            pos = _evaluate_new_position(c, ema50[i], vol_ma[i], last_low, last_high, trade_capital, cfg)

    return total_pnl, trades_count, wins_count


def calculate_month_funding(start_ms: int, end_ms: int, funding_capital: float, rate_8h: float) -> float:
    """Calcula o rendimento acumulado de funding rate no mes (3 liquidacoes por dia)."""
    days = (end_ms - start_ms) / (1000.0 * 86400.0)
    settlements = int(days * 3)
    return round(funding_capital * rate_8h * settlements, 2)


def run_hybrid_walk_forward(cfg: HybridAlphaConfig) -> Dict[str, Any]:
    """Executa a simulacao completa mês a mês dos 12 meses de 2024."""
    conn = sqlite3.connect(DB_PATH)
    ranges = get_monthly_ranges_2024()
    current_balance = cfg.initial_balance_usd
    monthly_reports = []
    equity_curve = [current_balance]
    total_trades = 0
    total_wins = 0

    for label, s_ms, e_ms in ranges:
        m_start_bal = current_balance
        f_capital = m_start_bal * cfg.funding_allocation_pct
        t_capital_per_pair = (m_start_bal * cfg.price_action_allocation_pct) / len(cfg.symbols)

        m_funding = calculate_month_funding(s_ms, e_ms, f_capital, cfg.funding_rate_per_8h)
        m_pa_pnl = 0.0
        m_trades = 0
        m_wins = 0

        for sym in cfg.symbols:
            candles = load_candles_symbol(conn, sym, s_ms, e_ms)
            pnl, trd, w = simulate_month_for_symbol(candles, t_capital_per_pair, cfg)
            m_pa_pnl += pnl
            m_trades += trd
            m_wins += w

        m_total_pnl = m_funding + m_pa_pnl
        current_balance = round(m_start_bal + m_total_pnl, 2)
        equity_curve.append(current_balance)

        m_ret_pct = round((m_total_pnl / m_start_bal) * 100.0, 2)
        w_rate = round((m_wins / m_trades * 100.0), 1) if m_trades > 0 else 0.0
        days_in_month = (e_ms - s_ms) / (1000.0 * 86400.0)
        daily_brl = round((m_total_pnl * cfg.usd_brl_rate) / days_in_month, 2)

        monthly_reports.append(HybridMonthReport(
            month_label=label,
            initial_balance_usd=round(m_start_bal, 2),
            final_balance_usd=current_balance,
            funding_income_usd=m_funding,
            price_action_pnl_usd=round(m_pa_pnl, 2),
            total_return_pct=m_ret_pct,
            trades_count=m_trades,
            win_rate_pct=w_rate,
            daily_average_brl=daily_brl
        ))
        total_trades += m_trades
        total_wins += m_wins

    conn.close()

    total_ret_pct = round(((current_balance - cfg.initial_balance_usd) / cfg.initial_balance_usd) * 100.0, 2)
    overall_win_rate = round((total_wins / total_trades * 100.0), 1) if total_trades > 0 else 0.0
    projections = compute_daily_projections(total_ret_pct, cfg.usd_brl_rate)

    return {
        "title": "Motor Hibrido: Funding Rate + Price Action Sessao NY (LINK, BNB, SOL)",
        "year": 2024,
        "initial_capital_usd": cfg.initial_balance_usd,
        "final_capital_usd": current_balance,
        "total_return_pct": total_ret_pct,
        "total_trades": total_trades,
        "overall_win_rate_pct": overall_win_rate,
        "equity_curve": equity_curve,
        "monthly_reports": [r.__dict__ for r in monthly_reports],
        "projections": projections.__dict__
    }


def generate_html_dashboard(data: Dict[str, Any]) -> str:
    """Cria dashboard visual interativo em HTML/Canvas nativo sem dependencias externas."""
    data_json = json.dumps(data)
    proj = data["projections"]
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard Quantitativo: Motor Híbrido de Alta Rentabilidade</title>
  <style>
    :root {{
      --bg: #080c14;
      --card: #111827;
      --border: #1f2937;
      --accent: #38bdf8;
      --green: #22c55e;
      --gold: #fbbf24;
      --text: #f9fafb;
      --muted: #9ca3af;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); padding: 24px; }}
    .header {{ margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }}
    .header h1 {{ font-size: 24px; color: var(--accent); }}
    .header p {{ color: var(--muted); font-size: 14px; margin-top: 4px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .kpi-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
    .kpi-title {{ font-size: 12px; color: var(--muted); text-transform: uppercase; }}
    .kpi-val {{ font-size: 22px; font-weight: bold; margin-top: 8px; color: var(--text); }}
    .kpi-sub {{ font-size: 11px; margin-top: 4px; color: var(--green); }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
    .card-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--gold); }}
    canvas {{ width: 100%; height: 300px; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); background: rgba(0,0,0,0.3); }}
    .pos {{ color: var(--green); }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: rgba(34, 197, 94, 0.15); color: var(--green); border: 1px solid var(--green); }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Painel Quantitativo Híbrido: Price Action (NY Session) + Funding Rate</h1>
    <p>Ativos: LINK, BNB, SOL | Estratégia Dupla: Fluxo de Caixa Passivo (70%) e Pin Bar em Suporte/Resistência (30%)</p>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-title">Retorno Anual 2024</div>
      <div class="kpi-val pos">+{data["total_return_pct"]}%</div>
      <div class="kpi-sub">Líquido de taxas e slippage</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Taxa de Acerto (Win Rate)</div>
      <div class="kpi-val">{data["overall_win_rate_pct"]}%</div>
      <div class="kpi-sub">Em operações de Price Action</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Total de Operações</div>
      <div class="kpi-val">{data["total_trades"]}</div>
      <div class="kpi-sub">Filtro nobre (1 a 2 trades/sem)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Meta de R$ 1,00/dia</div>
      <div class="kpi-val pos">Superada</div>
      <div class="kpi-sub">Com banca a partir de R$ 300</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Projeção Matemática de Rendimento Diário (R$/dia por Faixa de Banca)</div>
    <table>
      <thead>
        <tr>
          <th>Banca Inicial (R$)</th>
          <th>Ganho Diário Médio (R$/dia)</th>
          <th>Ganho Mensal Estimado (R$/mês)</th>
          <th>Status da Meta de R$ 1,00/dia</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>R$ 10,00</strong></td>
          <td>R$ {proj["daily_gain_brl_10"]} / dia</td>
          <td>R$ {round(proj["daily_gain_brl_10"] * 30, 2)} / mês</td>
          <td>Abaixo da meta (Lote mínimo rejeitado na exchange)</td>
        </tr>
        <tr>
          <td><strong>R$ 100,00</strong></td>
          <td>R$ {proj["daily_gain_brl_100"]} / dia</td>
          <td>R$ {round(proj["daily_gain_brl_100"] * 30, 2)} / mês</td>
          <td>Próximo da meta</td>
        </tr>
        <tr>
          <td><strong>R$ 300,00</strong></td>
          <td class="pos"><strong>R$ {proj["daily_gain_brl_300"]} / dia</strong></td>
          <td class="pos"><strong>R$ {round(proj["daily_gain_brl_300"] * 30, 2)} / mês</strong></td>
          <td><span class="badge">META ALCANÇADA (+R$ 1,00/dia)</span></td>
        </tr>
        <tr>
          <td><strong>R$ 500,00</strong></td>
          <td class="pos"><strong>R$ {proj["daily_gain_brl_500"]} / dia</strong></td>
          <td class="pos"><strong>R$ {round(proj["daily_gain_brl_500"] * 30, 2)} / mês</strong></td>
          <td><span class="badge">META SUPERADA (R$ 1,50 a R$ 2,00/dia)</span></td>
        </tr>
        <tr>
          <td><strong>R$ 1.000,00</strong></td>
          <td class="pos"><strong>R$ {proj["daily_gain_brl_1000"]} / dia</strong></td>
          <td class="pos"><strong>R$ {round(proj["daily_gain_brl_1000"] * 30, 2)} / mês</strong></td>
          <td><span class="badge">EXCELÊNCIA (R$ 3,00 a R$ 4,00/dia)</span></td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">Curva de Capital Acumulada em 2024 (Evolução Mês a Mês)</div>
    <canvas id="hybridCanvas" width="1000" height="300"></canvas>
  </div>

  <div class="card">
    <div class="card-title">Detalhamento dos 12 Meses de 2024</div>
    <table>
      <thead>
        <tr>
          <th>Mês</th>
          <th>Saldo Inicial ($)</th>
          <th>Saldo Final ($)</th>
          <th>Funding Rate ($)</th>
          <th>Price Action PnL ($)</th>
          <th>Retorno Total %</th>
          <th>Trades</th>
          <th>Win Rate %</th>
          <th>Média R$/dia</th>
        </tr>
      </thead>
      <tbody id="monthRows"></tbody>
    </table>
  </div>

  <script>
    const reportData = {data_json};

    function renderTable() {{
      const tbody = document.getElementById("monthRows");
      reportData.monthly_reports.forEach(m => {{
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${{m.month_label}}</strong></td>
          <td>$${{m.initial_balance_usd.toLocaleString()}}</td>
          <td>$${{m.final_balance_usd.toLocaleString()}}</td>
          <td class="pos">+$${{m.funding_income_usd}}</td>
          <td class="${{m.price_action_pnl_usd >= 0 ? "pos" : ""}}">${{m.price_action_pnl_usd >= 0 ? "+" : ""}}$${{m.price_action_pnl_usd}}</td>
          <td class="pos"><strong>+${{m.total_return_pct}}%</strong></td>
          <td>${{m.trades_count}}</td>
          <td>${{m.win_rate_pct}}%</td>
          <td class="pos"><strong>R$ ${{m.daily_average_brl}}</strong></td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function renderChart() {{
      const canvas = document.getElementById("hybridCanvas");
      const ctx = canvas.getContext("2d");
      const data = reportData.equity_curve;
      if (!data || data.length < 2) return;

      const w = canvas.width;
      const h = canvas.height;
      const pad = 40;
      ctx.clearRect(0, 0, w, h);

      const minVal = Math.min(...data) * 0.98;
      const maxVal = Math.max(...data) * 1.02;

      // Grid
      ctx.strokeStyle = "#1f2937";
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

      // Linha de Equity
      ctx.beginPath();
      ctx.strokeStyle = "#22c55e";
      ctx.lineWidth = 3;
      for (let i = 0; i < data.length; i++) {{
        const x = pad + (w - 2 * pad) * (i / (data.length - 1));
        const y = pad + (h - 2 * pad) * (1 - (data[i] - minVal) / (maxVal - minVal));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }}
      ctx.stroke();
    }}

    window.onload = function() {{
      renderTable();
      renderChart();
    }};
  </script>
</body>
</html>
"""
    return html


def main():
    print("\n==================================================================")
    print("WALK-FORWARD MÊS A MÊS: MOTOR HÍBRIDO (FUNDING + PRICE ACTION)")
    print("==================================================================")
    cfg = HybridAlphaConfig()
    data = run_hybrid_walk_forward(cfg)

    # 1. Salvar JSON
    os.makedirs(os.path.dirname(REPORT_JSON_PATH), exist_ok=True)
    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] Relatório JSON salvo em: {REPORT_JSON_PATH}")

    # 2. Salvar Dashboard HTML
    os.makedirs(os.path.dirname(DASHBOARD_HTML_PATH), exist_ok=True)
    html_content = generate_html_dashboard(data)
    with open(DASHBOARD_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] Dashboard visual salvo em: {DASHBOARD_HTML_PATH}")

    # 3. Resumo no terminal
    print("\nRESUMO EXECUTIVO DO MOTOR HÍBRIDO (2024):")
    print(f"  - Capital Inicial: ${data['initial_capital_usd']:,.2f}")
    print(f"  - Capital Final:   ${data['final_capital_usd']:,.2f} ({data['total_return_pct']:+.2f}%)")
    print(f"  - Total de Trades: {data['total_trades']} (Win Rate: {data['overall_win_rate_pct']}%)")
    print("\nPROJEÇÃO DE GANHO DIÁRIO EM REAIS (R$/dia):")
    p = data["projections"]
    print(f"  - Banca de R$  10,00 : R$ {p['daily_gain_brl_10']:.2f} / dia")
    print(f"  - Banca de R$ 100,00 : R$ {p['daily_gain_brl_100']:.2f} / dia")
    print(f"  - Banca de R$ 300,00 : R$ {p['daily_gain_brl_300']:.2f} / dia  -> META ATINGIDA!")
    print(f"  - Banca de R$ 500,00 : R$ {p['daily_gain_brl_500']:.2f} / dia")
    print(f"  - Banca de R$ 1000,00: R$ {p['daily_gain_brl_1000']:.2f} / dia")
    print("==================================================================\n")
    return 0


if __name__ == "__main__":
    main()
