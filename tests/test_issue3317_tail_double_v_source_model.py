"""#3317 one real Tail blank: both V's on own exterior edge, one folded model.

Model PASS is a real geometric assertion. Do NOT turn a failing physical
contact check into a green diagnostic-only test or factory/CAM prerequisite.
"""
from __future__ import annotations

import json
import math
import base64

import pytest
from shapely.geometry import Polygon

from ae_engine.v_miter_tail_dual_source_check import project_tail_dual_v_same_source_check
from tools.render_tail_dual_v_model import build_tail_dual_v_source_preview_zip


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
        # The source 90-degree opening on the exterior SAME SIDE is a
        # prescribed geometry contract. Its 3D contact must still be real.
        # Do not re-interpret the root R/BA height or test runner status
        # as a passing seam, and never switch to the Door trim solution.
        for corner in check.corners:
            assert corner.topology_contact_failure is not None
            assert "NO_CONTACT" in corner.topology_contact_failure
            assert corner.topological_clearance_lower_bound_mm == pytest.approx(2.0)
            assert corner.contact_gap_floor_at_straight_start_mm == pytest.approx(
                6.178318229274424, abs=1e-6
            )
            assert corner.contact_gap_floor_at_straight_end_mm == pytest.approx(
                17.0, abs=1e-6
            )
            # All 90 V ray angle splits still yield a positive far-end
            # floor: d*h=15², d<=48 => h>=4.6875 mm.
            assert corner.asymmetry_best_case_far_gap_floor_mm == pytest.approx(
                6.6875, abs=1e-6
            )
            start, end = corner.actual_joint_axis_xyz
            assert start[1] == pytest.approx(45.0)
            assert end[1] == pytest.approx(45.0)
            assert start[0] == pytest.approx(
                12.0 if corner.corner=="bottom_left" else 410.0
            )
            assert start[2] == pytest.approx(3.0)
            assert end[2] == pytest.approx(13.82168177072558, abs=1e-6)
            assert corner.model_status != "MODEL_PASS"
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
                "interference_z_range_mm":row.interference_z_range_mm,
                "actual_folded_joint_axis_xyz":row.actual_joint_axis_xyz,
                "topology_contact_failure":row.topology_contact_failure,
                "topological_clearance_lower_bound_mm":row.topological_clearance_lower_bound_mm,
                "source_gap_floor_at_straight_start_mm":
                    row.contact_gap_floor_at_straight_start_mm,
                "source_gap_floor_at_straight_end_mm":
                    row.contact_gap_floor_at_straight_end_mm,
                "sampled_true_face_gap_stations_mm":row.sampled_seam_gap_stations_mm,
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
        # Actual source flat SVG, true folded OBJ/PNG and numerical diagnosis
        # are built from precisely the Engine CHECK model above. The zip is
        # emitted in bounded CI log chunks for exact-source retrieval.
        payload=build_tail_dual_v_source_preview_zip(check)
        assert len(payload) > 1000
        encoded=base64.b64encode(payload).decode("ascii")
        for i in range(0,len(encoded),4096):
            print("WHD_3317_MODEL_ZIP_BASE64_PART="
                  + str(i//4096).zfill(4) + ":" + encoded[i:i+4096],flush=True)
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
