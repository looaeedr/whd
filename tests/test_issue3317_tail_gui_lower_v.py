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




def test_fractional_t_original_bend_precision_is_not_rounded_and_v_works(tmp_path):
    # Factory source carries a 175.5 mm material segment, even when the
    # unchanged legacy UI Fold Profile happens to display it as 176.
    from ae_engine.v_miter_tail_no_ba_sequential import (
        stations_from_real_flat,exact_tail_y_fold_profile_from_original_bends,
    )
    spec,render=_real_source(545.,180.,1.5,14.,17.,48.,25.)
    flat=project_tail_illustrated_side_v90_flat(spec,render)
    before_scene=tuple(render.scene.primitives)
    assert len(flat.opening_source_points_xy)==2
    st=stations_from_real_flat(flat)
    assert (st.bottom_y,st.upper_start,st.upper_crease,st.ymax)==pytest.approx(
        (48.,223.5,248.5,264.5)
    )
    exact=exact_tail_y_fold_profile_from_original_bends(flat,st)
    assert [row["len"] for row in exact]==pytest.approx((48.,175.5,25.,16.))
    assert [row.get("angle") for row in exact]==[-90,-90,-90,None]
    preview=api.project_operator_tail_lower_v_preview_render(spec,render,choice="v90")
    assert tuple(render.scene.primitives)==before_scene
    assert preview.metadata["tail_lower_v_physical_t"]==pytest.approx(1.5)
    assert preview.scene==flat.result_scene
    assert preview.material.bounds[3]==pytest.approx(264.5)
    mesh=api.project_independent_part_view_mesh(
        "tail",preview,x_profile=(),y_profile=(),thickness=1.5,
    )
    assert tuple(mesh.triangles)==api.tail_lower_v_preview_mesh(preview)
    assert len(mesh.triangles)>500
    # Same W545/D180/T1.5 physical source survives the real project codec,
    # then operator returns to the EXACT pre-V original selection.
    source={"model":"金庫型","w":545.,"d":180.,"t":1.5,"fw":25.,
            "yl1":14.,"yr1":17.,"ytop1":16.,"ybottom1":48.}
    before=api.commit_operator_tail_lower_v_choice(
        source,"original",tail_scene_values=source,
    )
    assert TAIL_LOWER_V_SNAPSHOT_KEY not in before
    selected=api.commit_operator_tail_lower_v_choice(
        source,"v90",tail_scene_values=source,
    )
    saved=project.write_project(tmp_path/"fractional-bend-v.p6fold",{
        "schema":project.PROJECT_SCHEMA,"snapshot":selected,
    })
    loaded=project.read_project(saved)["snapshot"]
    assert loaded[TAIL_LOWER_V_SNAPSHOT_KEY]=="v90"
    reopened=api.project_operator_tail_lower_v_preview_render(
        spec,render,choice=loaded[TAIL_LOWER_V_SNAPSHOT_KEY],
    )
    assert reopened.material.symmetric_difference(preview.material).area<1e-7
    assert tuple(api.tail_lower_v_preview_mesh(reopened))==tuple(mesh.triangles)
    restored=api.commit_operator_tail_lower_v_choice(
        loaded,"original",tail_scene_values=loaded,
    )
    assert TAIL_LOWER_V_SNAPSHOT_KEY not in restored
    assert api.tail_lower_v_preview_mesh(render) is None


def test_fractional_t_real_upper_bend_shift_rejected_not_masked_by_precision_fix():
    from ae_engine.sheetmetal_drawing import LinePrimitive, DrawingScene
    from ae_engine.sheetmetal_geometry_core import Vec2
    spec,render=_real_source(545.,180.,1.5,14.,17.,48.,25.)
    # Change the physical source BEND only, not the matching stepped CUTTING.
    moved=[]
    for primitive in render.scene.primitives:
        if (isinstance(primitive,LinePrimitive)
                and primitive.layer=="BEND"
                and abs(primitive.p1.y-223.5)<1e-7
                and abs(primitive.p2.y-223.5)<1e-7):
            primitive=LinePrimitive(
                Vec2(primitive.p1.x,224.),Vec2(primitive.p2.x,224.),
                layer=primitive.layer,color=primitive.color,
            )
        moved.append(primitive)
    changed=PartRenderData(
        scene=DrawingScene(moved),material=material_polygon_from_final_scene(DrawingScene(moved)),
        fold_guides=fold_guides_from_final_scene(DrawingScene(moved)),
    )
    bad_flat=project_tail_illustrated_side_v90_flat(spec,changed)
    with pytest.raises(GeometryError,match="UNCHANGED_UPPER_FOLD_TOPOLOGY_INVALID"):
        api.project_operator_tail_lower_v_preview_render(
            spec,changed,choice="v90",
        )

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


