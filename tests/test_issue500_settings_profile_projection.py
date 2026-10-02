from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest


MODULE = Path("phase6_settings_profile_projection.py")
BRIDGE = Path("fold_designer_bridge.py")


def _module():
    assert MODULE.is_file(), "RED R2: missing pure Settings-to-Profile projection owner"
    import phase6_settings_profile_projection as projection
    return projection


def _bridge_function_source(name: str) -> str:
    source = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BRIDGE))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_issue500_requires_frozen_request_and_plan_contracts():
    projection = _module()
    request_type = projection.SettingsProfileProjectionRequest
    plan_type = projection.SettingsProfileProjectionPlan

    assert dataclasses.is_dataclass(request_type)
    assert dataclasses.is_dataclass(plan_type)
    assert request_type.__dataclass_params__.frozen
    assert plan_type.__dataclass_params__.frozen


def test_issue500_pure_projection_is_deterministic_and_carries_required_plan_fields():
    projection = _module()
    request = projection.SettingsProfileProjectionRequest(
        settings_values={
            "w": 800,
            "h": 1100,
            "d": 300,
            "t": 2,
            "fw": 29,
        },
        input_snapshot={
            "w": 800,
            "h": 1100,
            "d": 300,
            "t": 2,
            "fw": 29,
            "part_dimensions": {},
        },
        available_parts=("box_body", "door", "base_plate"),
        existing_profiles={},
        box_body_profile=(),
        active_part="box_body",
        reset_box_profile=False,
    )

    first = projection.build_settings_profile_projection(request)
    second = projection.build_settings_profile_projection(request)

    assert first == second
    assert first.active_part == "box_body"
    assert "box_body" in first.part_dimensions
    assert "head" in first.part_dimensions
    assert "tail" in first.part_dimensions
    assert "door" in first.part_dimensions
    assert "base_plate" in first.part_dimensions
    assert tuple(first.active_profiles)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.active_part = "door"


def test_issue500_projection_owner_has_no_bridge_tk_workspace_render_or_manufacturing_import():
    projection = _module()
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = {
        name
        for name in imports
        if name == "fold_designer_bridge"
        or name == "tkinter"
        or name.startswith("tkinter.")
        or name == "phase6_designer_workspace"
        or name == "phase6_workspace_navigation_controller"
        or "renderer" in name
        or "manufacturing" in name
    }
    assert forbidden == set()


def test_issue500_dimension_projection_leaves_bridge_as_narrow_delegate():
    source = _bridge_function_source("_phase6_recalculate_part_dimensions")
    assert "project_part_dimensions" in source
    forbidden = (
        "calculate_door_finished_size",
        "derive_door_layout_cells",
        "cabinet_family_policy.door_material_frame_width",
        'snapshot["part_dimensions"]',
    )
    assert [token for token in forbidden if token in source] == []


def test_issue500_profile_projection_leaves_bridge_as_plan_apply_boundary():
    source = _bridge_function_source("_phase6_refresh_profiles_from_settings")
    assert "build_settings_profile_projection" in source
    forbidden = (
        "build_box_body_profile",
        "merge_box_body_profile",
        "build_endcap_xy_profiles",
        "build_standard_part_profiles",
        "_merge_keyed_profiles",
        "designer_workspace.stash_profiles",
        "bend_ui.render",
    )
    assert [token for token in forbidden if token in source] == []
