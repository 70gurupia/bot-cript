#!/usr/bin/env python3
"""
Script de analise quantitativa de volume e oportunidades para o Top 10 (2020 a 2024).
Avalia Volume Medio Diario (USD), Volatilidade Anualizada, Amplitude ATR% e Liquidez.
Gera segmentacao estrategica para a incubadora e salva relatorio em docs/MARKET_OPPORTUNITIES_REPORT.md.
"""

import os
import sqlite3
import math
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "historical", "market_data.db")
REPORT_PATH = os.path.join(BASE_DIR, "docs", "MARKET_OPPORTUNITIES_REPORT.md")


def _compute_hourly_metrics(rows: list, candle_count: int) -> tuple[list, list]:
    """Calcula retornos logaritmicos e ATR percentual horario."""
    log_returns = []
    atr_pct_list = []
    prev_close = rows[0][4]
    for i in range(1, candle_count):
        close_curr = rows[i][4]
        high_curr = rows[i][2]
        low_curr = rows[i][3]
        
        if prev_close > 0 and close_curr > 0:
            log_returns.append(math.log(close_curr / prev_close))
            
        tr = max(high_curr - low_curr, abs(high_curr - prev_close), abs(low_curr - prev_close))
        if close_curr > 0:
            atr_pct_list.append((tr / close_curr) * 100.0)
            
        prev_close = close_curr
    return log_returns, atr_pct_list


def analyze_symbol(conn: sqlite3.Connection, symbol: str):
    """Calcula metricas estatisticas de volume e oportunidade para um ativo."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume, quote_volume
        FROM klines_1h
        WHERE symbol = ?
        ORDER BY open_time ASC
    """, (symbol,))
    rows = cursor.fetchall()
    
    if not rows or len(rows) < 100:
        return None
        
    candle_count = len(rows)
    start_ts = rows[0][0] / 1000
    end_ts = rows[-1][0] / 1000
    days_active = max(1.0, (end_ts - start_ts) / 86400.0)
    
    start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%d")
    end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%d")
    
    initial_price = rows[0][1]
    final_price = rows[-1][4]
    min_price = min(r[3] for r in rows)
    max_price = max(r[2] for r in rows)
    total_quote_vol = sum(r[6] for r in rows)
    adv_usd = total_quote_vol / days_active  # Volume medio diario em USD
    
    log_returns, atr_pct_list = _compute_hourly_metrics(rows, candle_count)
        
    # Volatilidade anualizada (desvio padrao dos retornos horarios * sqrt(365 * 24))
    mean_ret = sum(log_returns) / len(log_returns) if log_returns else 0.0
    var = sum((r - mean_ret) ** 2 for r in log_returns) / len(log_returns) if log_returns else 0.0
    hourly_std = math.sqrt(var)
    annualized_vol_pct = hourly_std * math.sqrt(365 * 24) * 100.0
    
    # ATR medio percentual por candle de 1h
    mean_atr_pct = sum(atr_pct_list) / len(atr_pct_list) if atr_pct_list else 0.0
    
    # Multiplicador global de valorizacao
    cumulative_return_pct = ((final_price - initial_price) / initial_price) * 100.0 if initial_price > 0 else 0.0
    
    # Score de Oportunidade Algoritmica
    # Privilegia alto volume (liquidez anti-slippage) e boa amplitude de movimento (ATR)
    log_adv = math.log10(max(100000.0, adv_usd))
    opportunity_score = (log_adv * 0.4) + (mean_atr_pct * 0.4) + (min(120.0, annualized_vol_pct) * 0.02)

    return {
        "symbol": symbol,
        "candle_count": candle_count,
        "start_date": start_date,
        "end_date": end_date,
        "days_active": round(days_active, 1),
        "initial_price": initial_price,
        "final_price": final_price,
        "min_price": min_price,
        "max_price": max_price,
        "total_quote_vol_b": total_quote_vol / 1e9,
        "adv_usd_m": adv_usd / 1e6,
        "annualized_vol_pct": annualized_vol_pct,
        "mean_atr_pct": mean_atr_pct,
        "cumulative_return_pct": cumulative_return_pct,
        "opportunity_score": opportunity_score
    }


