#!/usr/bin/env python3
"""#354 T0 — Phase 2 ownership/state/effect/timing preflight.

This is a read-only static inventory/gate.  It intentionally does not change
manufacturing behavior.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(".")
OWNER_PATH = Path("phase6_manufacturing_geometry.py")
BRIDGE_PATH = Path("fold_designer_bridge.py")
OWNER_MODULE = "phase6_manufacturing_geometry"
BRIDGE_MODULE = "fold_designer_bridge"

ROOT_FUNCTIONS = (
    "_phase6_resolve_manufacturing_geometry",
    "_phase6_resolve_explicit_joint_reliefs",
)
PHASE1_WIRING = (
    "_phase6_mesh_profiles_for_part",
    "_phase6_operator_finished_dimensions",
    "_phase6_scene_query_payload_for_part",
    "_phase6_publish_live_state",
)
CONFIRMED_PUMP_ATTRS = {
    "update_idletasks",
    "mainloop",
    "wait_variable",
    "wait_window",
    "wait_visibility",
}
POTENTIAL_PUMP_ATTRS = {"update", "after"}
TCL_PUMP_WORDS = {"update", "vwait", "tkwait"}

SKIP_DIR_NAMES = {
    ".git", ".venv", "venv", "__pycache__", "BACKUP", "backup",
    "tests", ".agents", ".pytest_cache",
}


@dataclass
class FunctionInfo:
    module: str
    name: str
    path: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    module_tree: ast.Module
    module_imports: dict[str, str]
    symbol_imports: dict[str, tuple[str, str]]

    @property
    def key(self) -> str:
        return f"{self.module}:{self.name}"


def module_name(path: Path) -> str:
    rel = path.with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def iter_production_python() -> Iterable[Path]:
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def resolve_from(module: str, node: ast.ImportFrom) -> str | None:
    target = node.module or ""
    if node.level == 0:
        return target
    package = module.rpartition(".")[0] or module
    try:
        return importlib.util.resolve_name("." * node.level + target, package)
    except Exception:
        return None


def imports_for(module: str, tree: ast.AST) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    modules: dict[str, str] = {}
    symbols: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            src = resolve_from(module, node)
            if not src:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                symbols[alias.asname or alias.name] = (src, alias.name)
    return modules, symbols


def build_index() -> tuple[dict[str, FunctionInfo], dict[str, list[FunctionInfo]], dict[str, ast.Module]]:
    by_key: dict[str, FunctionInfo] = {}
    by_simple: dict[str, list[FunctionInfo]] = {}
    trees: dict[str, ast.Module] = {}
    for path in iter_production_python():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except Exception:
            continue
        mod = module_name(path)
        trees[mod] = tree
        module_imports, symbol_imports = imports_for(mod, tree)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info = FunctionInfo(
                    module=mod,
                    name=node.name,
                    path=str(path),
                    node=node,
                    module_tree=tree,
                    module_imports=module_imports,
                    symbol_imports=symbol_imports,
                )
                by_key[info.key] = info
                by_simple.setdefault(node.name, []).append(info)
    return by_key, by_simple, trees


def attr_chain(node: ast.AST) -> str:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def function_local_imports(info: FunctionInfo) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    return imports_for(info.module, info.node)


def call_targets(
    info: FunctionInfo,
    by_key: dict[str, FunctionInfo],
) -> tuple[set[str], list[dict], list[dict], list[dict]]:
    local_funcs = {
        node.name
        for node in info.module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    local_mods, local_symbols = function_local_imports(info)
    module_aliases = {**info.module_imports, **local_mods}
    symbol_aliases = {**info.symbol_imports, **local_symbols}

    edges: set[str] = set()
    confirmed_pumps: list[dict] = []
    potential_pumps: list[dict] = []
    unresolved_calls: list[dict] = []

    for node in ast.walk(info.node):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func

        # Phase 1 dynamic bridge callback registry: model the real callback edge.
        if isinstance(fn, ast.Name) and fn.id == "_phase6_call_bridge":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                target = f"{BRIDGE_MODULE}:{node.args[1].value}"
                if target in by_key:
                    edges.add(target)

        if isinstance(fn, ast.Name):
            if fn.id in local_funcs:
                target = f"{info.module}:{fn.id}"
                if target in by_key:
                    edges.add(target)
            elif fn.id in symbol_aliases:
                mod, symbol = symbol_aliases[fn.id]
                target = f"{mod}:{symbol}"
                if target in by_key:
                    edges.add(target)
            elif fn.id in CONFIRMED_PUMP_ATTRS:
                confirmed_pumps.append({
                    "function": info.key, "path": info.path, "line": node.lineno,
                    "call": fn.id,
                })
            continue

        if isinstance(fn, ast.Attribute):
            chain = attr_chain(fn)
            if fn.attr in CONFIRMED_PUMP_ATTRS:
                confirmed_pumps.append({
                    "function": info.key, "path": info.path, "line": node.lineno,
                    "call": chain,
                })
            elif fn.attr in POTENTIAL_PUMP_ATTRS:
                potential_pumps.append({
                    "function": info.key, "path": info.path, "line": node.lineno,
                    "call": chain,
                })
            elif fn.attr == "call" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value in TCL_PUMP_WORDS:
                    confirmed_pumps.append({
                        "function": info.key, "path": info.path, "line": node.lineno,
                        "call": f"{chain}({first.value!r})",
                    })

            # Imported module call, e.g. module.func(...)
            if isinstance(fn.value, ast.Name) and fn.value.id in module_aliases:
                target = f"{module_aliases[fn.value.id]}:{fn.attr}"
                if target in by_key:
                    edges.add(target)

    return edges, confirmed_pumps, potential_pumps, unresolved_calls


def reachable_call_graph(by_key: dict[str, FunctionInfo]) -> dict:
    roots = [f"{OWNER_MODULE}:{name}" for name in ROOT_FUNCTIONS]
    missing_roots = [key for key in roots if key not in by_key]
    if missing_roots:
        raise AssertionError(f"MISSING_ROOTS={missing_roots}")

    queue: list[tuple[str, list[str]]] = [(root, [root]) for root in roots]
    seen: set[str] = set()
    confirmed: list[dict] = []
    potential: list[dict] = []
    first_path: dict[str, list[str]] = {}

    while queue:
        key, path = queue.pop(0)
        if key in seen:
            continue
        seen.add(key)
        first_path[key] = path
        info = by_key[key]
        edges, pumps, potentials, _ = call_targets(info, by_key)
        for item in pumps:
            item = dict(item)
            item["path_from_root"] = path
            confirmed.append(item)
        for item in potentials:
            item = dict(item)
            item["path_from_root"] = path
            potential.append(item)
        for target in sorted(edges):
            if target not in seen:
                queue.append((target, path + [target]))

    return {
        "roots": roots,
        "reachable_function_count": len(seen),
        "reachable_functions": sorted(seen),
        "confirmed_pumps": sorted(confirmed, key=lambda x: (x["path"], x["line"], x["call"])),
        "potential_pumps": sorted(potential, key=lambda x: (x["path"], x["line"], x["call"])),
    }


def owner_state_inventory(owner_tree: ast.Module) -> dict:
    reads: dict[str, list[int]] = {}
    writes: dict[str, list[int]] = {}
    workspace: dict[str, list[int]] = {}
    callback_refs: dict[str, list[int]] = {
        "_PHASE6_BRIDGE_CALLBACKS": [],
        "_phase6_bind_bridge_callbacks": [],
        "_phase6_call_bridge": [],
    }

    for node in ast.walk(owner_tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
            target = writes if isinstance(node.ctx, (ast.Store, ast.Del)) else reads
            target.setdefault(node.attr, []).append(node.lineno)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # getattr(self, "name") / setattr(self, "name", ...)
            if node.func.id in {"getattr", "setattr"} and len(node.args) >= 2:
                if isinstance(node.args[0], ast.Name) and node.args[0].id == "self":
                    arg = node.args[1]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        target = writes if node.func.id == "setattr" else reads
                        target.setdefault(arg.value, []).append(node.lineno)

        if isinstance(node, ast.Attribute):
            chain = attr_chain(node)
            if chain.startswith("self.designer_workspace."):
                workspace.setdefault(chain.split(".", 2)[2], []).append(node.lineno)

        if isinstance(node, ast.Name) and node.id in callback_refs:
            callback_refs[node.id].append(node.lineno)

    normalize = lambda d: {k: sorted(set(v)) for k, v in sorted(d.items())}
    return {
        "self_reads": normalize(reads),
        "self_writes": normalize(writes),
        "designer_workspace_refs": normalize(workspace),
        "callback_registry_refs": normalize(callback_refs),
    }


def enclosing_top_function(tree: ast.Module, lineno: int) -> str:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= lineno <= end:
                return node.name
    return "<module>"


def wiring_inventory(bridge_tree: ast.Module) -> dict:
    result: dict[str, list[dict]] = {name: [] for name in PHASE1_WIRING}
    for node in ast.walk(bridge_tree):
        for name in PHASE1_WIRING:
            hit = False
            kind = ""
            if isinstance(node, ast.Name) and node.id == name:
                hit = True
                kind = type(node.ctx).__name__
            elif isinstance(node, ast.Attribute) and node.attr == name:
                hit = True
                kind = "attribute"
            elif isinstance(node, ast.keyword) and node.arg == name:
                hit = True
                kind = "binder_keyword"
            if hit and hasattr(node, "lineno"):
                result[name].append({
                    "line": node.lineno,
                    "owner": enclosing_top_function(bridge_tree, node.lineno),
                    "kind": kind,
                })

    for name, refs in result.items():
        unique = {(r["line"], r["owner"], r["kind"]): r for r in refs}
        result[name] = [unique[k] for k in sorted(unique)]
    return result


def cache_short_circuit(owner_tree: ast.Module) -> dict:
    resolver = next(
        node for node in owner_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_phase6_resolve_manufacturing_geometry"
    )
    body = list(resolver.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        body = body[1:]
    if len(body) < 3:
        raise AssertionError("RESOLVER_BODY_TOO_SHORT")

    first, second, third = body[:3]
    signature_ok = (
        isinstance(first, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "signature" for t in first.targets)
        and isinstance(first.value, ast.Call)
        and isinstance(first.value.func, ast.Name)
        and first.value.func.id == "_phase6_manufacturing_state_signature"
    )
    cached_ok = (
        isinstance(second, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "cached" for t in second.targets)
    )
    hit_return_ok = (
        isinstance(third, ast.If)
        and any(isinstance(n, ast.Return) and isinstance(n.value, ast.Name) and n.value.id == "cached"
                for n in third.body)
    )

    expensive_lines: list[tuple[str, int]] = []
    for node in ast.walk(resolver):
        if isinstance(node, ast.Name) and node.id == "_phase6_call_bridge":
            expensive_lines.append(("_phase6_call_bridge", node.lineno))
        elif isinstance(node, ast.Attribute):
            chain = attr_chain(node)
            if chain.startswith("self.designer_workspace"):
                expensive_lines.append((chain, node.lineno))
    first_expensive = min((line for _, line in expensive_lines), default=None)
    hit_if_line = third.lineno if isinstance(third, ast.If) else None

    signature_fn = next(
        node for node in owner_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_phase6_manufacturing_state_signature"
    )
    signature_self_attrs: set[str] = set()
    signature_calls: set[str] = set()
    for node in ast.walk(signature_fn):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
            signature_self_attrs.add(node.attr)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                signature_calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                signature_calls.add(attr_chain(node.func))

    return {
        "signature_first": signature_ok,
        "cached_read_second": cached_ok,
        "cache_hit_return_third": hit_return_ok,
        "cache_hit_if_line": hit_if_line,
        "first_expensive_payload_line": first_expensive,
        "hit_precedes_expensive_payload": (
            hit_if_line is not None and first_expensive is not None and hit_if_line < first_expensive
        ),
        "signature_self_attrs": sorted(signature_self_attrs),
        "signature_calls": sorted(signature_calls),
    }


def main() -> int:
    owner_source = OWNER_PATH.read_text(encoding="utf-8")
    bridge_source = BRIDGE_PATH.read_text(encoding="utf-8")
    owner_tree = ast.parse(owner_source, filename=str(OWNER_PATH))
    bridge_tree = ast.parse(bridge_source, filename=str(BRIDGE_PATH))

    by_key, _, _ = build_index()
    state = owner_state_inventory(owner_tree)
    wiring = wiring_inventory(bridge_tree)
    cache = cache_short_circuit(owner_tree)
    graph = reachable_call_graph(by_key)

    direct_confirmed = [
        p for p in graph["confirmed_pumps"]
        if p["function"].startswith(f"{OWNER_MODULE}:")
    ]

    payload = {
        "baseline_sha": "7a8b87f8cbb50a34c5038aa196fa137b301702a4",
        "owner_lines": len(owner_source.splitlines()),
        "bridge_lines": len(bridge_source.splitlines()),
        "state_inventory": state,
        "phase1_wiring_inventory": wiring,
        "cache_short_circuit": cache,
        "tk_event_loop": {
            "DIRECT_TK_PUMP_COUNT": len(direct_confirmed),
            "TRANSITIVE_TK_PUMP_PATHS": graph["confirmed_pumps"],
            "POTENTIAL_UPDATE_AFTER_CALLS": graph["potential_pumps"],
            "REACHABLE_FUNCTION_COUNT": graph["reachable_function_count"],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    # T0 fail-closed machine assertions.
    assert cache["signature_first"], "CACHE_SIGNATURE_NOT_FIRST"
    assert cache["cached_read_second"], "CACHE_RESULT_NOT_SECOND"
    assert cache["cache_hit_return_third"], "CACHE_HIT_NOT_EARLY_RETURN"
    assert cache["hit_precedes_expensive_payload"], "CACHE_HIT_DOES_NOT_PRECEDE_EXPENSIVE_PAYLOAD"

    # Direct owner must not itself pump Tk. Transitive findings require manual
    # classification and are intentionally surfaced rather than hidden.
    assert len(direct_confirmed) == 0, f"DIRECT_TK_PUMPS={direct_confirmed}"

    print(f"PASS SELF_READ_KEYS={len(state['self_reads'])}")
    print(f"PASS SELF_WRITE_KEYS={len(state['self_writes'])}")
    print(f"PASS DIRECT_TK_PUMP_COUNT={len(direct_confirmed)}")
    print(f"INFO TRANSITIVE_TK_PUMP_PATH_COUNT={len(graph['confirmed_pumps'])}")
    print(f"INFO POTENTIAL_UPDATE_AFTER_CALL_COUNT={len(graph['potential_pumps'])}")
    print("PASS CACHE_SIGNATURE_FIRST_SHORT_CIRCUIT=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
