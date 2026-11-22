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


@pytest.mark.parametrize("first_axis", ("x", "y"))
def test_tail_real_same_blank_dual_90_v_and_folded_contact(first_axis):
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
        # An actual CHECK corner's saved operator first-fold choice, not
        # a 90/90 inference or dictionary iteration order. Exercise both
        # valid selections with exactly the same mother sheet.
        from ae_engine.v_miter_operator_gui_check import (
            normalize_operator_v_miter_gui_first_bend_axes,
        )
        snapshot["v_miter_gui_check_corners"] = {
            "tail": {"bottom_left": "V_MITER_CHECK",
                     "bottom_right": "V_MITER_CHECK"}
        }
        snapshot["v_miter_gui_first_bend_axes"] = {
            "tail": {"bottom_left": first_axis, "bottom_right": first_axis}
        }
        operator_order=normalize_operator_v_miter_gui_first_bend_axes(
            snapshot["v_miter_gui_first_bend_axes"],
            snapshot["v_miter_gui_check_corners"],
        )["tail"]
        spec, _ = app._fold_designer_part_spec_from_payload("tail", snapshot)
        render = app._query_fold_designer_render_data("tail", snapshot)
        original = tuple(render.scene.primitives)
        with pytest.raises(Exception, match="V_MITER_TAIL_OPERATOR_FIRST_PHYSICAL_BEND_REQUIRED"):
            project_tail_dual_v_same_source_check(spec, render)
        check = project_tail_dual_v_same_source_check(
            spec, render, first_bend_axes=operator_order,
        )
        assert dict(check.operator_first_bend_axes) == operator_order
        assert all(row.first_bend_axis == first_axis and
                   row.second_bend_axis == ("y" if first_axis=="x" else "x")
                   for row in check.corners)
        # An actual one-source triangulation has two different 3D
        # transformations. Distinct first-fold choices MUST move different
        # physical V lips at stage one, not merely rename static parts.
        assert len(check.sequential_same_sheet_stage_models) == 1
        saved_axis,seq=check.sequential_same_sheet_stage_models[0]
        assert saved_axis == first_axis
        assert seq.first_axis == first_axis
        assert seq.second_axis == ("y" if first_axis=="x" else "x")
        assert seq.flat_source_triangles
        assert len(seq.flat_source_triangles) == len(
            seq.first_formed_skin_triangles
        ) == len(seq.second_formed_skin_triangles)
        assert seq.first_formed_skin_triangles != seq.second_formed_skin_triangles
        assert seq.first_thick_solid_triangles and seq.second_thick_solid_triangles
        assert seq.source_area_mm2 == pytest.approx(
            seq.triangulated_area_mm2,rel=1e-7
        )
        assert seq.first_stage_max_duplicate_vertex_jump_mm < 1e-7
        assert seq.final_stage_max_duplicate_vertex_jump_mm < 1e-7
        assert seq.root_process_status == (
            "FINITE_BEND_TIP_TRANSITION_KINEMATIC_ONLY"
        ), "A same-source kinematic mesh is NOT a proven elastic root fold"
        assert seq.stage1_shell_topology.triangle_count > 0
        assert seq.stage2_shell_topology.triangle_count > 0
        assert seq.stage1_shell_self_intersection.tested_nonadjacent_pairs >= 0
        assert seq.stage2_shell_self_intersection.tested_nonadjacent_pairs >= 0
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
        assert check.bottom_bend_span_x_mm == pytest.approx((16.0, 406.0))
        assert check.native_original_fold_path_mesh
        assert check.retained_out_of_span_corner_area_mm2[0] > 0
        assert check.retained_out_of_span_corner_area_mm2[1] > 0
        assert len(check.out_of_bottom_span_corner_contours_xy) == 2
        assert len(check.restored_stock_ownership_mm2) == 2
        for side,total,side_fold,bottom_fold,neither in check.restored_stock_ownership_mm2:
            assert side in ("bottom_left","bottom_right")
            assert total > 0
            assert bottom_fold > 0, (
                "The attached source corner must travel with its bottom "
                "flange through a finite-tip transition, without fabricating "
                "a full-width BEND"
            )
            assert total == pytest.approx(side_fold+bottom_fold+neither,abs=1e-7)
        assert len(check.native_bottom_span_boundary_jump_samples_mm) == 2
        assert len(check.native_side_span_boundary_jump_samples_mm) == 2
        for which, samples in check.native_side_span_boundary_jump_samples_mm:
            assert which in ("bottom_left", "bottom_right")
            assert len(samples) >= 3
            assert all(gap < 1e-3 for _x, gap in samples)
        for side,samples in check.native_bottom_span_boundary_jump_samples_mm:
            assert side in ("bottom_left","bottom_right")
            assert len(samples) >= 3
            assert all(0 < y < 48 and gap >= 0 for y,gap in samples)
        assert all(
            row.topology_contact_failure is None
            and row.topological_clearance_lower_bound_mm is None
            and row.asymmetry_best_case_far_gap_floor_mm is None
            for row in check.corners
        ), "The old full-bottom-fold 6.69mm impossibility proof is invalid"
        # Reproduce exactly the existing WHD 3D folding path from the
        # SAME corrected source and the actual finite BEND guides; the
        # retained corner stock outside 16..406 must not be assigned
        # to the bottom return.
        from ae_engine.assembly_geometry_folded_mesh import folded_mesh_from_polygon
        from ae_engine.final_scene_fold_source import (
            fold_ownership_exemptions, scene_fold_boundaries,
        )
        from ae_engine.v_miter_operator_gui_check import _endcap_existing_fold_angle_sources
        xp, yp = _endcap_existing_fold_angle_sources(spec, "tail")
        xb, yb = scene_fold_boundaries(render.scene, new_outline)
        original_path = folded_mesh_from_polygon(
            new_outline, xp, yp,
            fold_guides=render.fold_guides,
            fold_exemptions=fold_ownership_exemptions(new_outline, xb, yb),
            fold_tip_continuity=(
                ("y", 48.0,
                 float(new_outline.bounds[0]),
                 float(new_outline.bounds[2])),
                ("x", 15.0, 48.0, 290.0),
                ("x", 407.0, 48.0, 290.0),
            ),
        )
        assert check.native_original_fold_path_mesh == original_path
        assert check.bottom_bend_span_x_mm == pytest.approx((16,406))
        # The original hard-span mapping is discontinued for this V CHECK
        # only; the new connected stock skin must be continuous without
        # changing any source BEND endpoints or CUTTING holes.
        for corner in check.corners:
            # Trace both source V lips at the original UV, after the
            # selected first physical fold, and after second physical
            # fold. The stationary lip MUST differ by order; the opposite
            # lip must be transported by the actual first-stage map.
            rows=corner.sequential_source_cut_edge_tracks
            assert len(rows) == 14
            assert {t[1] for t in rows} == {
                "SIDE_UPPER","BOTTOM_LOWER"
            }
            upper=next(t for t in rows
                       if t[1]=="SIDE_UPPER" and t[2]==.5)
            lower=next(t for t in rows
                       if t[1]=="BOTTOM_LOWER" and t[2]==.5)
            apex=next(t for t in rows
                      if t[1]=="SIDE_UPPER" and t[2]==0.0)
            assert apex[4] == pytest.approx((*apex[3],0.0))
            assert apex[5] == pytest.approx((*apex[3],0.0))
            if first_axis=="x":
                assert upper[4][2] > 0
                assert lower[4][2] == pytest.approx(0.0)
            else:
                assert lower[4][2] > 0
                assert upper[4][2] == pytest.approx(0.0)
            assert upper[5][2] > 0 and lower[5][2] > 0
            assert upper[5][2] == pytest.approx(lower[5][2],abs=1e-6)
            assert upper[4] != upper[5] or lower[4] != lower[5]
            assert all((
                corner.sequential_first_side_cut_faces,
                corner.sequential_first_bottom_cut_faces,
                corner.sequential_second_side_cut_faces,
                corner.sequential_second_bottom_cut_faces,
            ))
            assert len(corner.sequential_final_seam_sections)==4
            assert all(z>0 and gap is not None and gap>0
                       for z,status,gap,_,_ in
                       corner.sequential_final_seam_sections
                       if status=="MEASURED")
            assert corner.sequential_root_process_status == (
                "FINITE_BEND_TIP_TRANSITION_KINEMATIC_ONLY"
            )
            assert corner.native_uncut_fold_endpoint_jump_max_mm is not None
            assert corner.native_uncut_fold_endpoint_jump_max_mm < 1e-3
            assert corner.native_uncut_fold_endpoint_status == (
                "NO_DETECTED_NATIVE_SPAN_DISCONTINUITY"
            )
            assert corner.native_side_tip_endpoint_jump_max_mm < 1e-3
            assert corner.native_side_tip_endpoint_status == (
                "NO_DETECTED_SIDE_TIP_DISCONTINUITY"
            )
            assert len(corner.source_cut_leg_owner_lengths_mm) == 4
            side_upper, side_lower, bottom_lower, bottom_upper = (
                corner.source_cut_leg_owner_lengths_mm
            )
            assert side_upper > 0 and bottom_lower > 0
            assert side_lower < 1e-5 and bottom_upper < 1e-5
            assert len(corner.sampled_cut_face_nearest_xyz) == 4
            assert corner.model_interference_pairs == 4
            assert corner.root_intersection_topology == (
                "COLLINEAR_SHARED_ROOT_EDGE_CANDIDATE_NOT_PENETRATION"
            )
            assert corner.inverse_root_candidate_status == (
                "ROOT_NEUTRAL_INVERSE_CURVES_CROSS_OUTSIDE_APEX_CHECK_ONLY"
            )
            assert len(corner.inverse_root_nonapex_crossings_xy) == 1
            cross_x,cross_y=corner.inverse_root_nonapex_crossings_xy[0]
            want_x=12.7675 if corner.corner=="bottom_left" else 409.2325
            assert cross_x == pytest.approx(want_x,abs=.02)
            assert cross_y == pytest.approx(45.7675,abs=.02)
            assert all(
                row.inverse_root_arc_source_traces_xy for row in check.corners
            )
            side_y, bottom_y, floor_y, reference_y = (
                corner.straight_section_y_domain_witness_mm
            )
            assert side_y == pytest.approx(48)
            assert bottom_y == pytest.approx(46)
            assert floor_y == pytest.approx(2)
            assert reference_y == pytest.approx(45)
            for (station,_,gap), (_,other_gap,side_xyz,bottom_xyz,status) in zip(
                corner.sampled_seam_gap_stations_mm,
                corner.sampled_cut_face_nearest_xyz,
            ):
                assert status == "MEASURED"
                assert gap == pytest.approx(other_gap,abs=1e-8)
                assert side_xyz[2] == pytest.approx(station,abs=1e-7)
                assert bottom_xyz[2] == pytest.approx(station,abs=1e-7)
            assert corner.sampled_seam_gap_stations_mm[0][0] == pytest.approx(
                5.705420442681394, abs=1e-6,
            )
            assert corner.model_status != "MODEL_PASS"
            assert len(corner.inverse_straight_contact_flat_trace_mm) == 4
            assert len(corner.inverse_flat_source_coverage_mm) == 4
            # Real Factory mother can contain a point that is not owned by
            # the actual side fold. Such a point cannot define an upper V cut.
            for z, side_mother, side_owned, bottom_mother, bottom_owned in (
                corner.inverse_flat_source_coverage_mm
            ):
                assert z > 0 and side_mother and bottom_mother
                assert not side_owned
                assert bottom_owned
            assert corner.inverse_source_fit_status in (
                "INVERSE_SOURCE_RAYS_NOT_COMPATIBLE",
                "INVERSE_SOURCE_RAYS_COMPATIBLE",
            )
        evidence = {
            "operator_first_physical_BEND_axis":first_axis,
            "operator_first_bend_axes":check.operator_first_bend_axes,
            "same_sheet_stage_model":"ONE_SOURCE_TRIANGULATION_SEQUENTIAL_RBA_T",
            "source_triangle_count":len(seq.flat_source_triangles),
            "first_folded_triangle_count":len(seq.first_formed_skin_triangles),
            "final_folded_triangle_count":len(seq.second_formed_skin_triangles),
            "source_area_mm2":seq.source_area_mm2,
            "stage1_source_vertex_jump_mm":
                seq.first_stage_max_duplicate_vertex_jump_mm,
            "stage2_source_vertex_jump_mm":
                seq.final_stage_max_duplicate_vertex_jump_mm,
            "root_process_status":seq.root_process_status,
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
            "bottom_real_BEND_span_x_mm":check.bottom_bend_span_x_mm,
            "side_real_BEND_span_y_mm":check.side_bend_span_y_mm,
            "retained_corner_stock_outside_bottom_BEND_area_mm2":
                check.retained_out_of_span_corner_area_mm2,
            "restored_corner_ownership_mm2":check.restored_stock_ownership_mm2,
            "native_finite_BEND_endpoint_3D_jump_mm":
                check.native_bottom_span_boundary_jump_samples_mm,
            "native_side_BEND_tip_3D_jump_mm":
                check.native_side_span_boundary_jump_samples_mm,
            "native_original_3D_triangle_count":
                len(check.native_original_fold_path_mesh),
            "corners": [],
        }
        for row in check.corners:
            continuity = row.seam_continuity
            def z_range(faces):
                zs = [float(p[2]) for tri in faces for p in tri]
                return [min(zs), max(zs)] if zs else None
            evidence["corners"].append({
                "corner":row.corner,
                "sequential_same_source_cut_edge_tracks":
                    row.sequential_source_cut_edge_tracks,
                "sequential_final_true_T_seam_sections":
                    row.sequential_final_seam_sections,
                "sequential_root_process_status":
                    row.sequential_root_process_status,
                "side_cut_face_z_mm":z_range(row.side_cut_faces),
                "bottom_cut_face_z_mm":z_range(row.bottom_cut_faces),
                "collision_surface_triangle_pairs":row.model_interference_pairs,
                "root_intersection_topology":row.root_intersection_topology,
                "hypothetical_RBA_root_inverse_crossings":
                    row.inverse_root_nonapex_crossings_xy,
                "straight_section_y_domain_witness_mm":
                    row.straight_section_y_domain_witness_mm,
                "volume_status":row.model_volume_status,
                "native_uncut_fold_endpoint_jump_max_mm":
                    row.native_uncut_fold_endpoint_jump_max_mm,
                "native_uncut_fold_endpoint_status":
                    row.native_uncut_fold_endpoint_status,
                "native_side_tip_endpoint_jump_max_mm":
                    row.native_side_tip_endpoint_jump_max_mm,
                "native_side_tip_endpoint_status":
                    row.native_side_tip_endpoint_status,
                "source_cut_leg_owner_lengths_mm":
                    row.source_cut_leg_owner_lengths_mm,
                "sampled_cut_face_nearest_xyz":
                    row.sampled_cut_face_nearest_xyz,
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
                "inverse_straight_contact_flat_trace_mm":
                    row.inverse_straight_contact_flat_trace_mm,
                "inverse_unconstrained_outer_hits_mm":
                    row.inverse_unconstrained_outer_hits_mm,
                "inverse_source_fit_status":row.inverse_source_fit_status,
                "inverse_datum_type":"HYPOTHETICAL_RBA_STRAIGHT_PLANE_INTERSECTION",
                "inverse_flat_source_coverage_mm":
                    row.inverse_flat_source_coverage_mm,
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
        # Actual source flat SVG, true folded OBJ/PNG and numerical diagnosis
        # are built from precisely the Engine CHECK model above. The zip is
        # emitted in bounded CI log chunks for exact-source retrieval.
        payload=build_tail_dual_v_source_preview_zip(check)
        assert len(payload) > 1000
        # Actual paired 2D / native 3D / RBA 3D / true-T cross-sections
        # must be emitted from THIS SAME immutable Engine source, not
        # an earlier separate hard-coded drawing or an approved DXF.
        from io import BytesIO
        from zipfile import ZipFile
        with ZipFile(BytesIO(payload)) as archive:
            names=set(archive.namelist())
            assert {
                "WHD_tail_dual_V_same_source_2D.svg",
                "WHD_tail_dual_V_true_T_left_right_sections.svg",
                "WHD_tail_dual_V_original_2D_and_folded_true_T_sections.svg",
                "WHD_tail_dual_V_actual_folded_model.obj",
                "WHD_tail_dual_V_RBA_focused_fold_check.obj",
                "WHD_tail_dual_V_same_sheet_AFTER_FIRST_T.obj",
                "WHD_tail_dual_V_same_sheet_AFTER_SECOND_T.obj",
                "WHD_tail_dual_V_same_sheet_stage1_stage2_V_tracks.svg",
                "WHD_tail_dual_V_folded_preview.png",
                "WHD_tail_dual_V_model_diagnosis.json",
            } <= names
            section=archive.read(
                "WHD_tail_dual_V_true_T_left_right_sections.svg"
            ).decode("utf-8")
            assert "bottom_left" in section and "bottom_right" in section
            assert "CHECK only" in section
            combined=archive.read(
                "WHD_tail_dual_V_original_2D_and_folded_true_T_sections.svg"
            ).decode("utf-8")
            assert "Side-lip source begins Y=48.000" in combined
            assert "Y gap floor 2.000 mm" in combined
            assert "Root R/BA inverse dashed curves intersect" in combined
            assert "bottom_left" in combined and "bottom_right" in combined
            assert "CHECK" in combined
            traced=json.loads(archive.read(
                "WHD_tail_dual_V_model_diagnosis.json"
            ))
            assert traced["formal_dxf_export"] == "NOT_ALLOWED"
            assert len(traced["corners"]) == 2
            assert traced["one_sheet_two_stage_models"][0]["source_area_mm2"] == pytest.approx(
                seq.source_area_mm2
            )
            assert traced["corners"][0]["same_sheet_stage_source_cut_tracks"]
            stageview=archive.read(
                "WHD_tail_dual_V_same_sheet_stage1_stage2_V_tracks.svg"
            ).decode("utf-8")
            assert "STAGE 1" in stageview and "STAGE 2" in stageview
            assert "bottom_left" in stageview and "bottom_right" in stageview
            assert traced["operator_first_bend_axes"] == [
                ["bottom_left",first_axis],["bottom_right",first_axis],
            ]
            assert traced["corners"][0]["true_cut_face_gap_by_z_mm"][0][
                "z"
            ] == pytest.approx(5.705420442681394,abs=1e-6)
        # The SAME ZIP JSON is the sole result/failure/CI log source;
        # previously the separately computed log report had the wrong Z.
        report=json.dumps(traced,ensure_ascii=False,sort_keys=True)
        print("WHD_3317_MODEL_VERDICT_JSON="+report,flush=True)
        # Publish the actual one-run annotated composite as a
        # *separate* SVG next to JSON/ZIP without redrawing anything.
        picture=base64.b64encode(combined.encode("utf-8")).decode("ascii")
        for i in range(0,len(picture),4096):
            print("WHD_3317_MODEL_COMPOSITE_SVG_BASE64_PART="
                  + first_axis+":"+str(i//4096).zfill(4)+":"
                  + picture[i:i+4096],flush=True)
        encoded=base64.b64encode(payload).decode("ascii")
        for i in range(0,len(encoded),4096):
            print("WHD_3317_MODEL_ZIP_BASE64_PART="
                  + first_axis+":"+str(i//4096).zfill(4)+":"
                  + encoded[i:i+4096],flush=True)
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
