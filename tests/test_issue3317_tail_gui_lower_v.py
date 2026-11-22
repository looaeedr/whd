# -*- coding: utf-8 -*-
"""#3317 GUI's one selector, shared actual-CUTTING V rule and project reload."""
from dataclasses import replace
from math import isclose
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.ae_endcap import _build_end_cap_scene
from ae_engine.manufacturing_render_data import (
    PartRenderData, material_polygon_from_final_scene, fold_guides_from_final_scene,
)
from ae_engine.operator_tail_lower_v import TAIL_LOWER_V_SNAPSHOT_KEY
from ae_engine.v_miter_tail_user_image_source import project_tail_illustrated_side_v90_flat
from ae_engine.sheetmetal_geometry_core import GeometryError
import phase6_project_file as project


def _real_source(w=500., d=150., t=2., left=15., right=15., bottom=48., fw=25.):
    spec=EndCapPartSpec(
        width=w,depth=d,thickness=t,frame_width=fw,height=600.,
        model_name="金庫型",is_tail=True,
        fold_left=left,fold_right=right,fold_top=16.,fold_bottom=bottom,
        box_fold_left=15.,box_fold_right=15.,
    )
    scene=_build_end_cap_scene(
        w=w,d=d,t=t,fw=fw,yl1=left,yr1=right,
        ytop1=16.,ybottom1=bottom,is_tail=True,model_name="金庫型",
    )
    render=PartRenderData(
        scene=scene,material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
    )
    return spec,render


def test_legacy_original_no_new_saved_key_and_reversible_real_source(tmp_path):
    source={"model":"金庫型","w":500.,"d":150.,"t":2.,"fw":25.,
            "yl1":15.,"yr1":15.,"ytop1":16.,"ybottom1":48.}
    original=api.commit_operator_tail_lower_v_choice(source,"original",tail_scene_values=source)
    assert TAIL_LOWER_V_SNAPSHOT_KEY not in original
    selected=api.commit_operator_tail_lower_v_choice(source,"v90",tail_scene_values=source)
    assert selected[TAIL_LOWER_V_SNAPSHOT_KEY]=="v90"
    path=project.write_project(tmp_path/"vault-tail-v90.p6fold",{
        "schema":project.PROJECT_SCHEMA,"snapshot":selected,
    })
    loaded=project.read_project(path)["snapshot"]
    assert loaded[TAIL_LOWER_V_SNAPSHOT_KEY]=="v90"
    restored=api.commit_operator_tail_lower_v_choice(loaded,"original",tail_scene_values=loaded)
    assert TAIL_LOWER_V_SNAPSHOT_KEY not in restored
    old=project.read_project(project.write_project(
        tmp_path/"legacy-unchanged.p6fold",{
            "schema":project.PROJECT_SCHEMA,"snapshot":source
        }
    ))["snapshot"]
    assert TAIL_LOWER_V_SNAPSHOT_KEY not in old


@pytest.mark.parametrize("w,d,t,left,right,bottom,fw",(
    (500.,150.,2.,15.,15.,48.,25.),  # User's original regression
    (620.,185.,2.,15.,15.,48.,25.),  # Different W and D; same V topology
))
def test_actual_source_generates_two_v_and_one_same_source_2d_3d(
    w,d,t,left,right,bottom,fw,
):
    spec,render=_real_source(w,d,t,left,right,bottom,fw)
    original_scene=tuple(render.scene.primitives)
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    assert tuple(render.scene.primitives)==original_scene
    assert len(flat.opening_source_points_xy)==2
    x0,y0,x1,y1=flat.result_material.bounds
    for corner,lo,tip,hi in flat.opening_source_points_xy:
        outer_x=x0 if corner=="bottom_left" else x1
        assert isclose(tip[1],bottom,abs_tol=1e-7)
        assert isclose(lo[0],outer_x,abs_tol=1e-7)
        assert isclose(hi[0],outer_x,abs_tol=1e-7)
        assert isclose(tip[1]-lo[1],hi[1]-tip[1],abs_tol=1e-7)
    preview=api.project_operator_tail_lower_v_preview_render(spec,render,choice="v90")
    assert preview.metadata["tail_lower_v_preview_only"] is True
    assert preview.metadata["tail_lower_v_physical_t"]==t
    assert preview.scene == flat.result_scene
    assert preview.material.geom_type == "Polygon"
    triangles=api.tail_lower_v_preview_mesh(preview)
    mesh=api.project_independent_part_view_mesh(
        "tail",preview,x_profile=(),y_profile=(),thickness=t
    )
    assert tuple(mesh.triangles)==triangles
    with pytest.raises(ValueError,match="禁止加工|尚未核准"):
        api.reject_tail_lower_v_preview_for_dxf(preview)




def test_variable_t_is_not_whitelisted_but_upper_factory_profile_must_match():
    # Real geometry / existing Fold Profile do not agree at this fractional
    # T for the observed Factory source. This is a concrete source conflict,
    # NOT an artificial T=2 or 522×233 white-list rejection.
    spec,render=_real_source(545.,180.,1.5,14.,17.,48.,25.)
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    assert len(flat.opening_source_points_xy)==2
    with pytest.raises(GeometryError,match="UNCHANGED_UPPER_FOLD_TOPOLOGY_INVALID:.*current_CUTTING_Y=.*current_profile_Y="):
        api.project_operator_tail_lower_v_preview_render(spec,render,choice="v90")

@pytest.mark.parametrize("w,d,t",((470.,148.,2.),(840.,230.,1.5)))
def test_different_dimensions_do_not_fail_the_operator_selection_gate(w,d,t):
    source={"model":"金庫型","w":w,"d":d,"t":t,"fw":25.,
            "yl1":15.,"yr1":15.,"ytop1":16.,"ybottom1":48.}
    got=api.commit_operator_tail_lower_v_choice(source,"v90",tail_scene_values=source)
    assert got[TAIL_LOWER_V_SNAPSHOT_KEY]=="v90"


def test_unsupported_short_side_reach_reports_geometric_reason():
    spec,render=_real_source(left=55.,bottom=30.)
    with pytest.raises(GeometryError,match="FLANGE_REACH|BEND|CUTTING|TOPOLOGY"):
        project_tail_illustrated_side_v90_flat(spec,render)


@pytest.mark.parametrize("invalid",(True,False,"guess",{},2,1,"V 型"))
def test_saved_choice_strictly_refuses_unknown_mode(invalid):
    with pytest.raises(ValueError):
        api.normalize_operator_tail_lower_v_choice(invalid)


def test_settings_row_projection_is_tail_only_in_vault_family():
    v={TAIL_LOWER_V_SNAPSHOT_KEY:"v90","model":"金庫型"}
    assert api.project_operator_tail_lower_v_settings(v,context="tail")["choice"]=="v90"
    assert api.project_operator_tail_lower_v_settings(v,context="head") is None
    assert api.project_operator_tail_lower_v_settings(
        {**v,"model":"受電箱"},context="tail"
    ) is None
