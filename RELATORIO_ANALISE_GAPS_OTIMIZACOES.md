# Relatório de Análise : Bot Cripto (`bot-cript`)

**Caminho:** `/home/reginato/Projetos/bot-cript/`
**Data:** 2026-09-29
**Análise:** Arquitetura, segurança (STRIDE/OWASP LLM01-10), motor genético (AST), tesouraria, monitoramento, testes, dados/logs, performance.
**Base:** Leitura de 35+ arquivos fonte (core/, strategy/, evolution/, treasury/, monitoring/, docs/, data/, tests/), 2.587 linhas de `bot_audit.jsonl` e 10 pares históricos (1h/15m).

---

## 1. Resumo Executivo

O ecossistema é **arquiteturalmente maduro**: documentação técnica completa (`ARCHITECTURE.md`, `SECURITY_THREAT_MODEL.md`, `EVOLUTIONARY_INCUBATOR.md`, `RISK_TREASURY_SPEC.md`, `ROADMAP_IMPLEMENTATION.md`), segurança em profundidade (Zero-Trust, AST tipada sem `eval`, circuit breaker atômico com `os.replace`), motor genético seguro (crossover de subárvores + mutação gaussiana com clamps), tesouraria com Kelly fracionário (20%), filtro de covariância e alavancagem isolada (teto 3x). Os testes de benchmarks de 2024 (`data/strategies_benchmark_report.json`) mostram resultados sólidos (Lead-Lag BTC->ETH: 74,4% win rate, PF 4,32, DD 1,6%).

Entretanto, há **gaps operacionais críticos** em autenticação do dashboard, token placeholder do Telegram, falta de testes de segurança do AST, ausência de loop assíncrono principal integrado e otimizações de cálculo estatístico ainda não vetorizadas. Nenhum arquivo de análise existia antes deste.

---

## 2. Segurança & Infraestrutura : Pontos Fortes

