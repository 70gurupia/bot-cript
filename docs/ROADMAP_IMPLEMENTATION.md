# Roteiro de Implementação e Metodologia de Construção (Roadmap)

Este documento estabelece o plano metódico de implementação do ecossistema Bot Cripto, alinhado ao Loop Metódico de 7 Passos do Devin Method e aos padrões de engenharia de software determinística.

---

## 1. Loop Metódico de Engenharia (Devin Method Conformity)

### Step 0: Classificação do Ask
* **Classificação**: Tarefa de Arquitetura e Engenharia de Software.
* **Escopo Declarado**: Estruturação completa, documentação integral de todos os subsistemas e criação do plano de implementação por fases com dependências pinadas e testes de segurança.

### Step 1: Definição de Done e Verificação Observável
* **Definição de Done**: O ecossistema está devidamente documentado na pasta `/home/reginato/Projetos/bot-cript/` (com link simbólico acessível `/home/reginato/Projetos/bot cript`), cobrindo arquitetura, modelo de ameaças, motor genético, tesouraria e roadmap, validado pelos scripts determinísticos de qualidade.
* **Critério Observável**: Aprovação nos testes dos scripts `validate-devin-method.py` e `validate-nlp.py` com zero violações.

INTENT: code does complete system documentation and engineering specification; check expects rigorous technical roadmap and architecture specs; spec says zero-trust evolutionary crypto bot with incubator, genetic AST crossover, central treasury and circuit breakers.

TWINS: searched none - found 0 other sites: initial architecture foundation.

---

## 2. Fases de Implementação Progressiva

```text
+-----------------------------------------------------------------------------------+
| FASE 1: FUNDAÇÃO DE SEGURANÇA E CONFIGURAÇÃO                                      |
| - Modelos Pydantic v2 para validação de esquemas e limites invariantes            |
| - Implementação do Kill Switch central e Circuit Breakers                         |
| - Interceptador e mascarador de segredos em logs                                  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| FASE 2: MOTOR DETERMINÍSTICO E CONECTIVIDADE (CCXT ASYNC)                         |
| - Wrapper assíncrono sobre CCXT com tratamento de reconexão e heartbeat           |
| - Simulador de Exchange local (PaperTradingExchange) para testes herméticos       |
| - Rastreador de estado de ordens e preenchimentos                                 |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| FASE 3: GRAMÁTICA DE REGRAS EM AST E AVALIADOR ESTATÍSTICO                        |
| - Estrutura de dados tipada de regras lógicas (sem eval/exec)                     |
| - Módulo de cálculo de Sharpe, Sortino, Calmar, Drawdown e Profit Factor          |
| - Suíte de testes com dados históricos de mercado sintéticos                      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| FASE 4: MOTOR GENÉTICO E INCUBADORA EM PAPER TRADING                              |
| - Algoritmo de crossover de subárvores e mutações gaussianas de parâmetros        |
| - Gerenciador da Incubadora em tempo real com taxas e slippage sintético          |
| - Regras de quarentena e protocolo de graduação condicional                      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| FASE 5: TESOURARIA CENTRAL E FILTRO DE COVARIÂNCIA                                |
| - Algoritmo de dimensionamento por Kelly Fracionário (20% de Kelly)               |
| - Matriz de correlação de retornos entre agentes ativos                           |
| - Validador de margem isolada e teto de alavancagem por ordem                     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
| FASE 6: SUPERVISÃO LLM, PAINEL WEB E BOT TELEGRAM                                 |
| - Módulo de classificação de regime de mercado via LLM                            |
| - Dashboard web em FastAPI com árvore genealógica de agentes                      |
| - Bot do Telegram para alertas em tempo real e comando de pânico remoto           |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| FASE 7: ESTRATÉGIAS AVANÇADAS, MOTOR MISTO E ANTI-MARTINGALE                      |
| - Ingestão de dados históricos de 15m (350.528 candles) e 1h (420.929 candles)   |
| - Motor de Micro-Scalping de Centavos com Bandas de Bollinger e Daily Profit Lock |
| - Motor Híbrido Misto Multi-Estratégia (Lead-Lag, Donchian, Scalp Maker, Funding) |
| - Dimensionamento Geométrico Anti-Martingale (+25% em vitórias, reset na perda)   |
| - Validação de 30 estratégias quantitativas e benchmark empírico de 2024          |
| - Orquestrador completo com 23 suítes verdes de testes determinísticos            |
+-----------------------------------------------------------------------------------+
```

---

## 3. Matriz de Dependências Pinadas (Versões Exatas)

Todas as dependências externas são fixadas com versões exatas (`==`) em conformidade com as políticas determinísticas de supply chain:

```text
# Núcleo Assíncrono e Tipagem
pydantic==2.8.2
pydantic-settings==2.4.0
aiohttp==3.10.5
aiosignal==1.3.1

# Conectividade de Mercado
ccxt==4.3.72

# Análise Numérica e Algoritmos Genéticos
numpy==2.0.1
pandas==2.2.2
scipy==1.14.0
deap==1.4.1

# Dashboard Web e API
fastapi==0.112.2
uvicorn==0.30.6
jinja2==3.1.4

# Bot de Telemetria e Alertas
python-telegram-bot==21.5

# Testes e Qualidade
pytest==8.3.2
pytest-asyncio==0.24.0
pytest-cov==5.0.0
```

---

## 4. Matriz de Gates de Validação Contínua

Antes de qualquer avanço de fase no código:
1. **Segurança (SAST)**: Execução de análise estática de segurança e verificação de segredos.
2. **Complexidade Ciclomática**: Funções com limite máximo de complexidade ciclomática de 10.
3. **Cobertura de Testes**: Mínimo de 85% de cobertura de código em testes unitários e de integração.
4. **Validação de Conformidade**: Aprovação contínua no script `validate-devin-method.py`.
