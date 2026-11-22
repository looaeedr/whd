"""#3317 old unsupported +/-45-degree V MUST NOT be treated as user geometry.

Previous x/y tests reported formed gaps for a locally invented symmetric
triangle. They are intentionally replaced by one provenance gate after the
user rejected that flat outline. NO 3D or old-gap computation is done.
"""
from __future__ import annotations

import base64
import json
import math

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


@pytest.mark.parametrize("axis",("x","y"))
def test_tail_3317_user_no_ba_blocks_old_assumed_radius_solver(axis):
    """Old cut-wall gap / three-panel numbers cannot answer this real job."""
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
        project_tail_illustrated_side_v90_staged_check,
        project_tail_illustrated_side_v90_nominal_and_stages,
    )
    spec,render=_image_sample_vault_tail()
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    for obsolete in (
        project_tail_illustrated_side_v90_staged_check,
        project_tail_illustrated_side_v90_nominal_and_stages,
    ):
        with pytest.raises(GeometryError,match="NO_BA_USER_RULE"):
            obsolete(flat,first_axis=axis)


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
def test_tail_3317_no_ba_nominal_pair_reads_whd_existing_profiles(axis):
    """Read current WHD sharp mapping and compare user target, never assert a cut gap."""
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
        project_tail_illustrated_side_v90_nominal_and_stages,
    )
    from ae_engine.v_miter_tail_sharp_no_ba_witness import (
        project_tail_sharp_no_ba_v_witness,
    )
    spec,render=_image_sample_vault_tail()
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    witness=project_tail_sharp_no_ba_v_witness(flat)
    assert witness.geometry_model.endswith("NO_BA_CHECK")
    assert witness.manufacturing_approved is False
    assert witness.source_blank_mm==(522.,233.)
    assert witness.physical_sheet_thickness_mm==2.
    assert dict(witness.nominal_outside_mm)=={
        "main_face_w":496., "main_face_d":148.,
        "side_left":17., "side_right":17., "bottom":50.,
    }
    assert len(witness.corners)==2
    for c in witness.corners:
        side_x=15. if c.corner=="bottom_left" else 507.
        assert c.user_nominal_sharp_target_xyz==(side_x,55.5,7.5)
        assert c.upper_source_mid_xy==pytest.approx((
            7.5 if c.corner=="bottom_left" else 514.5,55.5))
        assert c.lower_source_mid_xy==pytest.approx((
            7.5 if c.corner=="bottom_left" else 514.5,40.5))
        # Compare nominal SHARP finite-guide readback to the user's stated
        # pairing target. This 15 mm differential is an out-of-guide
        # kinematic MODEL DISCREPANCY, never an actual physical seam gap.
        assert c.upper_current_whd_sharp_xyz==pytest.approx((side_x,55.5,7.5))
        assert c.lower_current_whd_sharp_xyz==pytest.approx((side_x,40.5,7.5))
        assert c.upper_target_error_mm==pytest.approx(0.)
        assert c.lower_target_error_mm==pytest.approx(15.)
        assert c.current_two_midpoint_distance_mm==pytest.approx(15.)
        assert all(math.isfinite(v) for v in (
            *c.upper_current_whd_sharp_xyz,
            *c.lower_current_whd_sharp_xyz,
            c.upper_target_error_mm,c.lower_target_error_mm,
        ))
    with pytest.raises(GeometryError,match="NO_BA_USER_RULE"):
        project_tail_illustrated_side_v90_nominal_and_stages(flat,first_axis=axis)


def test_tail_3317_no_ba_old_root_alias_trial_is_explicitly_withdrawn():
    """A prior R/BA-based root count is not a permitted product verdict."""
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
        project_tail_illustrated_side_v90_nominal_and_stages,
    )
    spec,render=_image_sample_vault_tail()
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    with pytest.raises(GeometryError,match="NO_BA_USER_RULE"):
        project_tail_illustrated_side_v90_nominal_and_stages(flat,first_axis="x")



@pytest.mark.parametrize("order",("y","x"))
def test_tail_3317_sharp_no_ba_sequential_true_wall(order):
    """Same original V edges; Y-then-X must reach operator's exact sharp datum."""
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
    )
    from ae_engine.v_miter_tail_no_ba_sequential import (
        project_tail_v90_no_ba_sequential_check,
    )
    spec,render=_image_sample_vault_tail()
    originals=tuple(render.scene.primitives)
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    result=project_tail_v90_no_ba_sequential_check(flat,first_axis=order)
    assert tuple(render.scene.primitives)==originals
    assert result.manufacturing_approved is False
    assert result.root_status=="TRUE_T_ROOT_STILL_UNCERTIFIED"
    assert result.thickness_mm==2.
    assert dict(result.nominal_outside_mm)=={
        "main_face_w":496.,"main_face_d":148.,
        "side_left":17.,"side_right":17.,"bottom":50.,
    }
    assert result.original_source_area_mm2==pytest.approx(
        result.triangulated_source_area_mm2
    )
    assert len(result.original_source_triangles)==len(result.first_stage_triangles)
    assert len(result.first_stage_triangles)==len(result.second_stage_triangles)
    track={(name,tag):(flat_mid,stage1,stage2,n)
           for name,tag,flat_mid,stage1,stage2,n in result.midpoint_tracks}
    assert track["bottom_left","upper"][0]==pytest.approx((7.5,55.5))
    assert track["bottom_left","lower"][0]==pytest.approx((7.5,40.5))
    assert track["bottom_left","upper"][2]==pytest.approx((15.,55.5,7.5))
    if order=="y":
        assert track["bottom_left","lower"][1]==pytest.approx((7.5,48.,7.5))
        assert track["bottom_left","lower"][2]==pytest.approx((15.,55.5,7.5))
        assert track["bottom_right","lower"][2]==pytest.approx((507.,55.5,7.5))
        assert all(abs(axis[2])==pytest.approx(1.)
                   for _,axis in result.carried_second_axes)
        assert all(wall_max<=1e-6 for _,_,wall_max in result.paired_T_wall)
    else:
        # Opposite fold order is genuinely distinct, not a renamed label.
        assert math.dist(track["bottom_left","upper"][2],
                         track["bottom_left","lower"][2])>1.
        assert all(wall_max>1. for _,_,wall_max in result.paired_T_wall)


def test_tail_3317_sharp_no_ba_finite_bend_source_rejects_old_y49():
    from dataclasses import replace
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
    )
    from ae_engine.v_miter_tail_no_ba_sequential import (
        project_tail_v90_no_ba_sequential_check,
    )
    spec,render=_image_sample_vault_tail()
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    with pytest.raises(GeometryError,match="CORRECTED_FINITE_BEND_REQUIRED"):
        project_tail_v90_no_ba_sequential_check(
            replace(flat,result_scene=render.scene),first_axis="y",
        )
