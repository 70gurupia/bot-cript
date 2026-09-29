#!/usr/bin/env python3
"""
Gate 5: Static Application Security Testing (SAST)
Varre o repositório em busca de vulnerabilidades OWASP: Command Injection,
Path Traversal, eval(), SQL Injection e execução arbitrária de código.
"""

import sys
import os
import re
import json

SAST_RULES = [
    (r'\b(exec|execSync|spawnSync|popen)\s*\(\s*`[^`]*\$\{[^}]+\}[^`]*`', 'SEC-001', 'CRITICAL', 'Possível Command Injection via interpolação em template string'),
    (r'os\.system\s*\(\s*f["\']', 'SEC-001', 'CRITICAL', 'Possível Command Injection via f-string em os.system()'),
    (r'subprocess\.(Popen|run|call)\s*\([^)]*shell\s*=\s*True', 'SEC-001', 'HIGH', 'Execução de subprocesso com shell=True'),
    (r'\beval\s*\(', 'SEC-002', 'CRITICAL', 'Uso proibido de eval() para execução dinâmica'),
    (r'new\s+Function\s*\(', 'SEC-002', 'HIGH', 'Uso perigoso do construtor new Function()'),
    (r'pickle\.loads?\s*\(', 'SEC-003', 'HIGH', 'Desserialização insegura via Python pickle'),
    (r'(?i)\b(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+.+\s+SET|DELETE\s+FROM)\b.*["\']\s*\+\s*[a-zA-Z0-9_$]+', 'SEC-004', 'CRITICAL', 'Possível SQL Injection via concatenação de strings (use prepared statements)'),
    (r'document\.write\s*\(', 'SEC-005', 'MEDIUM', 'Uso perigoso de document.write() vulnerável a XSS'),
]

IGNORE_DIRS = {'.git', 'node_modules', 'dist', 'build', '.cache', '__pycache__', 'coverage', 'tests', 'test', 'venv', '.venv', 'env', '.env', 'vendor', 'Templates', 'templates'}

VALID_EXTS = {'.ts', '.js', '.tsx', '.jsx', '.py', '.go', '.rs', '.php', '.java'}

def check_line_rules(line, line_idx, rel_path):
    findings = []
    stripped = line.strip()
    if stripped.startswith(('//', '#', '*', '"""', "'''")):
        return findings
    if any(k in rel_path for k in ['gate-sast', 'sast-scanner', 'static-analyzer', 'complexity-analyzer']):
        return findings
    for pattern, rule_id, severity, desc in SAST_RULES:
        if re.search(pattern, line):
            findings.append({
                "file": rel_path,
                "line": line_idx,
                "rule_id": rule_id,
                "severity": severity,
                "description": desc,
                "snippet": stripped[:100]
            })
    return findings

def scan_sast_file(fp, repo_path):
    findings = []
    rel_path = os.path.relpath(fp, repo_path)
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as file_obj:
            for line_idx, line in enumerate(file_obj, start=1):
                findings.extend(check_line_rules(line, line_idx, rel_path))
    except Exception:
        pass
    return findings

def scan_sast(repo_path="."):
    findings = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if f.endswith('.min.js') or f.endswith('.min.css'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in VALID_EXTS:
                findings.extend(scan_sast_file(os.path.join(root, f), repo_path))
    return findings

def main():
    repo_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "."
    json_mode = "--json" in sys.argv

    findings = scan_sast(repo_path)
    critical_or_high = [f for f in findings if f['severity'] in ['CRITICAL', 'HIGH']]

    if json_mode:
        print(json.dumps({
            "gate": "gate-5-sast",
            "passed": len(critical_or_high) == 0,
            "total_findings": len(findings),
            "critical_high_count": len(critical_or_high),
            "findings": findings
        }, indent=2))
        sys.exit(0 if len(critical_or_high) == 0 else 1)

    print("🛡️ === [Gate 5] Varredura SAST de Segurança OWASP ===")
    print(f"  Total de arquivos inspecionados no repositório.")

    if len(critical_or_high) == 0:
        print("✅ Aprovado: Nenhuma vulnerabilidade crítica ou de alta severidade detectada.")
        sys.exit(0)
    else:
        print(f"❌ Falha de Segurança SAST: {len(critical_or_high)} problema(s) de alta/crítica severidade:\n")
        for f in critical_or_high:
            print(f"  [{f['severity']}] {f['file']}:{f['line']} -> {f['rule_id']}: {f['description']}")
            print(f"    Código: {f['snippet']}")
        print("\n💡 Remediação: Remova funções perigosas (eval), utilize queries parametrizadas e sanitize inputs.")
        sys.exit(1)

if __name__ == "__main__":
    main()
