# -*- coding: utf-8 -*-
"""Fold-profile mapping and folded-mesh construction for assembly geometry."""
from __future__ import annotations

from .assembly_geometry_primitives import place_assembly_points, place_assembly_triangles

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
    formed_y_offset = float(getattr(piece, "formed_y_offset", 0.0) or 0.0)

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
            return tuple((float(p[0]) + center, float(p[1]) + formed_y_offset, t) for p in (points or ()))
        return tuple((float(p[0]) + center, float(p[1]) + formed_y_offset, float(p[2])) for p in (points or ()))

    if role in {"left_side", "right_side"}:
        base_index = _profile_base_index(x_profile)
        segs = list(x_profile or ())
        base_len = _as_float(_segment_value(segs[base_index], "len", 0.0)) if segs else 0.0
        d_half = base_len / 2.0
        if role == "left_side":
            return tuple((
                -w_material_half + float(p[2]), float(p[1]) + formed_y_offset, d_half - float(p[0])
            ) for p in (points or ()))
        return tuple((
            w_material_half - float(p[2]), float(p[1]) + formed_y_offset, float(p[0]) + d_half
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
        length = max(0.0, _as_float(
            _segment_value(seg, "length", _segment_value(seg, "len", 0.0))
        ))
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


def folded_profile_segment_center_from_envelope(profile, segment_index: int) -> tuple[float, float]:
    """Return one folded segment midpoint relative to the folded-profile envelope center.

    Phase6 assembly placement recenters non-EndCap meshes from folded mesh
    bounds before applying the semantic world offset. For a strip profile,
    the longitudinal folded envelope is the endpoint envelope returned by
    _profile_geometry. This exposes that same relative coordinate without
    inventing a cabinet/world constant.
    """
    segs = list(profile or ())
    index = int(segment_index)
    if index < 0 or index >= len(segs):
        raise ValueError("folded profile segment index is outside the fold chain")
    _boundaries, folded = _profile_geometry(segs)
    if len(folded) != len(segs) + 1:
        raise ValueError("folded profile geometry is incomplete")
    u0, z0 = folded[index]
    u1, z1 = folded[index + 1]
    min_u = min(float(point[0]) for point in folded)
    max_u = max(float(point[0]) for point in folded)
    envelope_mid_u = (min_u + max_u) / 2.0
    return (
        (float(u0) + float(u1)) / 2.0 - envelope_mid_u,
        (float(z0) + float(z1)) / 2.0,
    )

def folded_profile_segment_center_from_full_envelope(
    profile,
    segment_index: int,
) -> tuple[float, float]:
    """Return one semantic folded segment midpoint in the same centered local frame as assembly placement.

    place_assembly_points recenters the full folded strip mesh in both folded
    U and folded Z before applying the authoritative placement offset. Contact
    owners that already know the semantic segment identity may use this helper
    to reproduce that exact local frame without selecting a face from a bbox.
    The envelope is therefore a placement-transform detail, not contact authority.
    """
    segs = list(profile or ())
    index = int(segment_index)
    if index < 0 or index >= len(segs):
        raise ValueError("folded profile segment index is outside the fold chain")
    _boundaries, folded = _profile_geometry(segs)
    if len(folded) != len(segs) + 1:
        raise ValueError("folded profile geometry is incomplete")
    u0, z0 = folded[index]
    u1, z1 = folded[index + 1]
    min_u = min(float(point[0]) for point in folded)
    max_u = max(float(point[0]) for point in folded)
    min_z = min(float(point[1]) for point in folded)
    max_z = max(float(point[1]) for point in folded)
    return (
        (float(u0) + float(u1)) / 2.0 - (min_u + max_u) / 2.0,
        (float(z0) + float(z1)) / 2.0 - (min_z + max_z) / 2.0,
    )

def _profile_segment_index(position, boundaries):
    value = float(position)
    total = float(boundaries[-1])
    value = min(max(value, 0.0), total)
    index = len(boundaries) - 2
    for i in range(len(boundaries) - 1):
        if value <= boundaries[i + 1] + 1e-9:
            index = i
            break
    return value, index


def _profile_map(position, boundaries, folded):
    value, index = _profile_segment_index(position, boundaries)
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
