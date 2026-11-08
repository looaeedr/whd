"""#2517: indicator result/snapshot must share raw public Engine source gates."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import cabinet_controller
from gui_modules.project import export_actions
from gui_modules.parts.panels.door import normalize_door_indicator_state


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


def host(*, box=True, door=False, multi=False, layers="2",
         groups=("3", "2", "2", "2", "2", "2"), saved=None):
    saved = {} if saved is None else saved
    return SimpleNamespace(
        is_indicator_box_var=Var(box),
        is_door_indicator_var=Var(door),
        multi_door_enabled_var=Var(multi),
        indicator_l_var=Var(layers),
        indicator_layer_g_vars=[Var(value) for value in groups],
        door_indicator_l_var=Var(layers),
        door_indicator_layer_g_vars=[Var(value) for value in groups],
        door_indicator_offset_x=-1.25,
        door_indicator_offset_y=2.75,
        is_box_dist_var=Var(False),
        door_layout_selected_var=Var("0:0"),
        door_layout_indicator_states=deepcopy(saved),
        get_door_layout_cells=lambda: (),
        _normalize_door_indicator_state=lambda _: pytest.fail(
            "saved physical groups must not use GUI display repair"
        ),
    )


@pytest.mark.parametrize("flag,enabled", [
    (True, True), (1, True), ("true", True), ("1", True),
    (False, False), (0, False), ("false", False), ("0", False),
])
def test_result_presence_follows_public_engine_boolean(flag, enabled):
    ui = host(box=flag, multi="false")
    result = cabinet_controller._active_indicator_box_groups_for_results(ui)
    assert result == ((3, 2) if enabled else None)
    assert cabinet_controller._has_any_indicator_box(ui) is enabled
    assert api.normalize_operator_settings_boolean(flag) is enabled


@pytest.mark.parametrize("invalid", [None, "false-ish", "2", 2, -1, 0.5, [], {}])
def test_invalid_result_presence_cannot_become_a_manufacturing_box(invalid):
    ui = host(box=invalid)
    with pytest.raises(ValueError):
        cabinet_controller._active_indicator_box_groups_for_results(ui)
    with pytest.raises(ValueError):
        cabinet_controller._has_any_indicator_box(ui)


@pytest.mark.parametrize("layers,groups", [
    (True, ("3", "2")), ("7", ("3", "2")), ("0", ("3", "2")),
    ("1.5", ("3", "2")), ("2", (True, "2")),
    ("2", ("3", "0")), ("2", ("3", "9")),
    ("2", ("3",)), ("2", (3.5, "2")), ("2", ("nan", "2")),
])
def test_invalid_live_result_groups_are_not_clamped_or_defaulted(layers, groups):
    ui = host(layers=layers, groups=groups)
    with pytest.raises(ValueError, match="指示燈"):
        cabinet_controller._active_indicator_box_groups_for_results(ui)


def test_multi_door_summary_and_export_presence_share_saved_engine_source():
    saved = {"0:0": {
        "mode": "indicator_box", "layers": "2",
        "groups": ["3", "2"], "offset_x": 0, "offset_y": 0,
        "is_box_dist": False,
    }}
    ui = host(multi="true", box="false", saved=saved)
    accepted = api.project_operator_door_cell_indicator_manufacturing_source(saved["0:0"])
    assert cabinet_controller._active_indicator_box_groups_for_results(ui) == tuple(
        accepted["groups"][:accepted["layers"]]
    )
    assert cabinet_controller._has_any_indicator_box(ui) is True
    assert ui.door_layout_indicator_states == saved


@pytest.mark.parametrize("bad", [
    {"mode": "indicator_box", "layers": 1.5, "groups": [2]},
    {"mode": "indicator_box", "layers": "1", "groups": [True]},
    {"mode": "indicator_box", "layers": 2, "groups": [2]},
])
def test_corrupt_saved_multi_door_box_does_not_become_result_or_export(bad):
    ui = host(multi=True, saved={"0:0": bad})
    with pytest.raises(ValueError):
        cabinet_controller._active_indicator_box_groups_for_results(ui)
    with pytest.raises(ValueError):
        cabinet_controller._has_any_indicator_box(ui)
    assert ui.door_layout_indicator_states == {"0:0": bad}


@pytest.mark.parametrize("box,door,expected", [
    ("false", "true", "indicator"),
    ("false", "false", "none"),
    ("true", "false", "indicator_box"),
    ("0", "1", "indicator"),
    (0, 1, "indicator"),
])
def test_single_door_saved_mode_matches_raw_engine_flags(box, door, expected):
    ui = host(box=box, door=door)
    ui._normalize_door_indicator_state = normalize_door_indicator_state
    snapshot = export_actions._single_door_indicator_state_snapshot(ui)
    assert snapshot["mode"] == expected
    assert snapshot["box_enabled"] is (expected == "indicator_box")
    assert snapshot["enabled"] is (expected == "indicator")
    if expected != "none":
        engine = api.normalize_operator_hole_editor_indicator_state({
            "mode": expected, "layers": "2", "groups": ["3", "2"] + ["2"] * 4,
            "offset_x": -1.25, "offset_y": 2.75, "is_box_dist": False,
        })
        for key in ("mode", "layers", "groups", "offset_x", "offset_y", "is_box_dist"):
            assert snapshot[key] == engine[key]


@pytest.mark.parametrize("box,door", [
    ("untrusted", "false"), (True, "invalid"), (False, "invalid"),
])
def test_invalid_single_door_flag_does_not_write_saved_source(box, door):
    ui = host(box=box, door=door)
    before = tuple(v.get() for v in (
        ui.is_indicator_box_var, ui.is_door_indicator_var,
        ui.indicator_l_var, ui.door_indicator_l_var,
    ))
    if box is True:
        # Box has explicit precedence and an inactive Door flag is irrelevant.
        assert export_actions._single_door_indicator_state_snapshot(ui)["mode"] == "indicator_box"
    else:
        with pytest.raises(ValueError):
            export_actions._single_door_indicator_state_snapshot(ui)
    assert before == tuple(v.get() for v in (
        ui.is_indicator_box_var, ui.is_door_indicator_var,
        ui.indicator_l_var, ui.door_indicator_l_var,
    ))


def test_gui_result_and_snapshot_have_no_lossy_physical_flag_or_group_cast():
    result = inspect.getsource(cabinet_controller._active_indicator_box_groups_for_results)
    export = inspect.getsource(export_actions._single_door_indicator_state_snapshot)
    assert "normalize_operator_hole_editor_indicator_state(" in result
    assert "project_operator_door_cell_indicator_manufacturing_source(" in result
    assert "max(1, min(6, int(" not in result
    assert "normalize_operator_settings_boolean(" in export
    assert "if self.is_indicator_box_var.get():" not in export
