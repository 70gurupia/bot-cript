# Devin Method: Backtest da Flotilha de 1 a 40 Sub-Bots em 8 Grupos Estratégicos

## Step 0: Classificação do Ask
Classificação: Tarefa de engenharia quantitativa e simulação distribuída para modelar, testar e comparar a progressão de 1 a 40 sub-bots organizados em 8 grupos de 5 bots especializados por estratégia e ativo na base SQLite.

## Step 1: Definição de Done e Critério de Verificação Observável
- Critério observável 1: Script `scripts/run_swarm_40_bots_backtest.py` implementado com arquitetura multi-agente, sem funções excedendo complexidade ciclomática 10.
- Critério observável 2: Execução de simulações comparativas para 1 bot, 5 bots, 10 bots, 20 bots e 40 bots (8 grupos de 5).
- Critério observável 3: Relatório JSON estruturado em `data/swarm_40_bots_backtest_report.json` com métricas completas de retorno, drawdown, trades diários e slippage evitado.
- Critério observável 4: Relatório técnico executivo `docs/RELATORIO_SWARM_40_BOTS.md` gerado sem uso de travessões.
- Critério observável 5: Suíte de testes `tests/run_all_tests.py` mantendo 32/32 suítes aprovadas.
- Critério observável 6: Aprovação em todos os gates estáticos de validação (Devin Method, NLP, Complexidade e Tokens).

## INTENT
INTENT: code does simulate multi-agent swarm architecture scaling from 1 to 40 bots across 8 specialized strategy pods of 5 bots each; check expects measurable reduction in drawdown and slippage with higher daily consistency; spec says decentralized multi-agent execution must outperform monolithic single-order execution.

## Step 2: Coleta de Evidências
- Banco de dados `data/historical/market_data.db` contém dados horários e intradiários (15m e 1h) para os pares chave (BTC, ETH, SOL, DOGE, AVAX, XRP, ADA, TRX, BNB).
- Uma ordem de $40.000 USD em altcoins gera slippage de 0.2% a 0.6%, enquanto 40 ordens de $1.000 USD são preenchidas como Maker com taxa de 0.02% e slippage zero.

## Step 3: Decisão Arquitetural
- Desenvolver o motor `scripts/run_swarm_40_bots_backtest.py` definindo os 8 grupos de 5 bots:
  - Grupo 1 (Bots 1-5): G3 Newtoniana Scalp BTC (15m)
  - Grupo 2 (Bots 6-10): G3 Newtoniana Scalp ETH (15m)
  - Grupo 3 (Bots 11-15): Lead-Lag Temporal BTC -> Altcoins (15m)
  - Grupo 4 (Bots 16-20): Donchian 40 Trend Following DOGE (1h)
  - Grupo 5 (Bots 21-25): Donchian 40 Trend Following SOL & AVAX (1h)
  - Grupo 6 (Bots 26-30): Reversão à Média RSI + Bollinger XRP & ADA (15m)
  - Grupo 7 (Bots 31-35): Trend Following Seletivo TRX & BNB (1h)
  - Grupo 8 (Bots 36-40): Cash & Carry Funding Rate Arbitrage (8h)
- Cada bot possui teto de risco isolado e limite de exposição agregada por ativo gerenciado pela Tesouraria.

## Step 4: Ação
- Criar e rodar o script de backtest do swarm.
- Gerar relatórios e validar conformidade em todos os gates.

## Step 5: Verificação (TWINS)
- Test: Executar `python3 scripts/run_swarm_40_bots_backtest.py` com retorno de código 0.
- Witness: Confirmar as tabelas comparativas de 1 a 40 bots no terminal e no JSON gerado.
- Isolate: Consultas read-only no banco SQLite.
- Nullify: Tratar adequadamente janelas sem sinal e concorrência de posições.
- Sign-off: Rodar analisadores estáticos e suíte completa de testes.

## Step 6: Relato e Fechamento
- Apresentar ao usuário a comparação precisa de 1 a 40 bots, destacando os 8 grupos de 5, retorno líquido, drawdown e impacto prático na escalabilidade patrimonial.
