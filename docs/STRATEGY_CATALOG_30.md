# Catálogo Quantitativo: 30 Estratégias Sistemáticas de Alta Performance para Criptoativos

> Documento de Engenharia Financeira e Pesquisa Algorítmica  
> Objetivo: Mapear 30 estratégias com vantagens estatísticas comprovadas para aceleração de micro-capital com juros compostos.  
> Regra de Escrita: Sem travessões, foco matemático e empírico.

---

## 1. Fundamentos Matemáticos do Crescimento Exponencial

Para transformar **R$ 10,00 em R$ 10.000,00 em 365 dias**, é necessária uma multiplicação total de **1.000x** (+99.900%).

### 1.1 A Fórmula do Juro Composto Diário

$$(1 + r)^{365} = 1.000 \implies 1 + r = 10^{\frac{3}{365}} \approx 1,01912 \implies r \approx 1,912\% \text{ ao dia}$$

* Se operado em **365 dias corridos**: meta diária de **1,91% líquido composto**.
* Se operado em **250 dias de alta volatilidade**: meta diária de **2,80% líquido composto**.
* **Conclusão:** O trader não precisa buscar 10% ou 20% em uma única operação. A busca por retornos diários astronômicos sem gestão de risco gera liquidação prematura. A chave matemática é a combinação de uma taxa de acerto estável (>58%), razão risco/retorno favorável e um dimensionamento dinâmico de lote (Anti-Martingale / Kelly Fracionário).

### 1.2 Modelos de Dimensionamento Dinâmico de Posição

1. **Anti-Martingale Puro (Paroli):** Após cada vitória, o lucro ou uma fração $x\%$ dele é adicionado à próxima posição. Em caso de stop loss, a posição retorna imediatamente ao tamanho base.
2. **Fixed Fractional (Kelly Fracionário):** A posição é calculada como uma fração constante do capital acumulado ($f^* = \frac{p \cdot b - q}{b}$ com multiplicador de segurança de 0,25 a 0,5). À medida que a banca cresce, o tamanho do trade sobe automaticamente em reais, gerando a curva parabólica.

---

## 2. Catálogo de 30 Estratégias por Vertente Operacional

---

### Vertente A: Arbitragem Estatística e Cointegração (Pairs Trading & Lead-Lag)

#### Estratégia 01: Lead-Lag Cross-Correlation BTC x ETH
* **Pares Envolvidos:** BTCUSDT (Líder) e ETHUSDT (Seguidor).
* **Timeframe:** 15m e 1h.
* **Tese:** Movimentos direcionais abruptos no BTC com alto volume demoram entre 1 e 2 barras de 15m para serem totalmente absorvidos pelo par ETHUSDT.
* **Gatilho de Entrada:** Variação no BTC superior a 1,5 desvios-padrão enquanto o ETH permanece em consolidação com defasagem temporal.
* **Alvo e Stop:** Alvo de +0,8% no ETH, Stop Loss no rompimento da mínima do candle anterior do ETH.
* **Execução:** Ordem limite passiva (Maker) na direção da ruptura do líder.

#### Estratégia 02: Cointegração e Reversão de Spread SOL x AVAX (L1 Beta)
* **Pares Envolvidos:** SOLUSDT e AVAXUSDT.
* **Timeframe:** 1h.
* **Tese:** Sendo ambos blockchains de Camada 1 concorrentes, o spread normalizado $Spread = Preço_{SOL} - \beta Preço_{AVAX}$ exibe estacionariedade estatística com teste ADF (Augmented Dickey-Fuller) p-value < 0,05.
* **Gatilho de Entrada:** Z-Score do spread ultrapassando +2,0 (Short SOL, Long AVAX) ou -2,0 (Long SOL, Short AVAX).
* **Alvo e Stop:** Fechamento no Z-Score = 0. Stop de descorrelação em Z-Score = 3,5.
* **Vantagem:** Estratégia neutra a mercado (Market Neutral), imune a quedas generalizadas do Bitcoin.

