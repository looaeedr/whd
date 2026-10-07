# -*- coding: utf-8 -*-
"""Shared assembly-space geometry transforms.

This module owns only pure 3D coordinate placement.  It does not know about
GUI state, rendering, DXF output, or collision ownership.  Both the FinalScene
viewer and manufacturing-side assembly collision code consume this same
transform so an assembled part has one world-coordinate definition.
"""
from __future__ import annotations

from dataclasses import dataclass


from .assembly_geometry_primitives import (
    triangle_bounds,
    thicken_triangle_surface,
    place_assembly_points,
    place_assembly_triangles,
    place_endcap_against_box_body,
)

from .assembly_geometry_folded_mesh import (
    _segment_value,
    _as_float,
    _profile_base_index,
    place_box_body_structure_points,
    _profile_geometry,
    folded_profile_segment_center_from_envelope,
    folded_profile_segment_center_from_full_envelope,
    _profile_segment_index,
    _profile_map,
    _profile_flat_map,
    _fold_mask_for_cross_coordinate,
    _profile_map_with_guides,
    folded_mesh_from_polygon,
    folded_world_mesh_from_render_data,
)

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



def _mating_vec_sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _mating_vec_add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _mating_vec_scale(v, k):
    return tuple(float(v[i]) * float(k) for i in range(3))


def _mating_dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _mating_cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _mating_normalize(v):
    import math

    mag = math.sqrt(sum(float(value) * float(value) for value in v))
    if mag <= 1e-12:
        raise ValueError("physical mating-region direction is degenerate")
    return tuple(float(value) / mag for value in v)


def _physical_face_plane_section_polygon(
    triangles,
    *,
    plane_point,
    plane_normal,
    numerical_tolerance=None,
):
    """Section a true-solid surface on one semantic plane into one bounded face.

    The plane itself comes from owner semantics plus authoritative placement.
    This helper only performs numerical surface/plane sectioning; its tolerance
    comes from the canonical T1 assembly-geometry owner and is not a product clearance.
    """
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    if numerical_tolerance is None:
        from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
        numerical_tolerance = (
            PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
        )
    tol = max(float(numerical_tolerance), 1e-12)
    origin = tuple(float(v) for v in plane_point)
    normal = _mating_normalize(plane_normal)
    segments = []

    def signed_distance(point):
        return _mating_dot(_mating_vec_sub(point, origin), normal)

    def close(a, b):
        return all(abs(float(a[i]) - float(b[i])) <= tol for i in range(3))

    for raw in tuple(triangles or ()):
        tri = tuple(tuple(float(v) for v in p) for p in raw[:3])
        if len(tri) != 3:
            continue
        distances = tuple(signed_distance(p) for p in tri)
        if all(abs(value) <= tol for value in distances):
            segments.extend(((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])))
            continue

        intersections = []
        for index in range(3):
            a = tri[index]
            b = tri[(index + 1) % 3]
            da = distances[index]
            db = distances[(index + 1) % 3]
            if abs(da) <= tol and abs(db) <= tol:
                segments.append((a, b))
                continue
            if abs(da) <= tol:
                intersections.append(a)
            if abs(db) <= tol:
                intersections.append(b)
            if da * db < 0.0:
                ratio = da / (da - db)
                intersections.append(tuple(
                    float(a[i]) + ratio * (float(b[i]) - float(a[i]))
                    for i in range(3)
                ))

        unique = []
        for point in intersections:
            if not any(close(point, seen) for seen in unique):
                unique.append(point)
        if len(unique) == 2 and not close(unique[0], unique[1]):
            segments.append((unique[0], unique[1]))

    nonzero = [
        pair for pair in segments
        if not close(pair[0], pair[1])
    ]
    if not nonzero:
        raise ValueError("semantic mating plane does not section the true-thickness solid")

    axis_u = _mating_normalize(_mating_vec_sub(nonzero[0][1], nonzero[0][0]))
    axis_v = _mating_normalize(_mating_cross(normal, axis_u))

    def project(point):
        delta = _mating_vec_sub(point, origin)
        return (_mating_dot(delta, axis_u), _mating_dot(delta, axis_v))

    lines = [LineString((project(a), project(b))) for a, b in nonzero]
    polygons = tuple(polygonize(unary_union(lines)))
    if not polygons:
        raise ValueError("semantic mating plane section did not produce a bounded physical face")

    face = unary_union(polygons)
    if str(getattr(face, "geom_type", "")) != "Polygon":
        raise ValueError(
            "semantic mating region must resolve to exactly one connected physical face"
        )
    if float(getattr(face, "area", 0.0)) <= tol * tol:
        raise ValueError("semantic mating region physical face has zero area")

    coords = tuple(face.exterior.coords)
    world = []
    for x, y in coords[:-1]:
        point = _mating_vec_add(
            origin,
            _mating_vec_add(
                _mating_vec_scale(axis_u, float(x)),
                _mating_vec_scale(axis_v, float(y)),
            ),
        )
        world.append(tuple(float(v) for v in point))
    if len(world) < 3:
        raise ValueError("semantic mating region polygon is degenerate")
    return tuple(world)


