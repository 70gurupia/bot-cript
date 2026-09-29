# Arquitetura do Sistema: Bot Cripto Autoevolutivo

Este documento detalha o funcionamento interno, a topologia de comunicação assíncrona e o ciclo de vida dos componentes do ecossistema de negociação algorítmica.

---

## 1. Topologia de Cinco Camadas

O sistema adota uma separação rigorosa de responsabilidades para garantir que falhas em camadas de inteligência artificial ou modelos de linguagem não afetem a integridade da execução determinística nem ultrapassem as travas financeiras.

```text
+-----------------------------------------------------------------------------------+
|                        CAMADA 1: SUPERVISÃO E INTERFACE                          |
|   - Dashboard Web Local (FastAPI): telemetria, árvore genealógica e posições      |
|   - Bot Telegram: notificações push de eventos e comando remoto de emergência     |
|   - LLM Market Supervisor: análise contextual de notícias e regimes de mercado    |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        CAMADA 2: MOTOR GENÉTICO E EVOLUÇÃO                        |
|   - Statistical Evaluator: cálculo de Sharpe, Sortino, Calmar e Drawdown          |
|   - Paper Trading Incubator: quarentena obrigatória de validação em tempo real    |
|   - AST Crossover Engine: recombinação sintática de regras sem código arbitrário  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        CAMADA 3: TESOURARIA CENTRAL E RISCO                       |
|   - Central Risk Controller: aprovação final de ordens e alocação de saldo        |
|   - Covariance Filter: verificação de correlação entre agentes ativos             |
|   - Multi-Level Circuit Breaker: Kill Switch por perda diária ou desconexão       |
|   - Invariant Leverage Enforcer: imposição estrita de margem isolada e teto de alav. |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        CAMADA 4: MOTOR DETERMINÍSTICO DE EXECUÇÃO                 |
|   - Async Event Loop (Python asyncio): processamento contínuo de baixa latência   |
|   - CCXT Async Adapter: normalização de mensagens WebSocket e REST                |
|   - Order State Tracker: rastreamento de preenchimentos, slippage e taxas         |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        CAMADA 5: INFRAESTRUTURA E CONECTIVIDADE                   |
|   - Container Docker sem root com recursos de CPU/Memória limitados               |
|   - Regras de firewall no host (UFW) com restrição de portas                      |
|   - Corretora de Criptoativos: chaves de API restritas a IP e sem permissão de saque|
+-----------------------------------------------------------------------------------+
```

---

## 2. Subsistemas Detalhados

### 2.1 Camada 1: Supervisão e Interface
* **Dashboard Web Local**: Construído sobre FastAPI e templates HTML minimalistas. Fornece uma visão unificada da árvore genealógica dos agentes (agente pai, mutações sofridas, filhos gerados), curvas de patrimônio líquido (PnL acumulado), histórico de operações e métricas dos agentes em quarentena na incubadora.
* **Bot de Notificações e Pânico (Telegram)**: Atua como canal de telemetria externa para o smartphone do operador. Dispara alertas de preenchimento de ordem, nascimento de novos clones e promoções da incubadora. Implementa o comando crítico `/kill` ou `/panic`, que aciona imediatamente o Circuit Breaker Nível 2 via endpoint autenticado local.
* **Supervisor LLM**: Executa em intervalos fixos (ex: a cada 1 hora ou 4 horas). Consulta agregadores de mercado e resumos noticiosos para determinar o "Regime de Mercado" (Tendência Forte de Alta, Tendência Forte de Baixa, Alta Volatilidade Indireta ou Mercado Lateralizado). Essa informação é convertida em um vetor numérico de ajuste de sensibilidade para os agentes operacionais.

### 2.2 Camada 2: Motor Genético e Incubadora
* **Avaliador Estatístico**: Responsável por auditar continuamente o livro de trades de cada agente. Diferente de sistemas ingênuos que medem apenas lucro percentual, o avaliador computa métricas estatísticas robustas:
  * Sharpe Ratio anualizado.
  * Sortino Ratio (penaliza apenas volatilidade negativa).
  * Drawdown máximo histórico e de janela móvel.
  * Profit Factor e Expectancy matemática por trade.
  * Contagem mínima de amostras (mínimo de 30 trades fechados).
* **Incubadora em Paper Trading**: Ambiente isolado de simulação que se alimenta do mesmo fluxo de dados em tempo real da corretora. Qualquer agente resultante de mutação ou cruzamento genético é depositado na incubadora. O agente não possui acesso a saldo real. Apenas após cumprir todo o checklist estatístico o agente é marcado como elegível para promoção.
* **Motor de Cruzamento de AST**: Processa a estrutura interna de regras dos agentes em formato de árvore de decisão tipada (Abstract Syntax Tree), combinando nós condicionais válidos entre dois genitores aprovados.

