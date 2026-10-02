#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only, Git-object-based T0 census for #442 / Master #441."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

BRIDGE = "fold_designer_bridge.py"
CONFIG = "config.ini"
TARGET_SYMBOLS = (
    "_phase6_resolve_profile_key",
    "_phase6_box_symmetry_allowed",
    "_phase6_apply_box_symmetry_policy",
    "_phase6_on_box_symmetry_changed",
    "_phase6_build_box_symmetry_settings",
    "_phase6_build_assembly_settings",
    "Phase6BendingUI",
)


def git(*args: str, binary: bool = False):
    cmd = ["git", *args]
    if binary:
        return subprocess.check_output(cmd)
    return subprocess.check_output(cmd, text=True, encoding="utf-8", errors="surrogateescape")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ref_paths(ref: str) -> list[str]:
    raw = git("ls-tree", "-r", "--name-only", "-z", ref, binary=True)
    return sorted(x.decode("utf-8", "surrogateescape") for x in raw.split(b"\0") if x)


def ref_bytes(ref: str, path: str) -> bytes:
    return git("show", f"{ref}:{path}", binary=True)


def ref_text(ref: str, path: str) -> str:
    return ref_bytes(ref, path).decode("utf-8", "surrogateescape")


def blob_oid(ref: str, path: str) -> str:
    return git("rev-parse", f"{ref}:{path}").strip()


def parse_py(ref: str, path: str):
    text = ref_text(ref, path)
    try:
        return text, ast.parse(text, filename=path)
    except SyntaxError as exc:
        return text, {"syntax_error": f"{type(exc).__name__}: {exc}"}


def bridge_metrics(ref: str) -> dict:
    text, tree = parse_py(ref, BRIDGE)
    if isinstance(tree, dict):
        raise RuntimeError(tree["syntax_error"])
    top = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    phase6 = [n for n in top if getattr(n, "name", "").startswith("_phase6_")]
    self_attrs = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "self"
    ]
    facade_count = None
    facade_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if name == "install_fold_designer_bridge_facade":
            facade_calls.append(node)
    if len(facade_calls) == 1:
        dict_args = [a for a in facade_calls[0].args if isinstance(a, ast.Dict)]
        if len(dict_args) == 1:
            facade_count = len(dict_args[0].keys)
    return {
        "path": BRIDGE,
        "git_blob_oid": blob_oid(ref, BRIDGE),
        "sha256": sha256(ref_bytes(ref, BRIDGE)),
        "line_count_splitlines": len(text.splitlines()),
        "newline_count": text.count("\n"),
        "ends_with_newline": text.endswith("\n"),
        "top_level_def_class_count": len(top),
        "phase6_top_level_symbol_count": len(phase6),
        "self_attr_ast_count": len(self_attrs),
        "self_dot_raw_substring_count": text.count("self."),
        "facade_binding_count": facade_count,
    }


def symbol_inventory(ref: str, py_paths: list[str]) -> dict:
    result = {s: [] for s in TARGET_SYMBOLS}
    for path in py_paths:
        text, tree = parse_py(ref, path)
        if isinstance(tree, dict):
            continue
        defs = {}
        calls = {s: [] for s in TARGET_SYMBOLS}
        getattr_refs = {s: [] for s in TARGET_SYMBOLS}
        string_refs = {s: [] for s in TARGET_SYMBOLS}
        facade_refs = {s: [] for s in TARGET_SYMBOLS}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in TARGET_SYMBOLS:
                    defs.setdefault(node.name, []).append(node.lineno)
            if isinstance(node, ast.Call):
                callee = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else None
                )
                if callee in calls:
                    calls[callee].append(getattr(node, "lineno", 0))
                if callee == "getattr" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    value = node.args[1].value
                    if value in getattr_refs:
                        getattr_refs[value].append(getattr(node, "lineno", 0))
                if callee == "install_fold_designer_bridge_facade":
                    for arg in node.args:
                        if isinstance(arg, ast.Dict):
                            for key in arg.keys:
                                if isinstance(key, ast.Constant) and key.value in facade_refs:
                                    facade_refs[key.value].append(getattr(key, "lineno", 0))
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for symbol in TARGET_SYMBOLS:
                    if symbol in node.value:
                        string_refs[symbol].append(getattr(node, "lineno", 0))
        for symbol in TARGET_SYMBOLS:
            raw = text.count(symbol)
            if raw or defs.get(symbol) or calls[symbol] or getattr_refs[symbol] or string_refs[symbol] or facade_refs[symbol]:
                result[symbol].append({
                    "path": path,
                    "definitions": defs.get(symbol, []),
                    "calls": calls[symbol],
                    "getattr_refs": getattr_refs[symbol],
                    "string_refs": string_refs[symbol],
                    "facade_refs": facade_refs[symbol],
                    "raw_occurrences": raw,
                })
    return result