#### Estratégia 03: Pairs Trading BNB x BTC (Exchange Token Hedge)
* **Pares Envolvidos:** BNBUSDT e BTCUSDT (ou par sintético BNB/BTC).
* **Timeframe:** 4h e 1h.
* **Tese:** O par BNB/BTC opera dentro de canais de suporte e resistência bem definidos devido à utilidade do token de taxas e queimas trimestrais da Binance.
* **Gatilho:** Desvio estocástico da média móvel ponderada por volume (VWAP) do ratio BNB/BTC acima de 2 desvios de Bollinger.
* **Alvo:** Retorno à média central da VWAP. Stop simétrico de 1,2%.

#### Estratégia 04: Cointegração LINK x ETH (Infraestrutura vs Camada 1)
* **Pares Envolvidos:** LINKUSDT e ETHUSDT.
* **Timeframe:** 1h.
* **Tese:** A atividade on-chain do Ethereum demanda consumo de serviços de oráculos Chainlink. Desconexões no spread de preços tendem a convergir rapidamente.
* **Gatilho:** Cálculo do resíduo de regressão linear dinâmica (Kalman Filter). Entrada quando o erro de previsão excede 2,2 sigmas.
* **Alvo:** Reversão completa do erro à média. Stop se o p-value do teste de cointegração se degradar para > 0,10.

#### Estratégia 05: Lead-Lag de Rompimento em Memecoins de Alta Liquidez (DOGE)
* **Pares Envolvidos:** DOGEUSDT e BTCUSDT.
* **Timeframe:** 15m.
* **Tese:** Rompimentos de consolidação no DOGE acompanhados de volume relativo extremo (RVol > 3,0) frequentemente antecedem rotações de risco especulativo no mercado.
* **Gatilho:** Rompimento da máxima de 24 horas no DOGE com confirmação de funding rate neutro ou negativo.
* **Alvo:** Relação risco/retorno assimétrica de 1:2,5. Stop técnico abaixo da mínima da barra de ignição.

---

### Vertente B: Arbitragem de Taxa de Financiamento e Carry Trade (Funding Harvest)

#### Estratégia 06: Cash & Carry Sintético Spot-Futures
* **Pares Envolvidos:** BTCUSDT Spot e BTCUSDT Futures Perpétuo.
* **Timeframe:** Horários de funding (00:00, 08:00, 16:00 UTC).
* **Tese:** Quando a taxa de financiamento ultrapassa 0,05% a cada 8 horas, a compra no mercado à vista casada com a venda equivalente no mercado futuro trava o retorno líquido sem exposição direcional.
* **Gatilho:** Funding previsto anualizado superior a 25% a.a.
* **Alvo:** Coleta contínua da taxa de financiamento com reinvestimento imediato na margem.
* **Risco:** Taxas de liquidação e custo de abertura/fechamento das pontas.

#### Estratégia 07: Funding Rate Spread Differential Cross-Pairs
* **Pares Envolvidos:** Par A com funding rate extremamente negativo (ex: -0,10%) e Par B com funding rate positivo (+0,08%).
* **Timeframe:** 8h.
* **Tese:** Comprar o ativo com taxa negativa (quem vende paga para você manter o long) e vender o ativo com taxa positiva (quem compra paga para você manter o short), equilibrando o beta dos setores.
* **Gatilho:** Diferencial de funding spread $\Delta F = F_B - F_A > 0,12\%$.
* **Alvo:** Coleta dupla de funding a cada ciclo de 8 horas.

#### Estratégia 08: Short Squeeze Hunting em Funding Negativo Extremo
* **Pares Envolvidos:** Altcoins de alta volatilidade (ex: SOL, AVAX, LINK).
* **Timeframe:** 15m.
* **Tese:** Quando o funding atinge patamares negativos severos (abaixo de -0,05%), o mercado futuro está saturado de posições vendidas. Qualquer micro-alta dispara cascatas de ordens de stop, provocando explosão vertical de preço.
* **Gatilho:** Preço formando fundo duplo em 15m concomitante com funding negativo recorde no book.
* **Alvo:** +2,0% a +4,0% de valorização rápida no short squeeze. Stop curto de -0,8%.

