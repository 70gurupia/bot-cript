#!/usr/bin/env python3
"""
Gerador de Dataset para Fine-Tuning LoRA de Day Trade (Laia / JEV / SLMs).
Extrai padrões empíricos da base histórica de 2024 e do catálogo de estratégias,
formatando exemplos de instrução/resposta em JSONL para o framework "It's Fine",
Unsloth ou LLaMA-Factory no Google Colab.
"""

from __future__ import annotations
import os
import sys
import json
import sqlite3
from typing import List, Dict, Any, Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

DB_PATH = os.path.join(ROOT_DIR, "data", "historical", "market_data.db")
OUTPUT_JSONL = os.path.join(ROOT_DIR, "data", "lora_daytrade_dataset.jsonl")


def _build_lead_lag_ex(r: tuple, nxt_r: tuple) -> Optional[Dict[str, str]]:
    """Gera exemplo de Lead-Lag rotulado."""
    b_ret = (r[1] - r[2]) / r[2]
    e_ret = (r[5] - r[6]) / r[6]
    if b_ret < 0.008 or e_ret >= 0.0025:
        return None

    e_future_ret = (nxt_r[5] - r[5]) / r[5]
    is_win = e_future_ret > 0.003
    decision = "EXECUTE_LEAD_LAG" if is_win else "WAIT_CONFIRMATION"
    risk = "ANTI_MARTINGALE_EXPAND" if is_win else "BASE_RISK_RESET"

    return {
        "instruction": "Você é um supervisor quantitativo de day trade cripto. Analise o estado dos ativos em 15m e determine a ação operacional e o modo de gestão de risco.",
        "input": f"Ativo Líder BTCUSDT 15m retorno: {b_ret*100:+.2f}%. Ativo Seguidor ETHUSDT 15m retorno: {e_ret*100:+.2f}%. Volatilidade: Moderada. Funding Rate: 0.025%.",
        "output": json.dumps({
            "action": decision,
            "target_pair": "ETHUSDT",
            "side": "BUY" if decision == "EXECUTE_LEAD_LAG" else "NONE",
            "risk_management": risk,
            "confidence": 0.88 if is_win else 0.55,
            "reasoning": "Descompasso temporal evidente entre a explosão do BTC e a inércia do ETH. Probabilidade histórica favorável de convergência rápida." if is_win else "Movimento sem confirmação suficiente de volume institucional no líder."
        }, ensure_ascii=False)
    }


def _build_scalp_ex(r: tuple) -> Optional[Dict[str, str]]:
    """Gera exemplo de compressão e micro-scalp."""
    b_rng = (r[3] - r[4]) / r[4]
    if b_rng > 0.0020:
        return None

    return {
        "instruction": "Você é um supervisor quantitativo de day trade cripto. Analise o estado dos ativos em 15m e determine a ação operacional e o modo de gestão de risco.",
        "input": f"BTCUSDT em compressão de range estreito: {b_rng*100:.2f}%. Bandas de Bollinger comprimidas. Volume relativo: Baixo.",
        "output": json.dumps({
            "action": "ACTIVATE_CENT_SCALPER",
            "target_pair": "BTCUSDT",
            "side": "MAKER_GRID",
            "risk_management": "FIXED_FRACTIONAL_MAKER",
            "confidence": 0.82,
            "reasoning": "Mercado em regime de consolidação e ruído. Ativação de micro-scalp com ordens limite passivas Maker para captura de 0.25% de retorno à média."
        }, ensure_ascii=False)
    }


def generate_training_examples(db_path: str, max_samples: int = 500) -> List[Dict[str, str]]:
    """Gera pares instrucao-entrada-saida baseados nos eventos historicos de 2024."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT b.open_time, b.close_price, b.open_price, b.high_price, b.low_price,
               e.close_price, e.open_price
        FROM klines_15m b
        JOIN klines_15m e ON b.open_time = e.open_time AND e.symbol = 'ETHUSDT'
        WHERE b.symbol = 'BTCUSDT' AND b.open_time >= 1704067200000
        ORDER BY b.open_time ASC
        LIMIT 4000;
    """)
    rows = cur.fetchall()
    conn.close()

    dataset = []
    for i in range(1, len(rows) - 2):
        if len(dataset) >= max_samples:
            break

        r = rows[i]
        nxt_r = rows[i + 2]

        ex_lead = _build_lead_lag_ex(r, nxt_r)
        if ex_lead:
            dataset.append(ex_lead)

        ex_scalp = _build_scalp_ex(r)
        if ex_scalp:
            dataset.append(ex_scalp)

    return dataset


def main():
    print("==================================================================")
    print("GERADOR DE DATASET PARA FINE-TUNING LoRA (LAIA / JEV / SLMs)")
    print("==================================================================")
    print(f"Banco de Dados: {DB_PATH}")

    examples = generate_training_examples(DB_PATH, max_samples=400)
    print(f"Exemplos de treino gerados: {len(examples)}")

    os.makedirs(os.path.dirname(OUTPUT_JSONL), exist_ok=True)
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"[OK] Dataset JSONL salvo em: {OUTPUT_JSONL}")
    print("\nExemplo da primeira amostra gerada:")
    if examples:
        print(json.dumps(examples[0], indent=2, ensure_ascii=False))
    print("==================================================================\n")


if __name__ == "__main__":
    main()
