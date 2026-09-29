#!/usr/bin/env python3
"""
Gate 0: Repository Cleanliness & Essential Material Validator
Verifica se o repositório contém apenas arquivos essenciais, bloqueando binários,
rascunhos, logs, arquivos de build e saídas pesadas rastreadas pelo Git.
"""

import sys
import os
import re
import subprocess
import json

FORBIDDEN_PATTERNS = [
    (r'\.(docx|xlsx|pptx|doc|xls|ppt|pdf)$', 'Documentos binários de escritório não devem ser versionados no Git'),
    (r'\.log$', 'Arquivos de log não devem ser commitados'),
    (r'\.tmp$', 'Arquivos temporários .tmp detectados'),
    (r'(^|/)PROMPT[_-][^/]*\.md$|^PROMPT\.md$', 'Arquivos de rascunho de prompt detectados na raiz'),
    (r'(^|/)patch_.*\.py$', 'Scripts scratch de patch temporário detectados'),
    (r'(^|/)\.DS_Store$', 'Arquivos de metadados do macOS (.DS_Store)'),
    (r'(^|/)Thumbs\.db$', 'Arquivos de cache do Windows (Thumbs.db)'),
    (r'^build/.*\.js$', 'Código transpilado em build/ não deve ser versionado no Git'),
    (r'^output/.*\.(html|mmd|meta\.json)$', 'Arquivos de saída de diagramas em output/ não devem ser rastreados no Git'),
    (r'(^|/)test\.ts$', 'Testes legados soltos na raiz (organize na pasta tests/)'),
    (r'(^|/)test-v2\.ts$', 'Testes legados soltos na raiz (organize na pasta tests/)'),
]

def get_tracked_files(repo_path="."):
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception:
        # Fallback para varredura de filesystem
        files = []
        for root, _, filenames in os.walk(repo_path):
            if any(x in root for x in ['.git', 'node_modules', 'venv', '.venv', 'dist', 'build']):
                continue
            for f in filenames:
                rel = os.path.relpath(os.path.join(root, f), repo_path)
                files.append(rel)
        return files

def audit_cleanliness(repo_path="."):
    tracked = get_tracked_files(repo_path)
    violations = []

    for file_path in tracked:
        for pattern, reason in FORBIDDEN_PATTERNS:
            if re.search(pattern, file_path, re.IGNORECASE):
                violations.append({
                    "file": file_path,
                    "reason": reason,
                    "pattern": pattern
                })
                break

    return violations

def main():
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    json_mode = "--json" in sys.argv

    violations = audit_cleanliness(repo_path)

    if json_mode:
        print(json.dumps({
            "gate": "gate-0-cleanliness",
            "passed": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations
        }, indent=2))
        sys.exit(0 if len(violations) == 0 else 1)

    print("🛡️ === [Gate 0] Auditoria de Limpeza e Arquivos Essenciais ===")
    if len(violations) == 0:
        print("✅ Aprovado: O repositório está limpo e contém apenas material essencial.")
        sys.exit(0)
    else:
        print(f"❌ Falha: {len(violations)} arquivo(s) não-essenciais ou temporários detectados no Git:\n")
        for v in violations:
            print(f"  - {v['file']}: {v['reason']}")
        print("\n💡 Remediação: Remova esses arquivos do Git ('git rm --cached <arquivo>') e adicione as regras ao .gitignore.")
        sys.exit(1)

if __name__ == "__main__":
    main()
