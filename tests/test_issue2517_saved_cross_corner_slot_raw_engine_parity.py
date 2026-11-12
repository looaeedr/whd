"""#2517: saved CornerType CROSS slot/rotation retain original Engine truth."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, corner_selection_residual,
)
import phase6_project_file as project
from gui_modules.application import fold_designer_manufacturing_projection as gui


def _typed():
    return {
        "top_left": CornerTypeSelection(
            CornerTypeId.CROSS, slot_width=12.0,
            slot_straight_depth=16.0, slot_radius=4.0,
        ),
        "top_right": CornerTypeSelection(CornerTypeId.CROSS),
        "bottom_left": CornerTypeSelection(CornerTypeId.CROSS),
        "bottom_right": CornerTypeSelection(CornerTypeId.CROSS),
    }


def _raw():
    return {
        "divider": {
            key: {
                "type_id": "CROSS",
                "rotation_quadrants": 0,
                **(
                    {
                        "slot_width": 12.0,
                        "slot_straight_depth": 16.0,
                        "slot_radius": 4.0,
                    } if key == "top_left" else {}
                ),
            }
            for key in ("top_left", "top_right", "bottom_left", "bottom_right")
        },
    }


def test_actual_project_save_reload_preserves_exact_source_cross_slot_and_residual(
    tmp_path,
):
    authored = {"model": "金庫型", "w": 800.0, "h": 1600.0,
                "d": 350.0, "t": 2.0, "fw": 25.0,
                "corner_state": {"divider": _typed()}}
    original = deepcopy(authored)
    before = api.corner_policy_from_payload(
        authored["corner_state"], "divider", authored["fw"],
    )
    assert before.top_left.slot_width == 12.0

    path = project.write_project(
        tmp_path / "corner-cross-physical-slot.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": authored},
    )
    restored = project.read_project(path)["snapshot"]
    saved_selection = restored["corner_state"]["divider"]["top_left"]
    assert isinstance(saved_selection, dict)
    assert saved_selection["slot_width"] == 12.0
    assert saved_selection["slot_straight_depth"] == 16.0
    assert saved_selection["slot_radius"] == 4.0

    after = api.corner_policy_from_payload(
        restored["corner_state"], "divider", restored["fw"],
    )
    from_gui = gui._fold_designer_corner_policy_from_payload(
        restored["corner_state"], "divider", restored["fw"],
    )
    assert from_gui == after == before
    assert after.top_left.slot_radius == 4.0
    # Original certified CROSS standard owner, NOT a new GUI or custom-cut
    # formula: preserve the complete optional U-slot residual through JSON.
    original_residual = corner_selection_residual(
        before.top_left, thickness=2.0, fw=25.0,
    )
    reload_residual = corner_selection_residual(
        after.top_left, thickness=2.0, fw=25.0,
    )
    assert reload_residual == original_residual
    assert (
        reload_residual.slot_width,
        reload_residual.slot_straight_depth,
        reload_residual.slot_radius,
    ) == (12.0, 16.0, 4.0)
    assert authored == original


@pytest.mark.parametrize("broken", (
    True, 1.75, "1.75", None, float("inf"), float("nan"),
))
def test_saved_fractional_boolean_or_nonfinite_corner_rotation_cannot_be_truncated(broken):
    original = _raw()
    source = deepcopy(original)
    source["divider"]["top_right"]["rotation_quadrants"] = broken
    before = deepcopy(source)
    with pytest.raises((TypeError, ValueError), match="corner rotation"):
        api.corner_policy_from_payload(source, "divider", 25.0)
    assert source == before


@pytest.mark.parametrize("bad", (
    {"slot_width": True, "slot_straight_depth": 16.0, "slot_radius": 4.0},
    {"slot_width": 12.0, "slot_straight_depth": None, "slot_radius": 4.0},
    {"slot_width": 12.0, "slot_straight_depth": "nan", "slot_radius": 4.0},
    {"slot_width": 12.0, "slot_straight_depth": 16.0, "slot_radius": -1},
))
def test_saved_corrupt_cross_slot_never_disappears_into_fake_standard_cutting(bad):
    source = _raw()
    source["divider"]["top_left"].update(bad)
    original = deepcopy(source)
    with pytest.raises((TypeError, ValueError)):
        api.corner_policy_from_payload(source, "divider", 25.0)
    assert source == original


@pytest.mark.parametrize("invalid", (True, False, float("nan"), float("inf"), -1))
def test_invalid_physical_fw_rejected_before_corner_geometry(invalid):
    original = _raw()
    with pytest.raises((TypeError, ValueError), match="CORNER_POLICY_PHYSICAL_FW_INVALID"):
        api.corner_policy_from_payload(original, "divider", invalid)


def test_missing_explicit_corner_source_not_silently_replaced_by_cross():
    source = _raw()
    source["divider"]["top_left"] = None
    before = deepcopy(source)
    with pytest.raises((TypeError, ValueError), match="CORNER_POLICY_SAVED_SELECTION_INVALID"):
        api.corner_policy_from_payload(source, "divider", 25)
    assert source == before


def test_gui_remains_plain_public_api_caller_for_saved_corner_payload():
    source = inspect.getsource(gui._fold_designer_corner_policy_from_payload)
    assert "manufacturing_api.corner_policy_from_payload(" in source
    assert "CornerTypeSelection(" not in source
    assert "slot_width" not in source