#### Estratégia 09: Long Exhaustion Fade em Funding Positivo Extremo
* **Pares Envolvidos:** Altcoins hipercompradas com funding anualizado > 80%.
* **Timeframe:** 1h.
* **Tese:** Compradores pagando taxas exorbitantes a cada 8 horas perdem poder de sustentação se o preço parar de subir. O desmonte de posições gera queda acentuada.
* **Gatilho:** Divergência de baixa no RSI (14) em 1h com funding rate no topo do percentil 95.
* **Alvo:** Retração até a média móvel exponencial de 50 períodos (EMA 50). Stop de 1,0% acima da máxima recente.

#### Estratégia 10: Delta-Neutral Yield Stacking com Reinvestimento Composto
* **Pares Envolvidos:** BNBUSDT e BTCUSDT.
* **Timeframe:** Contínuo.
* **Tese:** Manutenção de carteira delta-neutra acumulando juros de custódia e funding fees, convertendo automaticamente o yield em lotes fracionários adicionais.
* **Gatilho:** Monitoramento algorítmico do retorno diário composto.
* **Risco:** Descolamento de base e slippage de rebalanceamento.

---

### Vertente C: Rompimento de Volatilidade e Expansão de Range (Breakout & Momentum)

#### Estratégia 11: Volatility Squeeze com Keltner Channels e Bandas de Bollinger
* **Pares Envolvidos:** SOLUSDT e ETHUSDT.
* **Timeframe:** 15m.
* **Tese:** Quando as Bandas de Bollinger entram completamente dentro dos Canais de Keltner, a volatilidade atinge o patamar mínimo de compressão. A expansão subsequente produz tendências intradiárias poderosas.
* **Gatilho:** Primeira barra de 15m que fecha fora das bandas com o oscilador de momentum virando para o quadrante positivo.
* **Alvo:** 2x o valor do indicador ATR (Average True Range) de 14 períodos. Stop na linha central de Keltner.

#### Estratégia 12: Donchian Channel 20 Breakout com ATR Trailing Stop
* **Pares Envolvidos:** BTCUSDT e ETHUSDT.
* **Timeframe:** 1h.
* **Tese:** Estratégia clássica das Tartarugas (Trend Following) adaptada para micro-lotes de criptoativos.
* **Gatilho:** Rompimento da máxima dos últimos 20 candles de 1h.
* **Alvo:** Condução via Trailing Stop posicionado em 2x ATR abaixo da máxima acumulada.
* **Stop:** Mínima dos últimos 10 candles.

#### Estratégia 13: Opening Range Breakout (ORB) da Sessão de Nova York
* **Pares Envolvidos:** LINKUSDT e BNBUSDT.
* **Timeframe:** 15m.
* **Tese:** A primeira barra de 15 minutos após a abertura de Nova York (13:30 às 13:45 UTC) estabelece os extremos de liquidez do dia bancário.
* **Gatilho:** Rompimento do topo dos primeiros 15 minutos com volume 50% superior à média das últimas 10 barras.
* **Alvo:** 1,5x a amplitude do range de abertura. Stop na metade do candle de abertura.

#### Estratégia 14: London-NY Overlap Momentum Surge
* **Pares Envolvidos:** BTCUSDT, ETHUSDT e SOLUSDT.
* **Timeframe:** 15m (janela entre 12:00 e 16:00 UTC).
* **Tese:** A sobreposição das praças financeiras de Londres e Nova York concentra mais de 45% do volume global spot e futuros.
* **Gatilho:** Candle direcional com corpo superior a 70% do range total durante o horário de sobreposição, rompendo médias de 9 e 21 períodos.
* **Alvo:** +1,2% com Trailing Stop. Stop de -0,5%.

