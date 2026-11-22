"""#3317 old unsupported +/-45-degree V MUST NOT be treated as user geometry.

Previous x/y tests reported formed gaps for a locally invented symmetric
triangle. They are intentionally replaced by one provenance gate after the
user rejected that flat outline. NO 3D or old-gap computation is done.
"""
from __future__ import annotations

import base64
import json

import pytest

from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_tail_dual_source_check import (
    project_tail_dual_v_same_source_check,
)
from ae_engine.v_miter_tail_flat_source_audit import (
    project_tail_original_flat_source_audit,
)
from tools.render_tail_flat_source_audit import (
    build_tail_flat_audit_pair,
)


def test_tail_unconfirmed_symmetric_v_must_not_enter_3d_or_machining():
    import gui
    import tkinter as tk

    root=tk.Tk()
    app=None
    try:
        app=gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("tail")
        app.ybottom1_var.set("48")
        snapshot=app._make_original_fold_designer_snapshot()
        spec,_=app._fold_designer_part_spec_from_payload("tail",snapshot)
        render=app._query_fold_designer_render_data("tail",snapshot)
        # This is the true source 2D audit, NOT the old folded model.
        audit=project_tail_original_flat_source_audit(spec,render)
        assert all(c.confirmed_source_cut_legs_xy is None
                   for c in audit.corner_rows)
        source_svg, source_json=build_tail_flat_audit_pair(
            audit,snapshot_baseline=app.baseline_var.get(),
        )
        result=json.loads(source_json)
        assert result["3D_or_formed_gap_from_legacy_assumption"]==(
            "NOT_RUN_NOT_USER_SPEC"
        )
        assert result["manufacturing_DXF"]=="NOT_ALLOWED"
        # Both possible operator first-fold choices are REJECTED
        # BEFORE entering the historical symmetric V 3D engine.
        for axis in ("x","y"):
            with pytest.raises(
                GeometryError,
                match="V_MITER_TAIL_OLD_SYMMETRIC_45_DEG_NOT_USER_CONFIRMED",
            ):
                project_tail_dual_v_same_source_check(
                    spec,render,
                    first_bend_axes={
                        "bottom_left":axis,"bottom_right":axis,
                    },
                )
        print(
            "WHD_3317_TAIL_SOURCE_2D_JSON="+
            json.dumps(result,ensure_ascii=False,sort_keys=True),
            flush=True,
        )
        encoded=base64.b64encode(source_svg).decode("ascii")
        for i in range(0,len(encoded),4096):
            print(
                "WHD_3317_TAIL_SOURCE_2D_SVG_BASE64_PART="+
                str(i//4096).zfill(4)+":"+encoded[i:i+4096],
                flush=True,
            )
        # Keep real V acceptance RED; this is not a license to merge or
        # automatically draw unknown user asymmetrical cut lines.
        # Absence of a typed 2D source continues to be rejected,
        # regardless of a familiar-looking V sketch.
        assert all(c.confirmed_source_cut_legs_xy is None
                   for c in audit.corner_rows)
    finally:
        if app is not None:
            designer=getattr(app,"fold_designer_app",None)
            if designer is not None:
                try: designer.root.destroy()
                except Exception: pass
        root.destroy()


def _image_sample_vault_tail():
    """Use the EXISTING Vault intrinsic EndCap Factory on the image dimensions.

    The separate Vault *stretched baseline* public renderer currently reports
    a 200-mm-height external mapped contour for this 233-mm intrinsic
    Factory example. Do not silently mix the two as a supposedly identical
    production FinalScene. This CHECK deliberately exercises the actual
    Factory geometry that the corrected illustration specifies, with every
    Factory hole, mark and finite BEND intact.
    """
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine import ae_endcap as original_factory
    from ae_engine.manufacturing_render_data import (
        PartRenderData,material_polygon_from_final_scene,
        fold_guides_from_final_scene,
    )
    spec=EndCapPartSpec(
        width=500,depth=150,thickness=2,frame_width=25,height=600,
        model_name="金庫型",is_tail=True,
        fold_left=15,fold_right=15,fold_top=16,fold_bottom=48,
        box_fold_left=15,box_fold_right=15,
    )
    scene=original_factory._build_end_cap_scene(
        w=500,d=150,t=2,fw=25,yl1=15,yr1=15,
        ytop1=16,ybottom1=48,is_tail=True,model_name="金庫型",
    )
    return spec,PartRenderData(
        scene=scene,material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={"source":"DIRECT_WHD_INTRINSIC_ENDCAP_FACTORY_CHECK"},
    )


def test_user_illustrated_tail_2d_factory_cutting_bend_holes_and_dxf_reopen(tmp_path):
    """The actually selected user's V, not a second handwritten DXF outline."""
    import ezdxf
    from shapely.geometry import Polygon
    from ae_engine.dxf_serialization import save_scene_dxf
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
    )

    spec,render=_image_sample_vault_tail()
    snapshot=tuple(render.scene.primitives)
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    assert render.scene.primitives==list(snapshot)
    assert flat.status.endswith("FOLDED_FIT_NOT_VERIFIED")
    assert flat.manufacturing_approved is False
    assert flat.result_material.bounds == pytest.approx((0,0,522,233))
    assert len(flat.opening_source_points_xy)==2
    for key,lower,tip,upper in flat.opening_source_points_xy:
        wanted_x=0 if key=="bottom_left" else 522
        wanted_tip_x=15 if key=="bottom_left" else 507
        assert lower == pytest.approx((wanted_x,33))
        assert tip == pytest.approx((wanted_tip_x,48))
        assert upper == pytest.approx((wanted_x,63))
    assert len(flat.result_scene.primitives)==len(snapshot)
    # Only the CUTTING outer contour and two physical side BEND lines
    # change. Former Y=49 starts MUST NOT silently survive into this model.
    changed=[(old,new) for old,new in zip(snapshot,flat.result_scene.primitives)
             if old is not new]
    assert len(changed)==3
    assert flat.side_bend_source_extensions==(
        (15.0,49.0,0.0,190.0),(507.0,49.0,0.0,190.0),
    )
    from ae_engine.sheetmetal_drawing import LinePrimitive
    for old,new in changed:
        if isinstance(old,LinePrimitive):
            assert old.layer==new.layer=="BEND"
            assert old.p1.y==pytest.approx(49)
            assert new.p1.y==pytest.approx(0)
            assert new.p2==old.p2
    original_cutting=tuple(
        p for p in snapshot if p.layer=="CUTTING"
    )
    new_cutting=tuple(
        p for p in flat.result_scene.primitives if p.layer=="CUTTING"
    )
    assert len(new_cutting)==len(original_cutting)
    original_other=tuple(
        p for p in original_cutting
        if not (isinstance(p,PolylinePrimitive)
                and p.closed
                and Polygon([(q.x,q.y) for q in p.points]).symmetric_difference(
                    flat.original_factory_material,
                ).area < 1e-6)
    )
    assert all(p in new_cutting for p in original_other)
    assert all(
        old is new for old,new in zip(snapshot,flat.result_scene.primitives)
        if old.layer!="BEND" and old is not snapshot[0]
    )
    path=tmp_path/"tail_user_illustrated_90_same_side_2D_CHECK_NOT_CNC.dxf"
    save_scene_dxf(path,flat.result_scene)
    reopened=ezdxf.readfile(path)
    assert reopened.header["$INSUNITS"]==4
    side_lines=tuple(e for e in reopened.modelspace().query('LINE[layer=="BEND"]')
                     if abs(e.dxf.start.x-e.dxf.end.x)<1e-7)
    assert len(side_lines)==2
    assert sorted((round(e.dxf.start.x,5),round(e.dxf.start.y,5),
                   round(e.dxf.end.y,5)) for e in side_lines)==[
        (15.0,0.0,190.0),(507.0,0.0,190.0),
    ]
    poly=tuple(reopened.modelspace().query('LWPOLYLINE[layer=="CUTTING"]'))
    outline=tuple(e for e in poly if e.closed and len(e.get_points("xy"))>12)
    assert len(outline)==1
    got=Polygon(tuple(e[:2] for e in outline[0].get_points("xy")))
    assert got.symmetric_difference(flat.result_material).area<1e-6
    assert all(
        sum(1 for e in reopened.modelspace() if e.dxf.layer==layer)
        ==sum(1 for p in flat.result_scene.primitives if p.layer==layer)
        for layer in ("CUTTING","BEND","MARKING")
    )


