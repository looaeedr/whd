# -*- coding: utf-8 -*-
"""Shared assembly-space geometry transforms.

This module owns only pure 3D coordinate placement.  It does not know about
GUI state, rendering, DXF output, or collision ownership.  Both the FinalScene
viewer and manufacturing-side assembly collision code consume this same
transform so an assembled part has one world-coordinate definition.
"""
from __future__ import annotations

from dataclasses import dataclass


def triangle_bounds(triangles):
    """Return ((xmin, xmax), (ymin, ymax), (zmin, zmax)) for triangle meshes."""
    points = [point for tri in (triangles or ()) for point in tri[:3]]
    if not points:
        return None
    return tuple(
        (min(float(point[i]) for point in points), max(float(point[i]) for point in points))
        for i in range(3)
    )


def thicken_triangle_surface(triangles, thickness, *, tolerance=1e-7):
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
        elif placement in {"receiving_outer_door", "receiving_base_plate", "inner_door_panel", "inner_door_frame_left", "inner_door_frame_right"}:
            # T16 family-aware placements already carry their absolute world
            # datum in offset. Do not add a second depth/2 or origin rule.
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
        elif placement in {"divider_vertical", "vertical_divider"}:
            wx, wy, wz = cz, cy, cx
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


def _segment_value(segment, key, default=None):
    if hasattr(segment, "get"):
        if key == "len":
            value = segment.get("len", segment.get("length", default))
        else:
            value = segment.get(key, default)
    else:
        attr = "length" if key == "len" else key
        value = getattr(segment, attr, default)
    return value


def _as_float(value, default=0.0):
    try:
        return float(default if value is None else value)
    except (TypeError, ValueError):
        return float(default)


