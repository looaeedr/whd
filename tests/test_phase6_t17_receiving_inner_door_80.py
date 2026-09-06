from __future__ import annotations

import inspect
import os

import pytest

import ae_engine.assembly_placement as placement_module
from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.cabinet_types import receiving


def _snapshot(*, inner_doors=None):
    return {
        "model": "受電箱",
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "door_gap_w": 3.5,
        "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": inner_doors if inner_doors is not None else [{
            "stable_id": "upper",
            "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
            "inward_offset_mm": 80.0,
        }],
    }


def test_r15_r16_fresh_receiving_inner_door_default_is_80_mm_inward_from_own_outer_door():
    defaults = receiving.default_inner_doors(thickness=2.0)
    assert defaults[0]["inward_offset_mm"] == pytest.approx(80.0)

    snap = _snapshot(inner_doors=defaults)
    outer = resolve_assembly_placement(snap, "door_c1_r1")
    panel = resolve_assembly_placement(snap, "inner_door:upper:panel")
    top = resolve_assembly_placement(snap, "inner_door:upper:top_frame")
    left = resolve_assembly_placement(snap, "inner_door:upper:left_frame")
    right = resolve_assembly_placement(snap, "inner_door:upper:right_frame")

    inward = receiving.assembly_coordinate_contract(depth=350.0, thickness=2.0)["inward_vector"]
    expected_z = outer.world_offset[2] + inward[2] * 80.0
    assert expected_z == pytest.approx(95.0)
    assert panel.world_offset[2] == pytest.approx(expected_z)
    assert top.world_offset[2] == pytest.approx(expected_z)
    assert left.world_offset[2] == pytest.approx(expected_z)
    assert right.world_offset[2] == pytest.approx(expected_z)


def test_each_inner_door_owns_its_configurable_inward_offset_without_cross_contamination():
    snap = _snapshot(inner_doors=[
        {"stable_id": "upper", "cell_key": "0:0", "included_frame_sides": ["top", "left", "right"], "inward_offset_mm": 60.0},
        {"stable_id": "lower", "cell_key": "0:1", "included_frame_sides": ["top", "left", "right"], "inward_offset_mm": 100.0},
    ])
    upper_outer = resolve_assembly_placement(snap, "door_c1_r1")
    lower_outer = resolve_assembly_placement(snap, "door_c1_r2")
    upper = resolve_assembly_placement(snap, "inner_door:upper:panel")
    lower = resolve_assembly_placement(snap, "inner_door:lower:panel")

    assert upper.world_offset[2] == pytest.approx(upper_outer.world_offset[2] - 60.0)
    assert lower.world_offset[2] == pytest.approx(lower_outer.world_offset[2] - 100.0)
    assert upper.world_offset[1] != lower.world_offset[1]


def test_placement_uses_family_inward_vector_not_hardcoded_z_minus_80():
    source = inspect.getsource(placement_module._inner_door_geometry)
    assert "inward_vector" in source
    assert "- 80" not in source
    assert "-80" not in source


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_gui_per_door_inward_offset_is_editable_and_project_roundtrip_preserves_each_value(tmp_path):
    import tkinter as tk
    import gui
    import phase6_project_file as project

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    root2 = None
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        app._set_receiving_inner_door_enabled("0:0", True)
        app._set_receiving_inner_door_enabled("0:1", True)
        app._set_receiving_inner_door_inward_offset("0:0", 65.0)
        app._set_receiving_inner_door_inward_offset("0:1", 105.0)
        app.rebuild_door_layout_ui()
        app.door_layout_inner_door_offset_vars["0:0"].set("70")
        assert app._commit_receiving_inner_door_inward_offset("0:0") is True

        by_cell = {item["cell_key"]: item for item in app.receiving_inner_doors}
        assert by_cell["0:0"]["inward_offset_mm"] == pytest.approx(70.0)
        assert by_cell["0:1"]["inward_offset_mm"] == pytest.approx(105.0)

        snap = app._compose_phase6_project_snapshot_from_main_gui()
        path = tmp_path / "t17_inner_door_depth.p6fold"
        project.write_project(path, {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-09-06T16:10:00+08:00",
            "snapshot": snap,
            "final_geometry": {},
        })
        loaded = project.read_project(path)["snapshot"]

        root2 = tk.Tk(); root2.withdraw(); app2 = gui.BoxCalculatorGUI(root2)
        app2._apply_phase6_project_snapshot(loaded)
        root2.update_idletasks(); root2.update()
        by_cell2 = {item["cell_key"]: item for item in app2.receiving_inner_doors}
        assert by_cell2["0:0"]["inward_offset_mm"] == pytest.approx(70.0)
        assert by_cell2["0:1"]["inward_offset_mm"] == pytest.approx(105.0)

        app2.rebuild_door_layout_ui()
        assert app2.door_layout_inner_door_offset_vars["0:0"].get() in {"70", "70.0"}
        assert app2.door_layout_inner_door_offset_vars["0:1"].get() in {"105", "105.0"}
    finally:
        try:
            if root2 is not None:
                root2.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
