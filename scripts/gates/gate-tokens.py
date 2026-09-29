#!/usr/bin/env python3
"""
Gate 1: Secrets & Credentials Scanner
Varre o repositório em busca de chaves de API, tokens, senhas hardcoded e chaves privadas.
"""

import sys
import os
import re
import subprocess
import json

SECRET_PATTERNS = [
    (r'AKIA[0-9A-Z]{16}', 'Chave de Acesso AWS (AKIA)'),
    (r'(ghp|gho|ghu|ghs|ghr)_[0-9a-zA-Z]{36}', 'Token de Acesso Pessoal GitHub'),
    (r'github_pat_[0-9a-zA-Z_]{82}', 'Fine-grained GitHub Token'),
    (r'xox[baprs]-[0-9a-zA-Z]{10,48}', 'Token de API do Slack'),
    (r'sk_live_[0-9a-zA-Z]{24,}', 'Chave de Produção Stripe (sk_live)'),
    (r'AIza[0-9A-Za-z\-_]{35}', 'Chave de API Google / Firebase (AIza)'),
    (r'-----BEGIN ((RSA|EC|DSA|OPENSSH) )?PRIVATE KEY-----', 'Chave Privada Criptográfica (RSA/SSH/EC)'),
    (r'(?i)(password|senha|secret|api_key|access_token)\s*[:=]\s*["\']([^"\'\s]{8,})["\']', 'Possível senha ou token hardcoded'),
    (r'(postgres|mysql|mongodb|redis):\/\/[a-zA-Z0-9_-]+:[^@\s]+@[a-zA-Z0-9.-]+', 'URI de Banco de Dados com credenciais expostas'),
]

IGNORE_DIRS = {'.git', 'node_modules', 'dist', 'build', '.cache', '__pycache__', 'coverage', '.pytest_cache', 'tests', 'test', 'venv', '.venv', 'env', '.env', 'vendor'}
IGNORE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.pdf', '.woff', '.woff2', '.ttf', '.eot', '.lock'}

SAFE_WORDS = {'placeholder', 'example', 'dummy', 'mock', 'fake', 'test', 'your_', 'your-', 'your_key', 'your-key', 'sample', 'change_me', 'mysecret', 'dummy_key', 'test_key'}

def is_safe_value(val):
    v = val.lower()
    return any(w in v for w in SAFE_WORDS)

def scan_file(file_path):
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_idx, line in enumerate(f, start=1):
                if is_safe_value(line):
                    continue
                for pattern, desc in SECRET_PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        matched_str = match.group(0)
                        if is_safe_value(matched_str):
                            continue
                        # Redigir parcialmente para log seguro
                        redacted = matched_str[:4] + "..." + matched_str[-4:] if len(matched_str) > 8 else "***"
                        findings.append({
                            "file": file_path,
                            "line": line_idx,
                            "description": desc,
                            "snippet": redacted
                        })
    except Exception:
        pass
    return findings

def audit_secrets(repo_path="."):
    all_findings = []
    
    # Se estiver em repo git, usar git ls-files
    try:
        res = subprocess.run(["git", "ls-files"], cwd=repo_path, capture_output=True, text=True, check=True)
        files = [os.path.join(repo_path, f.strip()) for f in res.stdout.splitlines() if f.strip()]
    except Exception:
        files = []
        for root, dirs, fnames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fn in fnames:
                files.append(os.path.join(root, fn))

    for fp in files:
        if not os.path.isfile(fp):
            continue
        ext = os.path.splitext(fp)[1].lower()
        if ext in IGNORE_EXTS:
            continue
        if any(ignored in fp.split(os.sep) for ignored in IGNORE_DIRS):
            continue
        
        # Bloquear arquivos .env com conteúdo real
        if os.path.basename(fp) == '.env':
            all_findings.append({
                "file": fp,
                "line": 1,
                "description": "Arquivo .env rastreado pelo Git (use .env.example sem segredos)",
                "snippet": ".env"
            })
            continue

        findings = scan_file(fp)
        all_findings.extend(findings)

    return all_findings

def main():
    repo_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "."
    json_mode = "--json" in sys.argv

    findings = audit_secrets(repo_path)

    if json_mode:
        print(json.dumps({
            "gate": "gate-1-secrets",
            "passed": len(findings) == 0,
            "findings_count": len(findings),
            "findings": findings
        }, indent=2))
        sys.exit(0 if len(findings) == 0 else 1)

    print("🔑 === [Gate 1] Varredura de Segredos e Credenciais ===")
    if len(findings) == 0:
        print("✅ Aprovado: Nenhum segredo, token ou chave privada exposta no repositório.")
        sys.exit(0)
    else:
        print(f"❌ Falha de Segurança: {len(findings)} possível(is) segredo(s) detectado(s):\n")
        for f in findings:
            print(f"  - {f['file']}:{f['line']} -> {f['description']} (Valor: {f['snippet']})")
        print("\n💡 Remediação: Remova o segredo imediatamente, invalide a chave no provedor e utilize variáveis de ambiente seguras (GitHub Secrets).")
        sys.exit(1)

if __name__ == "__main__":
    main()
