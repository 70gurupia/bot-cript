# Devin Method: Matriz Abrangente de Simulações em Todos os Pares (2018 a 2025)

## Step 0: Classificação do Ask
Classificação: Pergunta/Assessment e Tarefa de engenharia quantitativa para simulação massiva em todos os 14 pares de 2018 a 2025.

## Step 1: Definição de Done e Critério de Verificação Observável
- Critério observável 1: Simulação executada para 100% dos 14 pares cadastrados no SQLite para o ano de 2025 isolado e para o período acumulado de 8 anos (2018 a 2025).
- Critério observável 2: Relatório estruturado `data/comprehensive_all_pairs_simulation_report.json` gerado com estatísticas completas (trades, win rate, retorno líquido, drawdown).
- Critério observável 3: Relatório técnico executivo `docs/RELATORIO_CONSOLIDADO_8ANOS_TODOS_PARES.md` documentando a especialização algorítmica de cada par.
- Critério observável 4: 100% das 31 suítes de teste de `tests/run_all_tests.py` aprovadas.
- Critério observável 5: Complexidade ciclomática de todas as funções do novo script inferior ou igual a 10.
- Critério observável 6: Sincronização remota via git commit e push para o repositório GitHub.

## INTENT
INTENT: code does evaluate historical performance across all 14 cryptocurrency pairs for 2025 and 8-year cumulative periods using G3 Newtonian momentum and Donchian trend following; check expects valid JSON metrics and zero test regressions; spec says trading system must provide empirical factual evidence for every asset in the portfolio.

## Step 2: Coleta de Evidências
- Banco de dados SQLite `data/historical/market_data.db` contém 697.191 candles de 1h distribuídos em 15 pares.
- Pares com dados até 31/12/2025: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT, XRPUSDT, LINKUSDT, DOGEUSDT, AVAXUSDT, DOTUSDT, TRXUSDT, LTCUSDT, XLMUSDT, ETCUSDT.

## Step 3: Decisão Arquitetural
- Desenvolver script autônomo `scripts/run_all_pairs_comprehensive_matrix.py` com funções atômicas e isoladas.
- Comparar cada par sob dois prismas complementares: Micro-rompimento com Entropia de Tsallis e Momento Vetorial (G3 Newtoniano) e Seguidor de Tendência Donchian 20.
- Identificar para cada ativo qual o modelo algorítmico ótimo.

## Step 4: Ação
- Criar e executar `scripts/run_all_pairs_comprehensive_matrix.py`.
- Gerar relatórios e atualizar base de documentação.

## Step 5: Verificação (TWINS)
- Test: Executar `python3 scripts/run_all_pairs_comprehensive_matrix.py` e validar retorno de exit 0.
- Witness: Conferir que o relatório JSON contém os 14 pares e números factuais sem interpolações falsas.
- Isolate: Garantir que leituras sejam em modo read-only no banco SQLite.
- Nullify: Verificar tratamento de dados vazios ou pares com menos de 100 velas.
- Sign-off: Rodar suíte de testes unitários e analisador de complexidade.

## Step 6: Relato e Fechamento
- Resumo claro para o usuário com tabela comparativa, sem travessões, destacando os pares alfa e os pares que devem ser evitados.
