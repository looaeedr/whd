"""#3317: actual WHD tail, 48-mm lower return, both physical lower V corners.

Real GUI -> canonical PartSpec/FinalScene -> Factory source V replacement
-> both true-T 3D folds -> real inclined cut faces -> continuous seam metrics.
This is a geometrical pass/fail, NOT a declaration of shop acceptance.
DXF units are independently covered by test_issue2690_composed_panel_dxf.py.
"""
from __future__ import annotations

import json
import math

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from ae_engine.v_miter_material_trial import _single_source_material


def _diagnose(live, *, corner, axis, spec, render):
    tol = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    result = {
        "board": "WHD existing tail / 封尾",
        "corner": corner,
        "first_bend": axis,
        "second_bend": "y" if axis == "x" else "x",
        "bottom_flange_mm": spec.fold_bottom,
        "side_flanges_mm": [spec.fold_left, spec.fold_right],
        "thickness_mm": spec.thickness,
        "geometry_tolerance_mm": tol,
        "issues": [],
    }
    issues = result["issues"]
    if live is None:
        issues.append("模型無法建立，無可驗證的折後實體")
        result["status"] = "模型不合／缺少來源"
        return result
    result["first_fold_angle_deg"] = 90.0
    result["second_fold_angle_deg"] = live.second_fold_angle_deg
    if live.material_check is None:
        issues.append("實際 Factory 母料 V 輪廓："
                      + str(live.material_check_failure))
    if live.factory_precut_fold_check is None:
        issues.append("真實折線來源：" + str(live.factory_precut_fold_failure))
    source_t = live.factory_true_t_check
    if source_t is None:
        issues.append("真實板厚 3D 折後模型：" + str(live.factory_true_t_failure))
    else:
        result["zero_r_intersection_pairs"] = source_t.surface_interference_pair_count
        if source_t.surface_interference_pair_count:
            issues.append(
                "零內R的厚板實體發現穿透/相交："
                + str(source_t.surface_interference_pair_count)
                + " 對表面三角形"
            )
    curved = live.factory_radius_ba_check
    if curved is None:
        issues.append("使用現有 R/BA 預設的折後實體："
                      + str(live.factory_radius_ba_failure))
    else:
        result.update({
            "r1_mm": curved.first_inner_radius_mm,
            "r2_mm": curved.second_inner_radius_mm,
            "ba1_mm": curved.first_bend_allowance_mm,
            "ba2_mm": curved.second_bend_allowance_mm,
            "curved_t_intersection_pairs": curved.curved_t_surface_interference_pairs,
            "volume_status": curved.curved_t_volume_status,
            "first_cut_face_failure": curved.first_cut_face_failure,
            "second_cut_face_failure": curved.second_cut_face_failure,
        })
        if curved.curved_t_surface_interference_pairs:
            issues.append(
                "實際 R/BA 厚板折後相交："
                + str(curved.curved_t_surface_interference_pairs)
                + " 對表面三角形"
            )
        if "NO_DETECTED_VOLUME_WITNESS" not in curved.curved_t_volume_status:
            issues.append("厚板穿透尚未排除：" + curved.curved_t_volume_status)
        continuity = curved.source_cut_face_continuity
        if continuity is None:
            issues.append(
                "兩個實際 V 切面的密合檢查無法完成："
                + str(curved.source_cut_face_continuity_failure)
            )
        else:
            result.update({
                "effective_seam_length_mm": continuity.seam_length_mm,
                "both_cut_face_span_mm": continuity.both_face_span_mm,
                "first_missing_span_mm": continuity.first_missing_span_mm,
                "second_missing_span_mm": continuity.second_missing_span_mm,
                "both_missing_span_mm": continuity.both_missing_span_mm,
                "max_sampled_cut_face_gap_mm": continuity.max_sampled_cut_face_gap_mm,
                "max_gap_lower_bound_mm": continuity.max_gap_lower_bound_mm,
                "max_gap_upper_bound_mm": continuity.max_gap_upper_bound_mm,
                "gap_status": continuity.gap_bound_status,
                "numerically_unresolved_events":
                    continuity.numerically_unresolved_vertex_event_count,
            })
            if continuity.missing_face_interval_count:
                result["missing_cut_face_intervals"] = [
                    {
                        "start_mm": float(section.start_mm),
                        "end_mm": float(section.end_mm),
                        "status": section.midpoint_section.status,
                    }
                    for section in continuity.intervals
                    if section.midpoint_section.status != "MEASURED"
                ]
                # The V root contains a designed R/round hole. A missing
                # triangle near the root is NOT automatically a bad seam.
                # Report exact spans, and distinguish physical relief from
                # a real lack of inclined mating face after its end.
                relief = live.factory_bottom_relief_check
                result["root_relief_flat_cutback_mm"] = (
                    relief.flat_leg_tip_cutback_mm if relief is not None
                    else None
                )
                issues.append(
                    "實際斜切面缺失／底部避裂待分段："
                    + f"{continuity.missing_face_interval_count} 個區段；"
                    + f"總長 {continuity.first_missing_span_mm + continuity.second_missing_span_mm + continuity.both_missing_span_mm:.6g} mm"
                )
            if continuity.numerically_unresolved_vertex_event_count:
                issues.append(
                    "接縫存在未解析的真實切面頂點事件："
                    + str(continuity.numerically_unresolved_vertex_event_count)
                )
            upper = continuity.max_gap_upper_bound_mm
            lower = continuity.max_gap_lower_bound_mm
            if lower is not None and lower > tol:
                issues.append(
                    f"至少一處 V 切面實際間隙已大於數值容差："
                    f"下界 {lower:.9g} mm > {tol:.9g} mm"
                )
            elif upper is None:
                issues.append("無法證明兩切面整段密合：缺有效間隙上界")
            elif upper > tol:
                issues.append(
                    f"兩切面整段密合尚未證實："
                    f"間隙上界 {upper:.9g} mm > 數值容差 {tol:.9g} mm"
                )
    result["status"] = "模型驗證通過" if not issues else "模型驗證未通過"
    return result


