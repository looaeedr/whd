#!/usr/bin/env python3
"""Issue #288 T0 AST inventory for gui.py.

QA-only diagnostic. It reports structure and dependency signals without changing
production behavior or importing gui.py.
"""
from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path("gui.py")
OUT = Path(".scratch/issue288")
OUT.mkdir(parents=True, exist_ok=True)

text = SOURCE.read_text(encoding="utf-8")
lines = text.splitlines()
tree = ast.parse(text, filename=str(SOURCE))


def qual_call(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = qual_call(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def span(node: ast.AST) -> int:
    return max(1, int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno) + 1)


def assigned_self_attrs(node: ast.AST) -> list[str]:
    attrs: set[str] = set()
    for child in ast.walk(node):
        targets = []
        if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = list(getattr(child, "targets", []))
            if hasattr(child, "target"):
                targets.append(child.target)
        for target in targets:
            for t in ast.walk(target):
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                    attrs.add(t.attr)
    return sorted(attrs)


def calls_in(node: ast.AST) -> list[str]:
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = qual_call(child.func)
            if name:
                calls.append(name)
    return calls


def classify_calls(calls: list[str]) -> dict[str, list[str]]:
    out = defaultdict(set)
    for c in calls:
        low = c.lower()
        if c.startswith(("tk.", "ttk.")) or any(x in low for x in (".pack", ".grid", ".place", ".bind", "messagebox", "filedialog", "create_window")):
            out["widget_ui"].add(c)
        if any(x in low for x in ("render", "draw", "canvas", "create_line", "create_polygon", "create_oval", "create_text")):
            out["render"].add(c)
        if any(x in low for x in ("save", "load", "read_project", "write_project", "project_controller", "filedialog")):
            out["persistence_project"].add(c)
        if any(x in low for x in ("geometry", "build_", "resolve_", "fold", "profile", "placement", "feature", "dimension")):
            out["geometry_projection_signal"].add(c)
        if any(x in low for x in ("visibility", "visible", "hide", "show")):
            out["visibility"].add(c)
    return {k: sorted(v) for k, v in sorted(out.items())}


def nested_defs(node: ast.AST) -> list[dict]:
    result = []
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.append({"name": child.name, "line": child.lineno, "end_line": child.end_lineno, "lines": span(child)})
    return sorted(result, key=lambda x: x["line"])

records = []
classes = []
top_functions = []

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        calls = calls_in(node)
        rec = {
            "kind": "function",
            "qualname": node.name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "lines": span(node),
            "nested_defs": nested_defs(node),
            "self_writes": assigned_self_attrs(node),
            "call_categories": classify_calls(calls),
            "calls": sorted(set(calls)),
        }
        records.append(rec)
        top_functions.append(rec)
    elif isinstance(node, ast.ClassDef):
        methods = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = calls_in(child)
                rec = {
                    "kind": "method",
                    "qualname": f"{node.name}.{child.name}",
                    "class": node.name,
                    "name": child.name,
                    "line": child.lineno,
                    "end_line": child.end_lineno,
                    "lines": span(child),
                    "nested_defs": nested_defs(child),
                    "self_writes": assigned_self_attrs(child),
                    "call_categories": classify_calls(calls),
                    "calls": sorted(set(calls)),
                }
                records.append(rec)
                methods.append(rec)
        classes.append({
            "name": node.name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "lines": span(node),
            "bases": [ast.unparse(b) for b in node.bases],
            "method_count": len(methods),
            "methods": methods,
        })

imports = []
for node in tree.body:
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.append({"kind": "import", "module": alias.name, "name": alias.asname or alias.name})
    elif isinstance(node, ast.ImportFrom):
        imports.append({"kind": "from", "module": node.module or "", "names": [a.name for a in node.names]})

all_calls = []
for rec in records:
    all_calls.extend(rec["calls"])

self_write_counts = Counter()
for rec in records:
    self_write_counts.update(rec["self_writes"])

large_methods = sorted((r for r in records if r["lines"] > 150), key=lambda r: (-r["lines"], r["line"]))
large_classes = sorted((c for c in classes if c["lines"] > 800), key=lambda c: (-c["lines"], c["line"]))
nested = []
for r in records:
    for d in r["nested_defs"]:
        nested.append({"parent": r["qualname"], **d})
nested.sort(key=lambda x: (-x["lines"], x["line"]))

payload = {
    "source": str(SOURCE),
    "loc": len(lines),
    "top_level_function_count": len(top_functions),
    "class_count": len(classes),
    "method_count": sum(c["method_count"] for c in classes),
    "nested_function_count": len(nested),
    "imports": imports,
    "classes": classes,
    "top_level_functions": top_functions,
    "large_methods_over_150": large_methods,
    "large_classes_over_800": large_classes,
    "largest_nested_functions": nested[:100],
    "self_write_attributes": dict(self_write_counts.most_common()),
    "call_category_counts": {
        category: sum(len(r["call_categories"].get(category, [])) for r in records)
        for category in ["widget_ui", "render", "persistence_project", "geometry_projection_signal", "visibility"]
    },
}

(OUT / "gui_ast_inventory.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

md = []
md.append("# Issue #288 gui.py AST inventory\n")
md.append(f"- LOC: **{payload['loc']}**")
md.append(f"- top-level functions: **{payload['top_level_function_count']}**")
md.append(f"- classes: **{payload['class_count']}**")
md.append(f"- methods: **{payload['method_count']}**")
md.append(f"- nested functions: **{payload['nested_function_count']}**")
md.append(f"- classes >800 lines: **{len(large_classes)}**")
md.append(f"- methods/functions >150 lines: **{len(large_methods)}**\n")
md.append("## Classes")
for c in classes:
    md.append(f"- `{c['name']}` L{c['line']}-L{c['end_line']} ({c['lines']} lines), {c['method_count']} direct methods")
md.append("\n## >150-line functions/methods")
for r in large_methods:
    cats = ", ".join(sorted(r["call_categories"])) or "none"
    md.append(f"- `{r['qualname']}` L{r['line']}-L{r['end_line']} ({r['lines']} lines); categories={cats}; nested={len(r['nested_defs'])}; self_writes={len(r['self_writes'])}")
md.append("\n## Largest nested callbacks/functions")
for d in nested[:40]:
    md.append(f"- `{d['parent']} -> {d['name']}` L{d['line']}-L{d['end_line']} ({d['lines']} lines)")
md.append("\n## Most frequently written self attributes")
for name, count in self_write_counts.most_common(80):
    md.append(f"- `self.{name}`: written by {count} function(s)/method(s)")
md.append("\n## Import modules")
for item in imports:
    if item["kind"] == "import":
        md.append(f"- `import {item['module']}`")
    else:
        md.append(f"- `from {item['module']} import ...`")

(OUT / "gui_ast_inventory.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"ISSUE288_LOC={payload['loc']}")
print(f"ISSUE288_TOP_LEVEL_FUNCTIONS={payload['top_level_function_count']}")
print(f"ISSUE288_CLASSES={payload['class_count']}")
print(f"ISSUE288_METHODS={payload['method_count']}")
print(f"ISSUE288_NESTED_FUNCTIONS={payload['nested_function_count']}")
print(f"ISSUE288_LARGE_CLASSES={len(large_classes)}")
print(f"ISSUE288_LARGE_METHODS={len(large_methods)}")
for c in large_classes:
    print(f"LARGE_CLASS|{c['name']}|{c['line']}|{c['end_line']}|{c['lines']}")
for r in large_methods:
    print(f"LARGE_METHOD|{r['qualname']}|{r['line']}|{r['end_line']}|{r['lines']}|nested={len(r['nested_defs'])}|writes={len(r['self_writes'])}")