def resolve_physical_mating_region(
    *,
    part_id,
    semantic,
    render_data,
    x_profile,
    y_profile,
    placement,
    dimensions,
    offset=(0.0, 0.0, 0.0),
    sheet_thickness,
):
    """Resolve an owner-published semantic region to its actual world physical face.

    T0 deliberately supports the first required neutral case: a longitudinal-Y
    terminal boundary wall such as Inner Door Frame LOWER_TERMINAL_FACE.  The
    face is sectioned from the real true-thickness solid.  No bbox extrema,
    renderer coordinates, collision probes, or fixture values select the region.
    """
    from .contracts import ResolvedPhysicalMatingRegion

    stable_id = str(part_id or "").strip()
    if not stable_id:
        raise ValueError("physical mating region requires stable part_id")
    if semantic is None:
        raise ValueError("physical mating region requires owner-published semantic")
    t = float(sheet_thickness or 0.0)
    if t <= 0.0:
        raise ValueError("physical mating region requires true sheet thickness > 0")

    axis = str(getattr(semantic, "flat_boundary_axis", "") or "").strip().upper()
    side = str(getattr(semantic, "flat_boundary_side", "") or "").strip().upper()
    face_kind = str(getattr(semantic, "physical_face_kind", "") or "").strip()
    if face_kind != "TERMINAL_BOUNDARY_WALL":
        raise ValueError(f"unsupported physical mating face kind: {face_kind!r}")
    if axis != "Y":
        raise ValueError("T0 terminal boundary-wall resolver currently requires flat Y ownership")
    if side not in {"MIN", "MAX"}:
        raise ValueError(f"unsupported terminal boundary side: {side!r}")

    mapped = tuple(folded_mesh_with_flat_uv_from_polygon(
        render_data.material,
        x_profile,
        y_profile,
        fold_guides=tuple(getattr(render_data, "fold_guides", ()) or ()),
    ))
    if not mapped:
        raise ValueError("physical mating region cannot resolve empty folded material")
    mid_triangles = tuple(tuple(row.local) for row in mapped)

    total_y = sum(float(_segment_value(row, "len", 0.0) or 0.0) for row in tuple(y_profile or ()))
    boundary_value = 0.0 if side == "MIN" else float(total_y)
    from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
    numerical_tolerance = (
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    )

    witnesses = []
    for row in mapped:
        for flat, local in zip(tuple(row.flat), tuple(row.local)):
            if abs(float(flat[1]) - boundary_value) <= numerical_tolerance:
                witnesses.append(tuple(float(v) for v in local))
    if not witnesses:
        raise ValueError("owner semantic terminal boundary is absent from canonical folded topology")
    witness_local = witnesses[0]

    flat_normal = tuple(float(v) for v in getattr(semantic, "flat_outward_normal", ()))
    if len(flat_normal) != 2 or abs(flat_normal[0]) > numerical_tolerance:
        raise ValueError("T0 Y-terminal semantic requires flat outward normal parallel to Y")
    if abs(flat_normal[1]) <= numerical_tolerance:
        raise ValueError("owner semantic terminal outward normal is degenerate")
    expected_sign = -1.0 if side == "MIN" else 1.0
    if flat_normal[1] * expected_sign <= 0.0:
        raise ValueError("owner semantic terminal outward normal disagrees with boundary side")

    local_normal = (0.0, expected_sign, 0.0)
    normal_probe = (
        witness_local,
        _mating_vec_add(witness_local, local_normal),
    )
    world_probe = place_assembly_points(
        normal_probe,
        mid_triangles,
        placement,
        dimensions,
        offset,
    )
    if len(world_probe) != 2:
        raise ValueError("authoritative placement could not resolve mating-region normal")
    world_normal = _mating_normalize(_mating_vec_sub(world_probe[1], world_probe[0]))
    plane_point = tuple(float(v) for v in world_probe[0])

    solid_local = tuple(thicken_triangle_surface(
        mid_triangles, t, tolerance=numerical_tolerance
    ))
    solid_points = [point for tri in solid_local for point in tri[:3]]
    placed_points = place_assembly_points(
        solid_points,
        mid_triangles,
        placement,
        dimensions,
        offset,
    )
    solid_world = tuple(
        tuple(placed_points[index:index + 3])
        for index in range(0, len(placed_points), 3)
    )
    world_polygon = _physical_face_plane_section_polygon(
        solid_world,
        plane_point=plane_point,
        plane_normal=world_normal,
        numerical_tolerance=numerical_tolerance,
    )

    return ResolvedPhysicalMatingRegion(
        part_id=stable_id,
        region_id=str(getattr(semantic, "region_id", "") or ""),
        region_role=str(getattr(semantic, "region_role", "") or ""),
        physical_face_kind=face_kind,
        supporting_plane=(plane_point, world_normal),
        outward_normal=world_normal,
        world_polygon=world_polygon,
        flat_mapping=None,
        provenance={
            "source": "OWNER_SEMANTIC_FINAL_MATERIAL_TRUE_SOLID_ASSEMBLY_PLACEMENT",
            "semantic_owner": str(getattr(type(semantic), "__module__", "") or ""),
            "semantic_type": str(getattr(type(semantic), "__name__", "") or ""),
            "flat_boundary_axis": axis,
            "flat_boundary_side": side,
            "true_thickness": t,
            "mapping_status": "BOUNDARY_WALL_WORLD_FACE_ONLY",
        },
    )

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
