# Especificação da Tesouraria Central e Gestão de Risco

Este documento formaliza as regras matemáticas de dimensionamento de posições, controle de alavancagem, filtragem de correlação e procedimentos de emergência gerenciados pela Tesouraria Central.

---

## 1. Princípios da Tesouraria Central

A Tesouraria Central funciona como o banco central interno do ecossistema. Nenhum agente possui autoridade sobre o saldo global da conta; os agentes recebem uma linha de crédito virtual controlada.

1. **Isolamento Total de Margem**: Em qualquer operação com contratos futuros, o tipo de margem é estritamente forçado como `ISOLATED`. O saldo restante na conta da exchange nunca pode ser usado como colateral em chamadas de margem.
2. **Teto Inviolável de Alavancagem**: O sistema impõe um limite máximo imutável (ex: 2x ou 3x). Ordens que solicitam alavancagem superior são imediatamente rejeitadas antes de qualquer requisição de rede.
3. **Limite de Exposição Agregada**: A soma de todas as posições abertas simultaneamente por todos os agentes ativos não pode ultrapassar o teto global de exposição (ex: 70% do saldo total da conta, mantendo 30% em caixa estável).

---

## 2. Dimensionamento de Lote (Critério de Kelly Fracionário)

O tamanho da posição de cada agente em uma nova operação é determinado pelo Critério de Kelly Fracionário para evitar a ruína matemática causada pela superestimação de probabilidades:

$$f^* = \left( \frac{p \cdot b - q}{b} \right) \times K_{frac}$$

Onde:
* $p$: Taxa histórica de acerto do agente (Win Rate nos últimos 30 trades).
* $q$: Taxa histórica de perda ($1 - p$).
* $b$: Razão de pagamento (Média de ganhos dividida pela média de perdas).
* $K_{frac}$: Fator conservador de segurança, fixado obrigatoriamente em $0.20$ ou $0.25$ (um quarto de Kelly).

### 2.1 Trava de Perda Máxima por Operação
Mesmo com o cálculo de Kelly, nenhuma ordem individual pode arriscar mais de **1.0% do capital alocado àquele agente**, calculado entre o preço de entrada e o preço do Stop Loss obrigatório.

---

## 3. Matriz de Covariância e Filtro de Descorrelação

O risco mais severo em sistemas que replicam estratégias é a concentração silenciosa de risco em um único movimento de mercado.

```text
               Agente 1 (BTC)    Agente 2 (BTC)    Agente 3 (ETH)    Agente 4 (SOL)
Agente 1 (BTC)      1.00              0.89*             0.61              0.44
Agente 2 (BTC)      0.89*             1.00              0.58              0.39
Agente 3 (ETH)      0.61              0.58              1.00              0.52
Agente 4 (SOL)      0.44              0.39              0.52              1.00

* ALERTA: Correlação Agente 1 e Agente 2 > 0.70.
  Ação da Tesouraria: O Agente 2 tem sua alocação de capital reduzida em 50%
  ou é redirecionado para operar um par alternativo descorrelacionado.
```

### 3.1 Regra de Concorrência de Sinais
Se dois ou mais agentes emitirem sinais de entrada simultâneos para o mesmo ativo na mesma direção, a Tesouraria aplica a seguinte regra de prioridade:
1. O agente com maior Sharpe Ratio nos últimos 30 dias recebe prioridade na alocação.
2. A exposição combinada no mesmo ativo é limitada a no máximo 25% do capital disponível da carteira.

---

## 4. Protocolo de Kill Switch e Procedimento de Emergência

O Kill Switch é um circuito determinístico que atua como freio de emergência em três níveis independentes:

### 4.1 Nível 1: Suspensão de Agente Individual
* **Condição de Disparo**: O agente atinge 2.0% de perda em um período móvel de 24 horas.
* **Comportamento**: A Tesouraria cancela ordens limite abertas do agente, fecha a posição corrente a mercado e move o agente para o estado `PAUSED`. O agente requer revisão ou passa por recalibração na incubadora.

### 4.2 Nível 2: Circuit Breaker Global de Carteira
* **Condição de Disparo**: O patrimônio líquido total da conta sofre uma desvalorização igual ou superior a 4.0% em 24 horas.
* **Comportamento**:
  1. Envio instantâneo de ordem de cancelamento para todas as ordens abertas em todos os pares.
  2. Envio de ordens de fechamento a mercado para todas as posições ativas.
  3. Desativação do loop de trading real por um período obrigatório de 24 horas (Cooling-off Period).
  4. Disparo de mensagem de alerta prioritária para o bot do Telegram com relatório dos eventos causadores.

### 4.3 Nível 3: Falha de Comunicação e Queda de Conexão
* **Condição de Disparo**: Ausência de dados de mercado via WebSocket ou falta de resposta a requisições de ping por mais de 10 segundos.
* **Comportamento**: O motor entra em estado de guarda, suspende novas entradas e tenta reconexão síncrona. Se a reconexão falhar por 30 segundos, posições alavancadas em futuros são reduzidas preventivamente via chamada REST de segurança para mitigar slippage em caso de colapso de rede.

---

## 5. Comandos Remotos via Telegram

O operador humano pode interagir com a Tesouraria a qualquer instante através do bot autenticado no Telegram:

* `/status`: Retorna o saldo da conta, capital em risco, posições abertas e métricas resumidas dos agentes ativos e em incubação.
* `/panic` ou `/kill`: Aciona manualmente o Circuit Breaker Nível 2 (fecha tudo a mercado e trava o sistema).
* `/resume`: Solicita confirmação explícita de dois fatores no chat para destravar o sistema após uma pausa manual ou automática.
