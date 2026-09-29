#!/usr/bin/env python3
"""
Gate 6: PR Quality & Governance Reporter Bot
Executa a bateria de gates de qualidade e gera uma tabela Markdown detalhada
para publicação automática em comentários de Pull Requests no GitHub Actions.
"""

import sys
import os
import subprocess
import json
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_gate(script_name, repo_path="."):
    script_path = os.path.join(SCRIPT_DIR, script_name)
    try:
        res = subprocess.run(
            [sys.executable, script_path, repo_path, "--json"],
            capture_output=True,
            text=True
        )
        data = json.loads(res.stdout) if res.stdout else {"passed": res.returncode == 0}
        return res.returncode == 0, data
    except Exception as e:
        return False, {"error": str(e), "passed": False}

def generate_report(repo_path="."):
    gates = [
        ("gate-cleanliness.py", "🧹 Repository Cleanliness", "Bloqueio de binários, rascunhos, logs e build no Git"),
        ("gate-secrets.py", "🔑 Secrets & Credenciais", "Varredura de chaves AWS, GitHub, tokens e .env"),
        ("gate-dependencies.py", "📌 Dependency Pinning", "Validação de versões exatas sem *, latest ou ranges"),
        ("gate-complexity.py", "🧠 Complexidade Ciclomática", "Limite máximo de complexidade ciclomática <= 10"),
        ("gate-dep-structure.py", "🏗️ Arquitetura & Ciclos", "Detecção de dependências e importações circulares"),
        ("gate-sast.py", "🛡️ Segurança SAST OWASP", "Varredura de injeções, path traversal e execução dinâmica"),
    ]

    results = []
    overall_passed = True

    for script, name, desc in gates:
        passed, data = run_gate(script, repo_path)
        if not passed:
            overall_passed = False
        results.append({
            "name": name,
            "description": desc,
            "passed": passed,
            "details": data
        })

    # Construir Markdown
    status_emoji = "✅" if overall_passed else "❌"
    status_text = "APROVADO" if overall_passed else "REPROVADO"

    md = f"## 🤖 Quality Gates Report: {status_emoji} {status_text}\n\n"
    md += f"> Auditoria automática de governança, segurança e qualidade de código.\n\n"
    md += "| Gate de Qualidade | Status | Descrição |\n"
    md += "|---|:---:|---|\n"

    for r in results:
        badge = "✅ **PASS**" if r["passed"] else "❌ **FAIL**"
        md += f"| {r['name']} | {badge} | {r['description']} |\n"

    md += "\n"
    if not overall_passed:
        md += "### ⚠️ Ações Necessárias para Desbloqueio do Merge:\n\n"
        for r in results:
            if not r["passed"]:
                md += f"- **{r['name']}:** Identificadas violações que violam as políticas de governança.\n"
    else:
        md += "🎉 **Todos os gates foram validados com 100% de conformidade!**\n"

    return overall_passed, results, md

def post_github_comment(markdown_body):
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    pr_number = os.getenv("PR_NUMBER")

    if not token or not repo or not pr_number:
        print("ℹ️ Ambiente fora do GitHub Actions PR. Relatório exibido apenas no console.")
        return

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    payload = json.dumps({"body": markdown_body}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "Quality-Gates-Bot"
    }

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                print("✅ Comentário publicado no Pull Request com sucesso.")
    except Exception as e:
        print(f"⚠️ Erro ao postar comentário no PR: {e}")

def main():
    repo_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "."
    post_comment = "--post-comment" in sys.argv or os.getenv("POST_PR_COMMENT") == "true"

    passed, results, markdown = generate_report(repo_path)
    print(markdown)

    if post_comment:
        post_github_comment(markdown)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