def source_test_inventory(ref: str, test_paths: list[str]) -> dict:
    importers = []
    readers = []
    for path in test_paths:
        text, tree = parse_py(ref, path)
        if isinstance(tree, dict):
            continue
        imports_bridge = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name == "fold_designer_bridge" for a in node.names):
                imports_bridge = True
            if isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge":
                imports_bridge = True
        if imports_bridge:
            importers.append(path)
        reasons = []
        if "bridge.__file__" in text:
            reasons.append("bridge.__file__")
        if "fold_designer_bridge.py" in text and (".read_text(" in text or "ast.parse(" in text):
            reasons.append("bridge source/AST read")
        if 'source.index("class Phase6BendingUI")' in text:
            reasons.append("BendingUI location slice")
        if 'assert \'text="對稱折彎"\' in source' in text:
            reasons.append("whole-bridge symmetry text assertion")
        if reasons:
            readers.append({"path": path, "reasons": sorted(set(reasons))})
    return {
        "test_py_path_count": len(test_paths),
        "bridge_import_test_count": len(importers),
        "bridge_import_tests": sorted(importers),
        "source_or_ast_reader_count": len(readers),
        "source_or_ast_readers": sorted(readers, key=lambda x: x["path"]),
        "complete": True,
    }


def reverse_imports(ref: str, root_phase6_paths: list[str]) -> dict:
    rows = []
    for path in root_phase6_paths:
        _, tree = parse_py(ref, path)
        if isinstance(tree, dict):
            continue
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        bridge = sorted(x for x in imports if x == "fold_designer_bridge" or x.startswith("fold_designer_bridge."))
        gui = sorted(x for x in imports if x == "gui_modules" or x.startswith("gui_modules."))
        rows.append({"path": path, "bridge_imports": bridge, "gui_modules_imports": gui})
    return {
        "root_phase6_module_count": len(rows),
        "bridge_reverse_import_violations": [r for r in rows if r["bridge_imports"]],
        "gui_modules_import_inventory": [r for r in rows if r["gui_modules_imports"]],
        "rows": rows,
    }


def git_object_manifest(ref: str, paths: list[str]) -> dict:
    rows = []
    lines = []
    for path in paths:
        data = ref_bytes(ref, path)
        oid = blob_oid(ref, path)
        digest = sha256(data)
        rows.append({"path": path, "git_blob_oid": oid, "byte_size": len(data), "sha256": digest})
        lines.append(f"{path}\t{len(data)}\t{digest}\t{oid}")
    text = "\n".join(lines) + ("\n" if lines else "")
    return {"ref": ref, "path_count": len(paths), "rows": rows, "aggregate_sha256": sha256(text.encode("utf-8"))}


def config_manifest(ref: str, all_paths: list[str]) -> dict:
    if CONFIG not in all_paths:
        return {"path": CONFIG, "exists": False}
    data = ref_bytes(ref, CONFIG)
    return {
        "path": CONFIG,
        "exists": True,
        "git_blob_oid": blob_oid(ref, CONFIG),
        "byte_size": len(data),
        "sha256": sha256(data),
    }


def worktree_status() -> dict:
    raw = git("status", "--porcelain=v1", "-z", binary=True)
    items = [x.decode("utf-8", "surrogateescape") for x in raw.split(b"\0") if x]
    return {"clean": int(not items), "entries": items}


