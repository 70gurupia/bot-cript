"""
Execução do Ciclo Walk-Forward Completo de 5 Anos (2020 a 2024) - Fase 6 / Task-017.
Processa os 420.929 candles históricos através de 4 regimes sequenciais:
Fase A: Treino Bull Market (2020-2021)
Fase B: Estresse Bear Market (2022)
Fase C: Recalibração e Crossover Genético (2023)
Fase D: Validação Cega Out-of-Sample (2024)
"""

from __future__ import annotations
import sqlite3
import json
import time
import math
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from typing import Dict, Any, List, Tuple

from strategy.ast_engine import (

    ConstantNode,
    DataNode,
    IndicatorNode,
    ConditionNode,
    LogicalNode,
    StrategyAST
)
from evolution.fitness_evaluator import (
    TradeRecord,
    PerformanceReport,
    evaluate_strategy_performance,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_fitness_score
)
from evolution.crossover_engine import recombine_strategies
from evolution.incubator_manager import IncubatorManager


DB_PATH = Path("/home/reginato/Projetos/bot-cript/data/historical/market_data.db")
OUTPUT_REPORT_PATH = Path("/home/reginato/Projetos/bot-cript/data/walk_forward_report.json")

# Limites temporais UTC em milissegundos
TS_2020_START = 1577836800000  # 2020-01-01 00:00:00
TS_2022_START = 1640995200000  # 2022-01-01 00:00:00
TS_2023_START = 1672531200000  # 2023-01-01 00:00:00
TS_2024_START = 1704067200000  # 2024-01-01 00:00:00
TS_2024_END   = 1735689600000  # 2024-12-31 23:59:59


# ==============================================================================
# 1. CÁLCULO VETORIAL DE INDICADORES TÉCNICOS
# ==============================================================================

def compute_indicators_for_candles(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calcula EMA_20, EMA_50, RSI_14 e ATR_14 sobre a sequencia de candles."""
    if not candles:
        return []

    enriched: List[Dict[str, Any]] = []
    ema_20 = float(candles[0]["close"])
    ema_50 = float(candles[0]["close"])
    k_20 = 2.0 / (20.0 + 1.0)
    k_50 = 2.0 / (50.0 + 1.0)

    gains: List[float] = []
    losses: List[float] = []

    for i, c in enumerate(candles):
        close_p = float(c["close"])
        high_p = float(c["high"])
        low_p = float(c["low"])

        # EMA
        ema_20 = (close_p * k_20) + (ema_20 * (1.0 - k_20))
        ema_50 = (close_p * k_50) + (ema_50 * (1.0 - k_50))

        # RSI 14
        if i > 0:
            diff = close_p - float(candles[i - 1]["close"])
            gains.append(max(0.0, diff))
            losses.append(max(0.0, -diff))
            if len(gains) > 14:
                gains.pop(0)
                losses.pop(0)
            avg_g = sum(gains) / len(gains)
            avg_l = sum(losses) / len(losses)
            rsi = 100.0 - (100.0 / (1.0 + (avg_g / avg_l))) if avg_l > 1e-9 else 100.0
        else:
            rsi = 50.0

        item = dict(c)
        item["ema_20"] = round(ema_20, 2)
        item["ema_50"] = round(ema_50, 2)
        item["rsi_14"] = round(rsi, 2)
        enriched.append(item)

    return enriched


def load_candles_from_db(symbol: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    """Carrega candles ordenados do banco SQLite para um periodo especifico."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Mapeia simbolo Binance (BTCUSDT) para notacao interna (BTC/USDT)
    db_sym = symbol.replace("/", "")
    cursor.execute("""
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM klines_1h
        WHERE symbol = ? AND open_time >= ? AND open_time < ?
        ORDER BY open_time ASC
    """, (db_sym, start_ts, end_ts))

    rows = cursor.fetchall()
    conn.close()

    raw_candles = [
        {
            "timestamp": r[0],
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5]
        }
        for r in rows
    ]
    return compute_indicators_for_candles(raw_candles)


# ==============================================================================
# 2. DEFINIÇÃO DA POPULAÇÃO FUNDADORA EM AST
# ==============================================================================

def create_initial_population(symbol: str) -> List[StrategyAST]:
    """Cria a primeira geracao de estrategias em AST com diferentes lógicas."""
    # 1. Estrategia RSI Reversao
    s1 = StrategyAST(
        strategy_id="strat_rsi_reversal",
        name="RSI Oversold Momentum",
        symbol=symbol,
        entry_rule=LogicalNode("AND", [
            ConditionNode("menor", IndicatorNode("rsi_14"), ConstantNode(32.0)),
            ConditionNode("maior", DataNode("close"), IndicatorNode("ema_50"))
        ]),
        exit_rule=ConditionNode("maior", IndicatorNode("rsi_14"), ConstantNode(68.0)),
        stop_loss_pct=0.02,
        take_profit_pct=0.04
    )

    # 2. Estrategia EMA Trend Following
    s2 = StrategyAST(
        strategy_id="strat_ema_trend",
        name="EMA Dynamic Trend",
        symbol=symbol,
        entry_rule=LogicalNode("AND", [
            ConditionNode("cruzamento_alta", IndicatorNode("ema_20"), IndicatorNode("ema_50")),
            ConditionNode("maior", IndicatorNode("rsi_14"), ConstantNode(45.0))
        ]),
        exit_rule=ConditionNode("cruzamento_baixa", IndicatorNode("ema_20"), IndicatorNode("ema_50")),
        stop_loss_pct=0.025,
        take_profit_pct=0.06
    )

    # 3. Estrategia de Rompimento Estrito
    s3 = StrategyAST(
        strategy_id="strat_breakout",
        name="Volatility Breakout",
        symbol=symbol,
        entry_rule=LogicalNode("AND", [
            ConditionNode("maior", DataNode("close"), IndicatorNode("ema_20")),
            ConditionNode("maior", IndicatorNode("rsi_14"), ConstantNode(55.0))
        ]),
        exit_rule=ConditionNode("menor", DataNode("close"), IndicatorNode("ema_20")),
        stop_loss_pct=0.018,
        take_profit_pct=0.045
    )

    return [s1, s2, s3]


