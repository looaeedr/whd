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


def test_d4_true_cutting_crease_crossing_source_keyed_t_skins_are_not_inferred():
    """Measure BOTH staged same-source limits and both material skins at Ø4.

    A discontinuous offset of normals of two *different* UV points is not a
    physical crack/penetration verdict. The two true T faces must obtain a
    common source-owned crease-edge connector before a closed mesh is claimed.
    """
    from ae_engine.v_miter_tail_no_ba_sequential import (
        _stages, stations_from_real_flat,
    )
    flat = _real_factory_with_fifth_original_cutting()
    st = stations_from_real_flat(flat)
    removed = []
    roots = []
    for corner, lower, apex, upper in flat.opening_source_points_xy:
        removed.append(
            Polygon((lower, apex, upper)).union(
                Point(*apex).buffer(2., resolution=48)
            )
        )
        roots.append((corner, tuple(apex)))
    candidate = flat.original_factory_restored_mother.difference(
        unary_union(removed)
    )
    boundary = candidate.boundary
    bends = tuple(fold_guides_from_final_scene(flat.result_scene))
    assert any(g.axis == "y" and abs(g.position - 48.) < 1e-8
               and g.span_start < 17 < g.span_end for g in bends)
    assert any(g.axis == "x" and abs(g.position - 15.) < 1e-8
               and g.span_start < 46 < 50 < g.span_end for g in bends)

    max_mid = 0.
    t_offset_discontinuities = []
    # Exact circle/outer-wedge CUTTING intersections with actual BEND,
    # no invented crease or midline and no source-point aliasing.
    cases = (
        ("left", (15.,48.), "x", -math.pi/2),
        ("left", (15.,48.), "x", math.pi/2),
        ("left", (15.,48.), "y", 0.),
        ("right", (627.,48.), "x", -math.pi/2),
        ("right", (627.,48.), "x", math.pi/2),
        ("right", (627.,48.), "y", math.pi),
    )
    for side, center, owner, angle in cases:
        crossing = (
            center[0] + 2*math.cos(angle),
            center[1] + 2*math.sin(angle),
        )
        assert Point(*crossing).distance(boundary) < 2e-7, (
            side, owner, crossing, "not the actual CUTTING boundary",
        )
        for first_axis in ("x", "y"):
            for stage in (0, 1):
                readings = []
                for delta in (1e-4, 1e-5):
                    pair = []
                    for sign in (-1,1):
                        a=angle+sign*delta/2.
                        target=Point(center[0]+2*math.cos(a),
                                     center[1]+2*math.sin(a))
                        u=boundary.interpolate(boundary.project(target))
                        uv=(u.x,u.y)
                        assert u.distance(boundary) < 1e-10
                        first, second, normal_first, normal_final, _ = _stages(
                            uv,first_axis,st,
                        )
                        mid=(first,second)[stage]
                        normal=(normal_first,normal_final)[stage]
                        # WHD full-T uses the inner source face as the zero
                        # skin and actual T=2 on the outside. This is only
                        # the ONE-SIDED offset witness, never a fabricated
                        # outside connector spanning a real crease.
                        inner=mid
                        outer=tuple(mid[k]-2.*normal[k] for k in range(3))
                        pair.append((uv,inner,outer,normal))
                    mid_jump=math.dist(pair[0][1],pair[1][1])
                    outer_jump=math.dist(pair[0][2],pair[1][2])
                    max_mid=max(max_mid,mid_jump)
                    readings.append((mid_jump,outer_jump,pair))
                fine=readings[-1]
                assert fine[0] < 2e-5, (
                    side,owner,crossing,first_axis,stage,
                    "SOURCE_MIDSURFACE_TEAR",fine,
                )
                # Test whether the normal-offset approach is continuous;
                # when it is not, record actual near-crease source UVs,
                # which skin, stage and gap. Do not call it penetration.
                # A sharp finite crease makes the two unconnected
                # ONE-SIDED outer-normal limits differ by T*sqrt(2).
                # This is not a physical gap: a source-keyed T corner
                # connector is needed at that EXACT CUTTING/BEND UV.
                expected_outer_discontinuity = (
                    (owner == "x" and
                     (first_axis == "x" or stage == 1))
                    or (owner == "y" and
                        (first_axis == "y" or stage == 1))
                )
                if expected_outer_discontinuity:
                    assert abs(fine[1] - 2.*math.sqrt(2.)) < 1e-3, (
                        side, owner, crossing, first_axis, stage,
                        "ONE_SIDED_T_OUTER_NORMAL_OFFSET", fine[1],
                    )
                    t_offset_discontinuities.append((
                        side,owner,first_axis,stage,crossing,
                        fine[1],fine[2][0][0],fine[2][1][0],
                        fine[2][0][3],fine[2][1][3],
                    ))
                else:
                    assert fine[1] <= 2.00001e-5, (
                        side,owner,crossing,first_axis,stage,
                        "UNEXPECTED_OUTER_SKIN_SEAM",fine[1],
                    )
                assert fine[0] < readings[0][0] + 1e-8
    assert len(t_offset_discontinuities) == 18, (
        "ONE_SIDED_T_NORMAL_DISCONTINUITY_LOCATION_CHANGED: "
        "then verify the complete sourced hole-wall shell instead"
    )
    print("ISSUE3317_D4_T_SKIN_ONE_SIDED_CHECK", {
        "max_mid_jump_mm": max_mid,
        "uncertified_one_sided_outer_offsets": t_offset_discontinuities,
        "status": "T_CREASE_CONNECTOR_NOT_PROVEN_NO_MESH_CLAIM",
    })


