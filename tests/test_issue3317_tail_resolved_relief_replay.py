# -*- coding: utf-8 -*-
"""#3317 real independent Tail relief, one source 2D + full T3D, no release."""
from dataclasses import replace
import math

import pytest
from shapely.geometry import Polygon, box

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive, LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.manufacturing_render_data import (
    PartRenderData,material_polygon_from_final_scene,fold_guides_from_final_scene,
)
from ae_engine.operator_tail_lower_v import project_operator_tail_lower_v_preview_render
from tests.test_issue3317_tail_gui_lower_v import _real_source


def _with_real_independent_tail_cut(render, rect):
    primitives=list(render.scene.primitives)
    outer=max(
        (p for p in primitives if isinstance(p,PolylinePrimitive)
         and p.closed and p.layer=="CUTTING"),
        key=lambda p:Polygon([(v.x,v.y) for v in p.points]).area,
    )
    old=Polygon([(v.x,v.y) for v in outer.points])
    changed=old.difference(box(*rect))
    assert changed.geom_type=="Polygon" and changed.is_valid
    new_outer=PolylinePrimitive(
        tuple(Vec2(float(x),float(y)) for x,y in changed.exterior.coords[:-1]),
        "CUTTING",True,outer.color,outer.semantic_id,
    )
    scene=DrawingScene([
        new_outer if p is outer else p for p in primitives
    ])
    return PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={"USER_ADDED":"joint_relief_for_integration_test"},
    )


def test_non_sample_independent_upper_side_relief_survives_same_2d_t3d_and_reload(tmp_path):
    # W/D changed. Side notch outside left fold and away from V legs and BEND.
    spec,raw=_real_source(w=620.,d=185.,t=2.)
    solved=_with_real_independent_tail_cut(raw,(-1.,112.,6.,122.))
    from ae_engine.v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
    )
    legacy=project_tail_illustrated_side_v90_flat(spec,raw)
    legacy_stock=material_polygon_from_final_scene(legacy.result_scene)
    preview=project_operator_tail_lower_v_preview_render(
        spec,raw,choice="v90",resolved_render_data=solved,
    )
    assert preview.material.area<legacy_stock.area
    assert preview.material.symmetric_difference(
        legacy_stock.difference(raw.material.difference(solved.material))
    ).area<1e-5
    assert preview.metadata["USER_ADDED"]=="joint_relief_for_integration_test"
    assert preview.metadata["tail_lower_v_independent_relief_replayed"]
    assert material_polygon_from_final_scene(preview.scene).symmetric_difference(
        preview.material
    ).area<1e-6
    mesh=api.project_independent_part_view_mesh(
        "tail",preview,x_profile=(),y_profile=(),thickness=spec.thickness,
    )
    assert mesh.triangles==api.tail_lower_v_preview_mesh(preview)
    assert len(mesh.triangles)>500
    from ae_engine.operator_tail_lower_v import (
        TAIL_LOWER_V_SNAPSHOT_KEY,commit_operator_tail_lower_v_choice,
    )
    import phase6_project_file as file
    source={"model":"金庫型","w":620.,"d":185.,"t":2.,"fw":25.,
            "yl1":15.,"yr1":15.,"ytop1":16.,"ybottom1":48.}
    selected=commit_operator_tail_lower_v_choice(source,"v90",tail_scene_values=source)
    saved=file.write_project(tmp_path/"selected.p6fold",{"schema":file.PROJECT_SCHEMA,"snapshot":selected})
    reloaded=file.read_project(saved)["snapshot"]
    assert reloaded[TAIL_LOWER_V_SNAPSHOT_KEY]=="v90"
    again=project_operator_tail_lower_v_preview_render(
        spec,raw,choice=reloaded[TAIL_LOWER_V_SNAPSHOT_KEY],resolved_render_data=solved,
    )
    assert again.material.symmetric_difference(preview.material).area<1e-6
    assert again.metadata["USER_ADDED"]=="joint_relief_for_integration_test"
    restored=commit_operator_tail_lower_v_choice(reloaded,"original",tail_scene_values=reloaded)
    assert TAIL_LOWER_V_SNAPSHOT_KEY not in restored
    assert raw.material.symmetric_difference(solved.material).area>0
    assert api.tail_lower_v_preview_mesh(solved) is None
    with pytest.raises(ValueError,match="DXF"):
        api.reject_tail_lower_v_preview_for_dxf(preview)


def test_real_other_relief_that_hits_v_must_fail_without_clipping_source():
    spec,raw=_real_source(w=620.,d=185.,t=2.)
    solved=_with_real_independent_tail_cut(raw,(-1.,54.,9.,65.))
    with pytest.raises(Exception,match="CONFLICTS_WITH_LOWER_V|RELIEF_TOUCHES_FINITE_BEND"):
        project_operator_tail_lower_v_preview_render(
            spec,raw,choice="v90",resolved_render_data=solved,
        )