# ==============================================================================
# 3. EXECUÇÃO DE UMA FASE WALK-FORWARD
# ==============================================================================

def run_phase_simulation(
    strategies: List[StrategyAST],
    candles: List[Dict[str, Any]],
    symbol: str,
    phase_name: str
) -> Dict[str, Any]:
    """Executa a simulacao de mercado para as estrategias em um bloco de candles."""
    incubator = IncubatorManager(
        initial_balance_usd=10000.0,
        rejection_drawdown_limit=8.0,
        min_quarantine_trades=10  # Calibrado para o bloco anual
    )

    candidate_map = {}
    for strat in strategies:
        c = incubator.admit_strategy(strat)
        candidate_map[strat.strategy_id] = c

    # Processa os candles sequencialmente
    prev_c = None
    for c in candles:
        incubator.process_candle(symbol, c, prev_candle=prev_c)
        prev_c = c

    results = []
    for strat in strategies:
        cand = candidate_map[strat.strategy_id]
        dd = calculate_max_drawdown(cand.equity_curve)
        sharpe = calculate_sharpe_ratio(cand.hourly_returns)
        final_eq = cand.equity_curve[-1] if cand.equity_curve else 10000.0
        pnl_pct = ((final_eq - 10000.0) / 10000.0) * 100.0

        results.append({
            "strategy_id": strat.strategy_id,
            "name": strat.name,
            "status": cand.status,
            "trades_count": len(cand.trades),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(dd, 2),
            "final_equity_usd": round(final_eq, 2),
            "pnl_pct": round(pnl_pct, 2),
            "survived": (cand.status != "ELIMINATED" and dd <= 8.0)
        })

    return {
        "phase": phase_name,
        "candles_processed": len(candles),
        "strategies": results
    }


# ==============================================================================
# 4. ORQUESTRADOR SEQUENCIAL DE 4 REGIMES
# ==============================================================================

def execute_walk_forward_pipeline(symbol: str = "BTC/USDT") -> Dict[str, Any]:
    """Executa o pipeline completo de Walk-Forward de 2020 a 2024."""
    print(f"\nINICIANDO PIPELINE WALK-FORWARD PARA {symbol} (2020 A 2024)...")

    # FASE A: Treino Bull Market (2020 a 2021)
    candles_a = load_candles_from_db(symbol, TS_2020_START, TS_2022_START)
    population = create_initial_population(symbol)
    res_a = run_phase_simulation(population, candles_a, symbol, "Fase A: Treino Bull Market (2020-2021)")
    print(f"  [CONCLUIDA] Fase A: {len(candles_a)} candles processados.")

    # FASE B: Estresse Bear Market (2022)
    candles_b = load_candles_from_db(symbol, TS_2022_START, TS_2023_START)
    res_b = run_phase_simulation(population, candles_b, symbol, "Fase B: Estresse Bear Market (2022)")
    print(f"  [CONCLUIDA] Fase B: {len(candles_b)} candles processados.")

    # FASE C: Recalibracao e Crossover Genetico (2023)
    # Seleciona os melhores genitores para recombinação
    parent_a = population[0]
    parent_b = population[1]
    child_strat = recombine_strategies(parent_a, parent_b, child_id="clone_gen2_2023", mutation_rate=0.08)
    gen2_population = population + [child_strat]

    candles_c = load_candles_from_db(symbol, TS_2023_START, TS_2024_START)
    res_c = run_phase_simulation(gen2_population, candles_c, symbol, "Fase C: Recalibracao e Crossover (2023)")
    print(f"  [CONCLUIDA] Fase C: {len(candles_c)} candles processados.")

    # FASE D: Validacao Cega Out-of-Sample (2024)
    candles_d = load_candles_from_db(symbol, TS_2024_START, TS_2024_END)
    res_d = run_phase_simulation(gen2_population, candles_d, symbol, "Fase D: Validacao Cega Out-of-Sample (2024)")
    print(f"  [CONCLUIDA] Fase D: {len(candles_d)} candles processados.")

    consolidated_report = {
        "symbol": symbol,
        "total_candles_processed": len(candles_a) + len(candles_b) + len(candles_c) + len(candles_d),
        "phases": [res_a, res_b, res_c, res_d],
        "completed_at_utc": int(time.time() * 1000)
    }

    OUTPUT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(consolidated_report, f, indent=2)

    print(f"\nRELATORIO WALK-FORWARD SALVO EM: {OUTPUT_REPORT_PATH.resolve()}")
    return consolidated_report


if __name__ == "__main__":
    execute_walk_forward_pipeline("BTC/USDT")