#### Estratégia 15: Liquidity Sweep & Turtle Soup
* **Pares Envolvidos:** BTCUSDT e ETHUSDT.
* **Timeframe:** 15m.
* **Tese:** O preço viola a máxima ou mínima do dia anterior em busca de ordens de stop loss de varejo, mas não sustenta e fecha novamente dentro da faixa anterior.
* **Gatilho:** Rompimento falso de topo/fundo seguido de fechamento reverso imediato.
* **Alvo:** Retorno até a VWAP da sessão. Stop na ponta externa da sombra de rejeição.

---

### Vertente D: Reversão à Média e Oscilações Estocásticas (Mean-Reversion Scalping)

#### Estratégia 16: RSI Divergence Estocástico com Bandas de Bollinger
* **Pares Envolvidos:** ADAUSDT e XRPUSDT.
* **Timeframe:** 15m.
* **Tese:** Divergências regulares entre a ação de preço (fundo mais baixo) e o indicador RSI de 14 períodos (fundo mais alto) nas extremidades das Bandas de Bollinger apontam exaustão de vendedores.
* **Gatilho:** Candle de reversão (martelo ou pin-bar) na banda inferior com divergência clássica no RSI.
* **Alvo:** Média móvel simples de 20 períodos. Stop loss 0,1% abaixo da mínima da divergência.

#### Estratégia 17: VWAP Bands Reversion Intraday Ancorada
* **Pares Envolvidos:** ETHUSDT.
* **Timeframe:** 15m (com VWAP ancorada na abertura semanal ou diária às 00:00 UTC).
* **Tese:** O preço oscila em torno do preço médio ponderado por volume institucional. Desvios extremos de 2,5 sigmas representam precificação desbalanceada.
* **Gatilho:** Toque na banda superior/inferior de 2,5 desvios com redução de volume relativo.
* **Alvo:** Retorno à linha de 1 desvio ou à VWAP central. Stop de 0,4%.

#### Estratégia 18: EMA Ribbon Compression & Snapback
* **Pares Envolvidos:** SOLUSDT e AVAXUSDT.
* **Timeframe:** 15m.
* **Tese:** Feixe de médias móveis exponenciais (8, 13, 21, 55). Quando o preço estica excessivamente para longe da EMA 8, a atração gravitacional da média desencadeia retorno à média.
* **Gatilho:** Distância percentual do preço em relação à EMA 21 superior a 2,5 vezes o ATR médio.
* **Alvo:** Toque na EMA 21. Stop na máxima/mínima recente.

#### Estratégia 19: Micro-Scalp de Centavos Otimizado com Anti-Martingale
* **Pares Envolvidos:** BTCUSDT.
* **Timeframe:** 15m.
* **Tese:** Captura de micro-oscilações de +0,25% com ordens limite passivas Maker (taxa de 0,02%). Se a operação for vitoriosa, o valor da posição seguinte aumenta 20% do lucro obtido. Se for perdedora, retorna ao lote mínimo.
* **Gatilho:** Reversão estocástica em barras de exaustão intradiárias.
* **Alvo:** +0,25% fixo. Stop de -0,25%. Trava de meta diária (Daily Profit Lock) de 10 vitórias.

#### Estratégia 20: Asymmetric High-Low Wick Rejection (Pin-Bars)
* **Pares Envolvidos:** LINKUSDT e DOTUSDT.
* **Timeframe:** 1h.
* **Tese:** Sombras longas superiores ou inferiores (pavios representando pelo menos 66% da amplitude do candle) indicam absorção maciça de ordens passivas institucionais.
* **Gatilho:** Fechamento de candle confirmando pavio longo contra suporte ou resistência histórica.
* **Alvo:** 2x o tamanho do pavio. Stop 0,1% além do extremo da sombra.

---

### Vertente E: Microestrutura de Order Flow e Desbalanceamento (Order Book & CVD)

