# -*- coding: utf-8 -*-
"""Low-level assembly placement and sheet-thickening primitives."""
from __future__ import annotations

def triangle_bounds(triangles):
    """Return ((xmin, xmax), (ymin, ymax), (zmin, zmax)) for triangle meshes."""
    points = [point for tri in (triangles or ()) for point in tri[:3]]
    if not points:
        return None
    return tuple(
        (min(float(point[i]) for point in points), max(float(point[i]) for point in points))
        for i in range(3)
    )


def thicken_triangle_surface(triangles, thickness, *, tolerance=None):
    """Turn a zero-thickness folded triangle surface into a sharp-bend sheet solid.

    The folded surface remains the geometric mid-surface.  Two skins are offset by
    ``thickness / 2`` along each panel normal.  Outer material boundaries receive
    side walls, while non-coplanar shared edges receive miter bridge faces so the
    formed sheet has visible inside/outside faces instead of a mathematical skin.

    This is intentionally a sharp-bend solid (no bend-radius tessellation yet).
    It is renderer-independent and can be reused by assembly collision later.
    """
    import math
    from collections import defaultdict

    if tolerance is None:
        from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
        tolerance = (
            PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
        )
    source = [tuple(tuple(float(v) for v in point) for point in tri[:3])
              for tri in (triangles or ()) if len(tuple(tri)) >= 3]
    t = max(0.0, float(thickness or 0.0))
    if not source or t <= float(tolerance):
        return tuple(source)
    half = t / 2.0

    def add(a, b):
        return tuple(a[i] + b[i] for i in range(3))

    def sub(a, b):
        return tuple(a[i] - b[i] for i in range(3))

    def scale(v, k):
        return tuple(v[i] * k for i in range(3))

    def normal(tri):
        a, b, c = tri
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(c[i] - a[i] for i in range(3))
        n = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        mag = math.sqrt(sum(value * value for value in n))
        if mag <= 1e-12:
            return None
        return tuple(value / mag for value in n)

    inv_tol = 1.0 / max(float(tolerance), 1e-12)

    def point_key(point):
        return tuple(int(round(float(value) * inv_tol)) for value in point)

    def edge_key(a, b):
        ka, kb = point_key(a), point_key(b)
        return (ka, kb) if ka <= kb else (kb, ka)

    solid = []
    edges = defaultdict(list)
    for tri in source:
        n = normal(tri)
        if n is None:
            continue
        off = scale(n, half)
        plus = tuple(add(point, off) for point in tri)
        minus = tuple(sub(point, off) for point in tri)
        solid.append(plus)
        solid.append((minus[0], minus[2], minus[1]))
        for index in range(3):
            a = tri[index]
            b = tri[(index + 1) % 3]
            edges[edge_key(a, b)].append((a, b, n))

    def add_quad(a, b, c, d):
        solid.append((a, b, c))
        solid.append((a, c, d))

    for adjacent in edges.values():
        if len(adjacent) == 1:
            a, b, n = adjacent[0]
            off = scale(n, half)
            add_quad(add(a, off), add(b, off), sub(b, off), sub(a, off))
            continue

        # Triangulation edges on one planar panel need no wall.  At a real fold
        # the two panel normals differ, so bridge both skins across that hinge.
        a, b, n1 = adjacent[0]
        n2 = adjacent[1][2]
        dot = sum(n1[i] * n2[i] for i in range(3))
        if abs(dot) >= 1.0 - 1e-6:
            continue
        o1 = scale(n1, half)
        o2 = scale(n2, half)
        add_quad(add(a, o1), add(b, o1), add(b, o2), add(a, o2))
        add_quad(sub(a, o1), sub(a, o2), sub(b, o2), sub(b, o1))

    return tuple(solid)


def place_assembly_points(points, reference_triangles, placement, dimensions, offset=(0.0, 0.0, 0.0)):
    """Place local points using the exact transform of a reference folded mesh."""
    bounds = triangle_bounds(reference_triangles)
    if bounds is None:
        return tuple()

    mids = tuple((lo + hi) / 2.0 for lo, hi in bounds)
    dims = tuple(float(v) for v in (dimensions or ()) if v is not None)
    width = dims[0] if len(dims) >= 1 else max(1.0, bounds[0][1] - bounds[0][0])
    height = dims[1] if len(dims) >= 2 else max(1.0, bounds[1][1] - bounds[1][0])
    depth = dims[2] if len(dims) >= 3 else max(1.0, bounds[2][1] - bounds[2][0])
    dx, dy, dz = (float(v) for v in (offset or (0.0, 0.0, 0.0)))
    placement = str(placement or "offset").lower()

    def world(point):
        x, y, z = (float(v) for v in point)
        cx, cy, cz = x - mids[0], y - mids[1], z - mids[2]
        if placement in {"box_body", "body", "cabinet"}:
            wx, wy, wz = cx, cy, cz
        elif placement in {"receiving_outer_door", "base_plate", "receiving_base_plate", "inner_door_panel", "inner_door_frame_left", "inner_door_frame_right"}:
            # Authoritative placements already carry their absolute world datum
            # in offset. Do not add a second depth/2, -H/2, or origin rule.
            wx, wy, wz = cx, cy, cz
        elif placement == "inner_door_frame_top":
            # Frame blank longitudinal Y maps to cabinet X.
            wx, wy, wz = cy, -cx, cz
        elif placement in {"top", "head"}:
            wx, wy, wz = cx, height / 2.0 + cz, cy
        elif placement in {"bottom", "tail"}:
            wx, wy, wz = cx, -height / 2.0 - cz, cy
        elif placement in {"front", "door"}:
            wx, wy, wz = cx, cy, depth / 2.0 + cz
        elif placement == "back":
            wx, wy, wz = cx, cy, -depth / 2.0 - cz
        elif placement == "base":
            wx, wy, wz = cx, -height / 2.0 + cy, cz
        elif placement in {"divider_horizontal", "horizontal_divider"}:
            wx, wy, wz = cy, cz, cx
        elif placement == "divider_horizontal_inward":
            wx, wy, wz = cy, cz, -cx
        elif placement in {"divider_vertical", "vertical_divider"}:
            wx, wy, wz = cz, cy, cx
        elif placement == "divider_vertical_inward":
            wx, wy, wz = cz, cy, -cx
        else:
            wx, wy, wz = cx, cy, cz
        return (wx + dx, wy + dy, wz + dz)

    return tuple(world(point) for point in (points or ()))


