#!/usr/bin/env python3
"""#351 T6: fail-closed compatibility and zero-reverse-import gate."""

from __future__ import annotations

import ast
import builtins
from pathlib import Path

OWNER = Path("phase6_manufacturing_geometry.py")
BRIDGE = Path("fold_designer_bridge.py")

MOVED = {
    "_PHASE6_ASSEMBLY_PLACEMENTS",
    "_phase6_door_part_assembly_placement",
    "_phase6_assembly_placement_for_part",
    "_phase6_relief_polygon_coords",
    "_phase6_assembly_relief_clearance",
    "_phase6_current_cabinet_family",
    "_phase6_solution_is_committable",
    "_phase6_apply_resolved_cut_to_part",
    "_phase6_apply_resolved_cut_to_owner",
    "_phase6_side_wrap_target_corners",
    "_phase6_box_body_piece_solver_key",
    "_phase6_expand_box_body_fw_world_mid",
    "_phase6_shift_multistage_terminal_fold_world_mid",
    "_phase6_joint_relief_state_item_matches",
    "_phase6_cut_geometry_from_state_item",
    "_phase6_signature_canonical_value",
    "_phase6_manufacturing_state_signature",
    "_phase6_joint_registry_diagnostic_info",
    "_phase6_build_joint_world_geometry",
    "_phase6_resolve_explicit_joint_reliefs",
    "_phase6_resolve_family_divider_reliefs",
    "_phase6_resolve_manufacturing_geometry",
}
BOUND = {
    "_phase6_mesh_profiles_for_part",
    "_phase6_operator_finished_dimensions",
    "_phase6_scene_query_payload_for_part",
    "_phase6_publish_live_state",
}


def tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def defined_names(mod: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in mod.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    out.add(target.id)
    return out


def imported_from_owner(mod: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in mod.body:
        if isinstance(node, ast.ImportFrom) and node.module == "phase6_manufacturing_geometry":
            out.update(alias.asname or alias.name for alias in node.names)
    return out


def class_wiring(mod: ast.Module) -> dict[str, int]:
    out: dict[str, int] = {}
    for node in mod.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "Phase6FoldDesignerApp"
            ):
                out[target.attr] = node.lineno
    return out


def helper_def_lines(mod: ast.Module) -> dict[str, int]:
    return {
        node.name: node.lineno
        for node in mod.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in BOUND
    }


def binder_calls(mod: ast.Module) -> list[ast.Call]:
    calls = []
    for node in mod.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if isinstance(func, ast.Name) and func.id == "_phase6_bind_bridge_callbacks":
            calls.append(node.value)
    return calls


def reverse_bridge_imports(mod: ast.Module) -> list[int]:
    hits: list[int] = []
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            if any(alias.name == "fold_designer_bridge" for alias in node.names):
                hits.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge":
            hits.append(node.lineno)
    return hits


def instance_shadowing(mod: ast.Module) -> list[tuple[int, str]]:
    hits = []
    for node in ast.walk(mod):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr in BOUND
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                hits.append((node.lineno, target.attr))
    return hits


def main() -> int:
    owner = tree(OWNER)
    bridge = tree(BRIDGE)

    owner_names = defined_names(owner)
    bridge_names = defined_names(bridge)

    assert MOVED <= owner_names, f"OWNER_MISSING={sorted(MOVED-owner_names)}"
    assert not (MOVED & bridge_names), f"BRIDGE_DUPLICATES={sorted(MOVED & bridge_names)}"

    imported = imported_from_owner(bridge)
    assert MOVED <= imported, f"BRIDGE_REEXPORT_MISSING={sorted(MOVED-imported)}"

    reverse = reverse_bridge_imports(owner)
    assert reverse == [], f"REVERSE_BRIDGE_IMPORT_LINES={reverse}"

    wired = class_wiring(bridge)
    assert BOUND <= set(wired), f"BOUND_WIRING_MISSING={sorted(BOUND-set(wired))}"

    defs = helper_def_lines(bridge)
    assert BOUND <= set(defs), f"BOUND_HELPER_DEF_MISSING={sorted(BOUND-set(defs))}"

    calls = binder_calls(bridge)
    assert len(calls) == 1, f"BINDER_CALL_COUNT={len(calls)}"
    call = calls[0]
    kw = {item.arg for item in call.keywords if item.arg}
    assert BOUND <= kw, f"BINDER_CALLBACK_MISSING={sorted(BOUND-kw)}"
    assert call.lineno > max(defs.values()), "BINDER_CALLED_BEFORE_HELPERS_DEFINED"
    assert call.lineno >= max(wired[name] for name in BOUND), "BINDER_CALLED_BEFORE_CLASS_WIRING"

    shadows = instance_shadowing(bridge)
    assert not shadows, f"INSTANCE_SHADOWING={shadows}"

    resolver = next(
        node for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_phase6_resolve_manufacturing_geometry"
    )
    loaded = {
        node.id for node in ast.walk(resolver)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert "_phase6_is_box_body_physical_piece_key" not in loaded
    assert "is_box_body_physical_piece_key" in loaded

    print(f"PASS moved_owner_count={len(MOVED)}")
    print("PASS reverse_bridge_imports=0")
    print(f"PASS class_wiring={len(BOUND)} binder_callbacks={len(BOUND)}")
    print("PASS instance_shadowing=0")
    print("PASS canonical_part_navigation_name=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
