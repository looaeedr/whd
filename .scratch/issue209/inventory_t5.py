import ast
import json
from pathlib import Path

source = Path('gui.py').read_text(encoding='utf-8')
tree = ast.parse(source)
keywords = ('part', 'selector', 'panel', 'visibility', 'visible', 'child')
rows = []

for node in ast.walk(tree):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    name = node.name.lower()
    if not any(k in name for k in keywords):
        continue
    reads = set()
    writes = set()
    calls = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name) and child.value.id == 'self':
            parent_ctx = getattr(child, 'ctx', None)
            if isinstance(parent_ctx, ast.Store):
                writes.add(child.attr)
            else:
                reads.add(child.attr)
        if isinstance(child, ast.Call):
            try:
                calls.add(ast.unparse(child.func))
            except Exception:
                pass
    rows.append({
        'name': node.name,
        'line': node.lineno,
        'end_line': getattr(node, 'end_lineno', node.lineno),
        'self_reads': sorted(reads),
        'self_writes': sorted(writes),
        'calls': sorted(calls),
    })

rows.sort(key=lambda r: r['line'])
Path('.scratch/issue209/run').mkdir(parents=True, exist_ok=True)
Path('.scratch/issue209/run/ast_candidates.json').write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8'
)
print(json.dumps(rows, ensure_ascii=False, indent=2))
