"""Engine-owned rear-panel manufacturing contract boundary.

A UI or external adapter supplies an input snapshot only; it must never
calculate Receiving W - 2.5T or the corner-dependent panel height.
"""
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.sheetmetal_geometry import box_body_height_from_corner_policies
from gui_modules.application import manufacturing_adapter


def test_receiving_back_panel_sizing_and_fixed_features_resolve_in_engine():
    state = family_policy.resolve_box_body_structure_state("受電箱", None)
    snapshot = {"model": "金庫型", "w": 1200.0, "h": 1600.0, "t": 2.0}
    resolved = manufacturing_api.resolve_box_body_back_panel_contract(
        "受電箱", snapshot, structure_state=state,
    )
    expected_height = box_body_height_from_corner_policies(1600.0, 2.0)
    assert resolved["mode"] == "FULL"
    assert resolved["panel_width"] == pytest.approx(1195.0)
    assert resolved["full_panel_height"] == pytest.approx(expected_height)
    assert len(resolved["fixed_slot_datums"]) == 4
    assert len(resolved["fixed_slot_profiles"]) == 4

    # Even a stale incoming GUI model cannot override the engine Family.
    equivalent = family_policy.resolve_back_panel_contract(
        "受電箱", {**snapshot, "model": "受電箱"},
        structure_state=state,
        panel_width=1200.0 - 2.5 * 2.0,
        full_panel_height=expected_height,
    )
    assert resolved == equivalent


def test_vault_has_no_receiving_back_panel_contract():
    state = family_policy.resolve_box_body_structure_state("金庫型", None)
    assert manufacturing_api.resolve_box_body_back_panel_contract(
        "金庫型", {"w": 1200.0, "h": 1600.0, "t": 2.0},
        structure_state=state,
    ) == {}


def test_receiving_engine_rejects_invalid_rear_panel_size():
    state = family_policy.resolve_box_body_structure_state("受電箱", None)
    with pytest.raises(ValueError, match="rear-panel dimensions"):
        manufacturing_api.resolve_box_body_back_panel_contract(
            "受電箱", {"w": 4.0, "h": 1600.0, "t": 2.0},
            structure_state=state,
        )


def test_gui_adapter_only_forwards_back_panel_input_to_engine():
    source = inspect.getsource(manufacturing_adapter._box_body_part_spec_from_values)
    assert "manufacturing_api.resolve_box_body_back_panel_contract" in source
    assert "back_width_comp_t" not in source
    assert "box_body_height_from_corner_policies" not in source