def test_factory_equivalent_one_ulp_right_boundary_does_not_join_corner_voids():
    """The actual raw CUTTING keeps its vertices; Factory only classifies old cuts."""
    import math
    from shapely.geometry import Polygon, box
    from ae_engine.v_miter_factory_mother_check import (
        _factory_original_shape, _selected_original_corner_component,
    )
    from ae_engine.sheetmetal_drawing import (
        DrawingScene, PolylinePrimitive, CirclePrimitive,
    )
    from ae_engine.sheetmetal_geometry_core import Vec2

    spec, render = _real_source(w=620., d=185., t=2., bottom=48.)
    factory, width, height, _ = _factory_original_shape(spec)
    outer = next(
        p for p in render.scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
        and p.closed and len(p.points) > 10
    )
    # Model the original native right boundary (641.9999999999999 vs 642).
    drifted = replace(
        outer, points=tuple(
            Vec2(math.nextafter(p.x, -math.inf), p.y)
            if abs(p.x - width) < 1e-8 else p for p in outer.points
        ),
    )
    scene = DrawingScene([
        drifted if p is outer else p for p in render.scene.primitives
    ])
    raw = PartRenderData(
        scene=scene, material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
    )
    raw_outline = Polygon([(p.x, p.y) for p in drifted.points])
    assert 0 < factory.symmetric_difference(raw_outline).area < 1e-6
    mother = box(0., 0., width, height)
    # This old computation wrongly bridges the upper and lower right cuts.
    with pytest.raises(GeometryError, match="FACTORY_RELIEF_SPANS_MULTIPLE_CORNERS"):
        _selected_original_corner_component(raw_outline, mother, "bottom_right")
    assert _selected_original_corner_component(
        factory, mother, "bottom_right"
    ).area > 0

    flat = project_tail_illustrated_side_v90_flat(spec, raw)
    assert flat.original_scene is scene
    assert flat.original_factory_material.equals(raw_outline)
    assert len(flat.opening_source_points_xy) == 2
    # Source holes and all horizontal BENDs are still the original objects.
    untouched = [
        p for p in scene.primitives
        if (isinstance(p, CirclePrimitive) and p.layer == "CUTTING")
        or (isinstance(p, PolylinePrimitive)
            and p.layer == "CUTTING" and p is not drifted)
        or (getattr(p, "layer", None) == "BEND"
            and hasattr(p, "p1") and p.p1.y == p.p2.y)
    ]
    assert untouched
    assert all(any(result is p for result in flat.result_scene.primitives)
               for p in untouched)


def test_true_one_mm_right_edge_cross_corner_still_rejected():
    from shapely.geometry import box
    from ae_engine.v_miter_factory_mother_check import (
        _factory_original_shape, _selected_original_corner_component,
    )

    spec, _render = _real_source(w=620., d=185., t=2., bottom=48.)
    factory, width, height, _ = _factory_original_shape(spec)
    mother = box(0., 0., width, height)
    actually_missing_one_mm = factory.intersection(
        box(0., 0., width - 1., height)
    )
    assert actually_missing_one_mm.symmetric_difference(factory).area > 1e-6
    with pytest.raises(GeometryError, match="FACTORY_RELIEF_SPANS_MULTIPLE_CORNERS"):
        _selected_original_corner_component(
            actually_missing_one_mm, mother, "bottom_right",
        )


def test_default_15_mm_lower_fold_v_rejects_real_factory_rect_hole():
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    spec, render = _real_source(w=620., d=185., t=2., bottom=15.)
    assert any(
        isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
        and p.closed and len(p.points) == 4
        and {round(v.x) for v in p.points} == {3, 7}
        and {round(v.y) for v in p.points} == {18, 22}
        for p in render.scene.primitives
    )
    with pytest.raises(
        GeometryError,
        match="V_MITER_LOWER_CUTTING_CONFLICTS_WITH_ORIGINAL_HOLE",
    ):
        project_tail_illustrated_side_v90_flat(spec, render)


def test_explicit_48_mm_lower_fold_factory_source_remains_separate_positive():
    spec, render = _real_source(w=620., d=185., t=2., bottom=48.)
    original = tuple(render.scene.primitives)
    flat = project_tail_illustrated_side_v90_flat(spec, render)
    assert flat.original_scene is render.scene
    assert tuple(render.scene.primitives) == original
    assert len(flat.opening_source_points_xy) == 2
    preview = api.project_operator_tail_lower_v_preview_render(
        spec, render, choice="v90",
    )
    assert preview.metadata["tail_lower_v_preview_only"] is True
    with pytest.raises(ValueError, match="禁止加工|尚未核准"):
        api.reject_tail_lower_v_preview_for_dxf(preview)
