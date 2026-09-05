# -*- coding: utf-8 -*-
from copy import deepcopy
import os

import pytest

import phase6_project_file as project
from ae_engine.cabinet_types import receiving
from ae_engine.door_dividers import derive_box_body_dividers


def _receiving_snapshot():
    snap = receiving.apply_family_defaults({"t": 2.0})
    snap.update({
        "existing_parts": ["box_body", "head", "tail", "door"],
        "door_handle_edges": {"0:0": "BOTTOM", "0:1": "TOP"},
        "door_nameplate_center_datum_top": 137.5,
    })
    return snap


def test_project_write_read_preserves_authoritative_door_state_and_repairs_shared_divider_reference(tmp_path):
    snap = _receiving_snapshot()
    snap["inner_doors"][0]["lower_frame_role"]["divider_stable_id"] = "dangling-divider"

    path = project.write_project(tmp_path / "receiving-authority.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": snap,
        "final_geometry": {},
    })
    loaded = project.read_project(path)["snapshot"]

    assert loaded["assembly_type"] == "WRAP_OVERLAY"
    assert loaded["door_layout_columns"] == [[800.0, [1100.0, 500.0]]]
    assert loaded["door_handle_edges"] == {"0:0": "BOTTOM", "0:1": "TOP"}
    assert loaded["door_nameplate_center_datum_top"] == pytest.approx(137.5)

    dividers = derive_box_body_dividers(
        [(800.0, [1100.0, 500.0])],
        depth=350.0,
        thickness=2.0,
        layout_scope="receiving-main",
        handle_edges=loaded["door_handle_edges"],
    )
    expected = next(part.stable_id for part in dividers if part.axis == "HORIZONTAL")
    assert loaded["inner_doors"][0]["lower_frame_role"] == {
        "role": "lower_frame",
        "divider_stable_id": expected,
    }


def test_project_serializer_removes_dangling_shared_role_when_boundary_disappears(tmp_path):
    snap = _receiving_snapshot()
    snap["door_layout_columns"] = [[800.0, [1600.0]]]
    snap["inner_doors"][0]["lower_frame_role"] = {
        "role": "lower_frame",
        "divider_stable_id": "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1",
    }

    path = project.write_project(tmp_path / "receiving-no-divider.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": snap,
        "final_geometry": {},
    })
    loaded = project.read_project(path)["snapshot"]

    assert "lower_frame_role" not in loaded["inner_doors"][0]


def test_project_round_trip_does_not_persist_transient_derived_part_geometry(tmp_path):
    snap = _receiving_snapshot()
    snap["divider_parts"] = [{"stable_id": "transient", "triangles": [[1, 2, 3]]}]
    snap["inner_door_frame_parts"] = [{"stable_id": "transient-frame", "scene": "cache"}]
    snap["inner_doors"][0]["frame_spans"] = {"top": 1.0, "left": 2.0, "right": 3.0}

    path = project.write_project(tmp_path / "no-derived-cache.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": snap,
        "final_geometry": {},
    })
    loaded = project.read_project(path)["snapshot"]

    assert "divider_parts" not in loaded
    assert "inner_door_frame_parts" not in loaded
    assert "frame_spans" not in loaded["inner_doors"][0]


def test_main_gui_snapshot_preserves_and_restores_t10_authoritative_door_fields():
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400.0, [300.0, 300.0])])
        app.door_layout_scope = "cabinet-A"
        app.door_layout_handle_edges = {"0:0": "BOTTOM", "0:1": "LEFT"}
        app.receiving_inner_doors = [{
            "stable_id": "upper",
            "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
            "lower_frame_role": {"role": "lower_frame", "divider_stable_id": "persist-me"},
        }]
        app.door_nameplate_center_datum_top = 133.0

        snapshot = app._make_original_fold_designer_snapshot()
        assert snapshot["door_handle_edges"] == {"0:0": "BOTTOM", "0:1": "LEFT"}
        assert snapshot["door_nameplate_center_datum_top"] == pytest.approx(133.0)

        app.multi_door_enabled_var.set(False)
        app.door_layout_columns = []
        app.door_layout_scope = "other"
        app.door_layout_handle_edges = {}
        app.receiving_inner_doors = []
        app.door_nameplate_center_datum_top = None

        app._apply_original_fold_designer_snapshot(deepcopy(snapshot))
        assert app.multi_door_enabled_var.get() is True
        assert app.get_door_layout_columns() == [(400.0, [300.0, 300.0])]
        assert app.door_layout_scope == "cabinet-A"
        assert app.door_layout_handle_edges == {"0:0": "BOTTOM", "0:1": "LEFT"}
        assert app.receiving_inner_doors[0]["stable_id"] == "upper"
        assert app.door_nameplate_center_datum_top == pytest.approx(133.0)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_door_part_spec_consumes_persisted_nameplate_datum_override():
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.door_nameplate_center_datum_top = 131.25
        val = app._collect_main_setting_values()
        spec = app._door_part_spec_from_values(
            val,
            model_name="金庫型",
            features=(),
        )
        assert spec.nameplate_center_datum_top == pytest.approx(131.25)
    finally:
        root.destroy()


def test_project_serializer_canonicalizes_handle_edges_and_rejects_unknown_values(tmp_path):
    snap = _receiving_snapshot()
    snap["door_handle_edges"] = {"0:0": "下", "0:1": "LEFT", "9:9": "RIGHT"}
    path = project.write_project(tmp_path / "handle-normalize.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": snap,
        "final_geometry": {},
    })
    loaded = project.read_project(path)["snapshot"]
    assert loaded["door_handle_edges"] == {"0:0": "BOTTOM", "0:1": "LEFT"}

    bad = _receiving_snapshot()
    bad["door_handle_edges"] = {"0:0": "DIAGONAL"}
    with pytest.raises(ValueError, match="unsupported door handle edge"):
        project.write_project(tmp_path / "bad-handle.p6fold", {
            "schema": project.PROJECT_SCHEMA,
            "snapshot": bad,
            "final_geometry": {},
        })
