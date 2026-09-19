#!/usr/bin/env python3
"""#351 compatibility gate, evolved by #358 for Phase 2 callback retirement."""

from __future__ import annotations

import ast
from pathlib import Path

OWNER = Path("phase6_manufacturing_geometry.py")
BRIDGE = Path("fold_designer_bridge.py")

SHARED_REEXPORTS = {
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
}
OWNER_ONLY = {"_phase6_resolve_manufacturing_result"}
BRIDGE_FACADE = "_phase6_resolve_manufacturing_geometry"
RETIRED_SERVICE_WIRING = {
    "_phase6_mesh_profiles_for_part",
    "_phase6_operator_finished_dimensions",
    "_phase6_scene_query_payload_for_part",
}
RETAINED_COMPAT_WIRING = {"_phase6_publish_live_state"}


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


def binder_calls(mod: ast.Module) -> list[ast.Call]:
    calls = []
    for node in ast.walk(mod):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "_phase6_bind_bridge_callbacks":
            calls.append(node)
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
    names = RETIRED_SERVICE_WIRING | RETAINED_COMPAT_WIRING
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
                and target.attr in names
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
    imported = imported_from_owner(bridge)

    assert SHARED_REEXPORTS <= owner_names, (
        f"OWNER_SHARED_MISSING={sorted(SHARED_REEXPORTS-owner_names)}"
    )
    assert not (SHARED_REEXPORTS & bridge_names), (
        f"BRIDGE_SHARED_DUPLICATES={sorted(SHARED_REEXPORTS & bridge_names)}"
    )
    assert SHARED_REEXPORTS <= imported, (
        f"BRIDGE_REEXPORT_MISSING={sorted(SHARED_REEXPORTS-imported)}"
    )

    assert OWNER_ONLY <= owner_names, f"OWNER_ONLY_MISSING={sorted(OWNER_ONLY-owner_names)}"
    assert not (OWNER_ONLY & bridge_names), f"OWNER_ONLY_BRIDGE_DUPLICATE={sorted(OWNER_ONLY & bridge_names)}"
    assert not (OWNER_ONLY & imported), f"OWNER_ONLY_REEXPORTED={sorted(OWNER_ONLY & imported)}"

    assert BRIDGE_FACADE in bridge_names, "BRIDGE_FACADE_MISSING"
    assert BRIDGE_FACADE not in owner_names, "BRIDGE_FACADE_DUPLICATED_IN_OWNER"

    reverse = reverse_bridge_imports(owner)
    assert reverse == [], f"REVERSE_BRIDGE_IMPORT_LINES={reverse}"

    wired = class_wiring(bridge)
    assert not (RETIRED_SERVICE_WIRING & set(wired)), (
        f"RETIRED_SERVICE_WIRING_PRESENT={sorted(RETIRED_SERVICE_WIRING & set(wired))}"
    )
    assert RETAINED_COMPAT_WIRING <= set(wired), (
        f"RETAINED_COMPAT_WIRING_MISSING={sorted(RETAINED_COMPAT_WIRING-set(wired))}"
    )
    assert binder_calls(bridge) == [], "PHASE1_BINDER_CALL_STILL_PRESENT"

    shadows = instance_shadowing(bridge)
    assert not shadows, f"INSTANCE_SHADOWING={shadows}"

    resolver = next(
        node for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_phase6_resolve_manufacturing_result"
    )
    loaded = {
        node.id for node in ast.walk(resolver)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert "_phase6_call_bridge" not in loaded
    assert "_phase6_bind_bridge_callbacks" not in loaded
    assert "_PHASE6_BRIDGE_CALLBACKS" not in loaded

    print(f"PASS shared_reexports={len(SHARED_REEXPORTS)}")
    print(f"PASS owner_only={len(OWNER_ONLY)}")
    print("PASS reverse_bridge_imports=0")
    print("PASS retired_service_wiring=0")
    print(f"PASS retained_compat_wiring={len(RETAINED_COMPAT_WIRING)}")
    print("PASS phase1_binder_calls=0")
    print("PASS bridge_facade=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
