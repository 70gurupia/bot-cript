#!/usr/bin/env python3
"""
Orquestrador Central e Executor de Quality Gates Deterministicos.
Executa sequencialmente todos os 9 Quality Gates do projeto bot-cript:
1. Gate 0: Limpeza do Repositorio (gate-cleanliness.py)
2. Gate 1: Varredura de Segredos e Chaves (gate-tokens.py)
3. Gate 2: Pinning Estrito de Dependencias (gate-dependencies.py)
4. Gate 3: Complexidade Ciclomatica <= 10 (gate-complexity.py)
5. Gate 4: Estrutura Modular e Dependencias Circulares (gate-dep-structure.py)
6. Gate 5: Seguranca SAST OWASP (gate-sast.py)
7. Gate 6: Regras de Linguagem Natural e Proibicao de Travessao (gate-nlp-rules.py)
8. Gate 7: Invariantes Financeiros e Travas de Risco (gate-financial-invariants.py)
9. Gate 8: Evals Deterministicos de IA e Estrategias (gate-deterministic-evals.py)
"""

from __future__ import annotations
import sys
import os
import json
import time
import subprocess
from typing import List, Dict, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

GATES = [
    {
        "id": "GATE_0",
        "name": "Limpeza do Repositorio",
        "cmd": [sys.executable, "scripts/gates/gate-cleanliness.py", "."]
    },
    {
        "id": "GATE_1",
        "name": "Varredura de Segredos e Chaves",
        "cmd": [sys.executable, "scripts/gates/gate-tokens.py", "."]
    },
    {
        "id": "GATE_2",
        "name": "Pinning de Dependencias",
        "cmd": [sys.executable, "scripts/gates/gate-dependencies.py", "."]
    },
    {
        "id": "GATE_3",
        "name": "Complexidade Ciclomatica (max 10)",
        "cmd": [sys.executable, "scripts/gates/gate-complexity.py", ".", "10"]
    },
    {
        "id": "GATE_4",
        "name": "Estrutura Modular e Sem Ciclos",
        "cmd": [sys.executable, "scripts/gates/gate-dep-structure.py", "."]
    },
    {
        "id": "GATE_5",
        "name": "Varredura SAST OWASP",
        "cmd": [sys.executable, "scripts/gates/gate-sast.py", "."]
    },
    {
        "id": "GATE_6",
        "name": "NLP: Sem Travessao e Gramatica pt-BR",
        "cmd": [sys.executable, "scripts/gates/gate-nlp-rules.py", "."]
    },
    {
        "id": "GATE_7",
        "name": "Invariantes Financeiros e Limites de Risco",
        "cmd": [sys.executable, "scripts/gates/gate-financial-invariants.py", "."]
    },
    {
        "id": "GATE_8",
        "name": "Evals Deterministicos de IA e Estrategias",
        "cmd": [sys.executable, "scripts/gates/gate-deterministic-evals.py"]
    }
]


def execute_single_gate(gate_info: Dict[str, Any]) -> Dict[str, Any]:
    """Executa um gate individual e coleta seu status e duracao."""
    t0 = time.time()
    res = subprocess.run(
        gate_info["cmd"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True
    )
    duration_sec = round(time.time() - t0, 3)
    passed = (res.returncode == 0)

    return {
        "id": gate_info["id"],
        "name": gate_info["name"],
        "passed": passed,
        "duration_sec": duration_sec,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
    }


def save_report(report: Dict[str, Any], output_path: str):
    """Salva o sumario dos quality gates em formato JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def run_all_gates() -> Dict[str, Any]:
    """Executa toda a bateria de quality gates."""
    gate_results = []
    all_passed = True

    print("==================================================================")
    print("ORQUESTRADOR DE QUALITY GATES DETERMINISTICOS DO BOT-CRIPT")
    print("==================================================================")

    for g in GATES:
        print(f"Executando {g['id']}: {g['name']}...", end=" ", flush=True)
        r = execute_single_gate(g)
        gate_results.append(r)

        if r["passed"]:
            print(f"[OK] ({r['duration_sec']}s)")
        else:
            print(f"[FALHA] ({r['duration_sec']}s)")
            all_passed = False
            if r["stdout"]:
                print(f"\n--- Detalhes da saida ({g['id']}) ---")
                print(r["stdout"][:800])
            if r["stderr"]:
                print(f"\n--- Erro ({g['id']}) ---")
                print(r["stderr"][:800])
            print("--------------------------------------------------")

    total_duration = round(sum(r["duration_sec"] for r in gate_results), 2)
    report = {
        "timestamp_utc": int(time.time() * 1000),
        "total_gates": len(GATES),
        "passed_gates": sum(1 for r in gate_results if r["passed"]),
        "failed_gates": sum(1 for r in gate_results if not r["passed"]),
        "all_passed": all_passed,
        "total_duration_sec": total_duration,
        "results": [
            {
                "id": r["id"],
                "name": r["name"],
                "passed": r["passed"],
                "duration_sec": r["duration_sec"]
            }
            for r in gate_results
        ]
    }

    report_path = os.path.join(ROOT_DIR, "data", "quality_gates_report.json")
    save_report(report, report_path)

    print("==================================================================")
    print(f"Status Final        : {'[TODOS APROVADOS]' if all_passed else '[FALHA DETECTADA]'}")
    print(f"Placar              : {report['passed_gates']}/{report['total_gates']} aprovados")
    print(f"Tempo Total         : {total_duration}s")
    print(f"Relatorio Salvo     : {report_path}")
    print("==================================================================")

    return report


def main():
    report = run_all_gates()
    sys.exit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()
