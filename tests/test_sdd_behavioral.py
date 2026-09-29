"""
Suíte de Testes Comportamentais SDD (Spec-Driven Development).
Implementa cenários Given-When-Then para validação dos contratos:
SDD-01 (Circuit Breaker L1), SDD-02 (Circuit Breaker L2),
SDD-03 (Margem Isolada e Alavancagem) e SDD-04 (Incubadora Paper Trading).
"""

from typing import Dict, Any

# ==============================================================================
# 1. MODELOS E CONTROLADORES MOCK DE COMPORTAMENTO
# ==============================================================================

class MockOrder:
    def __init__(self, symbol: str, side: str, amount: float, price: float, leverage: float, margin_type: str):
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.price = price
        self.leverage = leverage
        self.margin_type = margin_type.upper()


class CentralTreasuryRiskController:
    MAX_LEVERAGE_CEILING = 3.0

    @classmethod
    def validate_order(cls, order: MockOrder) -> Dict[str, Any]:
        """Aplica contrato SDD-03: margem isolada e teto de alavancagem."""
        if order.margin_type != "ISOLATED":
            return {"approved": False, "reason": "Margem deve ser obrigatoriamente ISOLATED."}
        if order.leverage > cls.MAX_LEVERAGE_CEILING:
            return {"approved": False, "reason": f"Alavancagem {order.leverage}x excede o teto de {cls.MAX_LEVERAGE_CEILING}x."}
        return {"approved": True, "reason": "Ordem aprovada pela Tesouraria."}


class CircuitBreakerEngine:
    L1_DAILY_AGENT_LOSS_LIMIT_PCT = 2.0
    L2_DAILY_GLOBAL_DD_LIMIT_PCT = 4.0

    @classmethod
    def evaluate_agent_l1(cls, allocated_capital: float, daily_loss_usd: float) -> str:
        """Aplica contrato SDD-01: Circuit Breaker Nivel 1."""
        loss_pct = (daily_loss_usd / allocated_capital) * 100.0
        if loss_pct >= cls.L1_DAILY_AGENT_LOSS_LIMIT_PCT:
            return "PAUSED"
        return "ACTIVE"

    @classmethod
    def evaluate_global_l2(cls, initial_equity: float, current_equity: float) -> Dict[str, Any]:
        """Aplica contrato SDD-02: Circuit Breaker Nivel 2."""
        dd_pct = ((initial_equity - current_equity) / initial_equity) * 100.0
        if dd_pct >= cls.L2_DAILY_GLOBAL_DD_LIMIT_PCT:
            return {
                "triggered": True,
                "action": "CLOSE_ALL_MARKET_AND_LOCK_24H",
                "cooling_off_hours": 24,
                "event_code": "CIRCUIT_BREAKER_L2_TRIGGERED"
            }
        return {"triggered": False, "action": "CONTINUE"}


class PaperTradingIncubator:
    MAKER_FEE_PCT = 0.02
    TAKER_FEE_PCT = 0.04
    SYNTHETIC_SLIPPAGE_PCT = 0.05

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.real_capital_allocated = 0.0  # SDD-04: saldo real comeca obrigatoriamente em zero
        self.closed_trades_count = 0
        self.sharpe_ratio = 0.0
        self.max_drawdown_pct = 0.0

    def simulate_order_fill(self, nominal_price: float, side: str) -> float:
        """Aplica slippage sintetico simulando desvantagem realista de book."""
        if side.upper() == "BUY":
            return nominal_price * (1.0 + (self.SYNTHETIC_SLIPPAGE_PCT / 100.0))
        else:
            return nominal_price * (1.0 - (self.SYNTHETIC_SLIPPAGE_PCT / 100.0))

    def evaluate_graduation(self) -> bool:
        """Critérios estritos de aprovacao para dinheiro real."""
        return (
            self.closed_trades_count >= 30
            and self.sharpe_ratio >= 1.25
            and self.max_drawdown_pct <= 4.5
        )


# ==============================================================================
# 2. CENÁRIOS DE TESTE SDD (GIVEN-WHEN-THEN)
# ==============================================================================

