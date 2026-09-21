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
