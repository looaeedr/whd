# -*- coding: utf-8 -*-
"""#3317 actual full T=2 Vault Tail, not old outer-only V midpoint sketch."""
import math
import pytest

from ae_engine.contracts import EndCapPartSpec
from ae_engine import ae_endcap as original_factory
from ae_engine.manufacturing_render_data import (
    PartRenderData, material_polygon_from_final_scene, fold_guides_from_final_scene,
)
from ae_engine.v_miter_tail_user_image_source import (
    project_tail_illustrated_side_v90_flat,
)
from ae_engine.v_miter_tail_full_t_no_ba import project_tail_v90_full_t_no_ba


def _factory():
    spec=EndCapPartSpec(
        width=500,depth=150,thickness=2,frame_width=25,height=600,
        model_name="金庫型",is_tail=True,fold_left=15,fold_right=15,
        fold_top=16,fold_bottom=48,box_fold_left=15,box_fold_right=15,
    )
    scene=original_factory._build_end_cap_scene(
        w=500,d=150,t=2,fw=25,yl1=15,yr1=15,
        ytop1=16,ybottom1=48,is_tail=True,model_name="金庫型",
    )
    return project_tail_illustrated_side_v90_flat(spec,PartRenderData(
        scene=scene,material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={"source":"DIRECT_WHD_INTRINSIC_ENDCAP_FACTORY_CHECK"},
    ))


@pytest.mark.parametrize("first_axis",("x","y"))
def test_tail_full_t_has_four_original_through_holes_upper_fold_and_outer_dimensions(first_axis):
    flat=_factory()
    original=tuple(flat.original_scene.primitives)
    result=project_tail_v90_full_t_no_ba(flat,first_axis=first_axis)
    assert tuple(flat.original_scene.primitives)==original
    assert result.manufacturing_approved is False
    assert result.source_hole_count==4
    assert min(result.source_hole_wall_segment_counts)>=4
    assert result.source_nonmanifold_edge_count==0
    assert result.shell_nonmanifold_edge_count==0
    assert result.shell_winding_error_edge_count==0
    assert result.shell_signed_volume_mm3>0
    assert result.forbidden_crossing_pair_count==0
    assert result.unexpected_coplanar_overlap_pair_count==0
    assert result.tested_nonadjacent_world_face_pairs>1000
    assert result.volume_nonpenetration_status.startswith("NUMERICAL_WORLD_TRUE_T")
    assert result.formed_outer_extents_xyz_mm==pytest.approx((496.,148.,50.))
    assert result.formed_side_outside_reach_mm==pytest.approx(17.)
    assert result.actual_upper_fold_sample_xyz==pytest.approx((261.,181.,25.))
    assert len(result.true_t_v_seam_contact)==2
    for name,lower_count,upper_count,difference,opposed in result.true_t_v_seam_contact:
        assert name in ("bottom_left","bottom_right")
        assert lower_count>0 and lower_count==upper_count
        assert difference==pytest.approx(0.)
        assert opposed
    assert len(result.source_triangles)==len(result.world_inside_skin_triangles)
    assert not math.isnan(result.shell_signed_volume_mm3)


def test_tail_full_t_refuses_outer_only_source_and_disabled_RBA():
    from dataclasses import replace
    from ae_engine.sheetmetal_geometry_core import GeometryError
    flat=_factory()
    from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
    broken=replace(flat,result_scene=DrawingScene(
        [p for p in flat.result_scene.primitives
         if p.layer!="CUTTING" or
         (isinstance(p,PolylinePrimitive) and len(p.points)>12)]
    ))
    with pytest.raises(GeometryError,match="HOLES_OR_SOURCE_MISSING"):
        project_tail_v90_full_t_no_ba(broken,first_axis="x")