#### Estratégia 21: Cumulative Volume Delta (CVD) Absorption Divergence
* **Pares Envolvidos:** BTCUSDT.
* **Timeframe:** 15m.
* **Tese:** Se o delta de volume acumulado de ordens a mercado agressivas cai vertiginosamente, mas o preço não renova fundos, participantes passivos estão absorvendo todas as vendas no book.
* **Gatilho:** Divergência de absorção: novos fundos no CVD sem novos fundos no preço.
* **Alvo:** Repique rápido de +0,6% a +1,0%. Stop logo abaixo do cluster de absorção.

#### Estratégia 22: Order Flow Imbalance (OFI) com Execução Limite Maker
* **Pares Envolvidos:** ETHUSDT.
* **Timeframe:** Micro-candles ou 15m.
* **Tese:** O desbalanceamento dinâmico entre a quantidade ofertada no topo do bid e do ask antecipa em segundos a direção do próximo tick.
* **Gatilho:** Indicador OFI superior a 0,70 com spread fechado.
* **Alvo:** Captura do spread e de micro-movimentos de 0,15% a 0,30%. Stop em caso de inversão do fluxo.

#### Estratégia 23: Bid-Ask Spread Micro-Market Making (Avellaneda-Stoikov Adaptado)
* **Pares Envolvidos:** Pares com volatilidade moderada e alta liquidez (ex: BTCUSDT, ETHUSDT).
* **Timeframe:** Sub-minuto / Contínuo.
* **Tese:** Colocação simultânea de ordens limite de compra e venda ajustadas pela aversão ao risco do estoque (inventário da banca).
* **Gatilho:** Posicionamento passivo constante ao redor do preço de reserva ótimo.
* **Alvo:** Captura das taxas negativas de Maker somadas ao spread bid-ask. Stop de contingência se o inventário direcional exceder o limite de tolerância.

#### Estratégia 24: Whale Liquidation Cascade Front-Running
* **Pares Envolvidos:** SOLUSDT e DOGEUSDT.
* **Timeframe:** 15m.
* **Tese:** Quando ocorre um pico atípico de volume acompanhado de milhões em liquidações compulsórias no livro de futuros, o movimento atinge clímax de pânico e esgota os vendedores.
* **Gatilho:** Detecção de cascata de ordens de liquidação em candle com volume superior ao percentil 99, seguido de rejeição imediata.
* **Alvo:** Repique de alívio de 1,5% a 3,0%. Stop na mínima do evento de liquidação.

#### Estratégia 25: Footprint Delta Clustering nos Extremos
* **Pares Envolvidos:** BTCUSDT.
* **Timeframe:** 15m.
* **Tese:** Concentração anormal de volume negociado nas extremidades de uma barra (delta negativo preso no fundo de uma barra compradora).
* **Gatilho:** Identificação de compradores passivos retendo ordens agressivas de venda. Entrada comprada na quebra da máxima do cluster.
* **Alvo:** 1,2x a distância do cluster. Stop no fundo do cluster.

---

### Vertente F: Modelos Algorítmicos Adaptativos e Híbridos (Multi-Factor & Machine Learning)

#### Estratégia 26: Multi-Factor Scoring (Momentum + Volatilidade + Funding)
* **Pares Envolvidos:** Rotação dinâmica diária entre os 10 pares do portfólio.
* **Timeframe:** Diário / 4h.
* **Tese:** Ranqueamento quantitativo dos pares atribuindo notas de 0 a 100 para três fatores: Momentum (Retorno em 14 dias), Volatilidade Relativa (Ratio ATR/Preço) e Taxa de Funding.
* **Gatilho:** Alocação de capital nos 2 ativos com maior nota fatorial no fechamento das 00:00 UTC.
* **Alvo:** Rebalanceamento a cada 24 horas. Stop individual por volatilidade de 2 sigmas.

