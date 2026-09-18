#!/usr/bin/env python3
"""Issue #345 T0: AST dependency-closure inventory for Phase 1 move-only extraction."""

from __future__ import annotations

import ast
import json
from pathlib import Path

BRIDGE = Path("fold_designer_bridge.py")

EXTRA_MOVE_SYMBOLS = {
    "_phase6_assembly_placement_for_part",
    "_phase6_door_part_assembly_placement",
    "_phase6_relief_polygon_coords",
    "_PHASE6_ASSEMBLY_PLACEMENTS",
}
EXCLUDED_CLUSTER_SYMBOLS = {"_phase6_make_assembly_scene_render_data"}

EXPECTED_A = {"_phase6_is_box_body_physical_piece_key"}
EXPECTED_C = {
    "_phase6_mesh_profiles_for_part",
    "_phase6_operator_finished_dimensions",
    "_phase6_publish_live_state",
    "_phase6_scene_query_payload_for_part",
}
EXPECTED_EXTERNAL = EXPECTED_A | EXPECTED_C


def top_level_symbols(tree: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node
    return out


def bound_names(node: ast.AST) -> set[str]:
    bound: set[str] = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = node.args
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            bound.add(arg.arg)
        if args.vararg:
            bound.add(args.vararg.arg)
        if args.kwarg:
            bound.add(args.kwarg.arg)

    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            bound.add(sub.id)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and sub is not node:
            bound.add(sub.name)
        elif isinstance(sub, ast.Import):
            for alias in sub.names:
                bound.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(sub, ast.ImportFrom):
            for alias in sub.names:
                bound.add(alias.asname or alias.name)
    return bound


def loaded_names(node: ast.AST) -> set[str]:
    return {
        sub.id
        for sub in ast.walk(node)
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
    }


def main() -> int:
    source = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BRIDGE))
    symbols = top_level_symbols(tree)

    start = symbols.get("_phase6_assembly_relief_clearance")
    end = symbols.get("_phase6_resolve_manufacturing_geometry")
    if start is None or end is None:
        raise SystemExit("target boundary missing on live HEAD")

    start_line = int(getattr(start, "lineno", 0))
    end_line = int(getattr(end, "end_lineno", getattr(end, "lineno", 0)))

    move_set = {
        name
        for name, node in symbols.items()
        if start_line <= int(getattr(node, "lineno", -1)) <= end_line
        and name not in EXCLUDED_CLUSTER_SYMBOLS
    }
    move_set |= EXTRA_MOVE_SYMBOLS

    missing = sorted(name for name in move_set if name not in symbols)
    if missing:
        raise SystemExit(f"move-set symbols missing: {missing}")

    bridge_defined = set(symbols)
    external: set[str] = set()
    per_symbol: dict[str, list[str]] = {}

    for name in sorted(move_set):
        node = symbols[name]
        loads = loaded_names(node)
        local = bound_names(node)
        refs = sorted(
            ref
            for ref in (loads - local)
            if ref in bridge_defined and ref not in move_set
        )
        if refs:
            per_symbol[name] = refs
            external.update(refs)

    unknown = sorted(external - EXPECTED_EXTERNAL)
    missing_expected = sorted(EXPECTED_EXTERNAL - external)

    payload = {
        "bridge_lines": len(source.splitlines()),
        "cluster_boundary": {
            "start": f"_phase6_assembly_relief_clearance@{start_line}",
            "end": f"_phase6_resolve_manufacturing_geometry@{end_line}",
        },
        "move_set_count": len(move_set),
        "move_set": sorted(move_set),
        "external_bridge_symbols": sorted(external),
        "classification": {
            "A_existing_canonical_owner": sorted(EXPECTED_A & external),
            "C_self_coupled_shared": sorted(EXPECTED_C & external),
        },
        "unknown_unclassified": unknown,
        "missing_expected": missing_expected,
        "per_symbol_external_refs": per_symbol,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if unknown:
        print("FAIL: unclassified bridge dependency found")
        return 2
    if missing_expected:
        print("FAIL: expected dependency topology changed; re-inventory required")
        return 3
    if external != EXPECTED_EXTERNAL:
        print("FAIL: external dependency set differs from contract")
        return 4

    print("PASS: final move-set dependency closure is exactly A(1)+C(4); unknown=0")
    print("PASS: predicted phase6_manufacturing_geometry -> fold_designer_bridge imports = 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
