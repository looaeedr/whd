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
    assert all(p is q for p,q in zip(
        flat.result_scene.primitives[1:],snapshot[1:],
    ))
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
    assert all(p in flat.result_scene.primitives for p in snapshot[1:])
    path=tmp_path/"tail_user_illustrated_90_same_side_2D_CHECK_NOT_CNC.dxf"
    save_scene_dxf(path,flat.result_scene)
    reopened=ezdxf.readfile(path)
    assert reopened.header["$INSUNITS"]==4
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
def test_user_image_v90_same_sheet_3d_left_right_fit_stays_red_if_open(first_axis):
    """Do real first/second T fold only AFTER confirmed image/source parity.

    The 2D image is now sourced, but 3D full seam fit must not be
    silently approved by simply rebuilding the historical V triangle.
    """
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
    )
    from tools.render_tail_dual_v_model import build_tail_dual_v_source_preview_zip
    from zipfile import ZipFile
    from io import BytesIO

    spec,render=_image_sample_vault_tail()
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    check=project_tail_dual_v_same_source_check(
        spec,render,
        first_bend_axes={
            "bottom_left":first_axis,"bottom_right":first_axis,
        },
        illustrated_v90_source=flat,
    )
    assert check.original_factory_scene is render.scene
    assert check.corrected_outline
    assert len(check.corners)==2
    assert all(c.first_bend_axis==first_axis for c in check.corners)
    assert len(check.sequential_same_sheet_stage_models)==1
    _,sequence=check.sequential_same_sheet_stage_models[0]
    assert sequence.stage1_shell_topology.edges_manifold_closed
    assert sequence.stage2_shell_topology.edges_manifold_closed
    assert sequence.root_process_status.endswith("KINEMATIC_ONLY")
    assert all(len(c.sequential_final_seam_sections)==4 for c in check.corners)
    evidence=build_tail_dual_v_source_preview_zip(check)
    with ZipFile(BytesIO(evidence)) as z:
        diag=json.loads(z.read("WHD_tail_dual_V_model_diagnosis.json"))
        assert len(diag["corners"])==2
        assert diag["formal_dxf_export"]=="NOT_ALLOWED"
        assert {
            "WHD_tail_dual_V_same_source_2D.svg",
            "WHD_tail_dual_V_same_sheet_AFTER_FIRST_T.obj",
            "WHD_tail_dual_V_same_sheet_AFTER_SECOND_T.obj",
            "WHD_tail_dual_V_true_T_left_right_sections.svg",
        } <= set(z.namelist())
    print("WHD_3317_USER_IMAGE_V90_3D_DIAG="+json.dumps(
        {"axis":first_axis,"data":diag},sort_keys=True,ensure_ascii=False,
    ),flush=True)
    # Correct 2D does not remove the required RED gate for unseated seams.
    assert all(c.model_status=="MODEL_PASS" for c in check.corners), (
        "USER_IMAGE_V90_2D_SOURCE_VERIFIED_3D_SEAM_NOT_YET_MATING"
    )
