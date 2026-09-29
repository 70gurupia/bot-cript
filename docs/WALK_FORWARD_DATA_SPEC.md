# Especificação de Dados Históricos e Metodologia Walk-Forward (2020 a 2024)

Este documento estabelece o protocolo de coleta, segmentação e avaliação temporal progressiva para os dez principais criptoativos do mercado ao longo de cinco anos de histórico completo (2020 a 2024).

---

## 1. Universo de Criptoativos Selecionados (Top 10)

Os dez pares selecionados representam mais de 75% da liquidez de todo o mercado de criptoativos e oferecem profundidade de livro de ofertas suficiente para minimizar custos de slippage:

| Ativo | Par | Início dos Dados na Binance | Papel na Carteira |
|---|---|---|---|
| **Bitcoin** | `BTC/USDT` | Anterior a 2020 | Âncora de liquidez e indicador de tendência macro do mercado |
| **Ethereum** | `ETH/USDT` | Anterior a 2020 | Liquidez institucional e alta correlação com finanças descentralizadas |
| **BNB** | `BNB/USDT` | Anterior a 2020 | Baixa taxa de corretagem nativa e dinâmica própria de ecossistema |
| **Solana** | `SOL/USDT` | Agosto de 2020 | Alta volatilidade e forte momentum direcional |
| **XRP** | `XRP/USDT` | Anterior a 2020 | Perfil de movimentos abruptos impulsionados por notícias e liquidez |
| **Cardano** | `ADA/USDT` | Anterior a 2020 | Amplo histórico de ciclos completos de acumulação e distribuição |
| **Dogecoin** | `DOGE/USDT` | Anterior a 2020 | Representante de alta liquidez do segmento de varejo e momentum |
| **Avalanche** | `AVAX/USDT` | Setembro de 2020 | Camada 1 com volatilidade assimétrica em relação ao Bitcoin |
| **Chainlink** | `LINK/USDT` | Anterior a 2020 | Ativo de infraestrutura com fortes tendências de médio prazo |
| **Polkadot** | `DOT/USDT` | Agosto de 2020 | Ativo multi-cadeia com ciclos de consolidação bem definidos |

---

## 2. Metodologia Walk-Forward Sequencial por Regimes

A evolução dos agentes ocorre em quatro estágios temporais encadeados, simulando a passagem real do tempo para prevenir viés de sobrevivência (look-ahead bias) e sobreajuste (overfitting):

```text
2020         2021         2022                 2023                 2024
 |------------|------------|--------------------|--------------------|
    FASE A: TREINO         FASE B: TESTE        FASE C: REAJUSTE     FASE D: VALIDAÇÃO
    BULL MARKET EXP.       BEAR MARKET ESTRESSE RECUPERAÇÃO          OUT-OF-SAMPLE
    - Criação de regras    - Eliminação de      - Recalibração de    - Teste cego final
      iniciais em alta       estratégias que      parâmetros para      de aprovação
    - Recombinação AST       quebram em queda     mercados mistos      para a incubadora
```

### 2.1 Fase A: Treino e Geração da População Base (2020 a 2021)
* **Ambiente de Mercado**: O ciclo de alta exponencial impulsionado pelo halving de 2020 e expansão de liquidez global.
* **Objetivo do Algoritmo**: O motor genético cria a primeira geração de indivíduos (árvores lógicas em AST), identificando padrões lucrativos de rompimento de volatilidade e acompanhamento de tendência.

### 2.2 Fase B: Teste de Fogo e Estresse Defensivo (2022)
* **Ambiente de Mercado**: O bear market severo de 2022 (queda de mais de 75% no BTC e colapso de plataformas como LUNA e FTX).
* **Objetivo do Algoritmo**: As estratégias criadas na Fase A são testadas às cegas neste período sem retreinamento. Estratégias frágeis que operam apenas na compra sem stops rígidos são eliminadas pelo avaliador de aptidão (Fitness zerado por drawdown > 8%). Apenas os agentes que conseguem preservar capital sobrevivem.

### 2.3 Fase C: Recalibração e Recuperação (2023)
* **Ambiente de Mercado**: Recuperação gradual e consolidação prolongada em faixas estreitas de preço.
* **Objetivo do Algoritmo**: O motor genético realiza crossover entre os sobreviventes de 2022, refinando regras de retorno à média e adaptando trailing stops para períodos de menor amplitude de velas.

### 2.4 Fase D: Validação Cega Fora da Amostra (2024)
* **Ambiente de Mercado**: O ano mais recente completo, com aprovação dos ETFs de Bitcoin e novo ciclo de halving.
* **Objetivo do Algoritmo**: Teste definitivo de aprovação. Os agentes que mantiverem Sharpe Ratio superior a 1.25 e drawdown inferior a 4.5% neste período de validação são condecorados como "Agentes Fundadores" e depositados na incubadora para operar em tempo real com dados recentes.

---

## 3. Métricas de Oportunidade e Segmentação de Volume

Após o download, os dados são processados por um script de análise quantitativa que avalia:

1. **Volume Médio Diário em Dólares (ADV - Average Daily Volume)**: Garante que o ativo possui profundidade para entrada e saída rápida sem mover o preço.
2. **Volatilidade Anualizada**: Mede a dispersão dos retornos percentuais para quantificar o potencial de ganhos.
3. **Amplitude Relativa do True Range (ATR %)**: Razão entre a amplitude média dos candles de 1h e o preço do ativo, indicando a facilidade de extrair operações de day trade.
4. **Índice de Eficiência de Tendência (Kaufman Efficiency Ratio)**: Razão entre o deslocamento líquido do preço e a soma total das variações, identificando se o ativo se move em tendências limpas ou em ruído desordenado.