def _profile_base_index(profile):
    segs = list(profile or ())
    if not segs:
        return 0
    for preferred in ("W_PART", "W_BACK", "W"):
        for index, seg in enumerate(segs):
            if str(_segment_value(seg, "core", "") or "") == preferred:
                return index
    core_indices = [
        index for index, seg in enumerate(segs)
        if bool(_segment_value(seg, "core", False))
    ]
    if core_indices:
        return core_indices[len(core_indices) // 2]
    return min(len(segs) - 1, len(segs) // 2)


def place_box_body_structure_points(points, piece, *, total_w, thickness, x_profile):
    """Place folded piece-local points into canonical multi-piece Box Body coordinates.

    Shared by operator rendering and assembly collision.  The role transform is a
    manufacturing geometry contract; keeping it here prevents the 3D viewer and
    solver from assembling side/back-separated cabinets differently.
    """
    total = float(total_w)
    t = max(0.0, float(thickness or 0.0))
    w_material_half = max(0.0, (total - 2.0 * t) / 2.0)
    role = str(getattr(piece, "role", "") or "")

    if role in {"left", "middle", "right", "integral", "back"}:
        center = (
            (float(getattr(piece, "formed_w_start", 0.0)) + float(getattr(piece, "formed_w_end", 0.0))) / 2.0
            - total / 2.0
        )
        if role == "back":
            # Side/back-split cabinets use the side rear flanges as the rear
            # outer layer.  The flat back panel is the inner WRAP target, so
            # its mid-plane sits one sheet thickness inward.  This preserves
            # face-to-face contact without placing both solids on one mid-plane.
            return tuple((float(p[0]) + center, float(p[1]), t) for p in (points or ()))
        return tuple((float(p[0]) + center, float(p[1]), float(p[2])) for p in (points or ()))

    if role in {"left_side", "right_side"}:
        base_index = _profile_base_index(x_profile)
        segs = list(x_profile or ())
        base_len = _as_float(_segment_value(segs[base_index], "len", 0.0)) if segs else 0.0
        d_half = base_len / 2.0
        if role == "left_side":
            return tuple((
                -w_material_half + float(p[2]), float(p[1]), d_half - float(p[0])
            ) for p in (points or ()))
        return tuple((
            w_material_half - float(p[2]), float(p[1]), float(p[0]) + d_half
        ) for p in (points or ()))

    return tuple(tuple(float(v) for v in p) for p in (points or ()))


def _profile_geometry(profile, *, enabled_folds=None):
    import math

    segs = list(profile or ())
    if not segs:
        return (0.0, 1.0), ((-0.5, 0.0), (0.5, 0.0))
    if enabled_folds is None:
        enabled_folds = (True,) * max(0, len(segs) - 1)
    else:
        enabled_folds = tuple(bool(v) for v in enabled_folds)

    raw_u = [0.0]
    raw_z = [0.0]
    angles = []
    current_angle = 0.0
    cumulative = [0.0]
    for index, seg in enumerate(segs):
        length = max(0.0, _as_float(_segment_value(seg, "len", 0.0)))
        angles.append(current_angle)
        rad = math.radians(current_angle)
        raw_u.append(raw_u[-1] + length * math.cos(rad))
        raw_z.append(raw_z[-1] + length * math.sin(rad))
        cumulative.append(cumulative[-1] + length)
        angle = _segment_value(seg, "angle", None)
        if index < len(segs) - 1 and angle is not None:
            if index >= len(enabled_folds) or enabled_folds[index]:
                current_angle -= _as_float(angle)

    base_idx = _profile_base_index(segs)
    base_angle = math.radians(angles[base_idx] if angles else 0.0)
    rotated = []
    for u, z in zip(raw_u, raw_z):
        ru = u * math.cos(-base_angle) - z * math.sin(-base_angle)
        rz = u * math.sin(-base_angle) + z * math.cos(-base_angle)
        rotated.append((ru, rz))
    center = (rotated[base_idx][0] + rotated[base_idx + 1][0]) / 2.0
    z0 = rotated[base_idx][1]
    folded = tuple((u - center, z - z0) for u, z in rotated)
    return tuple(cumulative), folded


def _profile_map(position, boundaries, folded):
    value = float(position)
    total = float(boundaries[-1])
    value = min(max(value, 0.0), total)
    index = len(boundaries) - 2
    for i in range(len(boundaries) - 1):
        if value <= boundaries[i + 1] + 1e-9:
            index = i
            break
    lo, hi = float(boundaries[index]), float(boundaries[index + 1])
    ratio = 0.0 if hi <= lo else (value - lo) / (hi - lo)
    u0, z0 = folded[index]
    u1, z1 = folded[index + 1]
    return (u0 + (u1 - u0) * ratio, z0 + (z1 - z0) * ratio)


def _profile_flat_map(position, boundaries, *, profile=None):
    seg_count = max(1, len(boundaries) - 1)
    base_idx = _profile_base_index(profile) if profile is not None else min(seg_count - 1, seg_count // 2)
    center = (float(boundaries[base_idx]) + float(boundaries[base_idx + 1])) / 2.0
    return float(position) - center, 0.0


def _fold_mask_for_cross_coordinate(profile, axis, cross_position, fold_guides, *, tol=1e-6):
    segs = list(profile or ())
    boundaries = [0.0]
    for seg in segs:
        boundaries.append(boundaries[-1] + max(0.0, _as_float(_segment_value(seg, "len", 0.0))))
    guides = tuple(g for g in (fold_guides or ()) if str(getattr(g, "axis", "")) == str(axis))
    mask = []
    cross = float(cross_position)
    for index in range(max(0, len(segs) - 1)):
        boundary = boundaries[index + 1]
        matches = [g for g in guides if abs(float(g.position) - boundary) <= tol]
        if not matches:
            mask.append(True)
            continue
        mask.append(
            any(
                float(g.span_start) - tol <= cross <= float(g.span_end) + tol
                for g in matches
            )
        )
    return tuple(mask)


def _profile_map_with_guides(position, cross_position, profile, *, axis, fold_guides):
    mask = _fold_mask_for_cross_coordinate(profile, axis, cross_position, fold_guides)
    boundaries, folded = _profile_geometry(profile, enabled_folds=mask)
    return _profile_map(position, boundaries, folded)


def folded_mesh_from_polygon(
    material,
    x_profile,
    y_profile,
    *,
    fold_exemptions=(),
    fold_guides=(),
):
    """Triangulate authoritative 2D material and fold it into local 3D space.

    This is the shared, renderer-independent version of the Phase6 FinalScene
    folding path.  Profiles may be mapping rows (``len``/``angle``/``core``)
    or contract ``FoldProfileSegment`` objects (``length``/``angle``/``core``).
    """
    from shapely.geometry import box
    from shapely.ops import triangulate

    xb, xf = _profile_geometry(x_profile)
    yb, yf = _profile_geometry(y_profile)
    total_x, total_y = float(xb[-1]), float(yb[-1])
    display_material = material.simplify(0.05, preserve_topology=True)
    clipped_material = display_material.intersection(box(0.0, 0.0, total_x, total_y))
    triangles3d = []

    def polygon_parts(geom):
        if geom.is_empty:
            return []
        if getattr(geom, "geom_type", "") == "Polygon":
            return [geom] if geom.area > 1e-9 else []
        return [
            g for g in getattr(geom, "geoms", ())
            if getattr(g, "geom_type", "") == "Polygon" and g.area > 1e-9
        ]

    x_cuts = set(float(v) for v in xb)
    y_cuts = set(float(v) for v in yb)
    for guide in tuple(fold_guides or ()):
        if str(getattr(guide, "axis", "")) == "y":
            for value in (float(guide.span_start), float(guide.span_end)):
                if 0.0 < value < total_x:
                    x_cuts.add(value)
        elif str(getattr(guide, "axis", "")) == "x":
            for value in (float(guide.span_start), float(guide.span_end)):
                if 0.0 < value < total_y:
                    y_cuts.add(value)
    x_cuts = sorted(x_cuts)
    y_cuts = sorted(y_cuts)

    for xi in range(len(x_cuts) - 1):
        for yi in range(len(y_cuts) - 1):
            cell = box(x_cuts[xi], y_cuts[yi], x_cuts[xi + 1], y_cuts[yi + 1])
            clipped = clipped_material.intersection(cell)
            if clipped.is_empty:
                continue
            regions = [(piece, frozenset()) for piece in polygon_parts(clipped)]
            for axis, exemption in tuple(fold_exemptions or ()):
                next_regions = []
                for geom, flags in regions:
                    inside = geom.intersection(exemption)
                    outside = geom.difference(exemption)
                    next_regions.extend((g, flags | {str(axis)}) for g in polygon_parts(inside))
                    next_regions.extend((g, flags) for g in polygon_parts(outside))
                regions = next_regions

            for piece, flags in regions:
                for tri in triangulate(piece):
                    if not piece.covers(tri):
                        continue
                    coords = list(tri.exterior.coords)[:3]
                    mapped = []
                    for x, y in coords:
                        if "x" in flags:
                            ux, zx = _profile_flat_map(x, xb, profile=x_profile)
                        elif fold_guides:
                            ux, zx = _profile_map_with_guides(
                                x, y, x_profile, axis="x", fold_guides=fold_guides
                            )
                        else:
                            ux, zx = _profile_map(x, xb, xf)

                        if "y" in flags:
                            uy, zy = _profile_flat_map(y, yb, profile=y_profile)
                        elif fold_guides:
                            uy, zy = _profile_map_with_guides(
                                y, x, y_profile, axis="y", fold_guides=fold_guides
                            )
                        else:
                            uy, zy = _profile_map(y, yb, yf)
                        mapped.append((float(ux), float(uy), float(zx + zy)))
                    triangles3d.append(tuple(mapped))
    return tuple(triangles3d)


def folded_world_mesh_from_render_data(
    render_data,
    x_profile,
    y_profile,
    *,
    placement="offset",
    dimensions=None,
    offset=(0.0, 0.0, 0.0),
    fold_exemptions=(),
):
    """Fold one authoritative render result and place it in assembly space."""
    local = folded_mesh_from_polygon(
        render_data.material,
        x_profile,
        y_profile,
        fold_exemptions=fold_exemptions,
        fold_guides=tuple(getattr(render_data, "fold_guides", ()) or ()),
    )
    return place_assembly_triangles(local, placement, dimensions, offset)


@dataclass(frozen=True)
class MeshInterferenceDiagnostic:
    """UI diagnostics for real world-space sheet-surface crossings.

    Coplanar contact is intentionally ignored: a mating skin touching another
    skin is not automatically an interference.  The highlighted target
    triangles are the EndCap/Tail physical-solid faces whose edges actually
    cross the retained Box Body physical-solid faces.
    """

    target_triangles: tuple
    intersection_points: tuple[tuple[float, float, float], ...]
    pair_count: int = 0
    intersection_segments: tuple = ()

    @property
    def has_interference(self) -> bool:
        return bool(self.target_triangles)


def restore_unrelieved_endcap_material(material):
    """Restore exterior corner reliefs for *assembly diagnostics only*.

    The current EndCap manufacturing material already contains fixed corner
    relief on its exterior ring.  To see the raw interference that those
    legacy/fixed cuts hide, rebuild the rectangular blank envelope while
    preserving every through-hole interior.  This helper must never replace
    production CUTTING geometry.
    """
    from shapely.geometry import MultiPolygon, Polygon, box
    from shapely.ops import unary_union

    if material is None or getattr(material, "is_empty", True):
        return material
    minx, miny, maxx, maxy = map(float, material.bounds)
    restored = box(minx, miny, maxx, maxy)
    polygons = ()
    if isinstance(material, Polygon):
        polygons = (material,)
    elif isinstance(material, MultiPolygon):
        polygons = tuple(material.geoms)
    else:
        return material
    holes = []
    for polygon in polygons:
        for ring in polygon.interiors:
            try:
                hole = Polygon(ring)
            except Exception:
                continue
            if not hole.is_empty and float(hole.area) > 1e-9:
                holes.append(hole)
    if holes:
        restored = restored.difference(unary_union(holes))
    if not restored.is_valid:
        restored = restored.buffer(0)
    return restored



def restored_endcap_relief_delta(material):
    """Return only material added back when fixed EndCap relief is ignored.

    Assembly diagnostics must not run collision tests against the entire
    restored EndCap because normal mating seams then dominate the result.
    The physically interesting diagnostic target is only the material that
    legacy/fixed corner relief removed.  Production CUTTING remains unchanged.
    """
    restored = restore_unrelieved_endcap_material(material)
    if restored is None or getattr(restored, "is_empty", True):
        return restored
    if material is None or getattr(material, "is_empty", True):
        return restored
    delta = restored.difference(material)
    if not delta.is_valid:
        delta = delta.buffer(0)
    return delta

def _segment_triangle_intersection(p0, p1, tri, *, tolerance=1e-7):
    """Moller-Trumbore segment/triangle hit; parallel/coplanar => None."""
    import math

    def sub(a, b):
        return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
    def add(a, b):
        return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
    def mul(a, k):
        return (a[0]*k, a[1]*k, a[2]*k)
    def dot(a, b):
        return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
    def cross(a, b):
        return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

    v0, v1, v2 = tri
    direction = sub(p1, p0)
    if dot(direction, direction) <= tolerance * tolerance:
        return None
    edge1 = sub(v1, v0)
    edge2 = sub(v2, v0)
    h = cross(direction, edge2)
    a = dot(edge1, h)
    if abs(a) <= tolerance:
        return None
    f = 1.0 / a
    s = sub(p0, v0)
    u = f * dot(s, h)
    if u < -tolerance or u > 1.0 + tolerance:
        return None
    q = cross(s, edge1)
    v = f * dot(direction, q)
    if v < -tolerance or u + v > 1.0 + tolerance:
        return None
    t = f * dot(edge2, q)
    if t < -tolerance or t > 1.0 + tolerance:
        return None
    return add(p0, mul(direction, t))


def detect_world_mesh_surface_interference(source_triangles, target_triangles, *, tolerance=1e-6):
    """Detect non-coplanar physical surface crossings in shared world space.

    This is a diagnostic overlay, not yet the production relief solver.  It
    highlights EndCap/Tail physical-solid faces which genuinely cross the Box
    Body physical-solid surface.  Coplanar mating contact is deliberately
    ignored so a correctly seated face is not painted as a collision.
    """
    import numpy as np

    source = tuple(tuple(tuple(map(float, p)) for p in tri) for tri in (source_triangles or ()))
    target = tuple(tuple(tuple(map(float, p)) for p in tri) for tri in (target_triangles or ()))
    if not source or not target:
        return MeshInterferenceDiagnostic((), (), 0, ())

    src = np.asarray(source, dtype=float)
    src_min = src.min(axis=1)
    src_max = src.max(axis=1)
    target_hits = []
    points = []
    pair_count = 0
    segments = []
    segment_keys = set()
    point_keys = set()

    def record(point):
        key = tuple(round(float(v), 6) for v in point)
        if key not in point_keys:
            point_keys.add(key)
            points.append(tuple(float(v) for v in point))

    for target_tri in target:
        arr = np.asarray(target_tri, dtype=float)
        tmin = arr.min(axis=0) - float(tolerance)
        tmax = arr.max(axis=0) + float(tolerance)
        mask = np.all(src_max + tolerance >= tmin, axis=1) & np.all(src_min - tolerance <= tmax, axis=1)
        candidate_indexes = np.nonzero(mask)[0]
        hit_target = False
        for idx in candidate_indexes:
            source_tri = source[int(idx)]
            pair_points = []
            for a, b in ((target_tri[0], target_tri[1]), (target_tri[1], target_tri[2]), (target_tri[2], target_tri[0])):
                hit = _segment_triangle_intersection(a, b, source_tri, tolerance=tolerance)
                if hit is not None:
                    pair_points.append(hit)
            for a, b in ((source_tri[0], source_tri[1]), (source_tri[1], source_tri[2]), (source_tri[2], source_tri[0])):
                hit = _segment_triangle_intersection(a, b, target_tri, tolerance=tolerance)
                if hit is not None:
                    pair_points.append(hit)
            unique_pair = []
            seen_pair = set()
            for point in pair_points:
                key = tuple(round(float(v), 6) for v in point)
                if key not in seen_pair:
                    seen_pair.add(key)
                    unique_pair.append(tuple(float(v) for v in point))
            # A true non-coplanar triangle/triangle crossing is a segment.
            # One isolated point is only a touch and is not painted as an
            # interference region.
            if len(unique_pair) >= 2:
                best = None
                best_d2 = -1.0
                for i in range(len(unique_pair)):
                    for j in range(i + 1, len(unique_pair)):
                        a, b = unique_pair[i], unique_pair[j]
                        d2 = sum((a[k] - b[k]) ** 2 for k in range(3))
                        if d2 > best_d2:
                            best_d2 = d2
                            best = (a, b)
                if best is not None and best_d2 > tolerance * tolerance:
                    pair_count += 1
                    hit_target = True
                    skey = tuple(sorted((
                        tuple(round(v, 6) for v in best[0]),
                        tuple(round(v, 6) for v in best[1]),
                    )))
                    if skey not in segment_keys:
                        segment_keys.add(skey)
                        segments.append(best)
                    for point in unique_pair:
                        record(point)
        if hit_target:
            target_hits.append(target_tri)

    return MeshInterferenceDiagnostic(
        tuple(target_hits), tuple(points), pair_count, tuple(segments)
    )



@dataclass(frozen=True)
class FoldedTriangleMap:
    """One folded triangle with its authoritative flat-pattern UV coordinates."""

    flat: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    local: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True)
class MappedSkinTriangle:
    """One physical sheet skin triangle retaining the flat-pattern UV mapping."""

    flat: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    world: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    side: int


def folded_mesh_with_flat_uv_from_polygon(
    material,
    x_profile,
    y_profile,
    *,
    fold_exemptions=(),
    fold_guides=(),
):
    """Fold material exactly like :func:`folded_mesh_from_polygon`, preserving 2D UV.

    The fold transform is piecewise affine inside each triangulated cell.  Keeping
    the original flat vertices makes later barycentric world->flat backprojection
    exact for the sharp-bend model instead of reconstructing coordinates from
    display-space bounds.
    """
    from shapely.geometry import box
    from shapely.ops import triangulate

    xb, xf = _profile_geometry(x_profile)
    yb, yf = _profile_geometry(y_profile)
    total_x, total_y = float(xb[-1]), float(yb[-1])
    display_material = material.simplify(0.05, preserve_topology=True)
    clipped_material = display_material.intersection(box(0.0, 0.0, total_x, total_y))
    mapped_triangles = []

    def polygon_parts(geom):
        if geom.is_empty:
            return []
        if getattr(geom, "geom_type", "") == "Polygon":
            return [geom] if geom.area > 1e-9 else []
        return [
            g for g in getattr(geom, "geoms", ())
            if getattr(g, "geom_type", "") == "Polygon" and g.area > 1e-9
        ]

    x_cuts = set(float(v) for v in xb)
    y_cuts = set(float(v) for v in yb)
    for guide in tuple(fold_guides or ()):
        if str(getattr(guide, "axis", "")) == "y":
            for value in (float(guide.span_start), float(guide.span_end)):
                if 0.0 < value < total_x:
                    x_cuts.add(value)
        elif str(getattr(guide, "axis", "")) == "x":
            for value in (float(guide.span_start), float(guide.span_end)):
                if 0.0 < value < total_y:
                    y_cuts.add(value)
    x_cuts = sorted(x_cuts)
    y_cuts = sorted(y_cuts)

    for xi in range(len(x_cuts) - 1):
        for yi in range(len(y_cuts) - 1):
            cell = box(x_cuts[xi], y_cuts[yi], x_cuts[xi + 1], y_cuts[yi + 1])
            clipped = clipped_material.intersection(cell)
            if clipped.is_empty:
                continue
            regions = [(piece, frozenset()) for piece in polygon_parts(clipped)]
            for axis, exemption in tuple(fold_exemptions or ()):
                next_regions = []
                for geom, flags in regions:
                    inside = geom.intersection(exemption)
                    outside = geom.difference(exemption)
                    next_regions.extend((g, flags | {str(axis)}) for g in polygon_parts(inside))
                    next_regions.extend((g, flags) for g in polygon_parts(outside))
                regions = next_regions

            for piece, flags in regions:
                for tri in triangulate(piece):
                    if not piece.covers(tri):
                        continue
                    flat = tuple(
                        (float(x), float(y))
                        for x, y in list(tri.exterior.coords)[:3]
                    )
                    local = []
                    for x, y in flat:
                        if "x" in flags:
                            ux, zx = _profile_flat_map(x, xb, profile=x_profile)
                        elif fold_guides:
                            ux, zx = _profile_map_with_guides(
                                x, y, x_profile, axis="x", fold_guides=fold_guides
                            )
                        else:
                            ux, zx = _profile_map(x, xb, xf)

                        if "y" in flags:
                            uy, zy = _profile_flat_map(y, yb, profile=y_profile)
                        elif fold_guides:
                            uy, zy = _profile_map_with_guides(
                                y, x, y_profile, axis="y", fold_guides=fold_guides
                            )
                        else:
                            uy, zy = _profile_map(y, yb, yf)
                        local.append((float(ux), float(uy), float(zx + zy)))
                    mapped_triangles.append(FoldedTriangleMap(flat=flat, local=tuple(local)))
    return tuple(mapped_triangles)


def _triangle_unit_normal(triangle):
    import math

    a, b, c = triangle
    u = tuple(float(b[i]) - float(a[i]) for i in range(3))
    v = tuple(float(c[i]) - float(a[i]) for i in range(3))
    n = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    mag = math.sqrt(sum(value * value for value in n))
    if mag <= 1e-12:
        return None
    return tuple(value / mag for value in n)


def world_skin_with_flat_uv(
    mapped_triangles, placement, dimensions, *, offset=(0.0, 0.0, 0.0), sheet_thickness=0.0
):
    """Place UV-aware mapped triangles for non-EndCap parts and build both skins."""
    half = max(0.0, float(sheet_thickness or 0.0)) / 2.0
    mapped_all = tuple(mapped_triangles or ())
    if not mapped_all:
        return tuple()
    placed_all = place_assembly_triangles(
        tuple(mapped.local for mapped in mapped_all), placement, dimensions, offset
    )
    out = []
    for mapped, world_mid in zip(mapped_all, placed_all):
        normal = _triangle_unit_normal(world_mid)
        if normal is None:
            continue
        for side in (-1, 1):
            delta = tuple(float(side) * half * value for value in normal)
            world = tuple(
                tuple(float(point[i]) + delta[i] for i in range(3))
                for point in world_mid
            )
            out.append(MappedSkinTriangle(flat=mapped.flat, world=world, side=side))
    return tuple(out)


def endcap_world_skin_with_flat_uv(
    mapped_triangles,
    placement,
    box_body_world_triangles,
    *,
    offset=(0.0, 0.0, 0.0),
    sheet_thickness=0.0,
    reference_triangles=None,
    preserve_core_origin=False,
):
    """Place UV-aware EndCap triangles and create both physical skins.

    Skin offsets are parallel to each folded panel, so barycentric coordinates
    on either skin are identical to those on the authoritative mid-surface.
    """
    half = max(0.0, float(sheet_thickness or 0.0)) / 2.0
    mapped_all = tuple(mapped_triangles or ())
    if not mapped_all:
        return tuple()
    placed_all = place_endcap_against_box_body(
        tuple(mapped.local for mapped in mapped_all),
        placement,
        box_body_world_triangles,
        offset,
        sheet_thickness=sheet_thickness,
        reference_triangles=reference_triangles,
        preserve_core_origin=preserve_core_origin,
    )
    out = []
    for mapped, world_mid in zip(mapped_all, placed_all):
        normal = _triangle_unit_normal(world_mid)
        if normal is None:
            continue
        for side in (-1, 1):
            delta = tuple(float(side) * half * value for value in normal)
            world = tuple(
                tuple(float(point[i]) + delta[i] for i in range(3))
                for point in world_mid
            )
            out.append(MappedSkinTriangle(flat=mapped.flat, world=world, side=side))
    return tuple(out)


def derive_side_back_split_endcap_bottom_relief(
    *, width: float, height: float, thickness: float,
    side_fold_left: float, side_fold_right: float,
    side_rear_bend: float, bottom_fold: float,
):
    """Project the corrected side/back-split lower-corner 3D overlap to flat UV.

    This is a geometry helper, not a Cabinet Family policy.  It models the
    corrected formed placement used by receiving-style side/back split boxes:

    * side rear flange occupies the outer rear layer;
    * rear panel is one sheet thickness inward;
    * EndCap lower face is positioned from the D-core origin, so its WRAP skin
      contacts the rear panel while its corner can still collide with the side
      rear flange.

    The returned two-stage relief is the flat-pattern projection of that side
    flange penetration.  Legal rear-panel WRAP face contact is not relief.
    """
    from .sheetmetal_geometry import ResolvedCornerRelief

    w = float(width)
    h = float(height)
    t = float(thickness)
    rear = float(side_rear_bend)
    bottom = float(bottom_fold)
    if w <= 0.0 or t <= 0.0 or rear <= 0.0 or bottom <= 0.0:
        raise ValueError("side/back split relief requires positive W/T/rear/bottom geometry")

    # Corrected world-space formed-face references.  W/H intentionally remain
    # in the derivation even though the final overlap cancels them algebraically.
    left_endcap_core_edge = -w / 2.0 + 2.0 * t
    left_side_rear_inner = -w / 2.0 + t + rear
    right_endcap_core_edge = w / 2.0 - 2.0 * t
    right_side_rear_inner = w / 2.0 - t - rear
    illegal_u_left = max(0.0, left_side_rear_inner - left_endcap_core_edge)
    illegal_u_right = max(0.0, right_endcap_core_edge - right_side_rear_inner)

    body_side_limit = h / 2.0 - t
    endcap_wrap_outer_edge = h / 2.0 - 0.5 * t
    endcap_bottom_inner_edge = endcap_wrap_outer_edge - bottom
    illegal_v = max(0.0, body_side_limit - endcap_bottom_inner_edge)
    wrap_contact_depth = max(0.0, endcap_wrap_outer_edge - body_side_limit)

    def row(side_fold, illegal_u, side):
        side_fold = float(side_fold)
        relief = ResolvedCornerRelief(
            primary_u=max(0.0, side_fold + illegal_u),
            primary_v=illegal_v,
            secondary_u=max(0.0, side_fold),
            secondary_depth=wrap_contact_depth,
        )
        return {
            "relief": relief,
            "world_evidence": {
                "side": side,
                "endcap_core_edge": left_endcap_core_edge if side == "left" else right_endcap_core_edge,
                "side_rear_inner_edge": left_side_rear_inner if side == "left" else right_side_rear_inner,
                "body_side_limit": body_side_limit,
                "endcap_wrap_outer_edge": endcap_wrap_outer_edge,
                "endcap_bottom_inner_edge": endcap_bottom_inner_edge,
                "illegal_overlap_u": illegal_u,
                "illegal_overlap_v": illegal_v,
                "wrap_contact_depth": wrap_contact_depth,
                "rear_panel_midplane_offset": t,
            },
        }

    return {
        "left": row(side_fold_left, illegal_u_left, "left"),
        "right": row(side_fold_right, illegal_u_right, "right"),
    }
