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


def test_r2_bridge_builds_immutable_plan_before_first_navigation_mutation():
    from pathlib import Path

    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_phase6_sync_authoritative_derived_parts"
    )
    body = ast.get_source_segment(source, fn) or ""
    assert "DerivedPartProjectionRequest(" in body
    assert "build_derived_part_sync_plan(request)" in body

    plan_pos = body.index("build_derived_part_sync_plan(request)")
    mutation_tokens = (
        "navigation.remove_part(",
        "navigation.sync_derived_parts(",
        "navigation.stash_features(",
        "navigation.add_part(",
        "navigation.stash_profiles(",
        "navigation.set_active_part(",
        "navigation.set_selected_part(",
    )
    positions = [body.index(token) for token in mutation_tokens if token in body]
    assert positions
    assert plan_pos < min(positions)
