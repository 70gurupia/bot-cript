"""
Dashboard Web FastAPI para Monitoramento e Controle em Tempo Real (Fase 6 e Flotilha 40 Bots).
Fornece interface grafica local e endpoints REST para auditoria da flotilha de 40 bots,
posicoes ativas do simulador Paper Trading, incubadora e travas de emergencia.
"""

from __future__ import annotations
import os
import time
import secrets
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.responses import HTMLResponse

from core.kill_switch import circuit_breaker
from core.logger import telemetry
from core.swarm_manager import swarm_manager


DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "BOT_CRIPTO_SECURE_KEY_2026")


def verify_dashboard_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> bool:
    """Valida a chave de API no header X-API-Key com comparacao em tempo constante."""
    if not x_api_key or not secrets.compare_digest(x_api_key, DASHBOARD_API_KEY):
        telemetry.emit_event(
            event="DASHBOARD_UNAUTHORIZED_ACCESS",
            level="WARNING",
            agent_id="WEB_DASHBOARD",
            payload={"action": "REJECTED_UNAUTHORIZED_REQUEST"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ACESSO NEGADO: Chave de API invalida ou ausente no header X-API-Key."
        )
    return True


app = FastAPI(
    title="Bot Cripto Autoevolutivo - Painel de Controle e Flotilha",
    description="Interface de monitoramento em tempo real dos 40 sub-bots, Paper Trading e risco.",
    version="2.0.0"
)

# Estado global compartilhado em memoria para visualizacao
system_context: Dict[str, Any] = {
    "total_equity": 10000.0,
    "cash_balance": 10000.0,
    "active_positions": [],
    "incubator_clones": [],
    "graduated_clones": [],
    "eliminated_clones": [],
    "market_regime": "NEUTRO_OPERACIONAL"
}


@app.get("/api/status")
def get_system_status() -> Dict[str, Any]:
    """Retorna o status geral de saude e risco do ecossistema."""
    cb_check = circuit_breaker.is_trading_allowed("WEB_DASHBOARD")
    sw_sum = swarm_manager.get_swarm_summary()
    return {
        "status": "OPERATIONAL" if cb_check["allowed"] else "LOCKED",
        "circuit_breaker_allowed": cb_check["allowed"],
        "circuit_breaker_reason": cb_check["reason"],
        "quarantine_l2_active": circuit_breaker.is_global_locked,
        "total_equity_usd": sw_sum["total_equity_usd"],
        "cash_balance_usd": sw_sum["cash_balance_usd"],
        "market_regime": system_context["market_regime"],
        "open_positions_count": sw_sum["open_positions_count"],
        "net_return_pct": sw_sum["net_return_pct"],
        "max_drawdown_pct": sw_sum["max_drawdown_pct"],
        "timestamp_utc": int(time.time() * 1000)
    }


@app.get("/api/incubator")
def get_incubator_clones() -> Dict[str, Any]:
    """Retorna a lista e status de todos os clones na incubadora."""
    return {
        "quarantine_count": len(system_context["incubator_clones"]),
        "graduated_count": len(system_context["graduated_clones"]),
        "eliminated_count": len(system_context["eliminated_clones"]),
        "quarantine_clones": system_context["incubator_clones"],
        "graduated_clones": system_context["graduated_clones"],
        "eliminated_clones": system_context["eliminated_clones"]
    }


@app.get("/api/swarm/status")
def get_swarm_status() -> Dict[str, Any]:
    """Retorna metricas consolidadas da flotilha de 40 bots em tempo real."""
    return swarm_manager.get_swarm_summary()


@app.get("/api/swarm/groups")
def get_swarm_groups() -> List[Dict[str, Any]]:
    """Retorna relatorio analitico consolidado dos 8 grupos de 5 bots."""
    return swarm_manager.get_groups_summary()


@app.get("/api/swarm/bots")
def get_swarm_bots() -> List[Dict[str, Any]]:
    """Retorna lista de status detalhado dos 40 sub-bots."""
    return swarm_manager.get_bots_list()


@app.get("/api/swarm/positions")
def get_swarm_positions() -> List[Dict[str, Any]]:
    """Retorna posicoes ativas abertas no simulador Paper Trading."""
    return swarm_manager.get_open_positions()


@app.post("/api/panic", dependencies=[Depends(verify_dashboard_api_key)])
def trigger_panic_button() -> Dict[str, Any]:
    """Aciona manualmente o Circuit Breaker L2 travando todo o sistema."""
    circuit_breaker.trip_level_2_portfolio(
        current_equity_usd=0.0,
        baseline_equity_usd=system_context["total_equity"],
        reason="MANUAL_PANIC"
    )
    telemetry.emit_event(
        event="CIRCUIT_BREAKER_MANUAL_PANIC",
        level="CRITICAL",
        agent_id="WEB_DASHBOARD",
        payload={"action": "TRIGGER_PANIC"}
    )
    return {
        "success": True,
        "message": "EMERGENCIA ACIONADA: Circuit Breaker L2 ativado. Sistema travado por 24h."
    }


@app.post("/api/resume", dependencies=[Depends(verify_dashboard_api_key)])
def trigger_resume_system() -> Dict[str, Any]:
    """Reseta o Circuit Breaker L2 liberando as operacoes da Tesouraria."""
    circuit_breaker.reset_lock(force_override=True)
    telemetry.emit_event(
        event="CIRCUIT_BREAKER_MANUAL_RESET",
        level="WARNING",
        agent_id="WEB_DASHBOARD",
        payload={"action": "RESET_L2"}
    )
    return {
        "success": True,
        "message": "SUCESSO: Circuit Breaker L2 resetado. Negociacoes liberadas."
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Cripto Autoevolutivo - Painel de Controle e Flotilha</title>
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(18, 24, 38, 0.9);
            --border-color: #232d42;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
            --accent-yellow: #f59e0b;
            --accent-purple: #8b5cf6;
        }
        body {
            margin: 0;
            padding: 24px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
        }
        .container { max-width: 1300px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        h1 { margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
        .grid-kpi {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.4);
            margin-bottom: 24px;
        }
        .card-title {
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-secondary);
            margin-bottom: 8px;
            letter-spacing: 0.6px;
            font-weight: 600;
        }
        .card-value { font-size: 26px; font-weight: 700; color: #ffffff; }
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-active { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #059669; }
        .badge-locked { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid #dc2626; }
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.85; }
        .btn-panic { background: var(--accent-red); color: #ffffff; }
        .btn-resume { background: var(--accent-green); color: #ffffff; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-color); font-size: 13px; }
        th { color: var(--text-secondary); font-weight: 600; font-size: 12px; text-transform: uppercase; }
        .text-green { color: var(--accent-green); }
        .text-red { color: var(--accent-red); }
        .text-blue { color: var(--accent-blue); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Bot Cripto: Monitoramento em Tempo Real</h1>
                <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">
                    Flotilha de 40 Sub-Bots e Simulador de Paper Trading (Maker Mode)
                </div>
            </div>
            <div id="status-container" style="display: flex; align-items: center; gap: 12px;">
                <span class="status-badge badge-active" id="system-badge">CONECTANDO...</span>
                <button class="btn btn-panic" onclick="triggerPanic()">PÂNICO (L2)</button>
                <button class="btn btn-resume" onclick="triggerResume()">DESTRAVAR</button>
            </div>
        </header>

        <div class="grid-kpi">
            <div class="card" style="margin-bottom: 0;">
                <div class="card-title">Patrimônio Líquido (Equity)</div>
                <div class="card-value" id="val-equity">$10.000,00</div>
            </div>
            <div class="card" style="margin-bottom: 0;">
                <div class="card-title">Saldo em Caixa Livre</div>
                <div class="card-value" id="val-cash">$10.000,00</div>
            </div>
            <div class="card" style="margin-bottom: 0;">
                <div class="card-title">Retorno Líquido Acumulado</div>
                <div class="card-value text-green" id="val-return">+0.00%</div>
            </div>
            <div class="card" style="margin-bottom: 0;">
                <div class="card-title">Max Drawdown</div>
                <div class="card-value" id="val-drawdown">0.00%</div>
            </div>
            <div class="card" style="margin-bottom: 0;">
                <div class="card-title">Flotilha de Sub-Bots</div>
                <div class="card-value" style="color: var(--accent-blue);" id="val-bots">40 / 40 Ativos</div>
            </div>
        </div>

        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div class="card-title" style="margin: 0; font-size: 14px;">Flotilha de 40 Bots: 8 Grupos Estratégicos Especializados</div>
                <span style="font-size: 12px; color: var(--text-secondary);">Atualização automática a cada 3s</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Grupo</th>
                        <th>Estratégia Quantitativa</th>
                        <th>Par</th>
                        <th>TF</th>
                        <th>Bots</th>
                        <th>Trades</th>
                        <th>Taxa Acerto</th>
                        <th>PnL Realizado</th>
                    </tr>
                </thead>
                <tbody id="tbody-groups">
                    <tr><td colspan="8" style="text-align: center; color: var(--text-secondary);">Carregando grupos...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="card">
            <div class="card-title" style="font-size: 14px;">Posições Ativas em Tempo Real (Paper Trading Exchange)</div>
            <table>
                <thead>
                    <tr>
                        <th>Posição ID</th>
                        <th>Bot Responsável</th>
                        <th>Par</th>
                        <th>Lado</th>
                        <th>Preço Entrada</th>
                        <th>Alavancagem</th>
                        <th>Colateral (USD)</th>
                        <th>PnL Não-Realizado</th>
                        <th>Preço Liquidação</th>
                    </tr>
                </thead>
                <tbody id="tbody-positions">
                    <tr><td colspan="9" style="text-align: center; color: var(--text-secondary);">Nenhuma posição aberta no momento.</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function updateDashboard() {
            try {
                const resStatus = await fetch('/api/swarm/status');
                const sw = await resStatus.json();
                
                document.getElementById('val-equity').textContent = '$' + sw.total_equity_usd.toLocaleString('pt-BR', {minimumFractionDigits: 2});
                document.getElementById('val-cash').textContent = '$' + sw.cash_balance_usd.toLocaleString('pt-BR', {minimumFractionDigits: 2});
                
                const retElem = document.getElementById('val-return');
                const retSign = sw.net_return_pct >= 0 ? '+' : '';
                retElem.textContent = retSign + sw.net_return_pct.toFixed(2) + '%';
                retElem.className = sw.net_return_pct >= 0 ? 'card-value text-green' : 'card-value text-red';
                
                document.getElementById('val-drawdown').textContent = sw.max_drawdown_pct.toFixed(2) + '%';
                document.getElementById('val-bots').textContent = sw.active_bots + ' / ' + sw.total_bots + ' Ativos';
                
                const badge = document.getElementById('system-badge');
                badge.className = 'status-badge badge-active';
                badge.textContent = 'FLOTILHA OPERACIONAL (40 BOTS)';
                
                const resGroups = await fetch('/api/swarm/groups');
                const groups = await resGroups.json();
                renderGroups(groups);
                
                const resPos = await fetch('/api/swarm/positions');
                const positions = await resPos.json();
                renderPositions(positions);
            } catch (e) {
                console.error('Erro na telemetria do swarm:', e);
            }
        }

        function renderGroups(groups) {
            const tbody = document.getElementById('tbody-groups');
            if (!groups || groups.length === 0) return;
            let html = '';
            for (const g of groups) {
                const pnlClass = g.realized_pnl_usd >= 0 ? 'text-green' : 'text-red';
                const pnlSign = g.realized_pnl_usd >= 0 ? '+' : '';
                html += `<tr>
                    <td><strong>${g.group_id}</strong> (${g.name})</td>
                    <td>${g.strategy}</td>
                    <td>${g.symbol}</td>
                    <td><span class="status-badge" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa;">${g.timeframe}</span></td>
                    <td>${g.bots_count}</td>
                    <td>${g.total_trades}</td>
                    <td>${g.win_rate_pct.toFixed(1)}%</td>
                    <td class="${pnlClass}">${pnlSign}$${g.realized_pnl_usd.toFixed(2)}</td>
                </tr>`;
            }
            tbody.innerHTML = html;
        }

        function renderPositions(positions) {
            const tbody = document.getElementById('tbody-positions');
            if (!positions || positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-secondary);">Nenhuma posição aberta no momento (Aguardando confluência).</td></tr>';
                return;
            }
            let html = '';
            for (const p of positions) {
                const sideClass = p.side === 'LONG' ? 'text-green' : 'text-red';
                const pnlClass = p.unrealized_pnl_usd >= 0 ? 'text-green' : 'text-red';
                html += `<tr>
                    <td><code>${p.position_id}</code></td>
                    <td><strong>${p.agent_id}</strong></td>
                    <td>${p.symbol}</td>
                    <td class="${sideClass}"><strong>${p.side}</strong></td>
                    <td>$${p.entry_price.toFixed(4)}</td>
                    <td>${p.leverage}x</td>
                    <td>$${p.collateral_usd.toFixed(2)}</td>
                    <td class="${pnlClass}">$${p.unrealized_pnl_usd.toFixed(2)}</td>
                    <td>$${p.liquidation_price.toFixed(4)}</td>
                </tr>`;
            }
            tbody.innerHTML = html;
        }

        function getAuthHeaders() {
            const key = localStorage.getItem('dashboard_api_key') || 'BOT_CRIPTO_SECURE_KEY_2026';
            return { 'Content-Type': 'application/json', 'X-API-Key': key };
        }

        async function triggerPanic() {
            if (!confirm('CONFIRMAÇÃO: Deseja acionar o travamento de emergência Circuit Breaker L2 por 24h?')) return;
            try {
                const res = await fetch('/api/panic', {method: 'POST', headers: getAuthHeaders()});
                const data = await res.json();
                alert(data.message || data.detail);
                updateDashboard();
            } catch (e) {
                alert('Erro ao acionar pânico: ' + e);
            }
        }

        async function triggerResume() {
            if (!confirm('CONFIRMAÇÃO: Deseja destravar as negociações do sistema?')) return;
            try {
                const res = await fetch('/api/resume', {method: 'POST', headers: getAuthHeaders()});
                const data = await res.json();
                alert(data.message || data.detail);
                updateDashboard();
            } catch (e) {
                alert('Erro ao destravar sistema: ' + e);
            }
        }

        updateDashboard();
        setInterval(updateDashboard, 3000);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def get_dashboard() -> str:
    """Serve a pagina web do painel de controle do Bot Cripto."""
    return DASHBOARD_HTML
