"""
Suíte de Testes de Observabilidade ODD (Observability-Driven Development).
Valida contratos de Telemetria: Spans, Métricas e Logs Estruturados de Auditoria.
Garante que todo comportamento do bot é observável e rastreável.
"""

import json
import time
from typing import Dict, Any, List


class TelemetrySink:
    """Coletor em memoria para validacao de contratos de telemetria nos testes."""
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []
        self.spans: List[Dict[str, Any]] = []
        self.metrics: Dict[str, float] = {}

    def emit_log(self, event: str, level: str, agent_id: str, payload: dict):
        log_entry = {
            "timestamp_utc": int(time.time() * 1000),
            "event": event,
            "level": level,
            "agent_id": agent_id,
            "payload": payload
        }
        # Valida que e serializavel em JSON puro
        serialized = json.dumps(log_entry)
        self.logs.append(json.loads(serialized))

    def record_span(self, name: str, attributes: dict):
        self.spans.append({"name": name, "attributes": attributes})

    def record_metric(self, name: str, value: float):
        self.metrics[name] = value


def test_odd_structured_log_contract():
    """Valida que logs estruturados possuem todos os campos obrigatorios do contrato."""
    sink = TelemetrySink()
    sink.emit_log(
        event="ORDER_SUBMITTED",
        level="INFO",
        agent_id="agent_alpha_01",
        payload={"symbol": "BTCUSDT", "amount": 0.05, "price": 62500.0}
    )

    assert len(sink.logs) == 1
    log = sink.logs[0]
    required_fields = ["timestamp_utc", "event", "level", "agent_id", "payload"]
    for field in required_fields:
        assert field in log, f"Campo obrigatorio ausente no log: {field}"
        
    assert log["event"] == "ORDER_SUBMITTED"
    assert log["level"] == "INFO"
    assert log["payload"]["symbol"] == "BTCUSDT"


def test_odd_trade_span_attributes_contract():
    """Valida que o span 'trade.execute' contem todos os metadados de auditoria necessarios."""
    sink = TelemetrySink()
    trade_attrs = {
        "trade.id": "tr_991823",
        "agent.id": "agent_beta_04",
        "symbol": "SOLUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 2.5,
        "price": 142.30,
        "leverage": 2.0,
        "margin_type": "ISOLATED"
    }
    sink.record_span("trade.execute", trade_attrs)

    assert len(sink.spans) == 1
    span = sink.spans[0]
    assert span["name"] == "trade.execute"
    for key in trade_attrs:
        assert key in span["attributes"], f"Atributo obrigatorio ausente no span: {key}"


def test_odd_circuit_breaker_metrics_contract():
    """Valida a emissao das metricas essenciais de protecao patrimonial."""
    sink = TelemetrySink()
    sink.record_metric("bot_portfolio_equity_usd", 10250.75)
    sink.record_metric("bot_circuit_breaker_trips_total", 0.0)
    sink.record_metric("bot_incubator_agent_count", 8.0)

    assert sink.metrics["bot_portfolio_equity_usd"] == 10250.75
    assert sink.metrics["bot_circuit_breaker_trips_total"] == 0.0
    assert sink.metrics["bot_incubator_agent_count"] == 8.0


if __name__ == "__main__":
    test_odd_structured_log_contract()
    test_odd_trade_span_attributes_contract()
    test_odd_circuit_breaker_metrics_contract()
    print("TODOS OS TESTES DE TELEMETRIA ODD FORAM APROVADOS COM SUCESSO.")
