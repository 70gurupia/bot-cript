# Reavaliação Profunda de Todos os Casos Win (Mesmo os Ruins)
Caminho: /home/reginato/Projetos/bot-cript/analysis/reavaliacao_wins_profunda.md
Base: data/strategies_benchmark_report.json + data/historical/*.csv (BTC, ETH, SOL, ADA, XRP, LINK, BNB, AVAX, DOGE, DOT)

## 1. Casos Win a reavaliar (toda a lista do benchmark 2024)
De `data/strategies_benchmark_report.json` (não só os bons, todos com win_rate > 0):
- Lead-Lag BTC->ETH (15m): 39 trades, 29W, +11,91%, PF 4,32, DD 1,6% — CENÁRIO BOM
- Cash & Carry Funding BTC (8h): 366 trades, 366W, +24,57%, PF 99, DD 0 — BOM
- Donchian Breakout BTC (1h): 124 trades, 51W, +42,35%, PF 1,39, DD 13,2% — MIXTO (DD alto)
- RSI+Bollinger ADA (15m): 864 trades, 468W, +14,88%, PF 1,02, DD 129,9% — RUIM (DD absurdo)
- RSI+Bollinger XRP (15m): 779 trades, 437W, +35,09%, PF 1,07, DD 103,3% — RUIM
- Cointegração SOL/AVAX (1h): 271 trades, 149W, -19,28%, PF 0,93 — PERDA (não win, excluir)
- ORB LINK (1h): 256 trades, 129W, -55,69% — PERDA
- ORB BNB (1h): 255 trades, 127W, -27,33% — PERDA

Objetivo: analisar os 29 wins do Lead-Lag + 51 wins Donchian + 468 wins RSI/ADA + 437 wins RSI/XRP, e buscar constantes de contexto (horário, vela, suporte, MM).

## 2. Indicadores a extrair de cada candle win (do CSV 1h/15m)
Arquivo de dados: `data/historical/BTCUSDT_1h_2020_2024.csv` (e ETH, SOL, ADA, XRP, etc.)
Campos: symbol, open_time (ms), open, high, low, close, volume, quote_volume, trades_count

Fórmulas (Python/numpy — já em requirements.txt):
```
# Conversão de tempo
hora_utc = pd.to_datetime(open_time, unit='ms').hour  # 0-23
dia_semana = pd.to_datetime(open_time, unit='ms').dayofweek  # 0=seg, 6=dom

# Sessões de mercado (UTC aproximado)
sessao = 'Tóquio' if 0 <= hora_utc < 7 else 'Londres' if 7 <= hora_utc < 13 else 'NY' if 13 <= hora_utc < 18 else 'Off'

# Tamanho da vela (range, body, sombra)
range_ = high - low
body = abs(close - open)
body_pct = body / range_ if range_ > 0 else 0
shadow_upper = high - max(open, close)
shadow_lower = min(open, close) - low
shadow_total = shadow_upper + shadow_lower

# Volume relativo (média móvel de 20 barras)
vol_media_20 = volume.rolling(window=20, min_periods=5).mean()
vol_rel = volume / vol_media_20

# Médias (20, 50, 200 barras — usar pandas no CSV)
mm20 = close.rolling(window=20, min_periods=5).mean()
mm50 = close.rolling(window=50, min_periods=10).mean()
mm200 = close.rolling(window=200, min_periods=20).mean()

posicao_mm20 = (close - mm20) / mm20 * 100  # % acima/abaixo
posicao_mm50 = (close - mm50) / mm50 * 100
posicao_mm200 = (close - mm200) / mm200 * 100

# ATR (Average True Range, janela 14, padrão técnico)
prev_close = close.shift(1)
tr1 = high - low
tr2 = abs(high - prev_close)
tr3 = abs(low - prev_close)
atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(window=14, min_periods=7).mean()

# Suporte / Resistência (últimos N=10, 20, 50 highs/lows)
sup_10 = low.rolling(window=10, min_periods=5).min()
res_10 = high.rolling(window=10, min_periods=5).max()
sup_20 = low.rolling(window=20, min_periods=10).min()
res_20 = high.rolling(window=20, min_periods=10).max()

# Deslocamento de preço (retorno % da vela)
ret_vela = (close - open) / open * 100

# Correlação de horas (para Lead-Lag BTC->ETH)
# Criar série de 1h alinhada por timestamp; calcular Pearson entre BTC e ETH defasado 1h (lead-lag)
```

## 3. O que sondar nos casos win (método)
Para cada trade win (ex: entrada do Lead-Lag BTC->ETH no candle i):
- Extrair janela [-12 barras, +12 barras] do CSV do par.
- Calcular todos os indicadores acima para o candle de entrada e os 3 anteriores.
- Buscar constantes: ex: "95% dos wins ocorreram com body_pct > 0,5, vol_rel > 1,5, ficavam entre 13h-18h UTC (sessão NY), e preço estava acima de mm20 mas abaixo de res_20".
- Fazer o mesmo para os casos ruins (Donchian com DD 13%, RSI/ADA com DD 129,9%) para ver o contrário: o que faltou (ex: volume baixo, vela pequena, fora da sessão, preço no suporte quebrado).

## 4. Correlações de horários mais profundas (não só Pearson estático)
- **Correlação por sessão:** calcular win_rate por sessão (Tóquio/Londres/NY/Off) para cada estratégia. Se Lead-Lag só ganha em NY, é constante.
- **Correlação por hora:** calcular win_rate por hora_utc (0-23). Se há pico em 14h-16h, é constante de mercado.
- **Correlação com dias da semana:** seg-ter-quarta etc.
- **Correlação com regime LLM:** usar `supervisor_loop.py` para marcar regime (`NEUTRO`, `ALTA_VOLATILIDADE`, `TENDENCIA`). Verificar se wins ocorrem principalmente em `TENDENCIA_ALTA` ou `NEUTRO`.

Fórmula para comparação:
```
win_rate_sessao = trades_win_sessao / total_trades_sessao
mean_vol_win = volume[win_candles].mean()
mean_vol_loss = volume[loss_candles].mean()
ratio_vol = mean_vol_win / mean_vol_loss  # se > 1,5, volume confirma win
```

## 5. Plano prático para outro backtest (usando o projeto)
1. Criar script Python (`scripts/reavaliacao_wins_profunda.py`) que lê `data/strategies_benchmark_report.json`, mapeia os trades win (usar timestamp aproximado do relatório) e extrai os CSV de `data/historical/`.
2. Calcular indicadores (range, body_pct, vol_rel, mm20/50/200, ATR, suporte/resistência, hora/sessão) para cada candle de entrada.
3. Agrupar por estratégia e buscar constantes: ex: para Lead-Lag, se 90% dos wins têm `vol_rel > 1,3` + `body_pct > 0,6` + `sessao == 'NY'` + `close > mm20`, então o filtro é válido.
4. Aplicar filtro no `strategy/ast_engine.py`: adicionar `DataNode` para `volume`, `mm20_position`, `session`, e regras de entrada (`condition`) que só liberam ordem se constantes forem atendidas.
5. Rodar novo backtest (`scripts/run_walk_forward_backtest.py`) com o filtro ativo e comparar: se win_rate subir de 74,4% para > 80% com menor DD, a constante é real.

## 6. Arquivos envolvidos (caminhos absolutos)
- Dados: `/home/reginato/Projetos/bot-cript/data/historical/BTCUSDT_1h_2020_2024.csv`, `/home/reginato/Projetos/bot-cript/data/historical/ETHUSDT_1h_2020_2024.csv`, etc.
- Benchmark: `/home/reginato/Projetos/bot-cript/data/strategies_benchmark_report.json`
- Relatórios win: `/home/reginato/Projetos/bot-cript/data/anti_martingale_report.json`, `data/mixed_portfolio_report.json`
- Indicadores/fórmulas: `/home/reginato/Projetos/bot-cript/treasury/correlation_matrix.py`, `/home/reginato/Projetos/bot-cript/strategy/ast_engine.py`, `/home/reginato/Projetos/bot-cript/strategy/laia_entry_evaluator.py`
- Scripts: `/home/reginato/Projetos/bot-cript/scripts/run_walk_forward_backtest.py`, `/home/reginato/Projetos/bot-cript/scripts/download_historical_15m.py`
- Supervision regime: `/home/reginato/Projetos/bot-cript/strategy/supervisor_loop.py`

## 7. Fórmulas resumidas para usar diretamente
```
# Correlação cruzada lead-lag (BTC -> ETH)
for lag in [1,2,3,4]:
    corr = np.corrcoef(btc[-n:].values, eth_shifted_by_lag[-n:].values)[0,1]

# Constante de hora/sessão
win_rate_sessao = df[df['win']==True]['sessao'].value_counts() / df['sessao'].value_counts()

# Volume confirma win
vol_rel_win = df.loc[df['win']==True, 'vol_rel'].mean()
vol_rel_loss = df.loc[df['win']==False, 'vol_rel'].mean()

# Suporte/Resistência dinâmico (para filtro de entrada)
entry_above_support = close > sup_20.iloc[-1]  # preço acima do suporte de 20 barras
entry_below_resist = close < res_20.iloc[-1]  # preço abaixo da resistência
```
