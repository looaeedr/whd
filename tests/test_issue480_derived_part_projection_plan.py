from __future__ import annotations

import ast
import importlib
import inspect
from dataclasses import FrozenInstanceError

import pytest


MODULE = "phase6_derived_part_projection"


def _projection_module():
    return importlib.import_module(MODULE)


def test_r2_projection_owner_is_pure_and_does_not_reverse_import_bridge_or_tk():
    module = _projection_module()
    source = inspect.getsource(module)
    tree = ast.parse(source)

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert "fold_designer_bridge" not in imported_roots
    assert "tkinter" not in imported_roots
    assert "DesignerWorkspace" not in source


def test_r2_projection_contracts_are_immutable_value_objects():
    module = _projection_module()
    request_type = module.DerivedPartProjectionRequest
    plan_type = module.DerivedPartSyncPlan

    assert request_type.__dataclass_params__.frozen is True
    assert plan_type.__dataclass_params__.frozen is True

    request = request_type()
    plan = module.build_derived_part_sync_plan(request)
    assert isinstance(plan, plan_type)

    if plan.__dataclass_fields__:
        field_name = next(iter(plan.__dataclass_fields__))
        with pytest.raises(FrozenInstanceError):
            setattr(plan, field_name, getattr(plan, field_name))


def test_r2_same_request_produces_same_plan_without_workspace_mutation_api():
    module = _projection_module()
    request = module.DerivedPartProjectionRequest()

    first = module.build_derived_part_sync_plan(request)
    second = module.build_derived_part_sync_plan(request)
    assert first == second

    source = inspect.getsource(module.build_derived_part_sync_plan)
    forbidden_mutations = (
        ".remove_part(",
        ".sync_derived_parts(",
        ".stash_features(",
        ".set_active_part(",
        ".set_selected_part(",
        ".add_part(",
        ".stash_profiles(",
    )
    assert not any(token in source for token in forbidden_mutations)


def test_r2_projection_values_are_deeply_frozen_and_materialize_detached_copies():
    module = _projection_module()
    source = {
        "X": [{"len": 12.0, "meta": {"tag": "x"}}],
        "Y": [{"len": 34.0}],
    }
    projection = module.profile_projection("door_c1_r1", source)
    request = module.DerivedPartProjectionRequest(
        namespaces=(module.namespace_projection("door_c", {"door_c1_r1": source}),),
        add_parts=(projection,),
    )
    plan = module.build_derived_part_sync_plan(request)

    source["X"][0]["len"] = 999.0
    first = module.materialize_profiles(plan.add_parts[0])
    second = module.materialize_profiles(plan.add_parts[0])
    assert first["X"][0]["len"] == 12.0
    first["X"][0]["len"] = 77.0
    assert second["X"][0]["len"] == 12.0


def test_r2_existing_projection_owner_assembles_immutable_request_without_domain_derivation():
    from pathlib import Path

    module = _projection_module()
    assert hasattr(module, "DerivedPartRequestAssemblyInput"), (
        "B5 RED: existing derived projection owner lacks bounded request-assembly input"
    )
    assert callable(getattr(module, "build_derived_part_projection_request", None)), (
        "B5 RED: existing derived projection owner lacks request-assembly owner"
    )

    source = Path(module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "fold_designer_bridge",
        "tkinter",
        "DesignerWorkspace",
        "phase6_manufacturing_geometry",
        "manufacturing_api",
        "derive_box_body_dividers",
        "derive_all_inner_door_frames",
        "derive_inner_door_panels",
        "build_standard_part_profiles",
    )
    assert not [token for token in forbidden if token in source]


def test_r2_composition_owns_derived_sync_orchestration_and_bridge_only_delegates():
    from pathlib import Path

    bridge_source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    bridge_tree = ast.parse(bridge_source)
    bridge_fn = next(
        node
        for node in bridge_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_phase6_sync_authoritative_derived_parts"
    )
    bridge_body = ast.get_source_segment(bridge_source, bridge_fn) or ""
    assert "sync_authoritative_derived_parts(globals())" in bridge_body
    for token in (
        "derive_door_layout_cells",
        "derive_box_body_dividers",
        "derive_all_inner_door_frames",
        "DerivedPartRequestAssemblyInput(",
        "navigation.apply_derived_sync_plan(plan)",
    ):
        assert token not in bridge_body, f"#1128 anti-regrowth: Bridge reclaimed orchestration: {token}"

    composition_source = Path("gui_modules/application/fold_designer_adapter.py").read_text(encoding="utf-8")
    composition_tree = ast.parse(composition_source)
    owner = next(
        node
        for node in composition_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6FoldDesignerComposition"
    )
    method = next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef) and node.name == "sync_authoritative_derived_parts"
    )
    implementation_source = Path(
        "gui_modules/application/fold_designer_composition_shell_settings.py"
    ).read_text(encoding="utf-8")
    implementation_tree = ast.parse(implementation_source)
    implementation = next(
        node for node in implementation_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "sync_authoritative_derived_parts"
    )
    body = ast.get_source_segment(implementation_source, implementation) or ""
    for token in (
        "_phase6_door_part_projections",
        "derive_door_layout_cells",
        "_phase6_box_body_piece_part_profiles",
        "derive_box_body_dividers",
        "derive_all_inner_door_frames",
        "DerivedPartRequestAssemblyInput(",
        "build_derived_part_projection_request(",
        "build_derived_part_sync_plan(request)",
        "navigation.apply_derived_sync_plan(plan)",
    ):
        assert token in body

    assert body.index("build_derived_part_projection_request(") < body.index(
        "build_derived_part_sync_plan(request)"
    ) < body.index("navigation.apply_derived_sync_plan(plan)")

def test_reactivated_standard_door_and_base_plate_replace_stale_family_profile_stash():
    module = _projection_module()
    target_door = {"X": [{"len": 365.0}], "Y": [{"len": 561.0}]}
    target_base = {"X": [{"len": 320.0}], "Y": [{"len": 520.0}]}
    request = module.build_derived_part_projection_request(
        module.DerivedPartRequestAssemblyInput(
            door_part_keys=(),
            door_profiles={},
            base_plate_profiles={},
            divider_profiles={},
            inner_profiles={},
            box_piece_profiles={},
            current_piece_keys=(),
            source_parts=("box_body", "head", "tail", "door", "base_plate"),
            available_parts=("box_body", "head", "tail"),
            source_part_features={},
            known_feature_keys=(),
            single_door_profiles=target_door,
            single_base_plate_profiles=target_base,
            active_part=None,
            selected_part=None,
        )
    )
    plan = module.build_derived_part_sync_plan(request)

    assert tuple(item.part_key for item in plan.add_parts) == ("door", "base_plate")
    assert tuple(item.part_key for item in plan.stash_profiles) == ("door", "base_plate")
    assert module.materialize_profiles(plan.stash_profiles[0]) == target_door
    assert module.materialize_profiles(plan.stash_profiles[1]) == target_base
