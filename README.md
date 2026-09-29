# Bot Cripto: Ecossistema de Trading Autônomo, Autoevolutivo e Replicável

Sistema modular de negociação algorítmica em criptoativos projetado sob os princípios de Defesa em Profundidade (Zero-Trust), arquitetura orientada a eventos assíncrona, supervisão híbrida por Modelos de Linguagem (LLMs), recombinação genética segura via Árvores de Sintaxe Abstrata (AST) e quarentena em Paper Trading na Incubadora.

---

## 1. Visão Geral e Proposta de Valor

Diferente de robôs convencionais de parâmetros fixos que se degradam conforme o regime de mercado se altera, ou de scripts experimentais que aplicam mutações diretas em dinheiro real arriscando liquidação, este ecossistema implementa:

1. **Camada de Execução Determinística**: Conectividade em tempo real via WebSockets (CCXT assíncrono), cálculo de indicadores e roteamento de ordens em milissegundos sem latência de linguagem natural.
2. **Supervisão Estratégica via LLM**: Análise periódica de regime macroeconômico, notícias e sentimento para ajustar viés de volatilidade e parâmetros operacionais globais.
3. **Cruzamento Genético Estruturado (AST)**: Recombinação de regras de entrada e saída entre os melhores agentes do ecossistema sem utilização de funções inseguras (`eval`/`exec`).
4. **Incubadora em Quarentena**: Agentes replicados nascem obrigatoriamente em simulação em tempo real (paper trading). Apenas estratégias com significância estatística comprovada (Sharpe ratio, drawdown controlado e volume de trades) são promovidas para operar frações de capital real.
5. **Circuit Breaker em 3 Camadas**: Travamento determinístico de emergência contra drawdown diário, perda de conexão ou anomalia operacional.

---

## 2. Estrutura de Documentação do Projeto

A documentação detalhada e modular do sistema está organizada na pasta `docs/`:

* **[docs/ARCHITECTURE.md](file:///home/reginato/Projetos/bot-cript/docs/ARCHITECTURE.md)**: Arquitetura completa de subsistemas em 5 camadas, fluxo de dados assíncrono, máquinas de estado de agentes e gerenciamento de posições.
* **[docs/SECURITY_THREAT_MODEL.md](file:///home/reginato/Projetos/bot-cript/docs/SECURITY_THREAT_MODEL.md)**: Modelagem de ameaças STRIDE, controle de segredos e chaves de API, mitigação de RCE no motor genético, sandbox e isolamento de margem.
* **[docs/EVOLUTIONARY_INCUBATOR.md](file:///home/reginato/Projetos/bot-cript/docs/EVOLUTIONARY_INCUBATOR.md)**: Especificação formal do motor genético, gramática de regras em AST, processo de crossover e ciclo probatório da incubadora.
* **[docs/RISK_TREASURY_SPEC.md](file:///home/reginato/Projetos/bot-cript/docs/RISK_TREASURY_SPEC.md)**: Regras da Tesouraria Central, critério fracionário de Kelly, matriz de covariância entre agentes e protocolos de Kill Switch.
* **[docs/ROADMAP_IMPLEMENTATION.md](file:///home/reginato/Projetos/bot-cript/docs/ROADMAP_IMPLEMENTATION.md)**: Roteiro metódico de implementação em fases alinhado ao Devin Method, lista de dependências pinadas e critérios de aceitação.

---

## 3. Topologia de Diretórios do Projeto

```text
/home/reginato/Projetos/bot-cript/
├── README.md                          # Este documento principal
├── docs/                              # Especificações técnicas completas
│   ├── ARCHITECTURE.md                # Arquitetura dos 5 subsistemas
│   ├── SECURITY_THREAT_MODEL.md       # Threat Model STRIDE e Circuit Breakers
│   ├── EVOLUTIONARY_INCUBATOR.md      # Motor genético de AST e incubadora
│   ├── RISK_TREASURY_SPEC.md          # Tesouraria e limites matemáticos de risco
│   └── ROADMAP_IMPLEMENTATION.md      # Plano de construção metódico
├── config/                            # Esquemas de configuração Pydantic e limites
├── core/                              # Loop de eventos assíncrono, exchange e kill switch
├── strategy/                          # Estratégias, regras em AST e supervisor LLM
├── evolution/                         # Módulo de avaliação estatística, crossover e incubadora
├── treasury/                          # Alocação de capital e matriz de correlação
├── monitoring/                        # Dashboard web FastAPI e bot Telegram
└── tests/                             # Suíte de testes unitários e de robustez
```

---

## 4. Requisitos de Segurança Primários

Antes de qualquer execução em ambiente real:
* Chaves de API configuradas sem permissão de saque na corretora.
* Vínculo obrigatório de IP estático da máquina executora na exchange.
* Execução em container Docker sem privilégios de superusuário (rootless).
* Margem estritamente isolada em contratos futuros com teto máximo de alavancagem pré-definido em código.
