"""
Suíte de Testes do Orquestrador do Supervisor OpenCode (Fase 6).
Valida consulta assíncrona, ajuste de multiplicadores na Tesouraria e acionamento de fallback em contingência.
"""

import sys
import os
import asyncio

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from strategy.opencode_client import OpenCodeSupervisorClient, FALLBACK_REGIME
from strategy.supervisor_loop import MarketSupervisorLoop, MarketRegimeState
from treasury.treasury_controller import TreasuryController


class MockOpenCodeClient(OpenCodeSupervisorClient):
    """Cliente mock que simula respostas determinísticas para testes herméticos."""
    def __init__(self, response_mode: str = "SUCCESS"):
        super().__init__(base_url="http://127.0.0.1:9999")
        self.response_mode = response_mode

    async def evaluate_market_regime(self, market_summary):
        if self.response_mode == "SUCCESS":
            return {
                "regime": "TENDENCIA_ALTA",
                "multiplicador_exposicao": 0.80,
                "permitir_novas_entradas": True,
                "foco_estrategico": "ROMPIMENTO_ATR",
                "justificativa_curta": "Momentum positivo nos principais pares com volume crescente."
            }
        elif self.response_mode == "DEFENSIVE":
            return {
                "regime": "ALTA_VOLATILIDADE",
                "multiplicador_exposicao": 0.30,
                "permitir_novas_entradas": False,
                "foco_estrategico": "PAUSA_DEFENSIVA",
                "justificativa_curta": "Spike severo de volatilidade detectado."
            }
        else:
            # Simula falha e contingencia
            return FALLBACK_REGIME


def test_supervisor_fallback_when_offline():
    """Valida que falha ou indisponibilidade aciona o modo de contingencia sem travar."""
    async def _run():
        treasury = TreasuryController(max_portfolio_exposure_pct=0.70)
        # Aponta para porta inexistente para forcar erro de conexao
        offline_client = OpenCodeSupervisorClient(base_url="http://127.0.0.1:59999", timeout=0.1)
        supervisor = MarketSupervisorLoop(treasury=treasury, opencode_client=offline_client)

        candles = {
            "BTC/USDT": [{"close": 50000.0, "volume": 100.0}, {"close": 50500.0, "volume": 120.0}]
        }
        state = await supervisor.update_market_regime(candles, force=True)

        assert state.is_fallback is True
        assert state.regime == "NEUTRO_CONSERVADOR"
        assert state.multiplicador_exposicao == 0.50
        # Tesouraria deve ter seu teto de exposicao reduzido para 70% * 0.50 = 35%
        assert round(treasury.max_portfolio_exposure_pct, 4) == 0.35

    asyncio.run(_run())


def test_supervisor_successful_evaluation():
    """Valida ajuste de risco na Tesouraria sob parecer favoravel do OpenCode."""
    async def _run():
        treasury = TreasuryController(max_portfolio_exposure_pct=0.70)
        mock_client = MockOpenCodeClient(response_mode="SUCCESS")
        supervisor = MarketSupervisorLoop(treasury=treasury, opencode_client=mock_client)

        candles = {
            "BTC/USDT": [{"close": 60000.0, "volume": 500.0}, {"close": 62000.0, "volume": 600.0}]
        }
        state = await supervisor.update_market_regime(candles, force=True)

        assert state.is_fallback is False
        assert state.regime == "TENDENCIA_ALTA"
        assert state.multiplicador_exposicao == 0.80
        assert state.permitir_novas_entradas is True
        # Teto de exposicao: 0.70 * 0.80 = 0.56 (56%)
        assert round(treasury.max_portfolio_exposure_pct, 4) == 0.56

    asyncio.run(_run())


def test_supervisor_defensive_pause():
    """Valida pausa defensiva em cenario de alta volatilidade."""
    async def _run():
        treasury = TreasuryController(max_portfolio_exposure_pct=0.70)
        mock_client = MockOpenCodeClient(response_mode="DEFENSIVE")
        supervisor = MarketSupervisorLoop(treasury=treasury, opencode_client=mock_client)

        candles = {"ETH/USDT": [{"close": 3000.0, "volume": 1000.0}]}
        state = await supervisor.update_market_regime(candles, force=True)

        assert state.permitir_novas_entradas is False
        assert state.regime == "ALTA_VOLATILIDADE"
        # Teto de exposicao: 0.70 * 0.30 = 0.21 (21%)
        assert round(treasury.max_portfolio_exposure_pct, 4) == 0.21

    asyncio.run(_run())


if __name__ == "__main__":
    test_supervisor_fallback_when_offline()
    test_supervisor_successful_evaluation()
    test_supervisor_defensive_pause()
    print("SUÍTE DE TESTES DO SUPERVISOR OPENCODE APROVADA COM SUCESSO (3/3 TESTES PASSARAM).")
