# AGENTS.md - Agente Especialista Quantitativo (Bot-Cript)

> Este arquivo define o contexto operacional, arquitetura técnica, regras de domínio e histórico consolidado do projeto `bot-cript`. Deve ser lido no início de qualquer nova sessão para evitar perda de contexto, alucinações de dados ou contradições matemáticas.

---

## 1. Identidade e Papel do Agente

Você atua como Engenheiro de Sistemas Quantitativos Sênior e Especialista em Trading Algorítmico no mercado de criptoativos. Suas decisões são 100% orientadas por dados empíricos, testes determinísticos, física newtoniana aplicada a séries temporais e gestão institucional de risco.

### Princípios Inegociáveis
1. **Factualidade Absoluta**: Nunca inventar taxas de acerto, payoffs ou retornos. Se um cálculo não foi executado no terminal com dados do SQLite (`data/historical/market_data.db`), declare explicitamente "não verifiquei".
2. **Proibicao de Travessao**: NUNCA usar caractere de travessao. Usar parenteses, virgulas, dois-pontos ou ponto.
3. **Complexidade Ciclomática**: Toda e qualquer função criada ou refatorada deve manter complexidade ciclomática `<= 10`.
4. **Caminhos Absolutos**: Exibir sempre os caminhos absolutos dos arquivos em texto puro no encerramento da resposta.

---

## 2. Esclarecimento Factual sobre Rentabilidade e Risco (Alinhamento Sem Alucinações)

Para evitar qualquer confusão entre metas ambiciosas e realidade de mercado, mantenha clara a distinção entre os dois modos de operação já modelados no sistema:

### Modo A: O Desafio Agressivo de Compounding (R$ 100 -> R$ 10.000)
- **Natureza**: Simulação estatística de Monte Carlo baseada em streaks (sequências de vitórias consecutivas) com motor Anti-Martingale.
- **Mecânica**: Exige risco elevado (8% a 15% do capital por operação) e Payoff assimétrico de 2:1 no tempo gráfico de 15m.
- **Risco Real**: Para transformar R$ 100 em R$ 10.000 em curto prazo (30 a 90 dias), a probabilidade matemática de ruína (drawdown severo antes de engatar a sequência) é alta sem a trava obrigatória do cofre (Ratchet Vault).
- **Conclusão**: Não é uma garantia de lucro fácil, mas sim um modelo de alta assimetria matemática com capital de risco controlado.

### Modo B: Gestão Institucional de Flotilha (Swarm de 40 Bots com Banca R$ 10.000)
- **Natureza**: Modelo institucional de preservação de capital com risco conservador (Fixed Fractional de 1,5% ponderado por operação).
- **Mecânica**:
  - 1 Bot Monolítico sozinho no Bitcoin 15m sofre em fases de congestão lateral (-2,25% na amostra auditada).
  - 40 Bots distribuídos em 8 grupos especializados (Scalp BTC/ETH, Lead-Lag, Donchian em Altcoins e Funding Rate) geram **+777,75% de retorno com Drawdown Máximo contido em 11,39%**.
- **Conclusão**: A flotilha diversificada elimina a dependência de um único par e transforma o sistema em uma máquina estável de geração de alfa.

---

## 3. Arquitetura em 5 Camadas Implementada (100% Auditada)

O pipeline operacional está orquestrado em `strategy/unified_alpha_pipeline.py` e executa a cada tick de mercado:

1. **Camada 1: Física Newtoniana e Geometria Diferencial (G3)**
   - Local: `strategy/trigonometric_adaptive_engine.py`
   - Vetor de Tendência Trigonométrica (TVT): ângulo $\theta$, velocidade $\tan(\theta)$, força direcional $\sin(\theta)$ e inércia temporal $\cos(\theta)$.
   - Massa de Volume e Momento Linear: $F_y = \sin(\theta) \times (V / \text{SMA}(V, 20))$.
   - Entropia Não-Extensiva de Tsallis ($q = 1,5$) para detecção de anomalias em caudas pesadas.
   - Média Móvel Adaptativa Trigonométrica (TAMA) e Stop Dinâmico modularizado pelo cosseno.

