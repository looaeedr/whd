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


@pytest.mark.parametrize("axis",("x","y"))
def test_d4_check_dxf_independently_reopens_full_source_no_formal_layers(axis,tmp_path):
    """AutoCAD-readable, source-typed loops and finite BEND *datums* only."""
    import ezdxf
    from ae_engine.v_miter_tail_d4_check_dxf import save_tail_d4_check_dxf
    from ae_engine.sheetmetal_drawing import CirclePrimitive,LinePrimitive
    from shapely.geometry import Polygon as ShPolygon

    flat=_d4_revised_factory_source()
    path=tmp_path/f"vault_tail_W620_D185_T2_D4_{axis}_CHECK_NOT_CNC.dxf"
    result=save_tail_d4_check_dxf(flat,path,first_axis=axis)
    assert result==path and path.exists()
    # Independent ezdxf audit, do NOT call the adapter's own reopen checker.
    doc=ezdxf.readfile(path)
    assert not doc.audit().has_errors
    assert doc.header["$INSUNITS"]==4
    assert not {"CUTTING","BEND","MARKING"}.intersection(doc.layers.entries.keys())
    entities=tuple(doc.modelspace())
    assert all(e.dxf.layer in ("CHECK","DATUM") for e in entities)
    check_polys=tuple(e for e in entities if e.dxftype()=="LWPOLYLINE")
    original_holes=tuple(p for p in flat.result_scene.primitives
                         if p.layer=="CUTTING"
                         and getattr(p,"semantic_id",None)!="OUTER_BOUNDARY")
    assert len(check_polys)==1+sum(isinstance(p,PolylinePrimitive)
                                   for p in original_holes)
    assert all(e.closed for e in check_polys)
    assert sum(e.dxftype()=="CIRCLE" for e in entities)==sum(
        isinstance(p,CirclePrimitive) for p in original_holes)
    outer=max(check_polys,key=lambda e:ShPolygon(
        tuple((p[0],p[1]) for p in e.get_points("xy"))).area)
    assert ShPolygon(tuple(e[:2] for e in outer.get_points("xy"))).symmetric_difference(
        flat.result_material).area<1e-7
    actual_circles=tuple(e for e in entities if e.dxftype()=="CIRCLE")
    expected_circles=tuple(p for p in original_holes if isinstance(p,CirclePrimitive))
    assert len(actual_circles)==len(expected_circles)
    for old,new in zip(expected_circles,actual_circles):
        assert new.dxf.center.x==pytest.approx(old.center.x,abs=1e-7)
        assert new.dxf.center.y==pytest.approx(old.center.y,abs=1e-7)
        assert new.dxf.radius==pytest.approx(old.radius,abs=1e-7)
    reference_lines=tuple(e for e in entities if e.dxftype()=="LINE")
    native_bends=tuple(p for p in flat.result_scene.primitives
                       if isinstance(p,LinePrimitive) and p.layer=="BEND")
    assert len(reference_lines)==len(native_bends)
    assert all(e.dxf.layer=="DATUM" for e in reference_lines)
    for old,new in zip(native_bends,reference_lines):
        assert (new.dxf.start.x,new.dxf.start.y,new.dxf.end.x,new.dxf.end.y)==pytest.approx(
            (old.p1.x,old.p1.y,old.p2.x,old.p2.y),abs=1e-7)
    labels=tuple(e for e in entities if e.dxftype()=="MTEXT")
    assert len(labels)==1 and "CHECK_NOT_CNC" in labels[0].text
    assert len(flat.opening_source_points_xy)==2
    # Both D4 root arcs remain present in the TRUE exported outer contour.
    real_boundary=ShPolygon(tuple(e[:2] for e in outer.get_points("xy"))).boundary
    for _name,_lower,apex,_upper in flat.opening_source_points_xy:
        for x,y in ((apex[0],apex[1]-2),(apex[0],apex[1]+2)):
            assert real_boundary.distance(Point(x,y))<1e-7