def test_sdd_01_circuit_breaker_l1():
    """
    GIVEN agente com $1.000,00 de capital e limite de 2.0%
    WHEN perde $20.00 (exatamente 2.0%)
    THEN transita para PAUSED
    """
    capital = 1000.0
    loss_usd = 20.0
    status = CircuitBreakerEngine.evaluate_agent_l1(capital, loss_usd)
    assert status == "PAUSED", "Agente deveria estar PAUSED ao atingir 2% de perda"

    # Caso de controle: perda de $15.00 (1.5%) -> continua ACTIVE
    status_ok = CircuitBreakerEngine.evaluate_agent_l1(capital, 15.0)
    assert status_ok == "ACTIVE", "Agente deveria permanecer ACTIVE com perda inferior a 2%"


def test_sdd_02_circuit_breaker_l2():
    """
    GIVEN carteira consolidada inicial de $10.000,00
    WHEN drawdown atinge 4.0% (saldo cai para $9.600,00)
    THEN dispara ordem de fechar tudo e trava por 24 horas
    """
    initial = 10000.0
    current = 9600.0
    result = CircuitBreakerEngine.evaluate_global_l2(initial, current)
    assert result["triggered"] is True, "Circuit Breaker L2 deveria ter sido disparado"
    assert result["action"] == "CLOSE_ALL_MARKET_AND_LOCK_24H"
    assert result["cooling_off_hours"] == 24


def test_sdd_03_isolated_margin_and_leverage():
    """
    GIVEN ordens geradas
    WHEN submetidas à Tesouraria
    THEN rejeita se margem for CROSS ou alavancagem > 3.0x
    """
    # Ordem com margem cruzada (deve ser rejeitada)
    order_cross = MockOrder("BTCUSDT", "BUY", 0.1, 60000.0, leverage=2.0, margin_type="CROSS")
    res_cross = CentralTreasuryRiskController.validate_order(order_cross)
    assert res_cross["approved"] is False
    assert "ISOLATED" in res_cross["reason"]

    # Ordem com alavancagem 5.0x (excede o teto de 3.0x)
    order_lev = MockOrder("BTCUSDT", "BUY", 0.1, 60000.0, leverage=5.0, margin_type="ISOLATED")
    res_lev = CentralTreasuryRiskController.validate_order(order_lev)
    assert res_lev["approved"] is False
    assert "excede o teto" in res_lev["reason"]

    # Ordem conforme (ISOLATED + 2.0x)
    order_valid = MockOrder("BTCUSDT", "BUY", 0.1, 60000.0, leverage=2.0, margin_type="ISOLATED")
    res_valid = CentralTreasuryRiskController.validate_order(order_valid)
    assert res_valid["approved"] is True


def test_sdd_04_incubator_quarantine_and_graduation():
    """
    GIVEN novo clone na incubadora
    WHEN criado e operando
    THEN capital real e zero, aplica slippage sintetico, so gradua se cumprir todas as 3 metricas
    """
    incubator = PaperTradingIncubator("clone_v1_001")
    assert incubator.real_capital_allocated == 0.0, "Novo clone nao pode ter saldo real alocado"

    # Slippage sintetico de compra deve penalizar o preco para cima
    filled_price = incubator.simulate_order_fill(100.0, "BUY")
    assert filled_price > 100.0, "Slippage de compra deve resultar em preco pior (mais alto)"

    # Falha na graduacao com apenas 15 trades (minimo e 30)
    incubator.closed_trades_count = 15
    incubator.sharpe_ratio = 1.8
    incubator.max_drawdown_pct = 2.0
    assert incubator.evaluate_graduation() is False, "Nao deve graduar com menos de 30 trades"

    # Aprovacao na graduacao (35 trades, Sharpe 1.4, Drawdown 3.2%)
    incubator.closed_trades_count = 35
    incubator.sharpe_ratio = 1.4
    incubator.max_drawdown_pct = 3.2
    assert incubator.evaluate_graduation() is True, "Deveria ser graduado com metricas robustas"


if __name__ == "__main__":
    test_sdd_01_circuit_breaker_l1()
    test_sdd_02_circuit_breaker_l2()
    test_sdd_03_isolated_margin_and_leverage()
    test_sdd_04_incubator_quarantine_and_graduation()
    print("TODOS OS TESTES COMPORTAMENTAIS SDD FORAM APROVADOS COM SUCESSO.")