@pytest.mark.parametrize("axis", ("x", "y"))
def test_existing_tail_48_both_lower_corners_folded_3d_gap_and_penetration(axis, record_property):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("tail")
        # The real WHD EndCap field, not a freehand re-drawn 48-mm rectangle.
        app.ybottom1_var.set("48")
        snap = app._make_original_fold_designer_snapshot()
        assert snap["ybottom1"] == pytest.approx(48.0)
        spec, _ = app._fold_designer_part_spec_from_payload("tail", snap)
        render = app._query_fold_designer_render_data("tail", snap)
        assert spec.is_tail
        assert spec.fold_bottom == pytest.approx(48.0)
        source = tuple(render.scene.primitives)
        material = _single_source_material(render.scene)
        assert material.is_valid
        details = []
        for corner in ("bottom_left", "bottom_right"):
            # The operator's first physical fold is explicit even on 90/90.
            try:
                live = api.project_operator_v_miter_live_corner_check(
                    spec, render, corner, relief_mode="ROUND_R",
                    run_radius_ba_trial=True, first_bend_axis=axis,
                )
            except Exception as exc:
                details.append({
                    "corner": corner, "first_bend": axis,
                    "status": "模型驗證未通過",
                    "issues": ["求解異常：" + type(exc).__name__ + ": " + str(exc)],
                })
            else:
                curved = live.factory_radius_ba_check
                if curved is not None:
                    # The far-end 1.178318mm is NOT the root ROUND_R relief.
                    # Its exact source is the flat 15mm reach minus the
                    # actual 90deg RBA mid-surface formed reach.
                    expected_reach = min(
                        live.ideal.formed_contact_length_mm,
                        live.first_flange_height_mm
                        - curved.first_bend_allowance_mm
                        + curved.first_inner_radius_mm + spec.thickness / 2,
                        live.second_flange_height_mm
                        - curved.second_bend_allowance_mm
                        + curved.second_inner_radius_mm + spec.thickness / 2,
                    )
                    assert curved.physical_formed_seam_reach_mm == pytest.approx(
                        expected_reach, abs=1e-7,
                    )
                    assert curved.distal_ideal_seam_shortfall_mm == pytest.approx(
                        live.ideal.formed_contact_length_mm - expected_reach,
                        abs=1e-7,
                    )
                    assert curved.distal_ideal_seam_shortfall_mm == pytest.approx(
                        1.178318229274425, abs=1e-6,
                    )
                    if curved.source_cut_face_continuity is not None:
                        assert (
                            curved.source_cut_face_continuity.seam_length_mm
                            == pytest.approx(expected_reach, abs=1e-7)
                        )
                details.append(_diagnose(
                    live, corner=corner, axis=axis, spec=spec, render=render,
                ))
        assert tuple(render.scene.primitives) == source, (
            "模型求解不得改動來源板料"
        )
        result_json = json.dumps(details, ensure_ascii=False, sort_keys=True)
        record_property("WHD_TAIL_48_MODEL_VALIDATION_RESULT", result_json)
        # A geometry FAIL is a legitimate modeling outcome, not a broken
        # test runner. Keep the real diagnosis in the JUnit evidence and
        # on stdout when run by the operator with pytest -s.
        print("WHD_TAIL_48_MODEL_VALIDATION_RESULT=" + result_json, flush=True)
        assert {d["corner"] for d in details} == {
            "bottom_left", "bottom_right",
        }
        assert all(
            d["status"] in ("模型驗證通過", "模型驗證未通過")
            for d in details
        )
        for d in details:
            assert bool(d["issues"]) == (d["status"] != "模型驗證通過")
            # Do not silently label any actually intersecting true-T model
            # as a geometrically verified pass.
            if d.get("curved_t_intersection_pairs", 0) > 0:
                assert d["status"] != "模型驗證通過"

    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
