from __future__ import annotations

import os

import pytest

from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2


def _feature(diameter: float, x: float):
    return CircleFeature(
        diameter=diameter,
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(x, 0.0),
        layer="CUTTING",
        source_type="t05",
    )


def test_dynamic_door_assembly_transform_uses_canonical_layout_cell_centers():
    import fold_designer_bridge as bridge

    receiving = {
        "w": 800.0,
        "h": 1600.0,
        "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
    }
    assert bridge._phase6_assembly_placement_for_part(receiving, "door_c1_r1") == (
        "front", (0.0, 250.0, 0.0)
    )
    assert bridge._phase6_assembly_placement_for_part(receiving, "door_c1_r2") == (
        "front", (0.0, -550.0, 0.0)
    )

    generic = {
        "w": 1100.0,
        "h": 1800.0,
        "multi_door_enabled": True,
        "door_layout_columns": [[600.0, [600.0, 500.0, 700.0]], [500.0, [800.0, 1000.0]]],
    }
    assert bridge._phase6_assembly_placement_for_part(generic, "door_c2_r2") == (
        "front", (300.0, -400.0, 0.0)
    )


def test_project_round_trip_preserves_independent_dynamic_door_features(tmp_path):
    import phase6_project_file as project

    upper = _feature(12.0, -20.0)
    lower = _feature(18.0, 30.0)
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "saved_at": "2026-09-04T20:00:00+08:00",
        "snapshot": {
            "model": "受電箱",
            "multi_door_enabled": True,
            "door_layout_columns": [[800.0, [1100.0, 500.0]]],
            "part_features": {
                "door_c1_r1": [upper],
                "door_c1_r2": [lower],
            },
        },
        "final_geometry": {},
    }
    path = tmp_path / "receiving_multi_door.p6fold"
    project.write_project(path, payload)
    loaded = project.read_project(path)
    restored = loaded["snapshot"]["part_features"]
    assert restored["door_c1_r1"] == [upper]
    assert restored["door_c1_r2"] == [lower]
    assert restored["door_c1_r1"] is not restored["door_c1_r2"]


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_fold_designer_live_sync_preserves_per_door_features_in_main_project_snapshot():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        upper = _feature(12.0, -20.0)
        lower = _feature(18.0, 30.0)
        designer.designer_workspace.stash_features("door_c1_r1", [upper])
        designer.designer_workspace.stash_features("door_c1_r2", [lower])
        designer._phase6_last_live_fingerprint = None
        assert bridge._phase6_publish_live_state(designer, force=True) is True
        root.update_idletasks(); root.update()

        assert app.surface_features["door_c1_r1"] == [upper]
        assert app.surface_features["door_c1_r2"] == [lower]
        saved = app._compose_phase6_project_snapshot_from_main_gui()
        assert saved["part_features"]["door_c1_r1"] == [upper]
        assert saved["part_features"]["door_c1_r2"] == [lower]
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_assembly_resolved_parts_place_upper_and_lower_doors_separately():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        doors = {part.part_key: part for part in resolved.parts if part.part_key.startswith("door_c")}
        assert tuple(doors) == ("door_c1_r1", "door_c1_r2")
        assert doors["door_c1_r1"].placement == "receiving_outer_door"
        assert doors["door_c1_r2"].placement == "receiving_outer_door"
        assert doors["door_c1_r1"].offset[2] == doors["door_c1_r2"].offset[2]
        assert doors["door_c1_r1"].offset != doors["door_c1_r2"].offset
        assert doors["door_c1_r1"].offset[1] > doors["door_c1_r2"].offset[1]
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