@pytest.mark.parametrize("kind",("delete_authored_hole","alter_non_hinge_arc"))
@pytest.mark.parametrize("axis",("x","y"))
def test_d4_check_dxf_rejects_edited_source_without_writing(kind,axis,tmp_path):
    from shapely.geometry import Point as ShPoint
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    from ae_engine.v_miter_tail_d4_check_dxf import save_tail_d4_check_dxf
    flat=_d4_revised_factory_source()
    old=tuple(flat.result_scene.primitives)
    outer=next(p for p in old if getattr(p,"semantic_id",None)=="OUTER_BOUNDARY")
    if kind=="delete_authored_hole":
        hole=next(p for p in old if isinstance(p,CirclePrimitive)
                  and p.layer=="CUTTING")
        altered=replace(flat,result_scene=DrawingScene(
            tuple(p for p in old if p is not hole)))
        pattern="TAIL_D4_CHECK_AUTHORED_CUTTING_IDENTITY_CHANGED"
    else:
        apex=flat.opening_source_points_xy[0][2]
        point=(apex[0]+math.sqrt(2),apex[1]+math.sqrt(2))
        modified=flat.result_material.difference(
            ShPoint(*point).buffer(.06,resolution=16))
        assert modified.symmetric_difference(flat.result_material).area>0
        new=PolylinePrimitive(
            points=tuple(Vec2(float(x),float(y))
                         for x,y in modified.exterior.coords[:-1]),
            layer="CUTTING",closed=True,semantic_id="OUTER_BOUNDARY")
        altered=replace(flat,result_scene=DrawingScene(
            tuple(new if p is outer else p for p in old)),
            result_material=modified)
        pattern="TAIL_D4_CHECK_OUTER_UNRELATED_DELTA"
    path=tmp_path/f"bad_{axis}_{kind}_CHECK_NOT_CNC.dxf"
    with pytest.raises(GeometryError,match=pattern):
        save_tail_d4_check_dxf(altered,path,first_axis=axis)
    assert not path.exists()
    assert not tuple(tmp_path.glob(".tail_d4_check_*.dxf"))


@pytest.mark.parametrize("first_axis", ("x", "y"))
def test_r2_retained_interior_stock_across_y48_has_unresolved_rigid_domain_jump(
    first_axis,
):
    """R2: real stock at Y48±eps has incompatible rigid final positions.

    Not an arc-point probe: sample strictly INSIDE the SAME connected mother
    at x=15-a / x=627+a for a=.1,.25,.5,.75. The finite lower BEND
    starts/ends at x16..626, hence none of this strip owns a real Y crease.
    This is a failure of the existing two-domain SHARP map, NOT proof that a
    physical formed R2 transition is impossible. No invented R/BA or BEND.
    """
    from ae_engine.v_miter_tail_no_ba_sequential import (
        _stages, stations_from_real_flat,
    )

    sharp = _real_factory_with_fifth_original_cutting()
    st = stations_from_real_flat(sharp)
    assert st.bottom_y == pytest.approx(48.)
    assert st.bottom_guide_start == pytest.approx(16.)
    assert st.bottom_guide_end == pytest.approx(626.)
    assert st.left_x == pytest.approx(15.)
    assert st.right_x == pytest.approx(627.)

    removed = []
    for corner, lower, apex, upper in sharp.opening_source_points_xy:
        rounded, cutback = _rounded_v_notch_polygon(
            Vec2(*apex), Vec2(*lower), Vec2(*upper),
            (lower, upper), 2.,
        )
        assert cutback == pytest.approx(2.)
        removed.append(rounded)
    stock=sharp.original_factory_restored_mother.difference(
        unary_union(removed)
    )
    assert stock.geom_type == "Polygon" and stock.is_valid
    assert not stock.is_empty
    assert len(stock.interiors) == 0

    # R2 arc crosses Y48 outside the ORIGINAL finite bottom bend.
    crossing_left=15.-(2.*math.sqrt(2.)-2.)  # 14.171572875...
    crossing_right=627.+(2.*math.sqrt(2.)-2.)
    assert crossing_left == pytest.approx(14.17157287525381)
    assert crossing_right == pytest.approx(627.8284271247462)
    for left in (True,False):
        for a in (.1,.25,.5,.75):
            x=15.-a if left else 627.+a
            assert (x<st.bottom_guide_start if left
                    else x>st.bottom_guide_end)
            gaps=[]
            for eps in (1e-4,1e-5):
                before=Point(x,48.-eps)
                after=Point(x,48.+eps)
                assert before.within(stock) and after.within(stock), (
                    "R2_REAL_RETAINED_STOCK_REQUIRED", first_axis,left,a,eps,
                )
                folded_minus=_stages((x,48.-eps),first_axis,st)
                folded_plus=_stages((x,48.+eps),first_axis,st)
                first_jump=math.dist(folded_minus[0],folded_plus[0])
                final_jump=math.dist(folded_minus[1],folded_plus[1])
                assert first_jump<=5.*eps, (
                    "R2_FIRST_STAGE_INCORRECTLY_DISCONNECTED",
                    first_axis,left,a,eps,first_jump,
                )
                # Source-connected material cannot have TWO distinct
                # final positions. Existing sharp rigid-domain mapping
                # converges to sqrt(2)*a, not zero, in BOTH orders.
                assert abs(final_jump-math.sqrt(2.)*a)<=5.*eps, (
                    "R2_FINITE_BEND_RIGID_DOMAIN_CONFLICT_CHANGED",
                    first_axis,left,a,eps,final_jump,
                )
                gaps.append(final_jump)
            assert gaps[1] > .1, (
                "R2_INCORRECTLY_ACCEPTED_AS_CONTINUOUS",first_axis,left,a,gaps,
            )
            assert abs(gaps[1]-math.sqrt(2.)*a) < abs(
                gaps[0]-math.sqrt(2.)*a
            ), ("R2_LIMIT_NOT_CONVERGING",first_axis,left,a,gaps)

    # No current exact finite-BEND, zero-new-crease, no-BA/R continuous
    # material transition has been proven for this R2 strip.
    # This check is a NEGATIVE witness only; do not weld/assign/remove stock.
    assert first_axis in ("x","y")