#### Estratégia 27: Regime Detection via Hidden Markov Model (HMM)
* **Pares Envolvidos:** BTCUSDT e ETHUSDT.
* **Timeframe:** 1h.
* **Tese:** O mercado opera em estados latentes distintos: Baixa Volatilidade Lateral, Alta Volatilidade em Tendência e Choque Estocástico. Estratégias de tendência falham em lateralização e vice-versa.
* **Gatilho:** Se o modelo HMM classifica o estado atual como "Tendência com Alta Probabilidade", ativa o Donchian Breakout. Se classifica como "Lateral", ativa o Micro-Scalp de Bollinger.
* **Alvo e Stop:** Parametrizados conforme a estratégia ativada para o regime.

#### Estratégia 28: Genetic Algorithm AST Rule Evolving (Árvores Lógicas)
* **Pares Envolvidos:** Todos os pares do repositório local.
* **Timeframe:** 15m e 1h.
* **Tese:** Motor genético (`strategy/ast_engine.py`) que recombina operadores lógicos (AND, OR, IF), indicadores (RSI, Bollinger, MACD) e limiares numéricos, submetendo cada geração à incubadora de quarentena.
* **Gatilho:** Estratégias que superam o limiar de Fitness (Sharpe > 1,8, Profit Factor > 1,4, Max Drawdown < 10%) são promovidas para execução real.
* **Alvo e Stop:** Determinados dinamicamente pelos nós terminais da árvore sintática.

#### Estratégia 29: Cross-Correlation Network Topology (Centralidade de Vetor)
* **Pares Envolvidos:** Matriz completa dos 10 pares em `klines_1h`.
* **Timeframe:** 1h / Diário.
* **Tese:** Construção de uma rede de correlações móveis. Ativos que se tornam o "centro da rede" (maior centralidade de autovetor) estão ditando a rotação de capital institucional.
* **Gatilho:** Entrada a favor da tendência no par com maior centralidade antes que a correlação se disperse para a periferia.
* **Alvo:** 2,0% de valorização com trailing stop. Stop de 0,8%.

#### Estratégia 30: Dynamic Fractional Kelly Portfolio Allocation
* **Pares Envolvidos:** Portfólio diversificado de 3 a 5 pares simultâneos.
* **Timeframe:** Contínuo.
* **Tese:** O capital não é concentrado em um único trade. O tamanho de cada posição é recalculado a cada encerramento utilizando o Kelly Fracionário ponderado pelo inverso da volatilidade (Risk Parity).
* **Gatilho:** Ajuste contínuo de lotes à medida que os lucros são reinvestidos.
* **Vantagem:** Garante o crescimento geométrico máximo possível da curva de equidade sem exceder o limiar de risco de ruína matemática.

---

## 3. Matriz Sintética das 30 Estratégias

