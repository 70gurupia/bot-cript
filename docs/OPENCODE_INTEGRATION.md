# Integração com OpenCode: Servidor Local e Supervisor Assíncrono

Este documento especifica a arquitetura de comunicação entre o ecossistema Bot Cripto e o servidor headless do OpenCode (`~/.opencode/bin/opencode serve`).

---

## 1. Topologia da Integração

O OpenCode atua como a camada de inteligência contextual do bot. Em vez de ser invocado a cada tick (o que causaria lentidão e consumo desnecessário), ele opera como um daemon HTTP em segundo plano no próprio host (`127.0.0.1`), sendo consultado em ciclos macro (ex: fechamento de velas de 4h ou 24h) ou em eventos de anomalia de mercado.

```text
+-----------------------------------------------------------------------------------+
|                        BOT CRIPTO (Asyncio Event Loop)                            |
|                                                                                   |
|  [Loop de Mercado]                                                                |
|         |                                                                         |
|         v                                                                         |
|  [Fechamento de Vela 4h / Alerta]                                                 |
|         |                                                                         |
|         v                                                                         |
|  [Supervisor Client: strategy/opencode_client.py]                                 |
|         |                                                                         |
|         +--- HTTP POST (JSON Payload com Volatilidade, Volume e Candles) --------+
|         |                                                                        |
|         |                                                                        v
|         |                                              +-------------------------+
|         |                                              |  OPENCODE SERVE DAEMON  |
|         |                                              |  Host: 127.0.0.1:4096   |
|         |                                              |  Processo isolado local |
|         |                                              +------------+------------+
|         |                                                           |
|         |<-- HTTP Response (JSON com Regime e Multiplicador) <------+
|         |
|         v
|  [Validação Pydantic: MarketRegimeDecision]
|         |
|         v
|  [Tesouraria Central: Atualiza Limites de Risco Globais]
+-----------------------------------------------------------------------------------+
```

---

## 2. Inicialização do Servidor OpenCode

O servidor do OpenCode é executado no host local sem exposição para a internet:

```bash
~/.opencode/bin/opencode serve --port 4096 --hostname 127.0.0.1 --log-level INFO
```

### 2.1 Verificação de Saúde (Health Check)
O cliente do bot executa uma verificação preventiva antes de disparar análises:
* Requisição: `GET http://127.0.0.1:4096/`
* Caso o servidor não responda em 2 segundos, o bot ativa o **Modo Fallback Determinístico**, assumindo um regime conservador (`NEUTRO_BAIXO_RISCO`) sem travar a execução das ordens correntes.

---

## 3. Esquema de Comunicação (Payloads e Tipagem)

### 3.1 Prompt Estruturado Enviado pelo Bot (Input)
O bot consolida métricas resumidas para evitar estouro de contexto e economizar processamento:

```json
{
  "timestamp": 1735689600000,
  "timeframe": "4h",
  "macro_metrics": {
    "btc_retorno_24h_pct": -2.45,
    "volatilidade_anualizada_pct": 58.2,
    "volume_24h_vs_media_7d_ratio": 1.42,
    "funding_rate_medio_pct": 0.012,
    "drawdown_maximo_agentes_24h_pct": 1.15
  },
  "top_assets_summary": [
    {"symbol": "BTC/USDT", "preco": 92450.0, "rsi_14": 42.1, "distancia_ema200_pct": 3.8},
    {"symbol": "ETH/USDT", "preco": 3420.0, "rsi_14": 38.5, "distancia_ema200_pct": -1.2}
  ]
}
```

### 3.2 Resposta Esperada do OpenCode (Output Validado por Pydantic)
A resposta deve retornar estritamente a estrutura JSON definida:

```json
{
  "regime": "ALTA_VOLATILIDADE_BAIXA",
  "multiplicador_exposicao": 0.65,
  "permitir_novas_entradas": true,
  "foco_estrategico": "TRAILING_STOP_CURTO",
  "justificativa_curta": "Volume acima da média com RSI em declínio e pressão vendedora em ativos alternativos. Reduzir tamanho dos lotes e aproximar stops."
}
```

---

## 4. Tratamento de Falhas e Degradação Graciosa (Graceful Degradation)

1. **Timeout Rígido**: Toda consulta ao OpenCode possui timeout assíncrono de 5 segundos.
2. **Defesa contra Respostas Malformadas**: Se o OpenCode retornar texto fora do padrão JSON esperado, o validador Pydantic rejeita o payload e mantém o último estado seguro previamente registrado.
3. **Imutabilidade das Travas de Risco**: O OpenCode pode apenas **reduzir** a exposição ou **pausar** entradas. Ele jamais possui permissão para aumentar alavancagem acima do teto fixo da Tesouraria (3x) ou desativar o Kill Switch.
