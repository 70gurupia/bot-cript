#!/usr/bin/env python3
"""
Gate 4: Architecture & Circular Dependency Analyzer
Analisa o grafo de importações do repositório e bloqueia dependências circulares (BLOCKER de arquitetura).
"""

import sys
import os
import re
import json

IGNORE_DIRS = {'.git', 'node_modules', 'dist', 'build', '.cache', '__pycache__', 'coverage', 'tests', 'test', 'venv', '.venv', 'env', '.env', 'vendor'}

def extract_imports_ts_js(filepath, root_dir):
    imports = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Matches: import ... from './path' or require('./path')
        rel_pattern = re.compile(r'(?:from\s+[\'"]|require\([\'"])((\.\/|\.\.\/)[^\'"]+)[\'"]')
        matches = rel_pattern.findall(content)
        
        file_dir = os.path.dirname(filepath)
        for m in matches:
            rel_import = m[0]
            # Resolve relative import to absolute normalized path
            target_path = os.path.normpath(os.path.join(file_dir, rel_import))
            
            # Tentar extensões comuns (.ts, .js, .tsx, .jsx, /index.ts, etc.)
            possible_targets = [
                target_path,
                target_path + '.ts',
                target_path + '.js',
                target_path + '.tsx',
                target_path + '.jsx',
                os.path.join(target_path, 'index.ts'),
                os.path.join(target_path, 'index.js')
            ]
            
            for pt in possible_targets:
                if os.path.isfile(pt):
                    imports.append(os.path.relpath(pt, root_dir))
                    break
    except Exception:
        pass
    return imports

def extract_imports_python(filepath, root_dir):
    imports = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        rel_pattern = re.compile(r'(?:from\s+(\.[a-zA-Z0-9_.]*)\s+import|import\s+([a-zA-Z0-9_.]+))')
        file_dir = os.path.dirname(filepath)
        for m in rel_pattern.findall(content):
            imp = m[0] or m[1]
            if imp.startswith('.'):
                target_py = os.path.normpath(os.path.join(file_dir, imp.lstrip('.').replace('.', os.sep) + '.py'))
                if os.path.isfile(target_py):
                    imports.append(os.path.relpath(target_py, root_dir))
    except Exception:
        pass
    return imports

def find_cycles(graph):
    visited = {}
    rec_stack = {}
    cycles = []

    def dfs(node, path):
        visited[node] = True
        rec_stack[node] = True
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif rec_stack.get(neighbor, False):
                cycle_start_idx = path.index(neighbor)
                cycle = path[cycle_start_idx:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack[node] = False

    for n in list(graph.keys()):
        if n not in visited:
            dfs(n, [])

    return cycles

def audit_dependencies_graph(repo_path="."):
    graph = {}
    root_dir = os.path.abspath(repo_path)

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            fp = os.path.join(root, f)
            rel_file = os.path.relpath(fp, root_dir)
            ext = os.path.splitext(f)[1].lower()

            if ext in ['.ts', '.js', '.tsx', '.jsx', '.mjs']:
                imps = extract_imports_ts_js(fp, root_dir)
                graph[rel_file] = imps
            elif ext == '.py':
                imps = extract_imports_python(fp, root_dir)
                graph[rel_file] = imps

    cycles = find_cycles(graph)
    return cycles, len(graph)

def main():
    repo_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "."
    json_mode = "--json" in sys.argv

    cycles, total_modules = audit_dependencies_graph(repo_path)

    if json_mode:
        print(json.dumps({
            "gate": "gate-4-dep-structure",
            "passed": len(cycles) == 0,
            "total_modules_analyzed": total_modules,
            "cycles_count": len(cycles),
            "cycles": cycles
        }, indent=2))
        sys.exit(0 if len(cycles) == 0 else 1)

    print("🏗️ === [Gate 4] Análise de Estrutura e Dependências Circulares ===")
    print(f"  Módulos analisados: {total_modules}")

    if len(cycles) == 0:
        print("✅ Aprovado: Nenhuma dependência circular detectada no grafo de importações.")
        sys.exit(0)
    else:
        print(f"❌ Falha Arquitetural (BLOCKER): {len(cycles)} ciclo(s) de importação detectado(s):\n")
        for c in cycles:
            print("  - Ciclo: " + " -> ".join(c))
        print("\n💡 Remediação: Desacople os módulos extraindo interfaces ou tipos compartilhados para uma camada base.")
        sys.exit(1)

if __name__ == "__main__":
    main()