@pytest.mark.parametrize("first_axis", ("x", "y"))
def test_d4_source_keyed_real_arc_full_t_shell_and_original_holes(first_axis,tmp_path):
    """The real Ø4 arc, retained straight V legs and five original holes.

    A CHECK mesh is returned ONLY after all source-edge incidence and local
    non-neighbor true-T tests pass. No apex cap, artificial BEND or BA/R.
    """
    from ae_engine.v_miter_tail_d4_check import (
        project_tail_d4_source_keyed_t_check,
        save_tail_d4_check_mesh_and_local_svg,
    )
    flat = _real_factory_with_fifth_original_cutting()
    old = tuple(flat.result_scene.primitives)
    outer = next(p for p in old if getattr(p,"semantic_id",None)=="OUTER_BOUNDARY")
    removed = tuple(
        Polygon((lower,apex,upper)).union(
            Point(*apex).buffer(2.,resolution=48),
        )
        for _,lower,apex,upper in flat.opening_source_points_xy
    )
    stock = flat.original_factory_restored_mother.difference(
        unary_union(removed)
    )
    assert stock.is_valid and stock.geom_type=="Polygon"
    updated = PolylinePrimitive(
        points=tuple(Vec2(float(x),float(y))
                     for x,y in stock.exterior.coords[:-1]),
        layer="CUTTING",closed=True,semantic_id="OUTER_BOUNDARY",
    )
    scene = DrawingScene(tuple(updated if item is outer else item for item in old))
    assert all(a is b for a,b in zip(old,scene.primitives) if a is not outer)
    check = project_tail_d4_source_keyed_t_check(
        replace(flat,result_scene=scene,result_material=stock),
        first_axis=first_axis,
    )
    assert check.manufacturing_approved is False
    assert check.source_hole_count == 5
    assert all(count > 0 for _,count in check.arc_wall_edges_by_corner)
    assert all(count > 0 for _,count in check.surviving_v_wall_edges_by_corner)
    assert not check.bad_incidence_edges and not check.bad_winding_edges
    assert len(check.shell_faces) > len(check.source_triangle_faces)*2
    assert len(check.local_interference_by_corner) == 2
    obj,svg=save_tail_d4_check_mesh_and_local_svg(
        check,replace(flat,result_scene=scene,result_material=stock),tmp_path,
    )
    assert obj.is_file() and svg.is_file()
    lines=obj.read_text(encoding="utf-8").splitlines()
    assert sum(row.startswith("v ") for row in lines) == (
        len(check.inner_xyz)+len(check.outer_xyz)
    )
    assert sum(row.startswith("f ") for row in lines) == len(check.shell_faces)
    assert "NOT CNC" in obj.read_text(encoding="utf-8")
    visual=svg.read_text(encoding="utf-8")
    assert "<svg" in visual and "bottom_left" in visual and "bottom_right" in visual
    assert "NOT CNC" in visual

    # Same UV is ONE indexed inner vertex and ONE original-owner outer
    # vertex, even at true intersecting X/Y finite-crease domains.
    # These are the six measured D4 source CUTTING/real BEND crossings,
    # NOT endpoints guessed from a radius or normal-offset gap.
    physical = (
        ((15.,46.), (15.,48.,2.), (13.,46.,2.)),
        ((15.,50.), (15.,50.,0.), (13.,50.,-2.)),
        ((17.,48.), (17.,48.,0.), (17.,46.,-2.)),
        ((627.,46.), (627.,48.,2.), (629.,46.,2.)),
        ((627.,50.), (627.,50.,0.), (629.,50.,-2.)),
        ((625.,48.), (625.,48.,0.), (625.,46.,-2.)),
    )
    for uv,inner_want,outer_want in physical:
        matches=tuple(i for i,p in enumerate(check.source_uv)
                      if math.dist(p,uv)<1e-7)
        assert len(matches)==1, ("D4_UV_SOURCE_NOT_UNIQUE",uv,matches)
        i=matches[0]
        assert check.inner_xyz[i] == pytest.approx(inner_want,abs=1e-7)
        assert check.outer_xyz[i] == pytest.approx(outer_want,abs=1e-7)


