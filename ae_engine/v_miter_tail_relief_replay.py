# -*- coding: utf-8 -*-
"""#3317 replay actual independent resolved relief onto the SAME lower-V sheet.

Only 2D CUTTING differences from the already resolved native manufacturing
result are replayed. V corners, source fold stations, original hole entities
and all authored upper geometry remain owned by their original Engine paths.
No tolerance, R or BA is invented, and no GUI Boolean/geometry is added.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace

from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

from .manufacturing_render_data import material_polygon_from_final_scene
from .sheetmetal_drawing import DrawingScene, PolylinePrimitive, LinePrimitive, CirclePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2


def _stock(render, role):
    if render is None or getattr(render,"scene",None) is None:
        raise GeometryError("V_MITER_REPLAY_MISSING_"+role+"_FINAL_SCENE")
    material=material_polygon_from_final_scene(render.scene)
    stated=getattr(render,"material",None)
    if (material.geom_type!="Polygon" or not material.is_valid
            or material.is_empty or stated is None
            or material.symmetric_difference(stated).area>1e-5):
        raise GeometryError("V_MITER_REPLAY_"+role+"_SCENE_MATERIAL_MISMATCH")
    return material


def _outer(scene, material, *, role):
    from shapely.geometry import Polygon
    matches=[]
    for primitive in scene.primitives:
        if not (isinstance(primitive,PolylinePrimitive)
                and primitive.layer=="CUTTING" and primitive.closed):
            continue
        poly=Polygon([(v.x,v.y) for v in primitive.points])
        # Cutting features are holes, not a substitute mother/outer.
        if poly.is_valid and poly.covers(material) and poly.area>material.area:
            matches.append((primitive,poly))
        elif poly.is_valid and poly.equals(material):
            matches.append((primitive,poly))
    if len(matches)!=1:
        # On open edge-notch sheets, outer must still cover the remaining
        # material. Never guess which of several closed loops owns it.
        raise GeometryError("V_MITER_REPLAY_"+role+"_OUTER_CUTTING_AMBIGUOUS")
    return matches[0][0]


def _cutting_except(scene, outer):
    return tuple(p for p in scene.primitives
                 if getattr(p,"layer",None)=="CUTTING" and p is not outer)


def _extra_features(original, solved, *, structural_outer, solved_outer):
    """Feature differences are only additive; original holes/marks can't vanish."""
    from collections import Counter
    orig_cut=_cutting_except(original.scene,structural_outer)
    resolved_cut=list(_cutting_except(solved.scene,solved_outer))
    for primitive in orig_cut:
        try:
            resolved_cut.remove(primitive)
        except ValueError as exc:
            raise GeometryError("V_MITER_REPLAY_ORIGINAL_CUTTING_FEATURE_REMOVED") from exc
    additions=[]
    for primitive in resolved_cut:
        if not (isinstance(primitive,(CirclePrimitive,PolylinePrimitive))
                and (not isinstance(primitive,PolylinePrimitive) or primitive.closed)):
            raise GeometryError("V_MITER_REPLAY_UNSUPPORTED_ADDED_CUTTING_LINE")
        additions.append(primitive)
    for layer in ("BEND",):
        source=[p for p in original.scene.primitives if getattr(p,"layer",None)==layer]
        changed=[p for p in solved.scene.primitives if getattr(p,"layer",None)==layer]
        if Counter(source)!=Counter(changed):
            raise GeometryError("V_MITER_REPLAY_FINITE_BEND_CHANGED")
    prior=[p for p in original.scene.primitives
           if getattr(p,"layer",None) not in ("CUTTING","BEND")]
    current=[p for p in solved.scene.primitives
             if getattr(p,"layer",None) not in ("CUTTING","BEND")]
    for primitive in prior:
        try:
            current.remove(primitive)
        except ValueError as exc:
            raise GeometryError("V_MITER_REPLAY_ORIGINAL_MARKING_REMOVED") from exc
    return tuple(additions),tuple(current)


