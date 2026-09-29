#!/usr/bin/env python3
"""
Gate 2: Strict Dependency Pinning Validator
Valida se todas as dependências de terceiros estão com versões exatas pinadas,
bloqueando 'latest', '*', '^', '~', ranges soltos em package.json, requirements.txt, Cargo.toml, etc.
"""

import sys
import os
import re
import json

FLOATING_PREFIXES = ('^', '~', '>', '<')
FLOATING_EXACT = {'*', 'latest', 'workspace:*'}

def is_floating_version(ver):
    return ver in FLOATING_EXACT or ver.startswith(FLOATING_PREFIXES)

def check_dep_map(filepath, sec, deps):
    issues = []
    if not isinstance(deps, dict):
        return issues
    for pkg, ver in deps.items():
        if is_floating_version(ver):
            issues.append({
                "file": filepath,
                "package": pkg,
                "version": ver,
                "reason": f"Versão flutuante '{ver}' em {sec}. Use versão exata (ex: '1.2.3')."
            })
    return issues

def check_package_json(filepath):
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for sec in ['dependencies', 'devDependencies', 'peerDependencies']:
            issues.extend(check_dep_map(filepath, sec, data.get(sec, {})))
    except Exception as e:
        issues.append({"file": filepath, "package": "N/A", "version": "N/A", "reason": f"Erro ao ler JSON: {str(e)}"})
    return issues

def check_requirements_txt(filepath):
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f, start=1):
                clean = line.strip()
                if not clean or clean.startswith('#') or clean.startswith('-r') or clean.startswith('-e'):
                    continue
                if '==' not in clean:
                    issues.append({
                        "file": filepath,
                        "line": line_idx,
                        "package": clean,
                        "reason": f"Dependência Python '{clean}' sem versão exata '=='. Pinar ex: 'requests==2.31.0'."
                    })
    except Exception as e:
        issues.append({"file": filepath, "package": "N/A", "reason": f"Erro ao ler arquivo: {str(e)}"})
    return issues

def check_cargo_toml(filepath):
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f, start=1):
                clean = line.strip()
                if clean.startswith('#') or not clean:
                    continue
                if 'version = "*"' in clean or 'version = "^' in clean:
                    issues.append({
                        "file": filepath,
                        "line": line_idx,
                        "package": clean,
                        "reason": f"Dependência Cargo com range flutuante: '{clean}'."
                    })
    except Exception as e:
        issues.append({"file": filepath, "package": "N/A", "reason": f"Erro ao ler Cargo.toml: {str(e)}"})
    return issues

def audit_dependencies(repo_path="."):
    all_issues = []
    
    for root, dirs, files in os.walk(repo_path):
        if any(x in root for x in ['node_modules', '.git', 'dist', 'build', 'venv', '.venv', 'env']):
            continue
            
        for f in files:
            fp = os.path.join(root, f)
            if f == 'package.json':
                all_issues.extend(check_package_json(fp))
            elif f in ['requirements.txt', 'requirements-dev.txt', 'requirements-prod.txt']:
                all_issues.extend(check_requirements_txt(fp))
            elif f == 'Cargo.toml':
                all_issues.extend(check_cargo_toml(fp))

    return all_issues

def main():
    repo_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "."
    json_mode = "--json" in sys.argv

    issues = audit_dependencies(repo_path)

    if json_mode:
        print(json.dumps({
            "gate": "gate-2-dependencies",
            "passed": len(issues) == 0,
            "issues_count": len(issues),
            "issues": issues
        }, indent=2))
        sys.exit(0 if len(issues) == 0 else 1)

    print("📌 === [Gate 2] Validação de Pinning de Dependências ===")
    if len(issues) == 0:
        print("✅ Aprovado: Todas as dependências do projeto estão devidamente pinadas com versão exata.")
        sys.exit(0)
    else:
        print(f"❌ Falha de Governança: {len(issues)} dependência(s) com versão flutuante/não-pinada:\n")
        for iss in issues:
            pkg = iss.get('package', 'Desconhecido')
            print(f"  - {iss['file']}: {pkg} -> {iss['reason']}")
        print("\n💡 Remediação: Altere para a versão exata no manifesto de dependências para evitar quebras em builds futuras.")
        sys.exit(1)

if __name__ == "__main__":
    main()
