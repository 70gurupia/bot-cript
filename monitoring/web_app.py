"""
Dashboard Web FastAPI para Monitoramento e Controle em Tempo Real (Fase 6).
Fornece interface gráfica local e endpoints REST para auditoria da incubadora,
visualização da árvore de clones e acionamento de travas de emergência.
"""

import os
import time
import secrets
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.responses import HTMLResponse

from core.kill_switch import circuit_breaker
from core.logger import telemetry


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
    title="Bot Cripto Autoevolutivo - Painel de Controle",
    description="Interface de monitoramento em tempo real da incubadora, clones e risco.",
    version="1.0.0"
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
    return {
        "status": "OPERATIONAL" if cb_check["allowed"] else "LOCKED",
        "circuit_breaker_allowed": cb_check["allowed"],
        "circuit_breaker_reason": cb_check["reason"],
        "quarantine_l2_active": circuit_breaker.is_global_locked,
        "total_equity_usd": system_context["total_equity"],
        "cash_balance_usd": system_context["cash_balance"],
        "market_regime": system_context["market_regime"],
        "open_positions_count": len(system_context["active_positions"]),
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
    <title>Bot Cripto Autoevolutivo - Painel de Controle</title>
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: rgba(22, 27, 34, 0.85);
            --border-color: #30363d;
            --text-primary: #c9d1d9;
            --accent-green: #238636;
            --accent-red: #da3633;
            --accent-blue: #58a6ff;
            --accent-yellow: #d29922;
        }
        body {
            margin: 0;
            padding: 24px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 24px; }
        h1 { margin: 0; font-size: 24px; font-weight: 600; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .card-title { font-size: 13px; text-transform: uppercase; color: #8b949e; margin-bottom: 8px; letter-spacing: 0.5px; }
        .card-value { font-size: 28px; font-weight: 700; color: #ffffff; }
        .status-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .badge-active { background: rgba(35, 134, 54, 0.2); color: #3fb950; border: 1px solid #238636; }
        .badge-locked { background: rgba(218, 54, 51, 0.2); color: #f85149; border: 1px solid #da3633; }
        .btn { padding: 10px 20px; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.85; }
        .btn-panic { background: var(--accent-red); color: #ffffff; }
        .btn-resume { background: var(--accent-green); color: #ffffff; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-color); font-size: 14px; }
        th { color: #8b949e; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Bot Cripto Autoevolutivo</h1>
                <div style="font-size: 13px; color: #8b949e; margin-top: 4px;">Monitoramento Local da Tesouraria e Incubadora</div>
            </div>
            <div id="status-container">
                <span class="status-badge badge-active" id="system-badge">CARREGANDO...</span>
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <div class="card-title">Patrimônio da Carteira</div>
                <div class="card-value" id="val-equity">$10.000,00</div>
            </div>
            <div class="card">
                <div class="card-title">Saldo Livre Disponível</div>
                <div class="card-value" id="val-cash">$10.000,00</div>
            </div>
            <div class="card">
                <div class="card-title">Regime do Mercado (OpenCode)</div>
                <div class="card-value" style="font-size: 20px; color: var(--accent-blue);" id="val-regime">NEUTRO</div>
            </div>
            <div class="card">
                <div class="card-title">Ações de Emergência</div>
                <div style="display: flex; gap: 8px; margin-top: 8px;">
                    <button class="btn btn-panic" onclick="triggerPanic()">PÂNICO (L2)</button>
                    <button class="btn btn-resume" onclick="triggerResume()">DESTRAVAR</button>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">Estatísticas da Incubadora de Clones</div>
            <table>
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Quantidade</th>
                        <th>Critério Chave</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><span class="status-badge badge-active">QUARENTENA</span></td>
                        <td id="cnt-quarantine">0</td>
                        <td>Paper trading em avaliação probatória</td>
                    </tr>
                    <tr>
                        <td><span class="status-badge" style="background: rgba(88, 166, 255, 0.2); color: #58a6ff; border: 1px solid #1f6feb;">GRADUADOS</span></td>
                        <td id="cnt-graduated">0</td>
                        <td>Aprovados (&ge; 30 trades, Sharpe &ge; 1.25, DD &le; 4.5%)</td>
                    </tr>
                    <tr>
                        <td><span class="status-badge badge-locked">ELIMINADOS</span></td>
                        <td id="cnt-eliminated">0</td>
                        <td>Descartados (DD &gt; 8.0% ou infração de risco)</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const badge = document.getElementById('system-badge');
                if (data.circuit_breaker_allowed) {
                    badge.className = 'status-badge badge-active';
                    badge.textContent = 'SISTEMA OPERACIONAL';
                } else {
                    badge.className = 'status-badge badge-locked';
                    badge.textContent = 'BLOQUEADO (CIRCUIT BREAKER)';
                }
                document.getElementById('val-equity').textContent = '$' + data.total_equity_usd.toLocaleString('pt-BR', {minimumFractionDigits: 2});
                document.getElementById('val-cash').textContent = '$' + data.cash_balance_usd.toLocaleString('pt-BR', {minimumFractionDigits: 2});
                document.getElementById('val-regime').textContent = data.market_regime;
            } catch (e) {
                console.error('Erro ao consultar status:', e);
            }
        }

        async function fetchIncubator() {
            try {
                const res = await fetch('/api/incubator');
                const data = await res.json();
                document.getElementById('cnt-quarantine').textContent = data.quarantine_count;
                document.getElementById('cnt-graduated').textContent = data.graduated_count;
                document.getElementById('cnt-eliminated').textContent = data.eliminated_count;
            } catch (e) {
                console.error('Erro ao consultar incubadora:', e);
            }
        }

        function getAuthHeaders() {
            const key = localStorage.getItem('dashboard_api_key') || 'BOT_CRIPTO_SECURE_KEY_2026';
            return { 'Content-Type': 'application/json', 'X-API-Key': key };
        }

        async function triggerPanic() {
            if (!confirm('CONFIRMAÇÃO: Deseja realmente acionar o travamento de emergência Circuit Breaker L2 por 24h?')) return;
            try {
                const res = await fetch('/api/panic', {method: 'POST', headers: getAuthHeaders()});
                const data = await res.json();
                alert(data.message || data.detail);
                fetchStatus();
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
                fetchStatus();
            } catch (e) {
                alert('Erro ao destravar sistema: ' + e);
            }
        }

        fetchStatus();
        fetchIncubator();
        setInterval(() => { fetchStatus(); fetchIncubator(); }, 3000);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def get_dashboard() -> str:
    """Serve a pagina web do painel de controle do Bot Cripto."""
    return DASHBOARD_HTML
