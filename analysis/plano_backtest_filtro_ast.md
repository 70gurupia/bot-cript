# Plano do Outro Backtest com Filtro AST (Constantes Confirmadas)
Caminho: /home/reginato/Projetos/bot-cript/analysis/plano_backtest_filtro_ast.md
Base: constantes_wins.json + ast_engine.py

## Constantes confirmadas (do script)
- BTC estratégias: best_hour=21 (NY/Londres), best_dow=Tue, vol NY > Lond > Tóquio, strong_pct 7,4% (body>0,6 + vol_rel>1,3).
- XRP/ADA: best_hour=2-3h (Tóquio/Londres), best_dow=Tue, strong_pct 6,9-7,8%.

## Filtro a inserir no AST (strategy/ast_engine.py)
Adicionar `ConditionNode` que só libera ordem se:
- `DataNode("volume")` relativo > 1,3 (vol_rel)
- `DataNode("body_pct")` > 0,6 (corpo da vela > 60% do range)
- `DataNode("session")` == "NY" (para BTC) ou "Londres" (para XRP/ADA) : ou usar `DataNode("hour_utc")` entre 13-18
- `DataNode("close")` > `DataNode("mm20")` (posição positiva)
- `DataNode("day_of_week")` == "Tue" (opcional, se quiser restringir)

## Como fazer o backtest
1. Rodar `scripts/reavaliacao_wins_profunda.py` (já feito : gerou constantes).
2. Editar `strategy/ast_engine.py`: criar `FilterNode` ou adicionar `ConditionNode` com operadores `maior`, `dentro_canal`, `cruzamento_alta` usando as variáveis novas.
3. Executar `scripts/run_walk_forward_backtest.py` (ou criar `scripts/run_backtest_com_filtro.py`) usando dados 2024 como treino e 2025/2026 como validação.
4. Comparar resultados: win_rate deve subir (meta: > 80% para Lead-Lag, > 45% para Donchian), DD deve cair (meta: < 4,5%).

## Expansão para outros cenários
Com os 10 pares disponíveis (`BTC, ETH, BNB, SOL, ADA, LINK, DOT, AVAX, XRP, DOGE`), rodar o mesmo script para cada par (alterar `STRATEGIES` no script ou criar loop automático). Se algum par tiver `best_hour` consistente e `strong_pct > 7%`, é candidato a nova estratégia.

Caminhos: `/home/reginato/Projetos/bot-cript/scripts/reavaliacao_wins_profunda.py`, `/home/reginato/Projetos/bot-cript/analysis/constantes_wins.json`, `/home/reginato/Projetos/bot-cript/analysis/plano_backtest_filtro_ast.md`, `/home/reginato/Projetos/bot-cript/strategy/ast_engine.py`.