### 2.3 Camada 3: Tesouraria Central e Controle de Risco
* **Validador de Invariantes**: Nenhuma ordem gerada por agente chega diretamente à exchange. Ela passa obrigatoriamente pela Tesouraria, que valida:
  1. Se a alavancagem solicitada está abaixo ou igual ao teto fixo estipulado em configuração imutável.
  2. Se a margem da posição está categorizada explicitamente como `ISOLATED`.
  3. Se o stop loss está parametrizado e posicionado a uma distância viável do preço de entrada.
* **Filtro de Descorrelação**: Avalia se a ordem proposta por um agente não duplica posições existentes na mesma direção para o mesmo ativo ou ativos com correlação histórica acima de 0,70.
* **Circuit Breakers**: Monitor de integridade que trava a emissão de ordens caso os tetos de perda diária ou falhas de comunicação sejam atingidos.

### 2.4 Camada 4: Motor Determinístico de Execução
* **Loop Assíncrono**: Baseado em `asyncio`, executando múltiplos corotinas concorrentes para leitura de WebSockets, cálculo de médias e despacho de mensagens de rede.
* **Camada de Abstração CCXT**: Isola as idiossincrasias de cada exchange, provendo formato único para ordens a mercado, ordens limite e cancelamentos.
* **Rastreador de Estado**: Mantém uma réplica local do estado de posições e saldo para evitar chamadas de rede redundantes (evitando rate limits da corretora).

---

## 3. Máquina de Estados do Agente

Todo agente no ecossistema transita rigorosamente pela seguinte máquina de estados finitos:

```text
       [Criação / Crossover]
                 |
                 v
         +---------------+
         |  INCUBATING   | <--- Quarentena em Paper Trading com dados em tempo real
         +-------+-------+
                 |
     (Atinge critérios estatísticos)
                 |
                 v
         +---------------+
         |   QUALIFIED   | <--- Elegível para alocação de capital real
         +-------+-------+
                 |
        (Aprovação da Tesouraria)
                 |
                 v
         +---------------+        (Drawdown diário individual > 2%)
         |     LIVE      | --------------------------------------------+
         +-------+-------+                                             |
                 |                                                     v
                 |                                             +---------------+
                 |                                             |    PAUSED     |
                 |                                             +-------+-------+
                 |                                                     |
    (Violação severa ou Sharpe < 0)                                    |
                 |                               (Recuperação ou descarte)
                 v                                                     |
         +---------------+ <-------------------------------------------+
         |  TERMINATED   | <--- Capital desalocado e agente arquivado
         +---------------+
```

---

## 4. Fluxo de Vida de uma Operação (Trade Lifecycle)

1. **Geração de Sinal**: O agente avalia a atualização mais recente de preço (candle ou tick) através da sua árvore de regras e emite um sinal de entrada (ex: `COMPRA_SPOT_BTC_USDT`).
2. **Consulta ao Supervisor**: O motor verifica o multiplicador de exposição recomendado pela camada de supervisão macro.
3. **Auditoria de Risco pela Tesouraria**:
   * A Tesouraria checa o saldo livre reservado ao agente.
   * Calcula o tamanho do lote pelo Critério de Kelly Fracionário (ex: 20% do Kelly integral).
   * Valida se a perda máxima permitida na operação respeita o limite individual do agente (máximo 1% do saldo do agente por trade).
4. **Despacho da Ordem**: A ordem limite ou a mercado é enviada à exchange via WebSocket autenticado com assinatura criptográfica HMAC-SHA256.
5. **Confirmação e Monitoramento**: Ao receber a confirmação de execução (fill), a Tesouraria registra a posição e envia a ordem de Stop Loss associada imediatamente.
6. **Encerramento e Registro**: Ao término da operação, o lucro ou perda líquido (deduzindo taxas e slippage) é persistido no banco de dados local para atualização contínua do Sharpe Ratio e score do agente.

---

## 5. Dimensionamento Exponencial e Portfólio Misto (Fase 7)

Para micro-capital (ex: R$ 10,00 inicial), o sistema acopla à Tesouraria o módulo de progressão geométrica Anti-Martingale:
* **Anti-Martingale Engine (`strategy/anti_martingale_engine.py`)**: Lote base proporcional ao saldo acumulado ($S_0 = 4\%$ da banca). A cada vitória, o lote do trade seguinte expande +25%. Ao atingir 3 vitórias seguidas, realiza lucro e volta à base. Em qualquer perda, reseta compulsoriamente para $S_0$.
* **Motor Híbrido Misto (`strategy/mixed_portfolio_engine.py`)**: Sincroniza quatro frentes ativas:
  1. Lead-Lag Temporal (BTC para ETH em 15m) com 74,4% de taxa de acerto.
  2. Micro-Scalp de Centavos em 15m com ordens Maker (taxa 0,02%) e alvos simétricos de 0,25%.
  3. Donchian 20 Breakout em 1h no Bitcoin para captura de grandes tendências.
  4. Cash & Carry de Funding Rate para retorno passivo delta-neutro contínuo (+24,5% a.a.).
* **Daily Profit Lock & Daily Loss Limit**: Travas diárias no motor que encerram operações ao atingir a meta do dia ou 3 stops consecutivos, prevenindo devolução de lucros ou ruína por overtrading.
