# Motor Evolutivo e Incubadora em Paper Trading

Este documento detalha o funcionamento do algoritmo genético baseado em Árvores de Sintaxe Abstrata (AST), o processo de crossover entre estratégias aprovadas e as regras rigorosas de quarentena da incubadora.

---

## 1. Fundamentos da Programação Genética Estruturada

O objetivo do motor evolutivo é permitir que os agentes adaptem suas regras a novos cenários de volatilidade e liquidez sem incorrer no erro de memorizar o passado (overfitting).

### 1.1 Representação dos Indivíduos (Cromossomos)
Cada agente possui seu comportamento codificado como um grafo acíclico dirigido (DAG) de blocos lógicos estruturados:

```text
                  [Nó Raiz: Avaliador de Sinal]
                                |
        +-----------------------+-----------------------+
        |                                               |
  [Subárvore de Entrada]                       [Subárvore de Saída]
        |                                               |
  +-----+-----+                                   +-----+-----+
  |           |                                   |           |
[Condição 1] [Condição 2]                       [Stop ATR]  [Trailing TP]
(RSI < 30)   (Preco > EMA_200)                  (Mult: 1.8) (Ativacao: 2.5%)
```

Os nós são classificados em quatro tipos primitivos:
1. **Nós de Dados (Inputs)**: Preço de fechamento, volume, spread do book, taxa de funding.
2. **Nós de Indicadores**: Média Móvel Exponencial (EMA), Índice de Força Relativa (RSI), Bandas de Bollinger, True Range Médio (ATR).
3. **Nós Operadores**: Operações de comparação (`>`, `<`, `cruzamento_acima`, `cruzamento_abaixo`) e lógicas booleanas (`E`, `OU`).
4. **Nós de Ação**: Determinam tipo de ordem (Limite com desconto, Mercado), lado (Comprar, Vender) e regras de saída (Stop Loss percentual, Stop ATR, Take Profit parcial).

---

## 2. Processo de Recombinação Genética (Crossover)

A replicação não cria clones idênticos. Ela realiza o cruzamento genético entre os dois indivíduos mais adaptados da população:

```text
Genitor A (Especialista em Entradas)       Genitor B (Especialista em Risco)
  - Entrada: Rompimento de Volatilidade       - Entrada: Retorno à Média
  - Saída: Stop Fixo 2%                      - Saída: Trailing Stop Dinâmico ATR
                 \                                /
                  \                              /
                   v                            v
               Filho Recombinado (Novo Agente Clone)
                 - Entrada: Rompimento de Volatilidade (Herdado do Genitor A)
                 - Saída: Trailing Stop Dinâmico ATR (Herdado do Genitor B)
                 - Parâmetros: Mutação Gaussiana de 5% a 10% nos períodos
```

### 2.1 Seleção de Pais por Torneio
* Um conjunto restrito dos 20% melhores agentes ativos (com Sharpe Ratio mais alto e histórico limpo de violações de risco) entra na piscina de procriação.
* Dois agentes são sorteados e submetidos a uma rodada de cruzamento de ramos estruturais compatíveis.

### 2.2 Mutação Paramétrica
Para evitar a perda de diversidade genética, o novo indivíduo sofre mutações numéricas leves:
* Os períodos dos indicadores (ex: janela de 14 para 16 no RSI, ou multiplicador de 2.0 para 2.15 no ATR) são perturbados através de uma distribuição normal em torno do valor herdado.
* Os valores resultantes são automaticamente truncados para respeitar as faixas de segurança estabelecidas nos limites imutáveis do sistema.

---

## 3. Função de Aptidão (Fitness Function)

A aptidão de um agente não é avaliada por lucro bruto nominal. Ela combina quatro dimensões estatísticas ponderadas:

$$Fitness = (0.35 \times Sharpe_{norm}) + (0.25 \times Sortino_{norm}) + (0.20 \times DrawdownScore) + (0.20 \times ProfitFactor_{norm})$$

Onde:
* **Sharpe Normalizado**: Mede a consistência do retorno acima da taxa livre de risco em relação à volatilidade total.
* **Sortino Normalizado**: Avalia o retorno penalizando exclusivamente a volatilidade prejudicial (quedas).
* **Drawdown Score**: Penaliza exponencialmente agentes que sofreram quedas acentuadas de capital acumulado. Agentes com rebaixamento superior a 8% recebem pontuação zero de aptidão.
* **Profit Factor**: Razão entre o lucro bruto acumulado e o prejuízo bruto acumulado.

---

## 4. Protocolo da Incubadora (Paper Trading em Tempo Real)

A incubadora é a salvaguarda operacional que separa a teoria da execução financeira real.

```text
[Novo Agente Gerado]
         |
         v
+---------------------------------------------------------------------------------+
|                         FASE DE INCUBAÇÃO (QUARENTENA)                          |
| - Conexão: Dados de mercado em tempo real via WebSocket                         |
| - Execução: Virtual (saldo fictício alocado pela incubadora)                    |
| - Simulação Realista: Aplicação obrigatória de taxas de corretagem (0.04% taker)|
|   e penalidade de slippage sintético (0.05% por ordem a mercado)                |
+---------------------------------------------------------------------------------+
                                         |
                                         v
                      (Auditoria Contínua dos Critérios de Graduação)
                                         |
         +-------------------------------+-------------------------------+
         |                                                               |
  [Critérios Cumpridos]                                           [Critérios Violados]
         |                                                               |
         v                                                               v
+---------------------------------+                             +-----------------+
| GRADUAÇÃO APROVADA              |                             | DESCARTE TOTAL  |
| - Mínimo de 30 trades fechados  |                             | Agente eliminado|
| - Sharpe Ratio >= 1.25          |                             | sem custo real  |
| - Drawdown máximo <= 4.5%       |                             +-----------------+
| - Duração mínima: 10 dias reais |
| - Alocação de 10% do capital    |
+---------------------------------+
```

### 4.1 Simulação Fiel de Fricções de Mercado
Muitos sistemas de simulação falham porque ignoram os custos operacionais. Na incubadora do Bot Cripto:
* Toda ordem preenchida desconta as taxas da corretora (taxas padrão de Maker e Taker).
* Ordens a mercado sofrem atraso sintético de latência (50 a 150 ms) e sofrem penalização de slippage no preço de execução.
* Isso garante que estratégias que lucram apenas em simulações teóricas perfeitas sejam prontamente eliminadas antes de receberem dinheiro de verdade.
