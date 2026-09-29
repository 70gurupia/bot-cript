# Estratégias e Otimizações para Altcoins: Da Teoria aos Resultados Factuais

## 1. Por que Altcoins Falham no Micro-Scalp mas Brilham em Tendências Longas

A simulação de 697.191 candles revelou uma dinâmica estrutural do mercado de criptoativos:
- **BTC, ETH e BNB (Trio Alfa)**: Apresentam alta inércia física, livros de ordens densos e ruído reduzido. Nestes ativos, o modelo de micro-scalp (G3 Newtoniana com stop dinâmico por cosseno e horizonte de 12 horas) é altamente lucrativo (+135.10% no ETH e +118.04% no BTC).
- **Altcoins (DOGE, XRP, AVAX, SOL, ADA, TRX, LINK)**: Apresentam caudas pesadas (fat tails) e alta volatilidade intradiária. Velas horárias formam pavios longos de 1.5 a 2.5 ATR que acionam trailing stops curtos, gerando taxas consecutivas de micro-prejuízos antes que o movimento direcional se consolide.

No entanto, quando ajustamos a estratégia para a natureza intrínseca das altcoins, os resultados se invertem dramaticamente.

---

## 2. Quais Estratégias Deram Win nas Altcoins? (Evidência Empírica do Banco SQLite)

### 2.1 Trend Following de Janela Ampliada (Donchian 40 Períodos em 1h)
Ao estender o canal de rompimento de 20 para 40 períodos (cerca de 40 horas ou ~2 dias de negociação contínua), o robô elimina o ruído intradiário e corta os falsos rompimentos pela metade.

Resultados reais consolidados na base de 8 anos:

| Ativo | Donchian 20 Retorno (Trades) | Donchian 40 Retorno (Trades) | Variação com Janela de 40h |
| :--- | :--- | :--- | :--- |
| **TRXUSDT** | +138.81% (374 trades) | **+1.951,23%** (203 trades) | Redução de 45% nos trades e explosão de retorno |
| **DOGEUSDT** | +570.71% (903 trades) | **+848,54%** (475 trades) | Quase metade dos trades e ganho de +277% |
| **AVAXUSDT** | +269.64% (807 trades) | **+704,03%** (432 trades) | Retorno quase triplicado |
| **BNBUSDT** | +314.97% (1206 trades) | **+699,83%** (629 trades) | De +314% para +699% |
| **ADAUSDT** | +134.92% (1157 trades) | **+487,53%** (601 trades) | Mais de 3.6x o resultado anterior |
| **XRPUSDT** | +341.24% (1053 trades) | **+452,78%** (575 trades) | Redução substancial de atrito e drawdown |
| **SOLUSDT** | +111.93% (847 trades) | **+252,23%** (462 trades) | Mais que o dobro do retorno líquido |
| **LINKUSDT** | -48.64% (1091 trades) | **+224,23%** (578 trades) | Reversão completa de prejuízo para forte lucro |
| **DOTUSDT** | -84.29% (848 trades) | **+39,15%** (490 trades) | Reversão para resultado positivo |

### 2.2 Reversão à Média em 15m (RSI Extremo + Bandas de Bollinger)
Altcoins passam entre 65% e 75% do tempo presas em congestionamentos e canais laterais.
Quando o preço toca as bandas externas (1.8 desvios padrão) com RSI em níveis de exaustão (< 32 ou > 68):
- **XRPUSDT**: Retorno líquido de **+35,09%** (779 trades, 56.1% de win rate).
- **ADAUSDT**: Retorno líquido de **+14,88%** (864 trades, 54.2% de win rate).

### 2.3 Arbitragem Temporal Lead-Lag (BTC -> Altcoins Líderes em 15m)
Quando o Bitcoin rompe forte (> 0.8% em uma vela) e as altcoins de grande capitalização demoram 1 a 2 velas para absorver o fluxo:
- **Lead-Lag BTC -> ETH**: **+11,91%** em 2024 com **74,4% de win rate** (Profit Factor 4.32 e Drawdown de apenas 1.6%).
- Aplicável também a pares correlacionados como BTC -> SOL e SOL -> AVAX.

---

## 3. Quatro Pilares para Melhorar as Altcoins no Robô

### Pilar 1: Filtro de Força Relativa contra o Bitcoin (Beta / RS Ratio)
- Altcoins raramente sobem contra a maré do Bitcoin.
- **Implementação**: Antes de abrir compra em qualquer altcoin, calcular a razão $P_{ALT} / P_{BTC}$.
- Se a razão estiver abaixo da média móvel de 20 períodos, a compra é bloqueada, evitando compras falsas durante "sangrias" causadas pela alta da dominância do Bitcoin.

### Pilar 2: Calibração Dinâmica de Stops ao Nível de Ruído do Ativo
- Em BTC e ETH, o desvio padrão horário é de 0.8% a 1.5%. Um stop de 1.2 * ATR é seguro.
- Em DOGE, SOL, AVAX e XRP, o desvio padrão chega a 3% a 5%. Um stop de 1.2 * ATR é frequentemente atingido por volatilidade natural.
- **Implementação**: Modulador de stop proporcional à volatilidade relativa:
  $$\text{StopDist}_{alt} = \text{ATR} \times \left(1.5 + \frac{\text{ATR}}{\text{Preço}} \times 20\right)$$
  Isso expande o stop para 2.5 a 3.0 ATR em altcoins voláteis e amplia a projeção de alvo para 5.0 a 6.0 ATR, permitindo surfar os ralis completos.

### Pilar 3: Seletor Dual de Regime de Mercado (Tendência vs Reversão)
- **Regime de Tendência (ADX > 25 ou Entropia de Tsallis < 0.65)**:
  Ativa o **Donchian 40 Trend Following**, permitindo correr a posição sem stop prematuro até o rompimento do canal oposto.
- **Regime Lateral / Congestão (ADX < 20 ou Entropia de Tsallis > 0.80)**:
  Ativa o **RSI + Bollinger Reversion em 15m**, realizando lucros rápidos no retorno à média ponderada.

### Pilar 4: Execução Maker Post-Only via SmartOrderRouter
- Com centenas de trades em altcoins, taxas Taker de 0.05% consomem até 40% dos ganhos brutos.
- **Implementação**: O roteador `strategy/smart_order_router.py` posiciona ordens limites no topo do livro (Best Bid / Best Ask) garantindo taxa Maker (0.00% a 0.02%), transformando atrito em margem de lucro líquido.
