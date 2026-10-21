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
    """Prove the four holes are *really cut* at this model's installed UV.

    Metadata counts alone are insufficient: a stale/damaged FinalScene may
    claim 4 locator openings although those exact CUTTING polygons are gone.
    Anchor the installation centre from the model's four actual source-
    identified V5 screw circles, then require the complete four polygons.
    Nothing is inferred from a paper DXF origin or a brand-specific constant.
    """
    from shapely.geometry import Polygon
    from .receiving_nfb_v5_configured_inner_door import AXES
    from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
    from .manufacturing_render_data import PartRenderData

    if not isinstance(render_data, PartRenderData) or not isinstance(pattern, PadPattern):
        raise TypeError("PAD_BASE_ACTUAL_FINALSCENE_REQUIRED")
    if type(rotation_deg) is not int or rotation_deg not in AXES:
        raise ValueError("PAD_BASE_SELECTED_ROTATION_MISSING")
    source_circles=tuple(p for p in render_data.scene.primitives
        if isinstance(p, CirclePrimitive) and p.layer=="CUTTING"
        and p.source_type=="NFB_V5_NUMERIC_BASE_TRIAL"
        and p.source_id is not None
        and p.source_id.startswith(str(owner_hole_id)+":screw:"))
    if len(source_circles)!=4:
        raise ValueError("PAD_BASE_FOUR_SOURCE_SCREWS_NOT_PRESENT")
    ux,uy=AXES[rotation_deg]
    def rotate(xy):
        x,y=map(float,xy)
        return (x*ux[0]+y*uy[0],x*ux[1]+y*uy[1])
    source_screws=tuple(map(rotate,pattern.base_screw_centres_xy_mm))
    observed=tuple((float(p.center.x),float(p.center.y)) for p in source_circles)
    mean_source=(sum(p[0] for p in source_screws)/4,
                 sum(p[1] for p in source_screws)/4)
    origin=(sum(p[0] for p in observed)/4-mean_source[0],
            sum(p[1] for p in observed)/4-mean_source[1])
    tol=1e-5
    def quantized(xy):
        return tuple(round(float(a),5) for a in xy)
    wanted_screws={
        quantized((origin[0]+x,origin[1]+y)) for x,y in source_screws
    }
    if ({quantized(xy) for xy in observed}!=wanted_screws
            or any(abs(2*float(p.radius)-pattern.screw_diameter_mm)>tol
                   for p in source_circles)):
        raise ValueError("PAD_BASE_SELECTED_CSV_SCREW_DATUM_DRIFT")
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
