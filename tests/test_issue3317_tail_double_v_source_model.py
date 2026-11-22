"""#3317 one real Tail blank: both V's on own exterior edge, one folded model.

Model PASS is a real geometric assertion. Do NOT turn a failing physical
contact check into a green diagnostic-only test or factory/CAM prerequisite.
"""
from __future__ import annotations

import json
import math

import pytest
from shapely.geometry import Polygon

from ae_engine.v_miter_tail_dual_source_check import project_tail_dual_v_same_source_check


def test_tail_real_same_blank_dual_90_v_and_folded_contact():
    import gui
    import tkinter as tk

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("tail")
        app.ybottom1_var.set("48")
        snapshot = app._make_original_fold_designer_snapshot()
        spec, _ = app._fold_designer_part_spec_from_payload("tail", snapshot)
        render = app._query_fold_designer_render_data("tail", snapshot)
        original = tuple(render.scene.primitives)
        check = project_tail_dual_v_same_source_check(spec, render)
        assert check.side_flange_left_mm == pytest.approx(15)
        assert check.side_flange_right_mm == pytest.approx(15)
        assert check.bottom_flange_mm == pytest.approx(48)
        assert tuple(render.scene.primitives) == original
        assert check.original_factory_scene is render.scene
        assert tuple(check.flat_check_scene.primitives[1:]) == check.original_other_primitives
        assert check.flat_check_scene.primitives[0].layer == "CHECK"
        for apex, hits, side in (
            (check.left_apex, check.left_outer_v_hits,
             min(p.x for p in check.original_outline)),
            (check.right_apex, check.right_outer_v_hits,
             max(p.x for p in check.original_outline)),
        ):
            assert all(p.x == pytest.approx(side) for p in hits)
            a = (hits[0].x-apex.x, hits[0].y-apex.y)
            b = (hits[1].x-apex.x, hits[1].y-apex.y)
            assert abs(a[0]*b[0]+a[1]*b[1]) < 1e-7
        original_outline = Polygon((p.x,p.y) for p in check.original_outline)
        new_outline = Polygon((p.x,p.y) for p in check.corrected_outline)
        assert original_outline.is_valid
        assert new_outline.is_valid and not new_outline.interiors
        assert len(check.corners) == 2
        evidence = {
            "original_flange_mm":[check.side_flange_left_mm,
                                  check.side_flange_right_mm,
                                  check.bottom_flange_mm],
            "left_v": [[p.x,p.y] for p in check.left_outer_v_hits],
            "right_v": [[p.x,p.y] for p in check.right_outer_v_hits],
            "apexes": [[check.left_apex.x,check.left_apex.y],
                       [check.right_apex.x,check.right_apex.y]],
            "original_bounds":original_outline.bounds,
            "corrected_bounds":new_outline.bounds,
            "unchanged_primitive_count":len(check.original_other_primitives),
            "corners": [],
        }
        for row in check.corners:
            continuity = row.seam_continuity
            evidence["corners"].append({
                "corner":row.corner,
                "collision_surface_triangle_pairs":row.model_interference_pairs,
                "volume_status":row.model_volume_status,
                "model_status":row.model_status,
                "formed_seam_reach_mm":row.actual_formed_reach_mm,
                "far_end_flat_minus_formed_reach_mm":row.distal_ideal_shortfall_mm,
                "cut_face_failure_side":row.side_cut_failure,
                "cut_face_failure_bottom":row.bottom_cut_failure,
                "seam_failure":row.seam_failure,
                "seam_span_mm":continuity.seam_length_mm if continuity else None,
                "gap_max_sample_mm":continuity.max_sampled_cut_face_gap_mm if continuity else None,
                "gap_upper_bound_mm":continuity.max_gap_upper_bound_mm if continuity else None,
                "gap_lower_bound_mm":continuity.max_gap_lower_bound_mm if continuity else None,
                "intervals":[
                    [round(p.start_mm,6),round(p.end_mm,6),
                     p.midpoint_section.status]
                    for p in continuity.intervals
                    if p.midpoint_section.status!="MEASURED"
                ] if continuity else [],
            })
        report=json.dumps(evidence,ensure_ascii=False,sort_keys=True)
        assert all(row.model_status == "MODEL_PASS" for row in check.corners), (
            "WHD_TAIL_DUAL_V_FOLDED_MODEL_NOT_YET_PASS=" + report
        )
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
