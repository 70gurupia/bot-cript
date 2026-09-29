#!/usr/bin/env python3
"""
Gate 3: Cyclomatic Complexity Analyzer
Calcula a complexidade ciclomática de funções e métodos em Python, JavaScript e TypeScript.
Rejeita funções que excedem o limiar de complexidade (padrão: 10).
"""

import sys
import os
import re
import ast
import json

DEFAULT_THRESHOLD = 10
IGNORE_DIRS = {'.git', 'node_modules', 'dist', 'build', '.cache', '__pycache__', 'coverage', 'tests', 'test', 'examples', 'venv', '.venv', 'env', '.env', 'vendor'}

def analyze_python_file(filepath):
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        tree = ast.parse(code, filename=filepath)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.Assert)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1
                    elif isinstance(child, ast.IfExp):
                        complexity += 1
                
                results.append({
                    "file": filepath,
                    "function": node.name,
                    "line": node.lineno,
                    "complexity": complexity
                })
    except Exception:
        pass
    return results

FN_PATTERN = re.compile(r'(?:function\s+([a-zA-Z0-9_$]+)|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|(?:async\s+)?([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*\{)')
BRANCH_PATTERN = re.compile(r'\b(if|else\s+if|for|while|case|catch)\b|\?|\&\&|\|\||\?\?')

def extract_fn_name(match, line_idx):
    return match.group(1) or match.group(2) or match.group(3) or f"anon_L{line_idx}"

def process_js_line(line, line_idx, state, results, filepath):
    stripped = line.strip()
    if stripped.startswith(('//', '/*', '*')):
        return

    match = FN_PATTERN.search(line)
    if match and not state['in_fn']:
        state['name'] = extract_fn_name(match, line_idx)
        state['comp'] = 1
        state['line'] = line_idx
        state['in_fn'] = True
        state['depth'] = 0

    if state['in_fn']:
        state['depth'] += line.count('{') - line.count('}')
        state['comp'] += len(BRANCH_PATTERN.findall(line))
        if state['depth'] <= 0 and ('{' in line or '}' in line):
            results.append({
                "file": filepath,
                "function": state['name'],
                "line": state['line'],
                "complexity": state['comp']
            })
            state['in_fn'] = False

def analyze_js_ts_file(filepath):
    results = []
    state = {'in_fn': False, 'name': None, 'comp': 1, 'line': 1, 'depth': 0}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f, start=1):
                process_js_line(line, idx, state, results, filepath)
    except Exception:
        pass
    return results

def audit_complexity(repo_path=".", threshold=DEFAULT_THRESHOLD):
    violations = []
    all_functions = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            fp = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            
            fns = []
            if ext == '.py':
                fns = analyze_python_file(fp)
            elif ext in ['.ts', '.js', '.tsx', '.jsx', '.mjs']:
                fns = analyze_js_ts_file(fp)
                
            all_functions.extend(fns)
            for fn in fns:
                if fn['complexity'] > threshold:
                    violations.append(fn)

    return violations, all_functions

def main():
    repo_path = "."
    threshold = DEFAULT_THRESHOLD
    json_mode = "--json" in sys.argv

    for arg in sys.argv[1:]:
        if arg.isdigit():
            threshold = int(arg)
        elif not arg.startswith("--") and os.path.exists(arg):
            repo_path = arg

    violations, all_functions = audit_complexity(repo_path, threshold)

    if json_mode:
        print(json.dumps({
            "gate": "gate-3-complexity",
            "passed": len(violations) == 0,
            "threshold": threshold,
            "total_functions_analyzed": len(all_functions),
            "violations_count": len(violations),
            "violations": violations
        }, indent=2))
        sys.exit(0 if len(violations) == 0 else 1)

    print(f"🧠 === [Gate 3] Análise de Complexidade Ciclomática (Threshold: {threshold}) ===")
    print(f"  Total de funções analisadas: {len(all_functions)}")
    
    if len(violations) == 0:
        max_c = max([f['complexity'] for f in all_functions]) if all_functions else 1
        print(f"✅ Aprovado: Nenhuma função excedeu a complexidade máxima permitida (Maior complexidade encontrada: {max_c}).")
        sys.exit(0)
    else:
        print(f"❌ Falha de Complexidade: {len(violations)} função(ões) excedem o limite de {threshold}:\n")
        for v in violations:
            print(f"  - {v['file']}:{v['line']} -> Função '{v['function']}' (Complexidade: {v['complexity']})")
        print("\n💡 Remediação: Refatore dividindo em funções menores, usando early returns, guard clauses ou lookup tables.")
        sys.exit(1)

if __name__ == "__main__":
    main()
