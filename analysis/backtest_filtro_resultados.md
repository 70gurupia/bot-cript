# Backtest com Filtro de Constantes vs Sem Filtro
Base: CSV 1h BTC/ETH + filtro (body>0,6, vol_rel>1,3, NY, close>mm20)

- **BTC_LeadLag_Donchian_Cash_filtro**: trades=335, win_rate=0.475, ret=-6.86%, DD=21.96%, cap_final=93.14
- **BTC_LeadLag_Donchian_Cash_semfiltro**: trades=21908, win_rate=0.512, ret=1203.83%, DD=96.18%, cap_final=1303.83
- **ETH_LeadLag_filtro**: trades=335, win_rate=0.49, ret=24.05%, DD=35.51%, cap_final=124.05
- **ETH_LeadLag_semfiltro**: trades=21908, win_rate=0.514, ret=2490.04%, DD=98.01%, cap_final=2590.04

**Interpretação:** Se win_rate sob filtro > sem filtro e DD menor, constante é válida.
Caminhos: /home/reginato/Projetos/bot-cript/scripts/backtest_com_filtro.py, /home/reginato/Projetos/bot-cript/analysis/backtest_filtro_resultados.json