@pytest.mark.parametrize("axis",("x","y"))
def test_d4_delivery_real_factory_without_fixture_writes_ascii_mm_dxf(
    tmp_path,axis,
):
    """Fixture's USER_ADDED_CHECK_CUTTING is never a source for delivery."""
    import ezdxf
    from ae_engine.ae_endcap import _build_end_cap_scene
    from ae_engine.v_miter_tail_d4_delivery import (
        default_vault_tail_d4_spec,build_tail_d4_check_from_original,
        deliver_tail_d4_check_only,
    )
    from ae_engine.sheetmetal_drawing import CirclePrimitive

    spec=default_vault_tail_d4_spec()
    original=_build_end_cap_scene(
        w=620,d=185,t=2,fw=25,yl1=15,yr1=15,
        ytop1=16,ybottom1=48,is_tail=True,model_name="金庫型",
    )
    from ae_engine.v_miter_factory_mother_check import _factory_original_shape
    factory,_,_,_=_factory_original_shape(spec)
    # The original Factory structural outer is NOT tagged OUTER_BOUNDARY.
    # Classify by exact Factory source geometry, not by insertion order,
    # bounding boxes, size or fake-hole coordinates.
    factory_outers=tuple(p for p in original.primitives
        if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING"
        and p.closed and Polygon([(q.x,q.y) for q in p.points])
            .symmetric_difference(factory).area<=1e-7)
    assert len(factory_outers)==1
    authored=tuple(p for p in original.primitives
                   if p.layer=="CUTTING" and p is not factory_outers[0])
    assert authored
    assert all(getattr(p,"semantic_id",None)!="USER_ADDED_CHECK_CUTTING"
               for p in authored)
    flat,meshes=build_tail_d4_check_from_original(spec)
    actual=tuple(p for p in flat.result_scene.primitives
                 if p.layer=="CUTTING"
                 and getattr(p,"semantic_id",None)!="OUTER_BOUNDARY")
    assert len(actual)==len(authored)
    assert all(getattr(p,"semantic_id",None)!="USER_ADDED_CHECK_CUTTING"
               for p in actual)
    assert len(meshes["x"].shell_faces)==len(meshes["y"].shell_faces)
    from ae_engine.v_miter_tail_d4_check_dxf import save_tail_d4_check_dxf
    path=tmp_path/f"factory_d4_{axis}_CHECK_NOT_CNC.dxf"
    save_tail_d4_check_dxf(flat,path,first_axis=axis)
    with path.open("rb") as fd:
        header=fd.read(130)
    assert b"SECTION" in header
    assert not header.startswith(b"AutoCAD Binary DXF")
    text=path.read_text(encoding="utf-8")
    assert "AC1015" in text
    doc=ezdxf.readfile(path)
    assert doc.header["$INSUNITS"]==4
    assert not doc.audit().has_errors
    entities=tuple(doc.modelspace())
    assert len(tuple(e for e in entities if e.dxftype()=="CIRCLE"))==sum(
        isinstance(p,CirclePrimitive) for p in authored)
    assert len(tuple(e for e in entities if e.dxftype()=="LWPOLYLINE"))==(
        1+sum(isinstance(p,PolylinePrimitive) for p in authored)
    )
    assert not {"CUTTING","BEND","MARKING"}.intersection(doc.layers.entries)
    assert all(e.dxf.layer in ("CHECK","DATUM") for e in entities)
    assert all("USER_ADDED_CHECK_CUTTING" not in e.dxf.layer
               for e in entities)