@pytest.mark.parametrize("first_axis",("x","y"))
def test_user_image_v90_same_sheet_3d_left_right_fit_stays_red_if_open(first_axis,tmp_path):
    """The operator's corrected Y=0 side BEND must drive BOTH physical folds.

    Old Y=49 three-panel diagnostics are rejected; a real retained source
    corner now gets both X and Y action. Keep physical cut-face mating as
    a hard gate and never declare a complete CNC model from this CHECK.
    """
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
        project_tail_illustrated_side_v90_staged_check,
    )
    from ae_engine.v_miter_trial_defaults import project_v_miter_trial_parameter_defaults
    from ae_engine.v_miter_seam_gap_trial import (
        project_v_miter_true_t_seam_section_gap_trial,
    )
    from ae_engine.v_miter_cut_face_continuity_trial import (
        project_v_miter_true_cut_face_continuity_trial,
    )
    from ae_engine.dxf_serialization import save_scene_dxf
    from ae_engine.contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
    import ezdxf

    spec,render=_image_sample_vault_tail()
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    # Prevent a valid-looking but WRONG old V result from the unchanged
    # original Factory guide start at Y=49.
    with pytest.raises(GeometryError,match="STALE_DISJOINT_BEND_MODEL"):
        project_tail_dual_v_same_source_check(
            spec,render,
            first_bend_axes={"bottom_left":first_axis,"bottom_right":first_axis},
            illustrated_v90_source=flat,
        )
    seq=project_tail_illustrated_side_v90_staged_check(flat,first_axis=first_axis)
    assert seq.first_axis==first_axis
    assert seq.stage1_shell_topology.edges_manifold_closed
    assert seq.stage2_shell_topology.edges_manifold_closed
    assert seq.root_process_status.endswith("KINEMATIC_ONLY")
    assert seq.source_x_only_vertices>0
    assert seq.source_y_only_vertices>0
    assert seq.source_double_bend_vertices>0
    assert seq.max_X_then_Y_vs_Y_then_X_final_delta_mm>1e-6
    assert seq.first_stage_max_duplicate_vertex_jump_mm<1e-5
    assert seq.final_stage_max_duplicate_vertex_jump_mm<1e-5
    assert len(seq.true_t_cut_faces_by_corner)==2

    dxf_path=tmp_path/f"Vault_Tail_500x150_side_V90_TO_BOTTOM_{first_axis}_NOT_CNC.dxf"
    save_scene_dxf(dxf_path,flat.result_scene)
    doc=ezdxf.readfile(dxf_path)
    assert doc.header["$INSUNITS"]==4

    # Both true source V CUTTING walls MUST mate over their complete
    # post-RBA straight physical span (never just a single nearest point).
    q=project_v_miter_trial_parameter_defaults(
        thickness_mm=spec.thickness,second_fold_angle_deg=90.0,
        relief_mode="ROUND_R",
    )
    mid_radius=q.first_inner_radius_mm+q.thickness_mm/2.0
    formed_reach=15-q.first_bend_allowance_mm+mid_radius
    assert formed_reach>mid_radius
    verdict=[]
    tol=float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    for corner,first_side,first_bottom,final_side,final_bottom in (
            seq.true_t_cut_faces_by_corner):
        x=15-mid_radius if corner=="bottom_left" else 507+mid_radius
        seam_start=(x,48-mid_radius,mid_radius)
        seam_end=(x,48-mid_radius,formed_reach)
        section=project_v_miter_true_t_seam_section_gap_trial(
            final_side,final_bottom,
            formed_seam_start=seam_start,formed_seam_end=seam_end,
            station_fractions=(.25,.50,.75,.95),
        )
        complete=project_v_miter_true_cut_face_continuity_trial(
            final_side,final_bottom,
            formed_seam_start=seam_start,formed_seam_end=seam_end,
        )
        verdict.append((corner,section,complete))
    print("WHD_3317_CORRECTED_BOTTOM_REACH_BEND_MODEL="+json.dumps({
        "first_axis":first_axis,
        "double_bend_source_vertices":seq.source_double_bend_vertices,
        "order_effect_mm":seq.max_X_then_Y_vs_Y_then_X_final_delta_mm,
        "cuts":tuple((corner,
            section.max_measured_gap_mm,
            complete.max_gap_upper_bound_mm,
            complete.missing_face_interval_count)
            for corner,section,complete in verdict),
    },sort_keys=True),flush=True)
    assert all(
        section.missing_section_count==0
        and section.max_measured_gap_mm is not None
        and section.max_measured_gap_mm<=tol
        and complete.max_gap_upper_bound_mm is not None
        and complete.max_gap_upper_bound_mm<=tol
        and complete.missing_face_interval_count==0
        and complete.numerically_unresolved_vertex_event_count==0
        for _,section,complete in verdict
    ), "CORRECTED_2D_BEND_TRUE_T_FINAL_V_FACES_NOT_FULLY_MATING"