def place_assembly_triangles(triangles, placement, dimensions, offset=(0.0, 0.0, 0.0)):
    """Place one already-folded local mesh into the shared cabinet coordinates.

    ``dimensions`` is the cabinet finished ``(width, height, depth)`` tuple.
    Local meshes are centered from their own bounds before semantic placement,
    matching the Phase6 assembly viewer behavior that existed before this
    transform became shared manufacturing geometry.
    """
    tris = tuple(tuple(tri[:3]) for tri in (triangles or ()))
    if not tris:
        return tuple()
    placed = place_assembly_points(
        [point for tri in tris for point in tri],
        tris, placement, dimensions, offset,
    )
    return tuple(tuple(placed[i:i + 3]) for i in range(0, len(placed), 3))


def place_endcap_against_box_body(
    triangles,
    placement,
    box_body_world_triangles,
    offset=(0.0, 0.0, 0.0),
    sheet_thickness=0.0,
    reference_triangles=None,
    preserve_core_origin=False,
):
    """Orient and mate Head/Tail core face to the Box Body in world space.

    Folded EndCap meshes use local ``z=0`` as the semantic finished core face.
    Do not recenter that axis: the core face itself is the mating datum.

    ``top/head`` applies the required 180-degree rotation about world X, then
    puts the core face on the Box Body upper world-Y bound.
    ``bottom/tail`` preserves the authoritative native EndCap in-plane orientation
    (local X and local Y) and puts the retained/core face on the Box Body lower
    world-Y bound.  Tail Fold Profile ordering is already native/orientation-aware,
    so assembly must not mirror local Y a second time. Canonical local ``+z`` folds
    map upward into the cabinet.
    """
    endcap_bounds = triangle_bounds(reference_triangles if reference_triangles is not None else triangles)
    body_bounds = triangle_bounds(box_body_world_triangles)
    if endcap_bounds is None or body_bounds is None:
        return tuple()

    # Authoritative Fold-Profile geometry normalizes its base/core segment around
    # local X/Y = 0.  Real manufacturing paths opt into that datum so asymmetric
    # flanges cannot drag the finished core off its cabinet mating plane.  Generic
    # triangle callers retain the historical whole-envelope centering contract.
    if bool(preserve_core_origin):
        mid_x = 0.0
        mid_y = 0.0
    else:
        mid_x = (float(endcap_bounds[0][0]) + float(endcap_bounds[0][1])) / 2.0
        mid_y = (float(endcap_bounds[1][0]) + float(endcap_bounds[1][1])) / 2.0
    dx, dy, dz = (float(v) for v in (offset or (0.0, 0.0, 0.0)))
    placement = str(placement or "top").lower()
    half_t = max(0.0, float(sheet_thickness or 0.0)) / 2.0

    if placement in {"top", "head"}:
        # z=0 is the sheet mid-surface.  Shift it outward by T/2 so the
        # physical inside skin (local +Z) is the surface that mates the box.
        anchor_y = float(body_bounds[1][1]) + half_t

        def world(point):
            x, y, z = (float(v) for v in point)
            cx, cy = x - mid_x, y - mid_y
            # Base top mapping is (cx, anchor_y + z, cy). Rotating 180 deg
            # about world X through the mating plane yields (cx, anchor_y-z, -cy).
            return (cx + dx, anchor_y - z + dy, -cy + dz)

    elif placement in {"bottom", "tail"}:
        anchor_y = float(body_bounds[1][0]) - half_t

        def world(point):
            x, y, z = (float(v) for v in point)
            cx, cy = x - mid_x, y - mid_y
            # Tail assembly semantic:
            #   * z=0 retained/core material mates the Box Body bottom plane;
            #   * left/right X is preserved;
            #   * EndCap native up/down (local Y) is preserved (already normalized
            #     by the authoritative tail Fold Profile; do not double-mirror);
            #   * canonical +Z folds (yl1/yr1/ybottom1 etc.) go UP into box.
            return (cx + dx, anchor_y + z + dy, cy + dz)

    else:
        raise ValueError(f"Unsupported EndCap assembly placement: {placement!r}")

    return tuple(tuple(world(point) for point in tri[:3]) for tri in (triangles or ()))