def test_d4_delivery_fixture_hole_remains_only_negative_guard():
    """Protect genuine authored holes; don't blacklist location (200,115)."""
    from ae_engine.v_miter_tail_d4_delivery import (
        default_vault_tail_d4_spec,build_tail_d4_check_from_original,
    )
    from ae_engine.ae_endcap import _build_end_cap_scene
    from ae_engine.manufacturing_render_data import PartRenderData
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    from ae_engine.manufacturing_render_data import (
        material_polygon_from_final_scene,fold_guides_from_final_scene,
    )
    spec=default_vault_tail_d4_spec()
    original=_build_end_cap_scene(
        w=620,d=185,t=2,fw=25,yl1=15,yr1=15,ytop1=16,
        ybottom1=48,is_tail=True,model_name="金庫型",
    )
    # A real project may legitimately have a circle near the old test
    # fixture location: it MUST be preserved by primitive identity.
    legitimate=CirclePrimitive(center=Vec2(204.,120.),
                               radius=1.5,layer="CUTTING",
                               source_type="USER_ADDED",source_id="real-job-1")
    scene=DrawingScene((*original.primitives,legitimate))
    render=PartRenderData(
        scene=scene,material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
    )
    flat,_=build_tail_d4_check_from_original(
        spec,original_render_data=render)
    assert any(p is legitimate for p in flat.result_scene.primitives)


def test_d4_one_time_real_factory_dxf_and_svg_capture_for_issue3317(
    record_property,tmp_path,
):
    """One-time real Factory CHECK payload in standard shard JUnit artifact.

    NO test fixture, no new general CI step and no manufacturing export.
    This temporary extraction witness is removed after independent delivery.
    """
    import base64
    from io import BytesIO
    from zipfile import ZipFile, ZIP_DEFLATED
    from ae_engine.v_miter_tail_d4_delivery import deliver_tail_d4_check_only
    from ae_engine.v_miter_tail_d4_check import (
        save_tail_d4_check_mesh_and_local_svg,
    )
    files,flat,checks=deliver_tail_d4_check_only(tmp_path)
    all_paths=list(files)
    for axis in ("x","y"):
        _obj,svg=save_tail_d4_check_mesh_and_local_svg(
            checks[axis],flat,tmp_path,
        )
        all_paths.append(svg)
    payload=BytesIO()
    with ZipFile(payload,"w",compression=ZIP_DEFLATED,compresslevel=9) as z:
        for p in all_paths:
            z.write(p,arcname=p.name)
    # record_property is part of pytest's EXISTING JUnit output;
    # no project CI workflow or test fixture is used to build the files.
    record_property("ISSUE3317_FACTORY_NO_FIXTURE_CHECK_ZIP_B64",
                    base64.b64encode(payload.getvalue()).decode("ascii"))
    assert len(tuple(p for p in flat.result_scene.primitives
                     if p.layer=="CUTTING"))==5  # outer + FOUR real features
