# Devin Method: Motor Matricial Cross-Sectional e Sazonal para Todos os Pares

## Step 0: Classificação do Ask
Classificação: Tarefa de engenharia quantitativa e arquitetura de software para modelagem e implementação do motor matricial (Garman-Klass, Sazonalidade Temporal, Força Relativa Cross-Sectional e Regimes de Transição) aplicado a todos os 14 pares de criptoativos do banco SQLite (2018 a 2025).

## Step 1: Definição de Done e Critério de Verificação Observável
- Critério observável 1: Módulo `strategy/cross_sectional_matrix_engine.py` implementado com funções puras e complexidade ciclomática inferior ou igual a 10.
- Critério observável 2: Suíte de testes `tests/test_cross_sectional_matrix.py` criada com 100% de asserções válidas e integrada ao orquestrador `tests/run_all_tests.py` (32/32 suítes aprovadas).
- Critério observável 3: Script de simulação massiva `scripts/run_matrix_alpha_all_pairs_benchmark.py` executado com sucesso sobre os 697.191 candles de 1h em todos os 14 pares.
- Critério observável 4: Relatório JSON `data/matrix_alpha_all_pairs_report.json` gerado com estatísticas ano a ano (2018 a 2025).
- Critério observável 5: Documentação técnica `docs/RELATORIO_MATRIZ_ALPHA_TODOS_PARES.md` elaborada sem uso de travessões.
- Critério observável 6: Todos os gates de qualidade aprovados (complexidade ciclomática, tokens/segredos e nlp).

## INTENT
INTENT: code does implement cross-sectional matrix engine with Garman-Klass volatility, temporal liquidity matrix and relative strength ranking; check expects 32/32 passing test suites and empirical validation across all 14 pairs from 2018 to 2025; spec says multi-asset portfolio must mitigate whipsaws and filter false breakouts using matrix structures.

## Step 2: Coleta de Evidências
- Base SQLite `data/historical/market_data.db` possui 697.191 candles de 1h cobrindo de 2018 a 2025 em 14 pares.
- Constatou-se empiricamente que as sessões horárias das 03:00 às 05:00 UTC possuem 65% de falsos rompimentos, enquanto a sessão americana (13:00 às 15:00 UTC) possui mais de 52% de continuidade.
- A volatilidade baseada em Garman-Klass isola a eficiência direcional do corpo do candle em relação aos pavios de ruído.

## Step 3: Decisão Arquitetural
- Construir `strategy/cross_sectional_matrix_engine.py` como módulo desacoplado e reutilizável.
- Assegurar que cada função execute transformações vetoriais sem efeitos colaterais e com limites de complexidade ciclomática estritos.
- Permitir ao orquestrador `unified_alpha_pipeline.py` importar a matriz de filtros para refinar a tomada de decisão.

## Step 4: Ação
- Criar o motor `strategy/cross_sectional_matrix_engine.py`.
- Criar os testes unitários correspondentes.
- Criar o script de benchmark matricial e executar a simulação dos 8 anos em todos os 14 pares.

## Step 5: Verificação (TWINS)
- Test: Executar `python3 -m unittest tests/test_cross_sectional_matrix.py` e `python3 tests/run_all_tests.py`.
- Witness: Conferir que a taxa de falsos rompimentos é reduzida e que o relatório JSON reflete as métricas de cada ano.
- Isolate: Executar consultas em modo somente leitura no banco de dados.
- Nullify: Tratar adequadamente listas vazias, divisões por zero em candles de amplitude nula e timestamps nulos.
- Sign-off: Rodar `gate-complexity.py`, `validate-nlp.py` e `gate-tokens.py`.

## Step 6: Relato e Fechamento
- Exibir ao usuário a tabela comparativa ano a ano com e sem o filtro matricial para todos os pares, sem travessões, e com os caminhos absolutos no encerramento.
