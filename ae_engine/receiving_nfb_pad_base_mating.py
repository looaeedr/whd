# -*- coding: utf-8 -*-
"""Map common PAD locator squares to the selected NFB's actual base datum.

No product-specific values. Selected CSV/PadPattern owns each dimension;
NfbPanelDatum owns the true panel UV transformation.
"""
from __future__ import annotations

from .receiving_nfb_pad_generator import PadPattern
from .receiving_nfb_numeric_panel_projection import NfbPanelDatum


def project_pad_base_squares(datum: NfbPanelDatum, pattern: PadPattern):
    if not isinstance(datum, NfbPanelDatum) or datum.role != "base-plate":
        raise ValueError("PAD 方孔需要實際底板 NFB 中心")
    datum.validate()
    if not isinstance(pattern, PadPattern) or pattern.manufacturing_ready:
        raise ValueError("PAD 定位方孔必須源自共用加工規則")
    return tuple(
        tuple(datum.map_xy(vertex) for vertex in square)
        for square in pattern.base_square_holes_xy_mm
    )



def verify_real_pad_base_square_cuts(
    render_data, pattern: PadPattern, *, owner_hole_id: str,
    rotation_deg: int,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Verify real Base locator squares using the original committed CSV datum.

    A raised NFB's four mounting screw circles are present in the separate
    PAD sheet, not in this Base. The source-projected Base centre/rotation is
    retained by the physical trial and every corresponding square is then
    checked against actual CUTTING and the material subtraction.
    """
    from math import isfinite
    from shapely.geometry import Polygon
    from .receiving_nfb_v5_configured_inner_door import AXES
    from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
    from .manufacturing_render_data import PartRenderData

    if not isinstance(render_data, PartRenderData) or not isinstance(pattern, PadPattern):
        raise TypeError("PAD_BASE_ACTUAL_FINALSCENE_REQUIRED")
    if type(rotation_deg) is not int or rotation_deg not in AXES:
        raise ValueError("PAD_BASE_SELECTED_ROTATION_MISSING")
    # Never accept a duplicate raised NFB screw CUTTING circle on the Base.
    old_base_screws=tuple(p for p in render_data.scene.primitives
        if isinstance(p, CirclePrimitive) and p.layer=="CUTTING"
        and p.source_id is not None
        and p.source_id.startswith(str(owner_hole_id)+":screw:"))
    if old_base_screws:
        raise ValueError("PAD_BASE_RAISED_NFB_SCREWS_MUST_BE_ON_PAD")
    source=render_data.metadata or {}
    owners=tuple(source.get("nfb_v5_pad_datum_centres_uv") or ())
    found=tuple(row for row in owners
        if isinstance(row,(tuple,list)) and len(row)==3
        and row[0]==owner_hole_id)
    if len(found)!=1:
        raise ValueError("PAD_BASE_SELECTED_CSV_DATUM_MISSING")
    _, raw_centre, stored_rotation=found[0]
    if (stored_rotation!=rotation_deg or type(stored_rotation) is not int
            or not isinstance(raw_centre,(tuple,list)) or len(raw_centre)!=2
            or any(type(v) not in (int,float) or not isfinite(float(v))
                   for v in raw_centre)):
        raise ValueError("PAD_BASE_SELECTED_CSV_DATUM_DRIFT")
    origin=tuple(float(v) for v in raw_centre)
    ux,uy=AXES[rotation_deg]
    def rotate(xy):
        x,y=map(float,xy)
        return (x*ux[0]+y*uy[0],x*ux[1]+y*uy[1])
    tol=1e-5
    expected=tuple(tuple(
        (origin[0]+rotate(vertex)[0],origin[1]+rotate(vertex)[1])
        for vertex in square
    ) for square in pattern.base_square_holes_xy_mm)
    if len(expected)!=4:
        raise ValueError("PAD_BASE_EXPECTED_FOUR_SQUARES_MISSING")
    real=tuple(Polygon(tuple((float(p.x),float(p.y))
                       for p in primitive.points))
        for primitive in render_data.scene.primitives
        if isinstance(primitive,PolylinePrimitive)
        and primitive.closed and primitive.layer=="CUTTING"
        and primitive.color==30 and len(primitive.points)==4)
    material=render_data.material
    if material is None or material.is_empty:
        raise ValueError("PAD_BASE_REAL_MATERIAL_MISSING")
    matched=set()
    for square in expected:
        geometry=Polygon(square)
        candidates=[idx for idx,physical in enumerate(real)
            if (idx not in matched and physical.is_valid
                and geometry.symmetric_difference(physical).area<tol)]
        if len(candidates)!=1:
            raise ValueError("PAD_BASE_FOUR_LOCATOR_SQUARES_NOT_REAL_CUTTING")
        matched.add(candidates[0])
        if material.intersection(geometry).area>tol:
            raise ValueError("PAD_BASE_LOCATOR_SQUARES_NOT_REMOVED_FROM_MATERIAL")
    return expected



def verify_real_pad_mesh_tab_engagement(
    triangles, pattern: PadPattern, actual_square_uv,
    *, world_x_mm: float, world_y_mm: float,
    base_front_world_z_mm: float, rotation_deg: int,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Verify actual folded mesh tip vertices in the four genuinely cut holes.

    The square positions are returned by verify_real_pad_base_square_cuts(),
    NOT manufactured from nominal metadata. This is a preview fit guard, not
    approval of full-mesh volume collision or manufacturing.
    """
    from math import isclose, isfinite
    from shapely.geometry import Point, Polygon
    from .receiving_nfb_v5_configured_inner_door import AXES
    from .assembly_geometry_primitives import triangle_bounds

    if not isinstance(pattern, PadPattern) or pattern.manufacturing_ready:
        raise ValueError("PAD_MESH_MATING_PATTERN_UNVERIFIED")
    if type(rotation_deg) is not int or rotation_deg not in AXES:
        raise ValueError("PAD_MESH_MATING_ROTATION_INVALID")
    if len(tuple(actual_square_uv or ())) != 4:
        raise ValueError("PAD_MESH_MATING_FOUR_REAL_SQUARES_REQUIRED")
    bounds = triangle_bounds(triangles)
    if bounds is None:
        raise ValueError("PAD_MESH_MATING_PHYSICAL_TRIANGLES_EMPTY")
    bottom, top = map(float, bounds[2])
    t = float(pattern.plate_thickness_mm)
    base = float(base_front_world_z_mm)
    if (not all(isfinite(v) for v in (bottom, top, t, base, world_x_mm, world_y_mm))
            or t <= 0
            # PAD-specific formed mid-surface projects both physical legs
            # T/2 farther than their material lengths. True sheet end is
            # now flush with the base BACK skin at base-T; the web stays
            # anchored to the selected NFB front skin, without moving it.
            or not isclose(bottom, base-t, rel_tol=0, abs_tol=1e-4)
            or not isclose(top, base+pattern.rise_mm, rel_tol=0, abs_tol=1e-4)):
        raise ValueError("PAD_MESH_MATING_REAL_PHYSICAL_Z_DRIFT")

    ux, uy = AXES[rotation_deg]
    def rotate(point):
        x, y = map(float, point)
        return (x*ux[0]+y*uy[0], x*ux[1]+y*uy[1])
    expected = tuple(pattern.base_square_holes_xy_mm)
    measured = tuple(tuple(tuple(map(float, v)) for v in square)
                     for square in actual_square_uv)
    first = rotate(expected[0][0])
    datum = (measured[0][0][0]-first[0], measured[0][0][1]-first[1])
    squares_world = []
    for nominal, actual in zip(expected, measured):
        if len(actual) != 4:
            raise ValueError("PAD_MESH_MATING_REAL_SQUARE_VERTEX_COUNT")
        polygon = Polygon(actual)
        reference = Polygon(tuple((datum[0]+rotate(v)[0],
                                   datum[1]+rotate(v)[1]) for v in nominal))
        if (not polygon.is_valid or polygon.area <= 0
                or polygon.symmetric_difference(reference).area > 1e-4):
            raise ValueError("PAD_MESH_MATING_REAL_BASE_SQUARE_DATUM_DRIFT")
        world = Polygon(tuple((x-datum[0]+float(world_x_mm),
                               y-datum[1]+float(world_y_mm)) for x, y in actual))
        squares_world.append(world)

    # Folded leg tips stop at the front skin; ONLY four protrusions extend
    # into the physical T2 base. Fail if any deepest vertex enters solid base.
    tips = {
        (round(float(pt[0]), 7), round(float(pt[1]), 7))
        for tri in tuple(triangles or ()) for pt in tri
        if abs(float(pt[2])-bottom) < 1e-5
    }
    if len(tips) < 4:
        raise ValueError("PAD_MESH_MATING_FOUR_TAB_TIPS_ABSENT")
    hits = [0, 0, 0, 0]
    for xy in tips:
        matching = [i for i, square in enumerate(squares_world)
                    if square.buffer(1e-4).covers(Point(xy))]
        if len(matching) != 1:
            raise ValueError("PAD_MESH_MATING_TIP_OUTSIDE_REAL_BASE_SQUARE")
        hits[matching[0]] += 1
    if not all(hits):
        raise ValueError("PAD_MESH_MATING_TAB_MISSING_IN_REAL_BASE_SQUARE")
    return tuple(tuple((float(x), float(y)) for x, y in polygon.exterior.coords[:-1])
                 for polygon in squares_world)


def verify_pad_solid_inside_real_base_cutouts(
    triangles, squares_world, *, base_front_world_z_mm: float,
    thickness_mm: float, tolerance: float = 1e-4,
) -> None:
    """Check the actual thickened PAD skin throughout the real Base T slab.

    Intersect ALL world-mesh triangles with the OPEN interval between the
    Base front/back skins. Every resulting 3D skin surface must project
    entirely into a verified real cutting square. A tip-only witness is
    insufficient: the entire solid edge in the sheet's volume must fit.
    This establishes local Base *slab* interference clearance only. It
    does NOT certify all other cabinet solids or production contact.
    """
    from math import isfinite
    from shapely.geometry import Point,LineString,Polygon,MultiPoint
    from shapely.ops import unary_union

    base=float(base_front_world_z_mm)
    t=float(thickness_mm)
    tol=float(tolerance)
    if (not all(isfinite(v) for v in (base,t,tol))
            or t <= 0 or tol <= 0 or tol >= min(t/4,0.01)):
        raise ValueError("PAD_BASE_SLAB_COLLISION_INVALID_TOLERANCE_OR_DATUM")
    squares=tuple(Polygon(square) for square in squares_world)
    if (len(squares)!=4
            or any(not p.is_valid or p.area<=0 for p in squares)):
        raise ValueError("PAD_BASE_SLAB_COLLISION_ACTUAL_CUT_SQUARES_MISSING")
    opening=unary_union(squares).buffer(tol)
    lower=base-t-tol/2
    upper=base-tol/2

    def clip(vertices,level,keep_ge):
        if not vertices:
            return []
        output=[]
        for a,b in zip(vertices,vertices[1:]+vertices[:1]):
            va=float(a[2])-level
            vb=float(b[2])-level
            inside_a=va>=0 if keep_ge else va<=0
            inside_b=vb>=0 if keep_ge else vb<=0
            if inside_a:
                output.append(a)
            if inside_a != inside_b:
                weight=va/(va-vb)
                output.append(tuple(a[i]+weight*(b[i]-a[i]) for i in range(3)))
        return output

    tested=0
    for tri in triangles:
        if len(tri)!=3:
            raise ValueError("PAD_BASE_SLAB_COLLISION_TRIANGLES_INVALID")
        vertices=[tuple(map(float,p)) for p in tri]
        if any(not all(isfinite(v) for v in point) for point in vertices):
            raise ValueError("PAD_BASE_SLAB_COLLISION_NONFINITE_VERTICES")
        vertices=clip(vertices,lower,True)
        vertices=clip(vertices,upper,False)
        if len(vertices)<2:
            continue
        xy=[]
        for x,y,_ in vertices:
            if not xy or abs(x-xy[-1][0])+abs(y-xy[-1][1])>1e-9:
                xy.append((x,y))
        if len(xy)>1 and xy[0]==xy[-1]:
            xy.pop()
        if not xy:
            continue
        tested+=1
        # Projection of a vertical 3D face may have 3-4 collinear
        # vertices or repeated endpoints. Its convex hull is the exact
        # projected region of a clipped *convex* triangle, so it does not
        # manufacture overlap by constructing an invalid zero-area polygon.
        geometry=MultiPoint(xy).convex_hull
        outside=geometry.difference(opening)
        if geometry.geom_type == "Polygon":
            excess=outside.area>tol*tol
        elif geometry.geom_type == "LineString":
            excess=outside.length>tol
        else:
            excess=not outside.is_empty
        if excess:
            raise ValueError("PAD_BASE_SLAB_SOLID_INTERFERES_WITH_REAL_BASE_MATERIAL")
    if tested<4:
        raise ValueError("PAD_BASE_SLAB_COLLISION_SAMPLED_SOLID_MISSING")
