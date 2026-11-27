"""#3317 operator first physical V bend must be explicit, persistent, CHECK only."""
from __future__ import annotations

from copy import deepcopy
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project


@pytest.mark.parametrize("axis", ("x", "y"))
def test_first_bend_saved_source_roundtrip_without_cnc(tmp_path, axis):
    selected = {"tail": {"bottom_left": "V_MITER_CHECK"}}
    axes = {"tail": {"bottom_left": axis}}
    path = write_project(tmp_path / f"first_{axis}.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "自訂", "w": 500, "h": 600, "d": 300, "t": 2,
            "v_miter_gui_check_corners": selected,
            "v_miter_gui_first_bend_axes": axes,
        },
    })
    loaded = read_project(path)["snapshot"]
    assert api.normalize_operator_v_miter_gui_first_bend_axes(
        loaded["v_miter_gui_first_bend_axes"], loaded["v_miter_gui_check_corners"],
    ) == axes
    with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
        api.require_no_operator_v_miter_gui_check_for_export(loaded)


def test_legacy_v_source_never_autoselects_first_fold():
    selected = {"door": {"bottom_left": "V_MITER_CHECK"}}
    assert api.normalize_operator_v_miter_gui_first_bend_axes(None, selected) == {}


@pytest.mark.parametrize("bad", [
    {"door": {"bottom_left": "X"}},
    {"door": {"bottom_left": True}},
    {"door": {"bottom_left": 90}},
    {"door": {"top": "x"}},
    {"fake": {"bottom_left": "x"}},
    [("door", "x")],
])
def test_first_fold_input_strictly_rejects_invalid_source(bad):
    with pytest.raises(GeometryError, match="FIRST_BEND"):
        api.normalize_operator_v_miter_gui_first_bend_axes(bad)


def test_first_fold_change_and_orphan_cleanup():
    selected = {"tail": {
        "bottom_left": "V_MITER_CHECK", "bottom_right": "V_MITER_CHECK",
    }}
    same = {"top": True, "bottom": True}
    axes = api.change_operator_v_miter_gui_first_bend_axis(
        {}, selected, "tail", "bottom", same, first_bend_axis="y",
    )
    assert axes == {"tail": {"bottom_left": "y", "bottom_right": "y"}}
    with pytest.raises(GeometryError, match="PAIR_IS_SPLIT"):
        api.change_operator_v_miter_gui_first_bend_axis(
            {}, selected, "tail", "bottom", {"bottom": False}, first_bend_axis="x",
        )
    with pytest.raises(GeometryError, match="SELECTED_V_REQUIRED"):
        api.change_operator_v_miter_gui_first_bend_axis(
            {}, {"tail": {"bottom_left": "V_MITER_CHECK"}},
            "tail", "bottom", same, first_bend_axis="x",
        )
    with pytest.raises(GeometryError, match="ORPHAN"):
        api.normalize_operator_v_miter_gui_first_bend_axes(
            axes, {"tail": {"bottom_left": "V_MITER_CHECK"}},
        )
    original = deepcopy(axes)
    assert api.project_operator_v_miter_gui_selected_first_bend_axes(
        axes, {"tail": {"bottom_left": "V_MITER_CHECK"}},
    ) == {"tail": {"bottom_left": "y"}}
    assert api.project_operator_v_miter_gui_selected_first_bend_axes(axes, {}) == {}
    assert axes == original


def test_real_gui_explicit_first_y_and_save_reload(tmp_path):
    import tkinter as tk
    import gui

    def build():
        root = tk.Tk()
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("door")
        app.select_manual_corner("bottom")
        return root, app

    def close(root, app):
        child = getattr(app, "fold_designer_app", None)
        if child is not None:
            try:
                child.root.destroy()
            except Exception:
                pass
        root.destroy()

    root, app = build()
    second, app2 = None, None
    try:
        app.set_v_miter_gui_check_choice()
        with pytest.raises(ValueError, match="FIRST_BEND_REQUIRED"):
            app._project_v_miter_gui_check_for_corner("door", "bottom")
        assert app.v_miter_first_bend_axis_var.get() == ""
        app.v_miter_first_bend_axis_var.set("y")
        app.set_v_miter_gui_first_bend_axis()
        live = app._project_v_miter_gui_check_for_corner("door", "bottom")
        assert (live.first_bend_axis, live.second_bend_axis) == ("y", "x")
        saved = app._compose_phase6_project_snapshot_from_main_gui()
        axes = saved["v_miter_gui_first_bend_axes"]
        assert axes["door"] == {"bottom_left": "y", "bottom_right": "y"}
        path = write_project(tmp_path / "gui_first_y.p6fold", {
            "schema": PROJECT_SCHEMA_V1, "snapshot": saved,
        })
        second, app2 = build()
        app2._apply_phase6_project_snapshot(read_project(path)["snapshot"])
        app2.workspace_controller.set_active_part("door")
        app2.select_manual_corner("bottom")
        assert app2.v_miter_first_bend_axis_var.get() == "y"
        again = app2._project_v_miter_gui_check_for_corner("door", "bottom")
        assert again.first_bend_axis == "y"
        with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
            api.require_no_operator_v_miter_gui_check_for_export(
                app2._compose_phase6_project_snapshot_from_main_gui()
            )
    finally:
        if app2 is not None:
            close(second, app2)
        close(root, app)
