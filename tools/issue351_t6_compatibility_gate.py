#!/usr/bin/env python3
"""#351 durable compatibility gate, evolved through #360 pure-service cutover."""

from __future__ import annotations

import ast
from pathlib import Path

OWNER = Path("phase6_manufacturing_geometry.py")
SERVICE = Path("phase6_manufacturing_service.py")
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
    "_phase6_box_body_piece_solver_key",
    "_phase6_manufacturing_state_signature",
    "_phase6_joint_registry_diagnostic_info",
    "_phase6_build_joint_world_geometry",
    "_phase6_resolve_explicit_joint_reliefs",
    "_phase6_resolve_family_divider_reliefs",
}
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
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "Phase6FoldDesignerApp"
                ):
                    out[target.attr] = node.lineno
            continue
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not (
            isinstance(call.func, ast.Name)
            and call.func.id == "install_fold_designer_bridge_facade"
        ):
            continue
        bindings = call.args[1] if len(call.args) >= 2 else None
        if bindings is None:
            for keyword in call.keywords:
                if keyword.arg == "bindings":
                    bindings = keyword.value
                    break
        if not isinstance(bindings, ast.Dict):
            continue
        for key in bindings.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                out[key.value] = node.lineno
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


def service_purity(mod: ast.Module) -> None:
    imports = []
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    roots = {name.split(".", 1)[0] for name in imports}
    forbidden_roots = {"fold_designer_bridge", "tkinter", "gui", "gui_modules"}
    assert not (roots & forbidden_roots), f"SERVICE_FORBIDDEN_IMPORTS={sorted(roots & forbidden_roots)}"

    names = {node.id for node in ast.walk(mod) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(mod) if isinstance(node, ast.Attribute)}
    forbidden = {
        "self", "designer_workspace", "_scene_query_callback",
        "_PHASE6_BRIDGE_CALLBACKS", "_phase6_bind_bridge_callbacks", "_phase6_call_bridge",
    }
    assert not (forbidden & (names | attrs)), (
        f"SERVICE_FORBIDDEN_REFS={sorted(forbidden & (names | attrs))}"
    )


def main() -> int:
    owner = tree(OWNER)
    service = tree(SERVICE)
    bridge = tree(BRIDGE)

    owner_names = defined_names(owner)
    service_names = defined_names(service)
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

    assert "resolve" in service_names, "PURE_SERVICE_RESOLVE_MISSING"
    assert "_phase6_resolve_manufacturing_result" not in owner_names, (
        "LEGACY_ORCHESTRATION_STILL_IN_GEOMETRY_OWNER"
    )

    assert BRIDGE_FACADE in bridge_names, "BRIDGE_FACADE_MISSING"
    assert BRIDGE_FACADE not in owner_names, "BRIDGE_FACADE_DUPLICATED_IN_OWNER"

    assert reverse_bridge_imports(owner) == [], "OWNER_REVERSE_BRIDGE_IMPORT"
    assert reverse_bridge_imports(service) == [], "SERVICE_REVERSE_BRIDGE_IMPORT"
    service_purity(service)

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
        node for node in service.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    )
    assert [arg.arg for arg in resolver.args.args] == ["request"]

    print(f"PASS shared_reexports={len(SHARED_REEXPORTS)}")
    print("PASS pure_service_resolve=1")
    print("PASS service_self_refs=0")
    print("PASS service_bridge_imports=0")
    print("PASS service_tk_imports=0")
    print("PASS service_designer_workspace_refs=0")
    print("PASS service_callback_registry_refs=0")
    print("PASS retired_service_wiring=0")
    print(f"PASS retained_compat_wiring={len(RETAINED_COMPAT_WIRING)}")
    print("PASS bridge_facade=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
