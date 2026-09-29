"""
Suíte de Testes da Metodologia Walk-Forward (Fase 6 / Task-017).
Valida integridade do relatório de 5 anos de simulação sequencial e sobrevivência sob estresse.
"""

import sys
import os
import json
from pathlib import Path

# Adiciona o diretorio raiz ao PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

REPORT_PATH = Path(ROOT_DIR) / "data" / "walk_forward_report.json"


def test_walk_forward_report_structure_and_coverage():
    """Valida presenca das 4 fases temporais e cobertura completa de candles."""
    assert REPORT_PATH.exists(), f"Relatorio Walk-Forward nao encontrado em {REPORT_PATH}"

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["symbol"] == "BTC/USDT"
    assert data["total_candles_processed"] >= 40000, "Deveria ter processado mais de 40.000 candles"
    assert len(data["phases"]) == 4, "Deveria conter exatamente 4 fases temporais sequenciais"

    phase_names = [p["phase"] for p in data["phases"]]
    assert any("Fase A" in name for name in phase_names)
    assert any("Fase B" in name for name in phase_names)
    assert any("Fase C" in name for name in phase_names)
    assert any("Fase D" in name for name in phase_names)


def test_walk_forward_risk_preservation_in_bear_market():
    """Valida que nenhuma estrategia sobrevivente violou o teto de 8% de Drawdown."""
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for phase in data["phases"]:
        for strat in phase["strategies"]:
            if strat["survived"]:
                assert strat["max_drawdown_pct"] <= 8.0, (
                    f"Estrategia {strat['strategy_id']} sobreviveu com DD excessivo ({strat['max_drawdown_pct']}%)"
                )


if __name__ == "__main__":
    test_walk_forward_report_structure_and_coverage()
    test_walk_forward_risk_preservation_in_bear_market()
    print("SUÍTE DE TESTES WALK-FORWARD APROVADA COM SUCESSO (2/2 TESTES PASSARAM).")
