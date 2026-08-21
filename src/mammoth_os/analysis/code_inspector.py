import ast
import os
from typing import Dict, Any


def analyze_codebase(path: str) -> Dict[str, Any]:
    """Lightweight static analysis across a codebase path.

    Returns metrics: file_count, total_lines, functions (count), classes (count), todos (list)
    """
    metrics = {
        "file_count": 0,
        "total_lines": 0,
        "functions": 0,
        "classes": 0,
        "todos": [],
        "files": {},
    }

    for root, dirs, files in os.walk(path):
        for fn in files:
            if not fn.endswith('.py'):
                continue
            metrics["file_count"] += 1
            full = os.path.join(root, fn)
            try:
                with open(full, 'r', encoding='utf-8') as fh:
                    src = fh.read()
            except Exception:
                continue
            metrics["total_lines"] += src.count('\n') + 1
            # simple AST parse
            try:
                tree = ast.parse(src)
                fcount = sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))
                ccount = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
                metrics["functions"] += fcount
                metrics["classes"] += ccount
                metrics["files"][os.path.relpath(full, path)] = {
                    "lines": src.count('\n') + 1,
                    "functions": fcount,
                    "classes": ccount,
                }
            except Exception:
                # record parse error
                metrics["files"][os.path.relpath(full, path)] = {"parse_error": True}

            # collect TODO/FIXME markers
            for i, line in enumerate(src.splitlines(), start=1):
                if 'TODO' in line or 'FIXME' in line:
                    metrics["todos"].append({"file": os.path.relpath(full, path), "line": i, "text": line.strip()})

    return metrics
