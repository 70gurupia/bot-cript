# Análise Profunda — Estratégia Win (Lead-Lag BTC→ETH)
Caminho: /home/reginato/Projetos/bot-cript/analysis/analise_profunda_estrategia_win.md
Base: data/strategies_benchmark_report.json (Lead-Lag BTC->ETH: 39 trades, 74,4% win, PF 4,32, DD 1,6%, +11,91%)

## 1. O que foi win (evidência)
- Par: BTC líder, ETH seguidor, 15m.
- 29 vitórias / 39 trades; lucro líquido +11,91%; drawdown máximo 1,6% (muito baixo); PF 4,32.
- Conclusão: a entrada não é aleatória — há lead temporal real.

## 2. Correlações profunda (fórmulas do projeto)
Arquivo: treasury/correlation_matrix.py
Fórmula Pearson (já implementada):
r = cov(X,Y) / (sqrt(var_X) * sqrt(var_Y))
Limite de corte: 0,70. Se r > 0,70 entre BTC e ETH na mesma janela, não operar os dois na mesma direção (evita duplicação).

Lead-Lag (não implementado totalmente, proposta):
- Calcular r com defasagem de 1, 2, 3, 4 barras (15m/1h).
- Se r(t-1) > r(t) em ETH vs BTC, a defasagem é real.
- Fórmula prática: corr_coef = np.corrcoef(btc[-n:], eth_shifted[-n:])[0,1]
- Usar janela móvel 50-100 barras (dados de data/historical/)

## 3. Análise profunda das entradas win (LAIA)
Arquivo: strategy/laia_entry_evaluator.py; report: data/laia_entry_comparison_report.json
Métricas a extrair de cada trade vencedor:
- EQS (Entry Quality Score): volume relativo, posição no canal de Bollinger, acumulação institucional oculta.
- Filtro de falsos rompimentos: se o preço retestou 0,618 do impulso antes de confirmar.
- Regime macro: supervisor_loop.py (multiplicador_exposicao 0,5-1,0) — só operar quando regime != PAUSA_DEFENSIVA.

Proposta: rodar laia_entry_evaluator.py sobre cada candle do período 2024 dos pares BTC/ETH para gerar score por entrada.

## 4. Fórmulas operacionais (já no código)
Kelly fracionário (treasury/treasury_controller.py):
f = (p*b - q) / b; f_frac = min(0,25; f * 0,25)
Com p=0,744 e b médio ~2,0 (PF 4,32), f ≈ 0,37 → limitado a 0,25 (25% de Kelly). Risco por trade = 1% do capital do agente (max_single_trade_risk_pct=1,0).

Stop dinâmico com ATR (crossover_engine.py):
SL = ATR * mult; mult [1,0; 4,0]; clamped.
Para Lead-Lag BTC→ETH: usar mult=2,0-3,0 (não 1,0, porque a volatilidade de ETH é alta).

Covariância entre agentes (correlation_matrix.py):
Se agente A opera BTC Long e agente B opera ETH Long, e r(BTC,ETH) > 0,70 → um dos dois deve ser pausado (treasury_controller valida antes da ordem).

## 5. Plano de melhoria (ordem)
1. Extrair os 39 trades win do benchmark (data/strategies_benchmark_report.json).
2. Para cada trade win: calcular v(RSI, BB, volume, regime LLM) usando laia_entry_evaluator.py.
3. Calcular lead-lag com defasagem 1-4 barras nos CSV históricos (data/historical/BTCUSDT_1h_... / ETHUSDT_...).
4. Aplicar filtro de covariância: se r(BTC,ETH) > 0,70, reduzir exposição agregada (max_portfolio_exposure_pct = 0,70 * multiplicador_exposicao).
5. Ajustar parâmetros da AST (ast_engine.py): profundidade <= 8, operadores permitidos, constantes clampadas.
6. Rodar em incubadora (incubator_manager.py) com 30 trades mínimos; promover apenas se Sharpe >= 1,25 e DD <= 4,5%.

Caminhos absolutos usados: /home/reginato/Projetos/bot-cript/data/strategies_benchmark_report.json, /home/reginato/Projetos/bot-cript/treasury/correlation_matrix.py, /home/reginato/Projetos/bot-cript/strategy/laia_entry_evaluator.py, /home/reginato/Projetos/bot-cript/strategy/ast_engine.py, /home/reginato/Projetos/bot-cript/evolution/incubator_manager.py.