def test_user_image_vault_stretched_baseline_not_silent_factory_substitute():
    """Do not quietly pass 200-mm mapped source as the user's 233-mm blank."""
    from ae_engine import manufacturing_api as api
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
    )
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    spec,intrinsic=_image_sample_vault_tail()
    baseline=api.build_operator_part_render_data(
        spec,ManufacturingContext(draw_stock=False),
    )
    boundary=tuple(
        p for p in baseline.scene.primitives
        if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING"
        and p.closed and len(p.points)>10
    )
    assert len(boundary)==1
    baseline_max_y=max(p.y for p in boundary[0].points)
    intrinsic_max_y=max(
        p.y for p in intrinsic.scene.primitives[0].points
    )
    assert intrinsic_max_y==pytest.approx(233.0)
    assert baseline_max_y==pytest.approx(200.0)
    with pytest.raises(Exception,match="TAIL_IMAGE_V90_FACTORY_SOURCE_DIFFERENT"):
        project_tail_illustrated_side_v90_flat(spec,baseline)


@pytest.mark.parametrize("axis",("x","y"))
def test_tail_corrected_nominal_w496_d148_and_both_first_fold_3d_skin(axis):
    """Source-verified WHD outside readback independent of unknown R/BA root.

    The X-first *solid* still fails closed separately: skin != a certified
    true-T solid. This test only verifies the actual ordered 3D skin motion
    from corrected 2D, untouched upper CUTTING and original physical holes.
    """
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
        project_tail_illustrated_side_v90_nominal_and_stages,
    )
    from ae_engine.sheetmetal_drawing import LinePrimitive

    spec,render=_image_sample_vault_tail()
    original=tuple(render.scene.primitives)
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    assert tuple(render.scene.primitives)==original
    assert all(a is b for a,b in zip(original,flat.result_scene.primitives)
               if a.layer not in ("BEND","CUTTING"))
    result=project_tail_illustrated_side_v90_nominal_and_stages(
        flat,first_axis=axis,
    )
    assert dict(result.nominal_outside_mm)=={
        "main_face_w":496.,"main_face_d":148.,
        "side_left":17.,"side_right":17.,"bottom":50.,
    }
    assert result.source_area_mm2==pytest.approx(117928.)
    assert result.source_triangle_area_mm2==pytest.approx(117928.)
    assert len(result.original_source_faces)==762
    assert len(result.after_first_faces_xyz)==len(result.after_second_faces_xyz)==762
    assert result.shared_source_uv_vertices>0
    assert result.physical_root_status.endswith("KINEMATIC_ONLY")
    assert result.manufacturing_approved is False
    # Pick the actual upper/lower left V SOURCE points, not standalone flanges.
    from ae_engine.v_miter_tail_sequential_fold_check import _advance_same_source_uv
    params=(15.,507.,48.,0.,522.,190.,
            result.first_ba_trial_mm,
            result.first_inner_r_trial_mm+spec.thickness/2)
    upper_first,upper_final,_,_=_advance_same_source_uv((7.5,55.5),axis,params)
    lower_first,lower_final,_,_=_advance_same_source_uv((7.5,40.5),axis,params)
    if axis=="x":
        # Corrected side BEND reaches Y=0: the lower shared corner
        # MUST already follow X on the first fold. The old Y49 model
        # incorrectly left this original source point stationary.
        assert upper_first[2]>0 and lower_first[2]>0
        assert lower_final[0]>lower_first[0]
    else:
        assert upper_first[2]==0 and lower_first[2]>0
        assert lower_final[0]>lower_first[0]
    assert upper_final[2]>0 and lower_final[2]>0
    # The corrected source guides are not the old Y49 original Factory guide.
    bends=[e for e in flat.result_scene.primitives
           if isinstance(e,LinePrimitive) and e.layer=="BEND"]
    assert sum(abs(e.p1.y)<1e-7 for e in bends)==2
    assert sum(abs(e.p1.y-49.)<1e-7 for e in bends)==0


def test_tail_corrected_nominal_and_stages_reject_old_y49_and_unselected_axis():
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
        project_tail_illustrated_side_v90_nominal_and_stages,
    )
    from dataclasses import replace
    spec,render=_image_sample_vault_tail()
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    for axis in (None,True,"z"):
        with pytest.raises(GeometryError,match="TAIL_V90_SOURCE_AND_OPERATOR_FOLD_REQUIRED"):
            project_tail_illustrated_side_v90_nominal_and_stages(
                flat,first_axis=axis,
            )
    # No fake success for the old finite BEND starting at Y49.
    invalid=replace(flat,result_scene=render.scene)
    with pytest.raises(GeometryError,match="TAIL_V90_CORRECTED_BEND_MISMATCH"):
        project_tail_illustrated_side_v90_nominal_and_stages(
            invalid,first_axis="x",
        )
