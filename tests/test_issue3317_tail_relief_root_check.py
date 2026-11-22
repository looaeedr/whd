# -*- coding: utf-8 -*-
"""#3317 Issue A: real Factory Tail relief-bottom source CHECK, never CNC.

Retain original CUTTING entities / finite BEND / MARKING by identity.  The
current full-T sharp witness must reject a retained ROUND_R2 or Ø4 slot root;
coincident cropped straight walls do not establish its root T boundary.
"""
from dataclasses import replace
import math

import pytest
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from ae_engine import ae_endcap
from ae_engine.contracts import EndCapPartSpec
from ae_engine.manufacturing_render_data import (
    PartRenderData, fold_guides_from_final_scene,
    material_polygon_from_final_scene,
)
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from ae_engine.v_miter_relief_trial import _rounded_v_notch_polygon
from ae_engine.v_miter_tail_user_image_source import (
    project_tail_illustrated_side_v90_flat,
)
from ae_engine.v_miter_tail_sharp_no_ba_witness import (
    project_tail_sharp_no_ba_v_witness,
)
from ae_engine.v_miter_tail_full_t_no_ba import project_tail_v90_full_t_no_ba


def _real_factory_with_fifth_original_cutting():
    spec = EndCapPartSpec(
        width=620, depth=185, thickness=2, frame_width=25, height=600,
        model_name="金庫型", is_tail=True, fold_left=15, fold_right=15,
        fold_top=16, fold_bottom=48, box_fold_left=15, box_fold_right=15,
    )
    scene = ae_endcap._build_end_cap_scene(
        w=620, d=185, t=2, fw=25, yl1=15, yr1=15,
        ytop1=16, ybottom1=48, is_tail=True, model_name="金庫型",
    )
    # Independent operator feature, deliberately away from both lower V roots.
    added = PolylinePrimitive(
        points=tuple(Vec2(*xy) for xy in (
            (200., 115.), (208., 115.), (208., 125.), (200., 125.),
        )),
        layer="CUTTING", closed=True, semantic_id="USER_ADDED_CHECK_CUTTING",
    )
    scene = DrawingScene((*scene.primitives, added))
    render = PartRenderData(
        scene=scene, material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={"source": "DIRECT_WHD_INTRINSIC_ENDCAP_FACTORY_CHECK"},
    )
    return project_tail_illustrated_side_v90_flat(spec, render)


@pytest.mark.parametrize("mode", ("ROUND_R2", "RELIEF_HOLE_D4"))
def test_vault_w620_d185_t2_relief_root_preserves_source_but_sharp_full_t_refuses(mode):
    sharp = _real_factory_with_fifth_original_cutting()
    old_items = tuple(sharp.result_scene.primitives)
    original_cutting = tuple(p for p in old_items if p.layer == "CUTTING")
    assert len(original_cutting) == 6  # 1 outer and 5 separate original features
    outer = next(p for p in original_cutting
                 if getattr(p, "semantic_id", "") == "OUTER_BOUNDARY")
    original_features = tuple(p for p in original_cutting if p is not outer)
    assert len(original_features) == 5

    removed = []
    straight_lengths = []
    for corner, lower, apex, upper in sharp.opening_source_points_xy:
        wedge = Polygon((lower, apex, upper))
        if mode == "ROUND_R2":
            rounded, cutback = _rounded_v_notch_polygon(
                Vec2(*apex), Vec2(*lower), Vec2(*upper), (lower, upper), 2.,
            )
            assert rounded.difference(wedge.buffer(1e-7)).area < 1e-6
            replacement = rounded
        else:
            cutback = 2.
            replacement = wedge.union(Point(*apex).buffer(2., resolution=48))
        removed.append(replacement)
        straight_lengths.append(math.dist(apex, lower) - cutback)
    assert straight_lengths == pytest.approx((19.213203435596427,)*2)

    candidate = sharp.original_factory_restored_mother.difference(
        unary_union(removed)
    )
    assert candidate.geom_type == "Polygon" and candidate.is_valid
    assert len(candidate.interiors) == 0
    new_outer = PolylinePrimitive(
        points=tuple(Vec2(float(x), float(y))
                     for x, y in candidate.exterior.coords[:-1]),
        layer="CUTTING", closed=True, semantic_id="OUTER_BOUNDARY",
    )
    revised_scene = DrawingScene(tuple(
        new_outer if p is outer else p for p in old_items
    ))
    revised = replace(
        sharp, result_scene=revised_scene, result_material=candidate,
    )
    assert len(revised_scene.primitives) == len(old_items)
    assert all(new is old for old, new in zip(old_items, revised_scene.primitives)
               if old is not outer)
    assert all(any(p is q for q in revised_scene.primitives)
               for p in original_features)
    assert tuple(p for p in revised_scene.primitives if p.layer == "BEND") == (
        tuple(p for p in old_items if p.layer == "BEND")
    )
    assert tuple(p for p in revised_scene.primitives if p.layer == "MARKING") == (
        tuple(p for p in old_items if p.layer == "MARKING")
    )
    physical = material_polygon_from_final_scene(revised_scene)
    assert physical.geom_type == "Polygon" and len(physical.interiors) == 5

    # A *source-keyed sharp* T2 shell cannot be relabelled as a relieved one.
    # It requires the complete apex->tip edges to remain CUTTING boundaries.
    with pytest.raises(GeometryError,
                       match="^TAIL_SHARP_NO_BA_V_NOT_ACTUAL_CUTTING$"):
        project_tail_sharp_no_ba_v_witness(revised)
    for first_axis in ("x", "y"):
        with pytest.raises(GeometryError,
                           match="^TAIL_SHARP_NO_BA_V_NOT_ACTUAL_CUTTING$"):
            project_tail_v90_full_t_no_ba(revised, first_axis=first_axis)