def _d4_revised_factory_source():
    flat=_real_factory_with_fifth_original_cutting()
    old=tuple(flat.result_scene.primitives)
    outer=next(p for p in old if getattr(p,"semantic_id",None)=="OUTER_BOUNDARY")
    removed=tuple(Polygon((lower,apex,upper)).union(
        Point(*apex).buffer(2.,resolution=48))
        for _,lower,apex,upper in flat.opening_source_points_xy)
    stock=flat.original_factory_restored_mother.difference(unary_union(removed))
    assert stock.geom_type=="Polygon" and stock.is_valid
    updated=PolylinePrimitive(
        points=tuple(Vec2(float(x),float(y))
                     for x,y in stock.exterior.coords[:-1]),
        layer="CUTTING",closed=True,semantic_id="OUTER_BOUNDARY",
    )
    scene=DrawingScene(tuple(updated if item is outer else item for item in old))
    return replace(flat,result_scene=scene,result_material=stock)


@pytest.mark.parametrize("kind",("delete_original","move_original_same_count"))
def test_d4_must_reject_mutated_authored_hole_source_even_if_shell_still_closes(kind):
    from ae_engine.v_miter_tail_d4_check import project_tail_d4_source_keyed_t_check
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    flat=_d4_revised_factory_source()
    old=tuple(flat.result_scene.primitives)
    feature=next(p for p in old if isinstance(p,CirclePrimitive)
                 and p.layer=="CUTTING")
    if kind=="delete_original":
        revised=tuple(p for p in old if p is not feature)
    else:
        changed=replace(feature,center=Vec2(
            float(feature.center.x)+0.5,float(feature.center.y)))
        revised=tuple(changed if p is feature else p for p in old)
    altered=replace(flat,result_scene=DrawingScene(revised))
    for order in ("x","y"):
        with pytest.raises(GeometryError,
            match=r"^TAIL_D4_CHECK_AUTHORED_CUTTING_IDENTITY_CHANGED"):
            project_tail_d4_source_keyed_t_check(altered,first_axis=order)