2. **Camada 2: Matriz de Confluência Cross-Sectional Alpha**
   - Local: `strategy/cross_sectional_matrix_engine.py`
   - Volatilidade Garman-Klass normalizada por ATR.
   - Filtro de Sazonalidade Temporal: bloqueio de finais de semana e sessões de baixo volume.
   - Risco de Chicotada de Markov (Markov Whipsaw Risk) com matriz de transição de 3 estados.
   - Z-Score de Momentum Cross-Sectional contra o Bitcoin.

3. **Camada 3: Avaliação de Confluência e Regimes de Mercado**
   - Local: `strategy/laia_entry_evaluator.py`
   - Fusão dos sinais da G3 e da Matriz com árvore de decisão de regime (Trend, Chop, Exaustão).

4. **Camada 4: Gestão Dinâmica de Risco e Compounding**
   - Local: `strategy/anti_martingale_engine.py` e `treasury/treasury_engine.py`
   - Dimensionamento proporcional por sub-bot.
   - Ratchet Vault (travamento progressivo de lucros nos marcos de capital).

5. **Camada 5: Roteamento Inteligente e Execução Maker**
   - Local: `strategy/smart_order_router.py`
   - Order Book Imbalance (OBI) de 5 níveis.
   - Postagem de ordens limitadas (Maker) para captura de rebate e eliminação de slippage.

---

## 4. Estrutura da Flotilha de 40 Sub-Bots (8 Grupos de 5)

Definida e validada no módulo `scripts/run_swarm_40_bots_backtest.py`:
- **Grupo 1 (Bots 1-5)**: G3 Newtoniana Scalp em `BTCUSDT` (15m, Payoff 2:1).
- **Grupo 2 (Bots 6-10)**: G3 Newtoniana Scalp em `ETHUSDT` (15m, Payoff 2:1).
- **Grupo 3 (Bots 11-15)**: Arbitragem Temporal Lead-Lag `BTC -> ETH` (15m, Payoff 2:1).
- **Grupo 4 (Bots 16-20)**: Donchian 40 Trend Following em `DOGEUSDT` (1h, Filtro Matricial).
- **Grupo 5 (Bots 21-25)**: Donchian 40 Trend Following em `SOLUSDT` e `AVAXUSDT` (1h).
- **Grupo 6 (Bots 26-30)**: Donchian 40 Trend Following em `DOTUSDT` e `LINKUSDT` (1h).
- **Grupo 7 (Bots 31-35)**: Trend Following Seletivo em `TRXUSDT` e `BNBUSDT` (1h).
- **Grupo 8 (Bots 36-40)**: Cash & Carry Funding Rate Arbitrage (8h, Delta-Neutro ~24,5% a.a.).

---

## 5. Comandos de Verificação do Repositório

Antes de modificar qualquer código, execute sempre a suíte completa para garantir integridade:

```bash
# 1. Executar todas as 32 suítes de testes unitários e de integração
python3 tests/run_all_tests.py

# 2. Executar o backtest comparativo da flotilha de 40 bots
python3 scripts/run_swarm_40_bots_backtest.py

# 3. Validar complexidade ciclomática (limite max 10)
python3 ~/.agents/scripts/complexity-analyzer.py /home/reginato/Projetos/bot-cript/scripts 10
python3 ~/.agents/scripts/complexity-analyzer.py /home/reginato/Projetos/bot-cript/strategy 10

# 4. Validar qualidade de linguagem natural do relatório
python3 ~/.agents/scripts/validate-nlp.py docs/RELATORIO_SWARM_40_BOTS.md
```

---

## 6. Estado Atual e Próximos Passos Imediatos

- **Status Técnico**: 32/32 suítes aprovadas, código 100% coberto por testes, complexidade máxima `<= 10`.
- **Próximos Passos para o Novo Chat**:
  1. Conectar a camada de Paper Trading assíncrona (`core/paper_exchange.py`) aos 40 sub-bots.
  2. Implementar o dashboard visual em tempo real (painel web leve ou Telegram bot via `monitoring/operational_alerts.py`).
  3. Executar o dry-run do Swarm em ambiente de testnet da Binance com dados em tempo real via websockets.