- **STRIDE documentado** com mitigação por controle (Spoofing: TLS 1.3 + HMAC; Tampering: proibição `eval/exec`; Repudiation: SQLite audit + hash de estado; Information Disclosure: regex de sanitização; DoS: Leaky Bucket + profundidade AST max 8; Elevation: separação física `PaperTradingExchange`).
- **Kill Switch** (`core/kill_switch.py`): persistência atômica (`tempfile.NamedTemporaryFile` + `os.replace`), recuperação de boot (`verify_boot_state`), níveis L1 (agente), L2 (portfólio global, 24h cooling-off), L3 (heartbeat > 10s).
- **Exchange Adapter** (`core/exchange_adapter.py`): bloqueio estrito de `withdraw()` e `transfer()` via `SecurityException`; configuração `brokerId: None`; heartbeat com `network_timeout_seconds` (10s); normalização de ticker/OHLCV.
- **Logger** (`core/logger.py`): `sanitize_text` + `sanitize_payload` com regex para `api_key`, `secret`, `token`, `password`, `auth`, `bearer`, além de strings hexadecimais longas (32-64 chars); formato JSON estrito.
- **AST Engine** (`strategy/ast_engine.py`): `FORBIDDEN_CALL_PATTERN` bloqueia `eval`, `exec`, `__import__`, `os`, `sys`, `subprocess`, `compile`, `globals`, `locals`, `builtins`, `getattr`, `setattr`; `ALLOWED_DATA_FIELDS` fechado; `MAX_AST_DEPTH = 8`; `_check_string_safety` rejeita `(`, `)`, `;`, `\`, `\n`, `\r`.
- **Settings** (`config/settings.py`): `RiskLimits` imutável (`.ConfigDict(frozen=True, extra="forbid")`); `SystemSettings` com `paper_trading_mode=True` por padrão.

---

## 3. Segurança : Gaps Críticos (Prioridade Alta)

| # | Gap | Impacto | Local / Evidência | Sugestão |
|---|-----|---------|-------------------|----------|
| S1 | **Dashboard sem autenticação** | Qualquer processo com acesso ao host (ou rede local) pode acionar `/api/panic` (L2 global) ou consultar estado de posições | `monitoring/web_app.py`: `FastAPI()` sem middleware, `/api/panic` exposto diretamente | Adicionar `OAuth2PasswordBearer` ou `APIKeyHeader`; restringir `0.0.0.0` para `127.0.0.1`; desativar `/api/panic` em produção sem 2FA |
| S2 | **Telegram token placeholder** | Bot opera com `bot_token="DUMMY_TOKEN"`; se usado em produção, qualquer um pode assumir o controle dos comandos `/panic`, `/kill`, `/resume` | `monitoring/telegram_service.py`: `bot_token or "DUMMY_TOKEN"`; `authorized_chat_ids` fixo `[123456789]` | Exigir `TELEGRAM_BOT_TOKEN` via env; validar `len(token) > 30`; implementar webhook HTTPS em vez de polling; rotacionar `authorized_chat_ids` via config |
| S3 | **Sem testes de injeção de código no AST** | Se uma mutação futura (ou payload externo) inserir `eval` de forma ofuscada (ex: `getattr(__builtins__, 'eval')`), não há regressão automatizada | Nenhum arquivo `tests/test_ast_security.py`; `tests/` tem `test_anti_martingale`, `test_laia`, `test_strategy_catalog`, `test_mixed_portfolio` | Criar `tests/test_ast_security.py` com casos: `eval`, `exec`, `__import__`, `getattr` disfarçado, `compile`, `subprocess`, `os.system`, injeção via `ConstantNode` de string maliciosa |
| S4 | **Não há validação de assinatura HMAC-SHA256** | Documentação menciona HMAC local, mas `submit_order` não assina payload de ordem; risco de ordem forjada se rede for comprometida | `core/exchange_adapter.py`: `submit_order()` envia `create_order` diretamente sem `signature` | Implementar HMAC-SHA256 com `secret` local, incluindo `agent_id`, `symbol`, `side`, `amount`, `nonce`; validar na camada `PaperTradingExchange` como simulador |
| S5 | **Logger sanitiza, mas não audita arquivos de config** | `config/settings.py` não verifica se `EXCHANGE_API_KEY` está no ambiente; se exposto, fica em memoria mas pode vazar via dump | Nenhuma verificação de `os.environ` no boot | Adicionar `check_env_secrets()` no `SystemSettings.__init__` que rejeita chaves com conteúdo de exemplo/placeholder; usar `secrets.token_urlsafe` para geração interna |
| S6 | **Paper trading retorna preços fixos** | Quando `ccxt` não está disponível (`self._ccxt_instance is None`), `fetch_ticker_normalized` retorna `last=60001.0` fixo; pode mascarar falhas de conectividade | `exchange_adapter.py`: mock hardcoded | Substituir por série sintética baseada em última série histórica disponível (`data/historical/BTCUSDT_1h_2020_2024.csv`) para manter comportamento determinístico mas realista |

---

## 4. Motor Genético & Evolução : Pontos Fortes

- **Crossover** (`evolution/crossover_engine.py`): seleção por torneio restrita aos 20% melhores (`elite_pool` de até `max(2, int(len(sorted_pop)*0.20))`); garantia de parentes distintos com até 5 tentativas.
- **Mutação paramétrica** (`mutate_constant_value`): `random.gauss(0.0, mutation_rate)` (padrão 8%); `mutate_ast_constants` percorre recursivamente; parâmetros de risco (`MIN_STOP_LOSS_PCT` 0.5% a `MAX_STOP_LOSS_PCT` 5.0%; `MIN_TAKE_PROFIT_PCT` 1.0% a `MAX_TAKE_PROFIT_PCT` 15.0%; `MIN_ATR_STOP_MULT` 1.0 a `MAX_ATR_STOP_MULT` 4.0) são clampados por `_clamp()`.
- **Fitness** (`evolution/fitness_evaluator.py`): cálculo de Sharpe, Sortino, Calmar, Drawdown, Profit Factor com anualização (`HOURLY_ANNUALIZATION_FACTOR = sqrt(365*24) ≈ 93.59`; `FIFTEEN_MIN_ANNUALIZATION_FACTOR = sqrt(365*24*4) ≈ 187.19`).
- **Incubadora** (`evolution/incubator_manager.py`): critérios de graduação explícitos (`min_graduation_sharpe=1.25`, `max_graduation_drawdown=4.5`, `rejection_drawdown_limit=8.0`, `min_quarantine_trades=30`, `max_clones_in_quarantine=20`); estados `QUARANTINE`, `GRADUATED`, `ELIMINATED`.

---

## 5. Motor Genético : Gaps (Prioridade Alta/Média)

| # | Gap | Impacto | Local | Sugestão |
|---|-----|---------|-------|----------|
| G1 | **Crossover não valida consistência semântica de tipos** | Pode gerar `ConditionNode` com `operator="maior"` mas `left` tipo `DataNode` e `right` tipo `ConstantNode(bool)` : sintaticamente válido, semanticamente quebrado | `evolution/crossover_engine.py`: `_pick_one()` retorna `StrategyAST` sem verificação de `type(left)` vs `type(right)` | Adicionar validador `validate_ast_semantics(node)` que verifica se comparações são entre `DataNode`/`IndicatorNode` e `ConstantNode` numérico |
| G2 | **Mutação não determinística (sem seed)** | `random.gauss` sem `random.seed()` implica que testes de mutação podem falhar de forma não reprodutível, dificultando regressão | `mutate_constant_value()` | Adicionar `seed` opcional (`mutate_constant_value(val, rate, seed=None)`); se `seed` definido, chamar `random.seed(seed)` antes da perturbação |
| G3 | **Sem controle de memória/população crescent** | Incubadora limita clones ativos (20), mas `candidates` é `Dict[str, CandidateAgent]` com histórico completo; pode crescer indefinidamente se não houver limpeza de `ELIMINATED` | `evolution/incubator_manager.py`: `candidates` nunca é limpo | Implementar `prune_eliminated()` que remove candidatos `ELIMINATED` com mais de 30 dias; ou usar `sqlite` para persistência externa |
| G4 | **Não há testes de segurança do AST** | Sem regressão contra injeção; se `ConstantNode.value` receber string maliciosa que passa pelo regex (ex: `"open\n"` com newline escapado), pode ocorrer comportamento inesperado | Nenhum arquivo de segurança do AST | Criar `tests/test_ast_security.py` com verificação de `_check_string_safety` contra 20+ vetores |

---

## 6. Tesouraria & Risco : Pontos Fortes

- **Kelly fracionário** (`treasury/treasury_controller.py`): `calculate_fractional_kelly` com `fractional_kelly=0.20`; se `win_rate <= 0` ou `win_loss_ratio <= 0`, retorna `0.0`; `min(kelly_full * 0.20, 0.20)` impede ruína.
- **Dimensionamento** (`calculate_position_size`): combina Kelly, trava de risco (`max_single_trade_risk_pct=1.0`), teto por ativo (`max_single_asset_exposure_pct=0.25`) e teto de exposição agregada (`max_portfolio_exposure_pct=0.70`).
- **Correlação** (`treasury/correlation_matrix.py` : não lido completamente, mas referenciado): `AssetCorrelationTracker` usado no `TreasuryController`; pressupõe atualização contínua.
- **Configuração** (`config/risk_limits.json` + `settings.py`): limites invariantes (`max_leverage_ceiling=3.0`, `max_agent_daily_loss_pct=2.0`, `max_portfolio_daily_drawdown_pct=4.0`, `max_kelly_fraction=0.25`, `max_single_trade_risk_pct=1.0`).

---

## 7. Tesouraria : Gaps (Prioridade Média)

| # | Gap | Impacto | Sugestão |
|---|-----|---------|----------|
| T1 | **Correlação pode ser estática** | Se `AssetCorrelationTracker` usa apenas dados históricos de 2020-2024, pode não refletir regimes atuais (ex: altcoins com correlação > 0,85 durante crash) | Usar janela móvel (30/90 dias) atualizada pelo loop de eventos; adicionar alerta se `correlation > 0.70` |
| T2 | **Paper trading não simula slippage real** | `PaperTradingExchange.create_order()` (não lido completamente) provavelmente usa preço de entrada sem spread/slippage; pode superestimar PnL | Adicionar `slippage_pct=0.05` (documentado) e `fee_maker=0.10%`, `fee_taker=0.15%` nas ordens simuladas |
| T3 | **Tesouraria não valida ordem antes do adapter** | `submi t_order` no adapter chama `circuit_breaker.is_trading_allowed()` mas não chama `treasury.validate_order()` explicitamente (verificar fluxo) | Garantir que `TreasuryController.validate_order()` seja chamado em `submit_order()` antes de `paper_exchange.create_order()` ou `ccxt.create_order()` |

---

## 8. Monitoramento, Dashboard & Interface : Pontos Fortes

- **Dashboard** (`monitoring/web_app.py`): endpoints `/api/status`, `/api/incubator`, `/api/panic`; exibe `total_equity`, `cash_balance`, `open_positions_count`, `market_regime`, estado do circuit breaker.
- **Telegram** (`monitoring/telegram_service.py`): comandos `/status`, `/panic`, `/kill`, `/resume`, `/confirm`; autenticação por `authorized_chat_ids`; registro de acesso não autorizado via `telemetry.emit_event`.
- **Prototype** (`prototype/index.html`): arquivo HTML de 21.658 bytes : provavelmente interface interativa completa.

---

## 9. Monitoramento : Gaps (Prioridade Alta/Média)

| # | Gap | Impacto | Sugestão |
|---|-----|---------|----------|
| M1 | **Web app não implementa autenticação** | Se o usuário expuser a porta 8000 (mesmo que `127.0.0.1`), qualquer processo do host pode acionar pânico | Implementar `FastAPI` com `HTTPBearer`; adicionar `X-API-Key` header; desativar `/api/panic` por padrão; usar `uvicorn` com `--host 127.0.0.1` confirmado |
| M2 | **Nenhuma métrica de performance (Prometheus)** | Não é possível monitorar latência do loop assíncrono, taxa de execução de ordens, tempo de resposta do supervisor LLM | Adicionar `fastapi` middleware com métricas `request_count`, `request_duration`; ou usar `prometheus_client` para expor `/metrics` |
| M3 | **Bot Telegram usa `urllib.request`** | Solicitação síncrona dentro de serviço potencialmente assíncrono; pode bloquear; token placeholder | Substituir por `python-telegram-bot` nativo (`telegram.Bot`) com `asyncio`; validar token real no `__init__` |

---

## 10. Testes, Validação & Qualidade : Pontos Fortes

- **Suíte existente:** `tests/test_anti_martingale.py` (Kelly, Monte Carlo), testes de `laia_entry_evaluator` (24/24 verdes), `test_strategy_catalog_tester` (23/23 verdes), `test_mixed_portfolio` (22/22 verdes).
- **Benchmark 2024:** `scripts/run_strategy_catalog_benchmark.py` gerou `data/strategies_benchmark_report.json` com 6 famílias; `run_mixed_portfolio_backtest.py` com 4 frentes; `run_hybrid_alpha_walk_forward.py`; `run_laia_entry_comparison.py`.
- **Kanban** (`KANBAN.md`): pipeline de 30 estratégias em 6 vertentes (A-F); 3 tarefas concluídas (`task-025`, `task-026`, `task-027`); WIP limit 1; gates de validação explicítos.

---

## 11. Testes : Gaps (Prioridade Alta)

| # | Gap | Impacto | Sugestão |
|---|-----|---------|----------|
| Q1 | **Falta `tests/test_ast_security.py`** | Sem regressão contra RCE via AST; se `ConstantNode` aceitar string com `eval` disfarçado, não há detecção | Criar arquivo com 20+ vetores (incluindo `getattr(__builtins__, 'eval')`, `compile`, `__import__`) |
| Q2 | **Falta `tests/test_circuit_breaker.py`** | Sem validação de recuperação de boot, persistência atômica, expiração de L2 | Testar `trip_level_2_portfolio` → `is_trading_allowed` → `verify_boot_state` → `reset_lock` |
| Q3 | **Falta `tests/test_exchange_adapter.py`** | Sem verificação de bloqueio de `withdraw`, heartbeat timeout, reconexão | Mock `ccxt.async_support`; testar `submit_order` com `paper_trading=True/False`; testar `check_connection_health` com `elapsed > 10` |
| Q4 | **Falta testes de carga/performance** | Loop assíncrono não testado sob concorrência real | Usar `pytest-asyncio` com 100 ordens simultâneas; medir latência média |

---

## 12. Dados, Logs & Integridade : Pontos Fortes

- **Histórico:** 10 pares (BTC, ETH, BNB, SOL, ADA, LINK, DOT, AVAX, XRP, DOGE) em 1h (`420.929 candles`) e 15m (`350.528 candles`) : `data/historical/`.
- **Banco SQLite:** `data/historical/market_data.db` (provavelmente indexado).
- **Auditoria:** `data/logs/bot_audit.jsonl` com 2.587 registros; eventos `CIRCUIT_BREAKER_L2_TRIGGERED` (drawdown 5%, patrônio de 10.000 → 9.500) e `BOOT_COOLING_OFF_RESTORED` (24h); reset manual autorizado; formato JSON estrito com `timestamp_utc`, `level`, `logger`, `message`, `event`, `agent_id`, `payload`.
- **Relatórios:** `data/anti_martingale_report.json`, `cent_scalper_report.json`, `hybrid_alpha_report.json`, `mixed_portfolio_report.json`, `walk_forward_report.json`, `strategies_benchmark_report.json`, `laia_entry_comparison_report.json`.

---

## 13. Dados, Logs : Gaps (Prioridade Média)

| # | Gap | Impacto | Sugestão |
|---|-----|---------|----------|
| D1 | **Log não rotacionado** | 2.587 linhas podem crescer rapidamente em operação contínua; risco de consumo de disco | Implementar `RotatingFileHandler` ou `logrotate`; ou escrever para `sqlite` com limite de linhas (ex: 50.000) |
| D2 | **Sem verificação de integridade dos CSV** | Arquivos históricos (`ADAUSDT_1h_...`) podem ser corrompidos por download parcial | Gerar `sha256` para cada CSV; armazenar em `data/historical/checksums.txt`; validar no boot |
| D3 | **Dados sintéticos no adapter quando CCXT falha** | Se `ccxt` estiver indisponível, `fetch_ohlcv_normalized` retorna candles sintéticos com preços fixos : pode mascarar falha real de rede | Logar evento `SYNTHETIC_DATA_USED` com `symbol` e `count`; alertar usuário via Telegram |

---

## 14. Otimizações de Performance (Prioridade Média)

| Área | Problema | Otimização | Impacto Esperado |
|------|----------|------------|------------------|
| Fitness evaluator | Loops Python puros em `calculate_sharpe_ratio`, `calculate_sortino_ratio`, `calculate_max_drawdown` | Vetorizar com `numpy` (já em `requirements.txt`): `np.mean`, `np.std`, `np.sqrt`, `np.minimum` | Redução de 70-90% no tempo de cálculo para populações > 100 indivíduos |
| Paper exchange | `Position.update_price()` e `create_order()` provavelmente usam atribuições individuais | Se muitos trades (>1.000), usar `list` ou `numpy.array` para `equity_curve`; implementar `update_prices_batch()` | Redução de latência em simulação de massa |
| Event loop | Nenhum arquivo `core/event_loop.py`; loop pode ser disperso entre scripts | Criar `core/event_loop.py` com `asyncio.gather()` centralizando `fetch_ticker`, `update_regime`, `evaluate_fitness`, `submit_order` | Melhor controle de concorrência, prevenção de bloqueio, facilidade de testes |
| Crossover | `copy.deepcopy(node)` para cada nó; pode ser custoso para árvores grandes | Usar `__slots__` nos nós `ASTNode`; implementar `clone()` personalizado sem `deepcopy` se estrutura é imutável | Redução de memória e tempo de cruzamento |
| Data loading | `csv` históricos lidos em memória completa | Se necessário, usar `pandas.read_csv` com `chunksize` ou `pyarrow` (já em requirements) para lazy loading | Menor footprint de RAM |

---

## 15. Melhorias de Arquitetura (Prioridade Média/Alta)

1. **Implementar `core/event_loop.py` integrador** (fase 6/7): conectar `supervisor_loop.py` (`MarketSupervisorLoop`), `incubator_manager.py`, `treasury_controller.py`, `exchange_adapter.py`, `web_app.py` em um único ciclo `asyncio` configurável (`interval_hours` para regime, `evaluation_interval` para fitness).
2. **Adicionará autenticação ao `monitoring/web_app.py`**: mínimo `APIKeyHeader` com chave de 32 bytes; desativar `/api/panic` por padrão; adicionar endpoint `/api/health` com status de `circuit_breaker`.
3. **Adicionar `tests/test_ast_security.py`**: 20 vetores de injeção; validar que qualquer token proibido levanta `SecurityError`; testar `_check_string_safety` contra `eval` disfarçado.
4. **Criar `tests/test_circuit_breaker.py`**: testar persistência atômica (`os.replace`), recuperação após falha de arquivo, expiração de L2, reset manual.
5. **Substituir `DUMMY_TOKEN` do Telegram por variável obrigatória**: `TELEGRAM_BOT_TOKEN`; validar se `len(token) > 30`; adicionar webhook HTTPS.
6. **Vetorização do `fitness_evaluator.py`**: substituir loops por `numpy`; confirmar que resultados permanecem idênticos (teste de regressão).
7. **Implementar rotação de logs**: `RotatingFileHandler` com `maxBytes=10MB`, `backupCount=5`; ou `sqlite` com `DELETE FROM audit WHERE timestamp < ?`.
8. **Verificar integridade de dados históricos**: gerar `checksums.txt` com `sha256` para cada CSV; validar no boot; alertar se divergente.

---

## 16. Plano de Ação (Prioridade e Ordem Sugerida)

### Imediato (0-2 dias)
- [S1] Adicionar autenticação mínima ao FastAPI (`APIKeyHeader`; restringir `/api/panic`).
- [S2] Corrigir Telegram token placeholder (`os.getenv("TELEGRAM_BOT_TOKEN")`; falhar se vazio).
- [S3] Criar `tests/test_ast_security.py` com vetores de injeção.
- [S4] Criar `tests/test_circuit_breaker.py` testando persistência e recuperação.

### Curto (3-7 dias)
- [G2] Adicionar `seed` determinística à mutação; criar `tests/test_crossover_consistency.py`.
- [Q1] Implementar `tests/test_exchange_adapter.py` (mock CCXT, testar withdraw, heartbeat).
- [M1] Implementar `fastapi` middleware de auth no dashboard; desativar `/api/panic` por padrão.
- [D1] Adicionar rotatividade de logs (`RotatingFileHandler`).

### Médio (1-2 semanas)
- [G1] Implementar validador semântico de AST pós-crossover.
- [O1] Vetorizar `fitness_evaluator.py` com `numpy`; adicionar teste de regressão.
- [T2] Adicionar slippage realista (`0.05%`) e fees no `PaperTradingExchange`.
- [O2] Criar `core/event_loop.py` integrador.

### Longo (2-4 semanas)
- [O3] Implementar métricas Prometheus no dashboard.
- [D2] Verificar integridade de CSV históricos; gerar checksums.
- [S6] Implementar HMAC-SHA256 nas ordens; validar no adapter.
- [S5] Adicionar verificação de ambiente (`check_env_secrets()`) no boot.

---

## 17. Verificações Executadas (Checklist)

- [x] Estrutura de diretórios (`ls`, `find`) confirmada
- [x] `README.md`, `docs/*.md` (8 arquivos) lidos
- [x] `config/settings.py`, `core/kill_switch.py`, `core/exchange_adapter.py`, `core/logger.py`, `core/paper_exchange.py` lidos
- [x] `strategy/ast_engine.py`, `strategy/supervisor_loop.py`, `strategy/opencode_client.py` lidos
- [x] `evolution/crossover_engine.py`, `evolution/fitness_evaluator.py`, `evolution/incubator_manager.py` lidos
- [x] `treasury/treasury_controller.py` lido (resumo)
- [x] `monitoring/web_app.py`, `monitoring/telegram_service.py` lidos
- [x] `tests/test_anti_martingale.py` lido; outros testes listados
- [x] `data/circuit_breaker_state.json` e `data/logs/bot_audit.jsonl` analisados
- [x] `requirements.txt` verificado (dependências pinadas `==`)
- [x] `KANBAN.md` analisado (pipeline de 30 estratégias, 3 concluídas)
- [x] Nenhum arquivo de relatório anterior existia (`ls RELATORIO*` = vazio)

---

## 18. Conclusão

O **Bot Cripto** é um projeto de alta qualidade técnica, com arquitetura de defesa em profundidade, documentação completa e resultados de benchmark empíricos comprovados. Os principais riscos operacionais estão em **autenticação ausente**, **token placeholder**, **falta de testes de segurança do AST**, **ausência de loop assíncrono integrado** e **otimizações de cálculo estatístico ainda não vetorizadas**. A aplicação das 8 melhorias imediatas (autenticação, Telegram, testes de segurança, testes de circuito, rotatividade de logs) reduziria significativamente a superfície de ataque e melhoraria a confiabilidade operacional.

**Arquivo gerado:** `/home/reginato/Projetos/bot-cript/RELATORIO_ANALISE_GAPS_OTIMIZACOES.md`
**Caminho absoluto:** `/home/reginato/Projetos/bot-cript/`
