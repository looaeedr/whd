"""Genuine Custom Head FinalScene and staged source; no product scope claim."""
from dataclasses import replace
import json
from copy import deepcopy
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError

@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("first_axis", ("x", "y"))
def test_actual_head_finite_bend_live_capture_replay(mode, first_axis):
    import tkinter as tk
    import gui
    root = tk.Tk()
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("head")
        snap = app._make_original_fold_designer_snapshot()
        def actual(render_snapshot):
            spec, _ = app._fold_designer_part_spec_from_payload("head", render_snapshot)
            return spec, app._query_fold_designer_render_data("head", render_snapshot)
        spec, render = actual(snap)
        source = tuple(render.scene.primitives)
        record = json.loads(json.dumps(api.capture_endcap_live_v_miter_check_snapshot(
            spec, render, "bottom_left", first_bend_axis=first_axis, relief_mode=mode,
        )))
        assert set(record) == {"contract", "manufacturing_status", "corner_key",
                               "first_bend_axis", "relief_mode", "source_fold_sha256"}
        assert api.normalize_endcap_live_v_miter_check_snapshot(record) == record
        fresh_spec, fresh_render = actual(snap)
        fresh_spec, fresh_render = replace(fresh_spec), deepcopy(fresh_render)
        assert all(not any(q is p for q in source) for p in fresh_render.scene.primitives)
        newer = api.replay_endcap_live_v_miter_check_snapshot(fresh_spec, fresh_render, record)
        live = api.project_operator_v_miter_live_corner_check(
            fresh_spec, fresh_render, "bottom_left", first_bend_axis=first_axis, relief_mode=mode,
        )
        assert newer == live
        original = tuple(fresh_render.scene.primitives)
        physical_y = newer.second_physical_bend if first_axis=="x" else newer.first_physical_bend
        physical_x = newer.first_physical_bend if first_axis=="x" else newer.second_physical_bend
        assert any(p is physical_y for p in original) and any(p is physical_x for p in original)
        assert physical_y.p1.y == physical_y.p2.y == 41
        assert physical_x.p1.x == physical_x.p2.x == 15
        assert newer.first_bend_source_gap_mm > 0 and newer.second_bend_source_gap_mm > 0
        assert newer.factory_bottom_relief_check.relief_mode.value == mode
        assert set(p.layer for p in newer.full_sheet_check_scene.primitives) <= {"CHECK", "DATUM"}
        assert tuple(render.scene.primitives) == source
        assert tuple(fresh_render.scene.primitives) == original
        assert newer.manufacturing_status.endswith("UNCERTIFIED")
        for mutate in ({"first_bend_axis":"y" if first_axis=="x" else "x"},
                       {"relief_mode":"OTHER"},
                       {"relief_mode":"ROUND_R" if mode=="RELIEF_HOLE" else "RELIEF_HOLE"},
                       {"corner_key":"bottom_right"},
                       {"thickness_mm":3}, {"first_flange_height_mm":30}):
            with pytest.raises(GeometryError):
                api.replay_endcap_live_v_miter_check_snapshot(fresh_spec, fresh_render, {**record, **mutate})
        with pytest.raises(GeometryError, match="V_MITER_LIVE_SOURCE_CHANGED"):
            api.replay_endcap_live_v_miter_check_snapshot(replace(fresh_spec, thickness=3), fresh_render, record)
    finally:
        root.destroy()
