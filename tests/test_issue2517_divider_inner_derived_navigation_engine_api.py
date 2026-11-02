"""#2517: Divider and InnerDoor physical source belongs to public Engine API."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family
from ae_engine.door_dividers import derive_box_body_dividers, divider_part_profiles
from ae_engine.inner_door_frames import (
    derive_all_inner_door_frames, inner_door_frame_part_profiles, InnerDoorFrameSet,
)
from ae_engine.inner_door_panels import inner_door_panel_part_profiles


def _receiving():
    return {
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "door_layout_scope": "main", "door_handle_edges": {"0:0": "RIGHT"},
        "inner_doors": [{"stable_id": "upper", "cell_key": "0:0"}],
    }


def test_receiving_divider_panel_and_frame_come_from_exact_family_sources():
    source = _receiving()
    before = deepcopy(source)
    result = api.project_operator_derived_divider_inner_profiles(source)
    dividers = derive_box_body_dividers(
        ((800.0, (1100.0, 500.0)),), depth=350.0, thickness=2.0,
        layout_scope="main", handle_edges={"0:0": "RIGHT"},
        model_name="受電箱", frame_width=29.0,
    )
    assert dict(result.divider_profiles) == divider_part_profiles(dividers)
    panels = family.derive_inner_door_panels(source)
    frames = derive_all_inner_door_frames(family.derive_inner_door_frame_sets(source))
    expected_inner = inner_door_panel_part_profiles(panels)
    expected_inner.update(inner_door_frame_part_profiles(frames))
    assert dict(result.inner_profiles) == expected_inner
    assert tuple(result.divider_part_ids) == tuple(x.stable_id for x in dividers)
    assert result.inner_part_ids == (
        *(frame.stable_id for frame in frames),
        *(panel.stable_id for panel in panels),
    )
    assert "inner_door:upper:panel" in result.inner_profiles
    assert not any(key.endswith(":bottom_frame") for key in result.inner_profiles)
    assert source == before
    with pytest.raises(FrozenInstanceError):
        result.inner_part_ids = ()


def test_vault_legacy_inner_door_frame_spans_preserve_existing_profiles():
    snapshot = {
        "model": "金庫型", "t": 2.0, "inner_doors": [{
            "stable_id": "legacy-A",
            "frame_spans": {"top": 500.0, "left": 700.0},
            "included_frame_sides": ("top", "left"),
        }],
    }
    rows = api.project_operator_derived_divider_inner_profiles(snapshot)
    expected = derive_all_inner_door_frames((InnerDoorFrameSet(
        inner_door_id="legacy-A", spans={"top": 500.0, "left": 700.0},
        thickness=2.0, included_sides=("top", "left"),
    ),))
    assert dict(rows.inner_profiles) == inner_door_frame_part_profiles(expected)
    assert rows.inner_part_ids == tuple(frame.stable_id for frame in expected)
    assert not rows.divider_profiles


def test_missing_topology_removes_derived_parts_without_invented_geometry():
    source = _receiving()
    source["multi_door_enabled"] = False
    result = api.project_operator_derived_divider_inner_profiles(source)
    assert result.divider_part_ids == ()
    assert result.inner_part_ids == ()
    assert not result.divider_profiles
    assert not result.inner_profiles


def test_malformed_divider_topology_cannot_become_selector_geometry():
    source = _receiving()
    source["door_layout_columns"] = [[800.0, [0.0, 500.0]]]
    with pytest.raises(ValueError):
        api.project_operator_derived_divider_inner_profiles(source)


def test_gui_derived_selection_only_consumes_public_physical_projection():
    from gui_modules.application import fold_designer_composition_shell_settings as gui
    source = inspect.getsource(gui.sync_authoritative_derived_parts)
    assert "manufacturing_api.project_operator_derived_divider_inner_profiles(" in source
    for token in (
        "derive_box_body_dividers(", "derive_all_inner_door_frames(",
        "inner_door_panel_part_profiles(", "inner_door_frame_part_profiles(",
        "derive_inner_door_frame_sets(", "derive_inner_door_panels(",
    ):
        assert token not in source
    import ae_engine.operator_derived_navigation as owner
    assert "from phase6_" not in inspect.getsource(owner)
    assert "from gui_modules" not in inspect.getsource(owner)
