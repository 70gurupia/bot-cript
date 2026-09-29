"""
Cliente assincrono para comunicacao com o servidor local do OpenCode (opencode serve).
Atua como supervisor macro de mercado, convertendo metricas quantitativas em pareceres de regime e risco.
Inclui verificacao de integridade e modo de contingencia (fallback deterministico).
"""

import json
import urllib.request
import urllib.error
import asyncio
from typing import Dict, Any

DEFAULT_OPENCODE_URL = "http://127.0.0.1:4096"
DEFAULT_TIMEOUT_SEC = 5.0

# Regime padrao conservador para fallback
FALLBACK_REGIME = {
    "regime": "NEUTRO_CONSERVADOR",
    "multiplicador_exposicao": 0.50,
    "permitir_novas_entradas": True,
    "foco_estrategico": "PRESERVACAO_CAPITAL",
    "justificativa_curta": "Modo de contingencia ativado: OpenCode indisponivel ou resposta fora do padrao."
}


class OpenCodeSupervisorClient:
    def __init__(self, base_url: str = DEFAULT_OPENCODE_URL, timeout: float = DEFAULT_TIMEOUT_SEC):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def check_health(self) -> bool:
        """Verifica se o servidor do OpenCode esta ativo e respondendo na porta local."""
        loop = asyncio.get_event_loop()
        def _check():
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/",
                    headers={"User-Agent": "BotCripto-Supervisor/1.0"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status in (200, 404)  # Se respondeu HTTP, o servidor esta de pe
            except Exception:
                return False
        return await loop.run_in_executor(None, _check)

    async def evaluate_market_regime(self, market_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envia o sumario do mercado para o OpenCode e retorna a classificacao do regime.
        Aplica fallback automatico em caso de falha de rede ou timeout.
        """
        prompt = (
            "Voce e o Agente Supervisor de Risco de um ecossistema quantitativo de criptoativos. "
            "Avalie o seguinte resumo estatistico de mercado e responda EXCLUSIVAMENTE em formato JSON valido, "
            "sem markdown, sem texto introdutorio e sem explicacoes extras:\n"
            "Formato esperado:\n"
            "{\n"
            '  "regime": "TENDENCIA_ALTA" | "TENDENCIA_BAIXA" | "ALTA_VOLATILIDADE" | "LATERAL_BAIXA_VOLATILIDADE",\n'
            '  "multiplicador_exposicao": float entre 0.1 e 1.0,\n'
            '  "permitir_novas_entradas": bool,\n'
            '  "foco_estrategico": "ROMPIMENTO_ATR" | "RETORNO_A_MEDIA" | "TRAILING_STOP_CURTO" | "PAUSA_DEFENSIVA",\n'
            '  "justificativa_curta": "explicacao em uma frase concisa"\n'
            "}\n\n"
            f"DADOS DO MERCADO:\n{json.dumps(market_summary, indent=2)}"
        )

        payload = {
            "message": prompt
        }

        loop = asyncio.get_event_loop()
        def _post_request():
            try:
                # O OpenCode serve expoe endpoint para envio de mensagens/prompt
                req = urllib.request.Request(
                    f"{self.base_url}/run",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "BotCripto-Supervisor/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        raw = resp.read().decode("utf-8")
                        data = json.loads(raw)
                        # Tratar possivel encapsulamento de resposta da API do OpenCode
                        text_response = data.get("response") or data.get("output") or raw
                        # Parse do JSON interno retornado pela LLM
                        if isinstance(text_response, str):
                            clean_text = text_response.strip().replace("```json", "").replace("```", "").strip()
                            return json.loads(clean_text)
                        elif isinstance(text_response, dict):
                            return text_response
            except Exception as e:
                # Log e retorno do fallback conservador
                return None
            return None

        result = await loop.run_in_executor(None, _post_request)
        if result and isinstance(result, dict) and "regime" in result:
            # Validar limites do multiplicador de exposicao
            mult = float(result.get("multiplicador_exposicao", 0.5))
            result["multiplicador_exposicao"] = max(0.1, min(1.0, mult))
            return result
            
        return FALLBACK_REGIME
