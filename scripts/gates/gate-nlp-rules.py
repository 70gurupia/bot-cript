#!/usr/bin/env python3
"""
Gate Determinístico: Validador de Regras de Linguagem Natural e Ausencia de Travessao.
Enforce estrito da diretriz operacional de proibicao absoluta do caractere de travessao.
Inspeciona arquivos rastreados de codigo, documentacao e configuracao.
"""

from __future__ import annotations
import sys
import os
import subprocess
import json
from typing import List, Dict, Any

FORBIDDEN_CHAR = "\u2014"  # Caractere proibido: travessao
VALID_EXTENSIONS = (".py", ".md", ".json", ".yml", ".yaml", ".html", ".sh")
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}


def get_target_files(repo_path: str = ".") -> List[str]:
    """Obtem lista de arquivos versionados relevantes para inspecao textual."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        return [f for f in files if f.endswith(VALID_EXTENSIONS)]
    except Exception:
        collected = []
        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for fn in filenames:
                if fn.endswith(VALID_EXTENSIONS):
                    collected.append(os.path.relpath(os.path.join(root, fn), repo_path))
        return collected


def scan_file_for_violations(file_path: str) -> List[Dict[str, Any]]:
    """Varre um arquivo linha a linha procurando ocorrencias do caractere de travessao."""
    violations = []
    if not os.path.exists(file_path):
        return violations

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
            for line_num, line in enumerate(fp, start=1):
                if FORBIDDEN_CHAR in line:
                    violations.append({
                        "file": file_path,
                        "line": line_num,
                        "content": line.strip()[:100],
                        "rule": "PROIBICAO_ABSOLUTA_DE_TRAVESSAO"
                    })
    except Exception:
        pass
    return violations


def audit_nlp_rules(repo_path: str = ".") -> Dict[str, Any]:
    """Executa a auditoria deterministica completa no repositorio."""
    files = get_target_files(repo_path)
    all_violations = []

    for rel_path in files:
        full_path = os.path.join(repo_path, rel_path)
        viols = scan_file_for_violations(full_path)
        all_violations.extend(viols)

    return {
        "gate": "GATE_NLP_RULES",
        "passed": len(all_violations) == 0,
        "files_analyzed": len(files),
        "total_violations": len(all_violations),
        "violations": all_violations
    }


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    res = audit_nlp_rules(repo)

    print("==================================================================")
    print("GATE DETERMINISTICO: REGRAS DE LINGUAGEM NATURAL E ZERO TRAVESSOES")
    print("==================================================================")
    print(f"Arquivos analisados : {res['files_analyzed']}")
    print(f"Total de violacoes  : {res['total_violations']}")
    print(f"Status do Gate      : {'[APROVADO]' if res['passed'] else '[REPROVADO]'}")
    print("==================================================================")

    if not res["passed"]:
        print("\nOcorrencias de travessao encontradas:")
        for v in res["violations"][:15]:
            print(f" - {v['file']}:{v['line']} -> {v['content']}")
        if len(res["violations"]) > 15:
            print(f" ... e mais {len(res['violations']) - 15} ocorrencias.")
        sys.exit(1)

    print("Conformidade confirmada: zero caracteres de travessao em todo o projeto.")
    sys.exit(0)


if __name__ == "__main__":
    main()
