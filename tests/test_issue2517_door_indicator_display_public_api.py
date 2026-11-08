"""#2517: Door Indicator display-only legacy repair belongs to public Engine."""
from copy import deepcopy
import inspect
import json

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.fold_designer_snapshot_dimensions import (
    project_operator_door_indicator_display_state as original_projection,
)
from gui_modules.parts.panels.door import normalize_door_indicator_state as gui_display
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def test_api_is_same_original_headless_owner_in_root_and_facade():
    assert ae_engine.project_operator_door_indicator_display_state is original_projection
    assert api.project_operator_door_indicator_display_state is original_projection
    assert "project_operator_door_indicator_display_state" in ae_engine.__all__


@pytest.mark.parametrize("raw", [
    None,
    {},
    {"mode": "indicator", "layers": "2", "groups": ["3", 2, 5],
     "offset_x": "-1.25", "offset_y": "2.5", "is_box_dist": "false"},
    {"enabled": "TRUE", "box_enabled": "false", "layers": 1, "groups": [3]},
    {"enabled": "false", "box_enabled": "true", "layers": 1, "groups": [2]},
    {"mode": "other", "enabled": "off", "groups": [False, "NaN", 0, -2, 8]},
    {"mode": "indicator", "layers": True, "groups": [False, 1.5, "oops"],
     "offset_x": float("nan"), "offset_y": float("inf"), "is_box_dist": "bad"},
])
def test_gui_matches_detached_engine_legacy_display_without_writing_raw(raw):
    before = deepcopy(raw)
    expected = original_projection(raw)
    assert gui_display(raw) == expected
    assert api.project_operator_door_indicator_display_state(raw) == expected
    assert raw == before
    if raw is not None:
        result = gui_display(raw)
        result["groups"][0] = 999
        assert raw == before


@pytest.mark.parametrize("invalid", [False, 0, [], "bad", True])
def test_invalid_root_is_not_replaced_with_empty_hole_state(invalid):
    with pytest.raises(ValueError, match="mapping"):
        gui_display(invalid)
    with pytest.raises(ValueError, match="mapping"):
        original_projection(invalid)


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_reopened_bad_door_cell_keeps_raw_and_engine_refuses_manufacturing(family, tmp_path):
    raw = {
        "mode": "indicator", "layers": 2,
        "groups": [False, 3, 2, 2, 2, 2],
        "offset_x": 1.125, "offset_y": -2.75, "is_box_dist": False,
    }
    stored = {"model": family, "door_layout_indicator_states": {"0:0": raw}}
    filename = write_project(
        tmp_path / f"door-display-{family}",
        {"schema": PROJECT_SCHEMA, "snapshot": stored},
    )
    reopened = read_project(filename)["snapshot"]
    saved = reopened["door_layout_indicator_states"]["0:0"]
    before = json.dumps(saved, sort_keys=True)
    display = gui_display(saved)
    assert display["groups"][0] == 2
    assert json.dumps(saved, sort_keys=True) == before
    with pytest.raises(ValueError):
        api.project_operator_door_layout_indicator_snapshot_states({"0:0": saved})
    with pytest.raises(ValueError):
        api.project_operator_door_cell_indicator_manufacturing_source(saved)


def test_gui_does_not_own_secondary_mode_group_or_offset_rules():
    source = inspect.getsource(gui_display)
    assert "manufacturing_api.project_operator_door_indicator_display_state(" in source
    assert "float(" not in source and "bool(" not in source
    assert "groups" not in source and "offset" not in source