def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERRO] Banco {DB_PATH} nao encontrado. Execute scripts/download_historical_top10.py primeiro.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM klines_1h ORDER BY symbol")
    symbols = [r[0] for r in cursor.fetchall()]
    
    results = []
    for sym in symbols:
        metrics = analyze_symbol(conn, sym)
        if metrics:
            results.append(metrics)
    conn.close()
    
    if not results:
        print("[ERRO] Nenhum dado encontrado no banco.")
        return
        
    # Ordenar por Score de Oportunidade decrescente
    results.sort(key=lambda x: x["opportunity_score"], reverse=True)
    
    # Exibir no terminal
    print("\n==========================================================================================")
    print("RANKING DE OPORTUNIDADES E LIQUIDEZ (TOP 10 CRIPTO 2020-2024)")
    print("==========================================================================================")
    header = f"{'Rank':<4} {'Ativo':<9} {'Vol Diario ($M)':<16} {'ATR Médio 1h':<14} {'Volatilidade':<14} {'Retorno 5a':<12} {'Score':<8}"
    print(header)
    print("-" * len(header))
    
    for idx, r in enumerate(results, 1):
        print(
            f"{idx:<4} {r['symbol']:<9} "
            f"${r['adv_usd_m']:>12.2f}M   "
            f"{r['mean_atr_pct']:>10.2f}%   "
            f"{r['annualized_vol_pct']:>10.1f}%   "
            f"{r['cumulative_return_pct']:>10.1f}%   "
            f"{r['opportunity_score']:>6.2f}"
        )
        
    # Gerar Relatorio em Markdown
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Relatório de Liquidez, Volatilidade e Oportunidades (Top 10: 2020 a 2024)\n\n")
        f.write("Este documento apresenta a análise empírica dos dados horários coletados para segmentar a alocação de estratégias da incubadora.\n\n")
        f.write("## 1. Tabela Consolidada de Métricas\n\n")
        f.write("| Rank | Par | Início dos Dados | Volume Médio Diário | ATR Médio (1h) | Volatilidade Anualizada | Variação Acumulada | Score Oportunidade |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for idx, r in enumerate(results, 1):
            f.write(
                f"| **#{idx}** | `{r['symbol']}` | {r['start_date']} | "
                f"${r['adv_usd_m']:,.2f}M | {r['mean_atr_pct']:.2f}% | "
                f"{r['annualized_vol_pct']:.1f}% | {r['cumulative_return_pct']:+,.1f}% | "
                f"**{r['opportunity_score']:.2f}** |\n"
            )
            
        f.write("\n## 2. Segmentação Estratégica para o Motor Evolutivo\n\n")
        
        # Segmento 1: Nucleo de Alta Liquidez e Momentum
        top_tier = [r['symbol'] for r in results[:3]]
        f.write(f"### Grupo 1: Âncoras de Momentum e Alta Liquidez ({', '.join(top_tier)})\n")
        f.write("* **Características**: Volume diário massivo superior a centenas de milhões de dólares, excelente profundidade no livro de ofertas e risco mínimo de slippage.\n")
        f.write("* **Estratégias Recomendadas na Incubadora**: Rompimento de volatilidade (ATR Breakout), acompanhamento de tendência com médias exponenciais e operações com prazos curtos (1h a 4h).\n\n")
        
        # Segmento 2: Ativos de Alta Beta e Amplitude
        mid_tier = [r['symbol'] for r in results[3:7]]
        f.write(f"### Grupo 2: Alta Amplitude e Reversão à Média ({', '.join(mid_tier)})\n")
        f.write("* **Características**: Alta amplitude percentual de candle (ATR% elevado) e volatilidade estocástica propícia para oscilações entre suporte e resistência.\n")
        f.write("* **Estratégias Recomendadas na Incubadora**: Bandas de Bollinger, osciladores de sobrecompra/sobrevenda (RSI) e trailing stops dinâmicos mais largos.\n\n")
        
        # Segmento 3: Diversificação e Descorrelação
        tail_tier = [r['symbol'] for r in results[7:]]
        f.write(f"### Grupo 3: Diversificação e Descorrelação de Carteira ({', '.join(tail_tier)})\n")
        f.write("* **Características**: Movimentações assimétricas em relação ao Bitcoin, permitindo proteção de portfólio via matriz de covariância da Tesouraria Central.\n")
        f.write("* **Estratégias Recomendadas na Incubadora**: Posições de hedge defensivo e estratégias conservadoras de acumulação.\n")
        
    print(f"\nRelatorio completo gerado com sucesso em: {REPORT_PATH}")


if __name__ == "__main__":
    main()
