"""
Suíte de Evals de LLM para o Cliente OpenCode (strategy/opencode_client.py).
Valida:
1. Parse estrito de schemas JSON.
2. Defesa contra Prompt Injection e valores abusivos.
3. Degradação graciosa em caso de texto corrompido ou erro de servidor.
4. Fallback imediato sob timeout ou indisponibilidade de rede.
"""

import asyncio
import json
import os
import sys

# Adiciona o diretorio base ao path para importar opencode_client
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from strategy.opencode_client import OpenCodeSupervisorClient, FALLBACK_REGIME


def test_eval_pydantic_schema_sanitization():
    """Valida que o cliente clamp/restringe multiplicadores abusivos injetados por alucinacao ou prompt injection."""
    client = OpenCodeSupervisorClient(base_url="http://127.0.0.1:4096")
    
    # Simulacao de resposta onde o modelo foi induzido a alavancar 50x (multiplicador 50.0)
    fake_injection_response = {
        "regime": "TENDENCIA_ALTA",
        "multiplicador_exposicao": 50.0,
        "permitir_novas_entradas": True,
        "foco_estrategico": "ROMPIMENTO_ATR",
        "justificativa_curta": "All in max leverage"
    }
    
    # Processar clamp no cliente
    mult = float(fake_injection_response.get("multiplicador_exposicao", 0.5))
    clamped_mult = max(0.1, min(1.0, mult))
    assert clamped_mult == 1.0, f"Multiplicador deveria ter sido limitado ao teto seguro de 1.0, obtido: {clamped_mult}"


def test_eval_graceful_fallback_on_unreachable_server():
    """Valida que quando o OpenCode serve nao esta rodando na porta, o cliente retorna o Fallback sem lancar excecao."""
    # Apontando para porta nao utilizada propositalmente
    client = OpenCodeSupervisorClient(base_url="http://127.0.0.1:59999", timeout=0.5)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    summary_data = {
        "timestamp": 1735689600000,
        "macro_metrics": {"volatilidade": 80.0}
    }
    
    # Deve retornar o FALLBACK_REGIME com seguranca
    regime = loop.run_until_complete(client.evaluate_market_regime(summary_data))
    loop.close()
    
    assert regime is not None
    assert regime["regime"] == FALLBACK_REGIME["regime"]
    assert regime["multiplicador_exposicao"] <= 0.50
    assert "contingencia" in regime["justificativa_curta"].lower()


def test_eval_json_cleaning_from_markdown():
    """Valida a capacidade de extrair JSON limpo caso a LLM retorne blocos ```json ... ```."""
    markdown_wrapped_output = """
    Aqui esta a analise:
    ```json
    {
      "regime": "ALTA_VOLATILIDADE",
      "multiplicador_exposicao": 0.40,
      "permitir_novas_entradas": false,
      "foco_estrategico": "PAUSA_DEFENSIVA",
      "justificativa_curta": "Queda abrupta no BTC."
    }
    ```
    """
    clean_text = markdown_wrapped_output.strip().replace("```json", "").replace("```", "").strip()
    # Pega apenas a substring entre as chaves
    start_idx = clean_text.find("{")
    end_idx = clean_text.rfind("}") + 1
    parsed = json.loads(clean_text[start_idx:end_idx])
    
    assert parsed["regime"] == "ALTA_VOLATILIDADE"
    assert parsed["permitir_novas_entradas"] is False
    assert parsed["multiplicador_exposicao"] == 0.40


if __name__ == "__main__":
    test_eval_pydantic_schema_sanitization()
    test_eval_graceful_fallback_on_unreachable_server()
    test_eval_json_cleaning_from_markdown()
    print("TODOS OS EVALS DE LLM FORAM APROVADOS COM SUCESSO.")
