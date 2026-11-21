"""#3317: per-corner R/hole source persists through real .p6fold Save→Reload.

Only operator CHECK inputs are saved; no derived sheet, RBA/T mesh or CNC
permission is serialized. Old project snapshots default to ROUND_R.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from phase6_project_file import PROJECT_SCHEMA_V1, write_project, read_project


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_project_roundtrip_preserves_checked_relief_mode_and_no_cnc(tmp_path, mode):
    selected = {"head": {"bottom_left": "V_MITER_CHECK"}}
    modes = {"head": {"bottom_left": mode}}
    saved = write_project(tmp_path / f"{mode}.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "自訂", "w": 500, "h": 600, "d": 300, "t": 2,
            "v_miter_gui_check_corners": selected,
            "v_miter_gui_relief_modes": modes,
        },
    })
    loaded = read_project(saved)["snapshot"]
    assert api.normalize_operator_v_miter_gui_relief_modes(
        loaded["v_miter_gui_relief_modes"],
        loaded["v_miter_gui_check_corners"],
    ) == modes
    assert "formed_source_outline" not in repr(loaded)
    assert "corrected_remaining_outline" not in repr(loaded)
    with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
        api.require_no_operator_v_miter_gui_check_for_export(loaded)


def test_saved_old_v_choice_without_mode_falls_back_to_round_r(tmp_path):
    selected = {"door": {"bottom_left": "V_MITER_CHECK"}}
    path = write_project(tmp_path / "legacy_v.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {"model": "自訂", "w": 400, "h": 400, "d": 300,
                     "t": 2, "v_miter_gui_check_corners": selected},
    })
    readback = read_project(path)["snapshot"]
    assert api.normalize_operator_v_miter_gui_relief_modes(
        readback.get("v_miter_gui_relief_modes"), selected,
    ) == {}


@pytest.mark.parametrize("bad", [
    {"door": {"bottom_left": "CERTIFIED"}},
    {"door": {"bottom_left": True}},
    {"door": {"bottom_left": 1}},
    {"door": {"top": "RELIEF_HOLE"}},
    {"foo": {"bottom_left": "ROUND_R"}},
    [("door", "bottom_left")],
])
def test_relief_mode_schema_rejects_forgery(bad):
    with pytest.raises(GeometryError):
        api.normalize_operator_v_miter_gui_relief_modes(bad)


def test_relief_modes_reject_orphan_and_trim_when_v_type_removed():
    selected = {"door": {"bottom_left": "V_MITER_CHECK"}}
    raw = {"door": {"bottom_left": "RELIEF_HOLE", "bottom_right": "ROUND_R"}}
    with pytest.raises(GeometryError, match="ORPHAN"):
        api.normalize_operator_v_miter_gui_relief_modes(raw, selected)
    trimmed = api.project_operator_v_miter_gui_selected_relief_modes(raw, selected)
    assert trimmed == {"door": {"bottom_left": "RELIEF_HOLE"}}
    original = deepcopy(raw)
    assert api.project_operator_v_miter_gui_selected_relief_modes(raw, {}) == {}
    assert raw == original


def test_relief_transition_tracks_pair_and_checks_original_v_selection():
    choices = {"door": {
        "bottom_left": "V_MITER_CHECK", "bottom_right": "V_MITER_CHECK",
    }}
    same = {"bottom": True, "top": True}
    rows = api.change_operator_v_miter_gui_relief_mode(
        {}, choices, "door", "bottom", same, relief_mode="RELIEF_HOLE",
    )
    assert rows["door"] == {
        "bottom_left": "RELIEF_HOLE", "bottom_right": "RELIEF_HOLE",
    }
    rows2 = api.change_operator_v_miter_gui_relief_mode(
        rows, choices, "door", "bottom", same, relief_mode="ROUND_R",
    )
    assert all(v == "ROUND_R" for v in rows2["door"].values())
    assert rows["door"]["bottom_left"] == "RELIEF_HOLE"
    with pytest.raises(GeometryError, match="SELECTED_V_REQUIRED"):
        api.change_operator_v_miter_gui_relief_mode(
            {}, {"door": {"bottom_left": "V_MITER_CHECK"}},
            "door", "bottom", same, relief_mode="RELIEF_HOLE",
        )
    with pytest.raises(GeometryError, match="PAIR_IS_SPLIT"):
        api.change_operator_v_miter_gui_relief_mode(
            {}, choices, "door", "bottom",
            {"bottom": False}, relief_mode="ROUND_R",
        )


def _new_live_gui():
    import tkinter as tk
    import gui
    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("自訂")
    app.workspace_controller.set_active_part("door")
    app.select_manual_corner("bottom")
    return root, app


def _close_gui(root, app):
    designer = getattr(app, "fold_designer_app", None)
    if designer is not None:
        try:
            designer.root.destroy()
        except Exception:
            pass
    root.destroy()


def test_true_gui_mode_switch_and_new_gui_reload_keeps_hole(tmp_path):
    first, app = _new_live_gui()
    second = None
    app2 = None
    try:
        app.set_v_miter_gui_check_choice()
        app.v_miter_first_bend_axis_var.set("x")
        app.set_v_miter_gui_first_bend_axis()
        app.v_miter_relief_mode_var.set("RELIEF_HOLE")
        app.set_v_miter_gui_relief_mode()
        assert app.v_miter_gui_relief_modes["door"]["bottom_left"] == "RELIEF_HOLE"
        committed = app._compose_phase6_project_snapshot_from_main_gui()
        modes = committed["v_miter_gui_relief_modes"]
        assert modes["door"]["bottom_left"] == "RELIEF_HOLE"
        path = write_project(tmp_path / "actual_operator_v_hole.p6fold", {
            "schema": PROJECT_SCHEMA_V1, "snapshot": committed,
        })
        reread = read_project(path)["snapshot"]
        second, app2 = _new_live_gui()
        app2._apply_phase6_project_snapshot(reread)
        app2.workspace_controller.set_active_part("door")
        app2.select_manual_corner("bottom")
        assert app2.v_miter_relief_mode_var.get() == "RELIEF_HOLE"
        result = app2._project_v_miter_gui_check_for_corner("door", "bottom")
        assert result.trial_defaults.relief_mode.value == "RELIEF_HOLE"
        assert result.factory_bottom_relief_check is not None, result.factory_bottom_relief_failure
        assert result.manufacturing_status.endswith("UNCERTIFIED")
        assert app2._compose_phase6_project_snapshot_from_main_gui()[
            "v_miter_gui_relief_modes"
        ] == modes
    finally:
        if app2 is not None:
            _close_gui(second, app2)
        _close_gui(first, app)