def replay_independent_lower_v_relief(flat, *, original_render, resolved_render):
    """Return a new flat with independently resolved CUTTING restored or reject.

    This is Engine geometry provenance, not an approximate GUI overlay.
    Geometry changed by the real relief solver is compared against the
    raw sheet; no unrelated cut, hole, or marking may disappear silently.
    """
    raw=_stock(original_render,"SOURCE")
    resolved=_stock(resolved_render,"RESOLVED")
    if raw.symmetric_difference(resolved).area<=1e-7:
        # Material could be the same while new marking operations exist.
        additions=None
    else:
        additions=True
    original_outer=_outer(original_render.scene,raw,role="SOURCE")
    solved_outer=_outer(resolved_render.scene,resolved,role="RESOLVED")
    extra_cutting,extra_marks=_extra_features(
        original_render,resolved_render,
        structural_outer=original_outer,solved_outer=solved_outer,
    )
    if not additions and not extra_cutting and not extra_marks:
        return flat,()

    v_stock=material_polygon_from_final_scene(flat.result_scene)
    removed=raw.difference(resolved)
    added=resolved.difference(raw)
    v_difference=raw.symmetric_difference(v_stock)
    change=removed.union(added)
    if (not change.is_empty and
            change.buffer(1e-7).intersection(v_difference).area>1e-7):
        raise GeometryError("V_MITER_REPLAY_CONFLICTS_WITH_LOWER_V_CUTTING")
    # A new independent cut may not break the physical finite fold guides.
    # The 1e-7 tube is a numeric containment check, not a bend allowance.
    for guide in flat.result_scene.primitives:
        if not isinstance(guide,LinePrimitive) or guide.layer!="BEND":
            continue
        segment=LineString((
            (guide.p1.x,guide.p1.y),(guide.p2.x,guide.p2.y)
        ))
        if not change.is_empty and change.intersects(segment):
            raise GeometryError("V_MITER_REPLAY_RELIEF_TOUCHES_FINITE_BEND")
    combined=v_stock.difference(removed).union(added)
    if (combined.geom_type!="Polygon" or not combined.is_valid
            or combined.is_empty or not v_stock.bounds==combined.bounds):
        raise GeometryError("V_MITER_REPLAY_REQUIRES_ONE_VALID_SOURCE_SHEET")
    # Keep every unchanged source primitive (especially exact circles)
    # and every independent later CUTTING; only the V outer is redrawn
    # from the Boolean composition, exactly once, for both 2D and T solid.
    source_v_outer=_outer(flat.result_scene,v_stock,role="V")
    new_outer=PolylinePrimitive(
        points=tuple(Vec2(float(x),float(y))
                     for x,y in combined.exterior.coords[:-1]),
        layer="CUTTING",closed=True,semantic_id="OUTER_BOUNDARY",
    )
    primitives=[
        new_outer if p is source_v_outer else p
        for p in flat.result_scene.primitives
    ]+list(extra_cutting)+list(extra_marks)
    new_scene=DrawingScene(primitives)
    actual=material_polygon_from_final_scene(new_scene)
    if (actual.geom_type!="Polygon" or not actual.is_valid or
            actual.symmetric_difference(combined).area>1e-5):
        raise GeometryError("V_MITER_REPLAY_2D_CUTTING_NOT_RECONSTRUCTABLE")
    from .v_miter_tail_user_image_source import TailIllustratedSideV90Flat
    if not isinstance(flat,TailIllustratedSideV90Flat):
        raise GeometryError("V_MITER_REPLAY_ORIGINAL_V_SOURCE_REQUIRED")
    updated=replace(
        flat,result_scene=new_scene,
        result_material=Polygon(combined.exterior),
        inherited_non_v_cutting_features=tuple(extra_cutting),
    )
    # Physical CUTTING removed by a verified EndCap/USER_ADDED solution
    # is itself a replayed source difference. Do not report zero replayed
    # relief merely because the cut was an exterior notch rather than an
    # additional CUTTING hole or MARKING primitive.
    physical_differences=tuple(
        item for item in (removed,added)
        if not item.is_empty and item.area>1e-7
    )
    return updated,physical_differences+tuple(extra_cutting)+tuple(extra_marks)
