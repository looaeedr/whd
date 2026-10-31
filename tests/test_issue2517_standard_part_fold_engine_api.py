"""#2517 Engine owns standard X/Y Fold profile geometry; GUI routes custom only."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import manufacturing_api, build_standard_part_fold_profiles
import phase6_settings_profile_projection as settings


def _snapshot():
    return {
        "model": "金庫型", "w": 400, "h": 600, "d": 250,
        "t": 2, "fw": 25,
        "part_dimensions": {
            "door": {"width": 300, "height": 500},
            "door_c1_r1": {"width": 300, "height": 500},
            "base_plate": {"width": 250, "height": 450},
            "indicator_box": {"width": 180, "height": 210},
            "indicator_door": {"width": 100, "height": 130},
        },
    }


@pytest.mark.parametrize("key,expected_x,expected_y", [
    ("door", [20, 296, 20], [20, 496, 20]),
    ("door_c1_r1", [20, 296, 20], [20, 496, 20]),
    ("base_plate", [20, 250, 20], [20, 450, 20]),
    ("indicator_box", [49, 82, 49], [49, 112, 49]),
    ("indicator_door", [19, 62, 19], [19, 92, 19]),
])
def test_engine_standard_profiles_match_existing_material_ui_contract(key, expected_x, expected_y):
    snapshot = _snapshot()
    rows = build_standard_part_fold_profiles(snapshot, key)
    assert [row["len"] for row in rows["X"]] == expected_x
    assert [row["len"] for row in rows["Y"]] == expected_y
    assert settings.build_standard_part_profiles(snapshot, key) == rows
    assert [row["ui_len_add"] for row in rows["X"]] == [2, 4, 2]
    assert [row["ui_len_add"] for row in rows["Y"]] == [2, 4, 2]


def test_engine_is_public_and_gui_does_not_own_material_formulas():
    assert build_standard_part_fold_profiles is manufacturing_api.build_standard_part_fold_profiles
    source = inspect.getsource(settings.build_standard_part_profiles)
    assert "build_standard_part_fold_profiles(snapshot, part_key)" in source
    assert "build_custom_part_profiles(snapshot, part_key)" in source
    for token in ("_three_segment_profile", "outside_add", "x_core", "apply_outside_dimension_compensation"):
        assert token not in source


def test_standard_engine_api_fails_closed_for_custom_physical_part():
    with pytest.raises(ValueError, match="CUSTOM_FOLD_REQUIRES_CUSTOM_API"):
        build_standard_part_fold_profiles(_snapshot(), "custom:1")


def test_gui_custom_id_still_uses_existing_persisted_custom_fold_contract():
    snapshot = _snapshot()
    snapshot["custom_parts"] = {
        "next_id": 2,
        "items": {"custom:1": {
            "physical_id": "custom:1", "display_name": "測試板",
            "fold_axis": "X", "transverse_length": 333,
            "per_box_count": 1, "fold_preset": "OUTSIDE_17_100",
        }},
    }
    from phase6_custom_fold_profiles import build_custom_part_profiles
    assert settings.build_standard_part_profiles(snapshot, "custom:1") == build_custom_part_profiles(snapshot, "custom:1")


def test_receiving_baseplate_uses_same_physical_fold_source_for_standard_gui():
    snapshot = _snapshot()
    snapshot["model"] = "受電箱"
    rows = build_standard_part_fold_profiles(snapshot, "base_plate")
    assert rows == settings.build_standard_part_profiles(snapshot, "base_plate")
    assert rows["X"] and rows["Y"]