def render_md(data: dict) -> str:
    b = data["bridge"]
    st = data["source_tests"]
    rev = data["reverse_imports"]
    dxf = data["dxf_git_object_manifest"]
    cfg = data["config_git_object"]
    symbols = data["symbols"]
    lines = [
        "# Issue #442 T0 Census",
        "",
        f"- baseline ref: `{data['baseline_ref']}`",
        f"- candidate evidence HEAD: `{data['candidate_head']}`",
        f"- BASE_SHA_EXACT: `{data['BASE_SHA_EXACT']}`",
        f"- worktree clean: `{data['worktree']['clean']}`",
        "",
        "## Bridge metrics",
        f"- splitlines: {b['line_count_splitlines']}",
        f"- newline count: {b['newline_count']}",
        f"- top-level def/class: {b['top_level_def_class_count']}",
        f"- _phase6_* top-level symbols: {b['phase6_top_level_symbol_count']}",
        f"- AST self attrs: {b['self_attr_ast_count']}",
        f"- raw self. substrings: {b['self_dot_raw_substring_count']}",
        f"- facade bindings: {b['facade_binding_count']}",
        "",
        "## Source-test exposure",
        f"- test .py paths: {st['test_py_path_count']}",
        f"- bridge import tests: {st['bridge_import_test_count']}",
        f"- source/AST readers: {st['source_or_ast_reader_count']}",
        "",
        "## Selected symbol repo-wide occurrence counts",
    ]
    for name in TARGET_SYMBOLS:
        rows = symbols[name]
        lines.append(f"- `{name}`: {sum(r['raw_occurrences'] for r in rows)} raw occurrences across {len(rows)} files")
    lines += [
        "",
        "## Reverse imports",
        f"- root phase6 modules: {rev['root_phase6_module_count']}",
        f"- bridge reverse-import violations: {len(rev['bridge_reverse_import_violations'])}",
        "",
        "## Git-object baseline",
        f"- tracked DXF paths: {dxf['path_count']}",
        f"- DXF aggregate SHA-256: `{dxf['aggregate_sha256']}`",
        f"- config exists: `{cfg.get('exists')}`",
        f"- config SHA-256: `{cfg.get('sha256')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-ref", required=True)
    ap.add_argument("--expected-base-sha", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--markdown", required=True)
    args = ap.parse_args()

    baseline = git("rev-parse", args.baseline_ref).strip()
    expected = git("rev-parse", args.expected_base_sha).strip()
    if baseline != expected:
        raise SystemExit(f"BASE_SHA_MISMATCH baseline={baseline} expected={expected}")
    git("merge-base", "--is-ancestor", baseline, "HEAD")

    paths = ref_paths(baseline)
    py_paths = [p for p in paths if p.endswith(".py")]
    test_paths = [p for p in py_paths if p.startswith("tests/")]
    root_phase6 = [p for p in py_paths if "/" not in p and p.startswith("phase6_")]
    dxf_paths = [p for p in paths if p.lower().endswith(".dxf")]

    data = {
        "schema": "WHD_ISSUE442_T0_CENSUS_V1",
        "baseline_ref": baseline,
        "expected_base_sha": expected,
        "candidate_head": git("rev-parse", "HEAD").strip(),
        "branch": git("branch", "--show-current").strip(),
        "BASE_SHA_EXACT": 1,
        "worktree": worktree_status(),
        "bridge": bridge_metrics(baseline),
        "symbols": symbol_inventory(baseline, py_paths),
        "source_tests": source_test_inventory(baseline, test_paths),
        "reverse_imports": reverse_imports(baseline, root_phase6),
        "dxf_git_object_manifest": git_object_manifest(baseline, dxf_paths),
        "config_git_object": config_manifest(baseline, paths),
    }
    Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.markdown).write_text(render_md(data), encoding="utf-8")
    print(json.dumps({
        "schema": data["schema"],
        "baseline_ref": data["baseline_ref"],
        "candidate_head": data["candidate_head"],
        "BASE_SHA_EXACT": data["BASE_SHA_EXACT"],
        "worktree_clean": data["worktree"]["clean"],
        "bridge": data["bridge"],
        "bridge_import_test_count": data["source_tests"]["bridge_import_test_count"],
        "source_or_ast_reader_count": data["source_tests"]["source_or_ast_reader_count"],
        "root_phase6_module_count": data["reverse_imports"]["root_phase6_module_count"],
        "bridge_reverse_import_count": len(data["reverse_imports"]["bridge_reverse_import_violations"]),
        "tracked_dxf_count": data["dxf_git_object_manifest"]["path_count"],
        "dxf_aggregate_sha256": data["dxf_git_object_manifest"]["aggregate_sha256"],
        "config_sha256": data["config_git_object"].get("sha256"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
