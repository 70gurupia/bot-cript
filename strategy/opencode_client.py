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

    def _parse_llm_json(self, raw_payload: Any) -> Dict[str, Any] | None:
        """Processa e decodifica a resposta da LLM em um dicionário estruturado."""
        text_response = raw_payload.get("response") or raw_payload.get("output") if isinstance(raw_payload, dict) else raw_payload
        if isinstance(text_response, str):
            clean_text = text_response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        if isinstance(text_response, dict):
            return text_response
        return None

    def _execute_http_request_sync(self, payload: dict) -> Dict[str, Any] | None:
        """Executa a requisição síncrona HTTP para o servidor OpenCode."""
        try:
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
                    return self._parse_llm_json(data)
        except Exception:
            return None
        return None

    async def evaluate_market_regime(self, market_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envia o sumário do mercado para o OpenCode e retorna a classificação do regime.
        Aplica fallback automático em caso de falha de rede ou timeout.
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
        payload = {"message": prompt}
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._execute_http_request_sync, payload)

        if result and isinstance(result, dict) and "regime" in result:
            mult = float(result.get("multiplicador_exposicao", 0.5))
            result["multiplicador_exposicao"] = max(0.1, min(1.0, mult))
            return result

        return FALLBACK_REGIME
