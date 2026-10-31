"""#2517 Engine classifies existing physical derivative IDs; GUI only presents."""
from __future__ import annotations

import inspect
import pytest

from ae_engine import manufacturing_api
import phase6_part_navigation as navigation
import phase6_settings_profile_projection as settings


@pytest.mark.parametrize("key", [
    "box_body:left_side", "box_body:right_side",
    "box_body:back", "box_body:legacy_piece",
])
def test_engine_boxbody_physical_id_matches_navigation(key):
    assert manufacturing_api.is_box_body_physical_piece_key(key)
    assert navigation.is_box_body_physical_piece_key(key)
    assert settings.is_derived_physical_part_key(key)


@pytest.mark.parametrize("key", [
    None, "", "box_body", "box_body:divider:1",
    "head", "door_c1_r1", "base_plate", "custom:1",
])
def test_box_body_children_exclude_logical_parents_and_divider(key):
    assert not manufacturing_api.is_box_body_physical_piece_key(key)


@pytest.mark.parametrize("key", [
    "door_c1_r1", "base_plate_c2_r3",
    "base_plate:fixing_plate:left", "base_plate:nfb_layer:0",
    "nfb_pad:1", "box_body:divider:1",
    "inner_door:a_frame", "inner_door:7:panel",
])
def test_engine_classifies_known_derived_physical_id_families(key):
    assert manufacturing_api.is_derived_physical_part_key(key)
    assert settings.is_derived_physical_part_key(key)


@pytest.mark.parametrize("key", [
    None, "", "door", "box_body", "head", "tail", "base_plate",
    "indicator_box", "indicator_door", "custom:1",
    "door_c1_rA", "inner_door:7", "inner_door:7:top",
])
def test_engine_does_not_mark_operator_or_custom_source_as_derived(key):
    assert not manufacturing_api.is_derived_physical_part_key(key)


def test_phase6_classifiers_are_only_engine_api_delegates():
    for function, name in (
        (settings.is_derived_physical_part_key, "is_derived_physical_part_key"),
        (navigation.is_box_body_physical_piece_key, "is_box_body_physical_piece_key"),
    ):
        source = inspect.getsource(function)
        assert f"manufacturing_api.{name}(value)" in source
        assert "startswith(" not in source
        assert "fullmatch(" not in source


def test_physical_child_hierarchy_does_not_change():
    ids = ("box_body", "box_body:left_side", "box_body:back",
           "box_body:divider:1", "head")
    rows = navigation.project_hierarchy(ids)
    assert [(row.part_key, row.parent_key) for row in rows] == [
        ("box_body", None),
        ("box_body:left_side", "box_body"),
        ("box_body:back", "box_body"),
        ("box_body:divider:1", None),
        ("head", None),
    ]
    assert navigation.operator_part_selector_keys(ids) == (
        "box_body", "box_body:divider:1", "head"
    )


def test_settings_plan_does_not_build_fake_derived_sheet_fold_profiles():
    request = settings.SettingsProfileProjectionRequest(
        settings_values={},
        input_snapshot={"model": "金庫型", "w": 400, "h": 600, "d": 200, "t": 2, "fw": 25},
        available_parts=("box_body", "door", "door_c1_r1", "box_body:back"),
        active_part="door",
    )
    plan = settings.build_settings_profile_projection(request)
    assert "door" in plan.part_profiles
    assert "door_c1_r1" not in plan.part_profiles
    assert "box_body:back" not in plan.part_profiles