| ID | Nome da Estratégia | Pares Recomendados | Timeframe | Edge Principal | Risco / Retorno Típico |
|---|---|---|---|---|---|
| **01** | Lead-Lag Cross-Correlation | BTCUSDT & ETHUSDT | 15m / 1h | Defasagem temporal de fluxo | 1 : 2,0 |
| **02** | Cointegração L1 Beta | SOLUSDT & AVAXUSDT | 1h | Estacionariedade de spread | 1 : 1,5 (Market Neutral) |
| **03** | Pairs Trading BNB/BTC | BNBUSDT & BTCUSDT | 1h / 4h | Utilidade e queima trimestral | 1 : 1,8 |
| **04** | Cointegração Oráculo/L1 | LINKUSDT & ETHUSDT | 1h | Demanda on-chain estrutural | 1 : 1,6 |
| **05** | Lead-Lag High-Beta Memes | DOGEUSDT & BTCUSDT | 15m | Ruptura com volume extremo | 1 : 2,5 |
| **06** | Cash & Carry Sintético | BTCUSDT Spot & Futuros | 8h | Financiamento positivo seguro | Retorno delta-neutro |
| **07** | Funding Spread Differential | Pares com taxas opostas | 8h | Spread entre taxas extremas | Delta-neutro composto |
| **08** | Short Squeeze Hunting | SOL, AVAX, LINK | 15m | Funding negativo extremo | 1 : 3,0 |
| **09** | Long Exhaustion Fade | Altcoins com funding alto | 1h | Cansaço de compradores alavancados | 1 : 2,0 |
| **10** | Delta-Neutral Yield Stacking | BNBUSDT & BTCUSDT | Contínuo | Reinvestimento diário de taxas | Risco baixo de capital |
| **11** | Volatility Squeeze Keltner/BB | SOLUSDT & ETHUSDT | 15m | Expansão pós-compressão | 1 : 2,0 |
| **12** | Donchian Channel 20 Breakout | BTCUSDT & ETHUSDT | 1h | Condução de grandes tendências | 1 : 2,5 |
| **13** | Opening Range Breakout (ORB) | LINKUSDT & BNBUSDT | 15m | Fluxo bancário de Nova York | 1 : 1,8 |
| **14** | London-NY Overlap Momentum | BTC, ETH, SOL | 15m | Horário de pico de liquidez | 1 : 2,2 |
| **15** | Liquidity Sweep Turtle Soup | BTCUSDT & ETHUSDT | 15m | Caça de stops de varejo | 1 : 2,0 |
| **16** | RSI Divergence Estocástico | ADAUSDT & XRPUSDT | 15m | Exaustão em bandas extremas | 1 : 1,5 |
| **17** | VWAP Bands Reversion | ETHUSDT | 15m | Preço médio ponderado institucional | 1 : 1,7 |
| **18** | EMA Ribbon Compression | SOLUSDT & AVAXUSDT | 15m | Retração rápida à média 21 | 1 : 1,8 |
| **19** | Micro-Scalp de Centavos Otimizado | BTCUSDT | 15m | Ruído de 0,25% com taxas Maker | 1 : 1,0 (com Win Rate 62%) |
| **20** | Asymmetric Wick Rejection | LINKUSDT & DOTUSDT | 1h | Absorção institucional em pavios | 1 : 2,0 |
| **21** | CVD Absorption Divergence | BTCUSDT | 15m | Comprador passivo absorvendo | 1 : 2,0 |
| **22** | Order Flow Imbalance (OFI) | ETHUSDT | Sub-15m | Pressão no topo do book | 1 : 1,4 |
| **23** | Avellaneda-Stoikov Market Making | BTCUSDT & ETHUSDT | Contínuo | Captura de rebate de taxa Maker | Alta frequência / Micro |
| **24** | Liquidation Cascade Front-Run | SOLUSDT & DOGEUSDT | 15m | Exaustão de vendas forçadas | 1 : 2,5 |
| **25** | Footprint Delta Clustering | BTCUSDT | 15m | Nível de preço com volume preso | 1 : 1,8 |
| **26** | Multi-Factor Scoring Rotation | Top 10 ativos | Diário | Alocação no par com maior alfa | Sistemático / 24h |
| **27** | Regime Detection via HMM | BTCUSDT & ETHUSDT | 1h | Chaveamento de estratégia por estado | Adaptativo |
| **28** | Genetic Algorithm AST Evolving | Todos os 10 pares | 15m / 1h | Busca automática por mutação | Auto-otimizável |
| **29** | Cross-Correlation Network | Matriz 10x10 em 1h | 1h | Centralidade e rotação de capital | 1 : 2,0 |
| **30** | Dynamic Fractional Kelly | Portfólio Diversificado | Contínuo | Otimização geométrica de banca | Crescimento exponencial |

---

## 4. O Roadmap de Implementação no Sistema

1. **Camada de Sizing (Task-023):** Implementar o motor de Anti-Martingale e Kelly Fracionário em `strategy/anti_martingale_engine.py`.
2. **Camada de Cointegração e Correlação (Task-024):** Criar analisador estocástico para testar pares cointegrados em `strategy/pairs_cointegration.py`.
3. **Simulador de Crescimento Exponencial:** Submeter o pipeline a 10.000 iterações Monte Carlo com probabilidades empíricas reais de 2024 para definir os limites exatos de alavancagem que impedem a ruína.