def test_d4_resolved_overlay_feature_requires_same_original_primitive():
    from ae_engine.v_miter_tail_d4_check import project_tail_d4_source_keyed_t_check
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    flat=_d4_revised_factory_source()
    overlay=CirclePrimitive(center=Vec2(255.,135.),radius=2.,layer="CUTTING")
    scene=DrawingScene((*flat.result_scene.primitives,overlay))
    checked=replace(flat,result_scene=scene,
                    inherited_non_v_cutting_features=(overlay,))
    # Valid independent overlay is preserved and contributes its own wall.
    result=project_tail_d4_source_keyed_t_check(checked,first_axis="x")
    assert result.source_hole_count==6
    dropped=replace(checked,
        result_scene=DrawingScene(tuple(p for p in scene.primitives
                                      if p is not overlay)))
    with pytest.raises(GeometryError,
        match=r"^TAIL_D4_CHECK_AUTHORED_CUTTING_IDENTITY_CHANGED"):
        project_tail_d4_source_keyed_t_check(dropped,first_axis="x")


def test_d4_only_true_retained_v_wall_pairs_are_exempt():
    from ae_engine.v_miter_tail_d4_check import (
        _actual_opposed_v_contact_ignores,
        _actual_interference_source_face_pair,
    )
    # Two matched but UNRELATED opposite triangles must stay in the actual
    # collision input. Only explicitly sourced lower/upper V faces can skip.
    a=((0.,0.,0.),(1.,0.,0.),(0.,1.,0.))
    b=(a[2],a[1],a[0])
    local_ids=(101,102,103,104)
    local_triangles=(a,b,a,b)
    filtered,faces=_actual_opposed_v_contact_ignores(
        local_ids,local_triangles,(),(),(),(),
        (((101,),(102,)),),
    )
    assert filtered==(101,103,104)
    assert faces==(a,a,b)
    assert _actual_interference_source_face_pair(filtered,(1,2))==(103,104)
    assert _actual_interference_source_face_pair(filtered,(0,1))==(101,103)
    with pytest.raises(GeometryError,
        match="^TAIL_D4_CHECK_INVALID_COLLISION_FACE_REFERENCE"):
        _actual_interference_source_face_pair(filtered,(1,3))


@pytest.mark.parametrize("kind", ("top_edge_same_bounds", "d4_arc_non_hinge"))
@pytest.mark.parametrize("axis", ("x", "y"))
def test_d4_rejects_unauthorized_outer_change_even_with_same_bbox_and_holes(
    kind, axis,
):
    """No outside edits or subtle non-hinge edits may borrow D4 provenance."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    from ae_engine.v_miter_tail_d4_check import (
        project_tail_d4_source_keyed_t_check,
    )
    flat=_d4_revised_factory_source()
    expected=flat.result_material
    before=tuple(flat.result_scene.primitives)
    outer=next(p for p in before if getattr(p,"semantic_id",None)=="OUTER_BOUNDARY")
    if kind=="top_edge_same_bounds":
        # CUTTING removes 0.125 mm2 at the original upper edge, while all
        # bounds, authored holes, V legs and six Ø4 hinge hits are unchanged.
        changed=expected.difference(box(320.,267.75,320.5,268.))
        assert expected.bounds==changed.bounds
        assert expected.difference(changed).area == pytest.approx(.125,abs=1e-8)
    else:
        # Remove a tiny piece near an ACTUAL polygonal Ø4 arc point,
        # away from its three BEND hinge crossings.
        apex=flat.opening_source_points_xy[0][2]
        from math import pi,cos,sin
        point=(apex[0]+2.*cos(pi/4.),apex[1]+2.*sin(pi/4.))
        # This point lies on the already removed circular opening: move
        # outward into retained stock on the opposite arc quadrant.
        from shapely.geometry import Point as ShPoint
        changed=expected.difference(ShPoint(*point).buffer(.06,resolution=16))
        assert changed.symmetric_difference(expected).area>0
    assert changed.geom_type=="Polygon" and changed.is_valid
    new_outer=PolylinePrimitive(
        points=tuple(Vec2(float(x),float(y))
                     for x,y in changed.exterior.coords[:-1]),
        layer="CUTTING",closed=True,semantic_id="OUTER_BOUNDARY",
    )
    revised=replace(flat,
        result_scene=DrawingScene(tuple(new_outer if p is outer else p
                                        for p in before)),
        result_material=changed,
    )
    with pytest.raises(GeometryError,
            match=r"^TAIL_D4_CHECK_OUTER_UNRELATED_DELTA"):
        project_tail_d4_source_keyed_t_check(revised,first_axis=axis)
