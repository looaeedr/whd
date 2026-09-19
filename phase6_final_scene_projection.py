# -*- coding: utf-8 -*-
"""Pure Final Scene geometry/projection helpers for Phase 4 T5.

This module owns calculation and projection only. It does not mutate renderer
axes/canvas, own Tk/UI state, import the bridge, or invoke application owners.
"""
from __future__ import annotations

from ae_engine.display_dimensions import folded_outside_envelope
from phase6_final_scene_contracts import AssemblySceneRenderData
from phase6_fold_profiles import _num, engine_segment_length_to_ui


def _phase6_profile_base_index(profile):
    """Return the semantic finished-face/core segment used as the 3D base plane."""
    segs = list(profile or ())
    if not segs:
        return 0
    # Prefer explicit W-piece/back cores when a multi-piece Box Body is being
    # rendered. A right W-split piece can also carry the legacy D core, so the
    # old "middle core" heuristic would incorrectly make the side face the base.
    for preferred in ("W_PART", "W_BACK", "W"):
        for i, seg in enumerate(segs):
            if str(seg.get("core") or "") == preferred:
                return i
    core_indices = [i for i, seg in enumerate(segs) if seg.get("core")]
    if core_indices:
        return core_indices[len(core_indices) // 2]
    return min(len(segs) - 1, len(segs) // 2)


def _phase6_profile_geometry(profile, *, enabled_folds=None):
    """Return cumulative unfolded boundaries and folded endpoints.

    ``enabled_folds[i]`` controls only the bend after segment ``i``.  This is
    how finite manufacturing BEND spans can leave a retained tongue attached
    while later folds in the same axis still occur.
    """
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
    for i, seg in enumerate(segs):
        length = max(0.0, float(_num(seg.get("len", 0.0))))
        angles.append(current_angle)
        rad = math.radians(current_angle)
        raw_u.append(raw_u[-1] + length * math.cos(rad))
        raw_z.append(raw_z[-1] + length * math.sin(rad))
        cumulative.append(cumulative[-1] + length)
        if i < len(segs) - 1 and "angle" in seg:
            if i >= len(enabled_folds) or enabled_folds[i]:
                current_angle -= float(_num(seg.get("angle", 0.0)))

    base_idx = _phase6_profile_base_index(segs)
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


def _phase6_fold_mask_for_cross_coordinate(profile, axis, cross_position, fold_guides, *, tol=1e-6):
    """Return one enabled/disabled flag per profile bend using final BEND spans."""
    segs = list(profile or ())
    boundaries = [0.0]
    for seg in segs:
        boundaries.append(boundaries[-1] + max(0.0, float(_num(seg.get("len", 0.0)))))
    guides = tuple(g for g in (fold_guides or ()) if str(getattr(g, "axis", "")) == str(axis))
    mask = []
    cross = float(cross_position)
    for i in range(max(0, len(segs) - 1)):
        boundary = boundaries[i + 1]
        matches = [g for g in guides if abs(float(g.position) - boundary) <= tol]
        if not matches:
            # Custom/legacy scenes without an explicit matching BEND keep the
            # editor profile behavior instead of silently dropping a fold.
            mask.append(True)
            continue
        mask.append(any(float(g.span_start) - tol <= cross <= float(g.span_end) + tol for g in matches))
    return tuple(mask)


def _phase6_profile_map_with_guides(position, cross_position, profile, *, axis, fold_guides):
    mask = _phase6_fold_mask_for_cross_coordinate(profile, axis, cross_position, fold_guides)
    boundaries, folded = _phase6_profile_geometry(profile, enabled_folds=mask)
    return _phase6_profile_map(position, boundaries, folded)


def _phase6_profile_map(position, boundaries, folded):
    """Map one unfolded scalar to a folded cross-section coordinate (u, z)."""
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


def _phase6_profile_flat_map(position, boundaries, *, profile=None):
    """Map one unfolded scalar onto the semantic unbent base plane."""
    seg_count = max(1, len(boundaries) - 1)
    base_idx = _phase6_profile_base_index(profile) if profile is not None else min(seg_count - 1, seg_count // 2)
    center = (float(boundaries[base_idx]) + float(boundaries[base_idx + 1])) / 2.0
    return float(position) - center, 0.0


def _phase6_folded_mesh_from_polygon(
    material, x_profile, y_profile, *, fold_exemptions=(), fold_guides=()
):
    """Compatibility wrapper around shared manufacturing-space folding."""
    from ae_engine.assembly_geometry import folded_mesh_from_polygon

    return list(folded_mesh_from_polygon(
        material,
        x_profile,
        y_profile,
        fold_exemptions=fold_exemptions,
        fold_guides=fold_guides,
    ))


def _phase6_mesh_feature_segments(triangles, *, tolerance=1e-6):
    """Return physical solid edges that are visible geometric features.

    Coplanar triangulation diagonals are excluded.  Boundary edges and shared
    edges whose adjacent face normals are non-coplanar are retained.  On a
    thickened formed sheet this yields the actual outer/inner hole rims, sheet
    perimeter, bend/miter edges, and thickness corners on the physical skins.
    """
    import math
    from collections import defaultdict

    inv_tol = 1.0 / max(float(tolerance), 1e-12)

    def key(point):
        return tuple(int(round(float(v) * inv_tol)) for v in point)

    def normal(tri):
        a, b, c = tri[:3]
        ux, uy, uz = (float(b[i]) - float(a[i]) for i in range(3))
        vx, vy, vz = (float(c[i]) - float(a[i]) for i in range(3))
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        mag = math.sqrt(nx * nx + ny * ny + nz * nz)
        if mag <= 1e-12:
            return None
        return (nx / mag, ny / mag, nz / mag)

    edges = defaultdict(list)
    original = {}
    for tri in triangles or ():
        if len(tri) < 3:
            continue
        n = normal(tri)
        if n is None:
            continue
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            ka, kb = key(a), key(b)
            edge = (ka, kb) if ka <= kb else (kb, ka)
            edges[edge].append(n)
            original[ka] = tuple(float(v) for v in a)
            original[kb] = tuple(float(v) for v in b)

    segments = []
    for edge, normals in edges.items():
        visible = len(normals) == 1
        if not visible and len(normals) >= 2:
            base = normals[0]
            visible = any(
                abs(sum(base[i] * other[i] for i in range(3))) < 1.0 - 1e-6
                for other in normals[1:]
            )
        if visible:
            segments.append((original[edge[0]], original[edge[1]]))
    return tuple(segments)


def _phase6_fitted_limits_from_vertices(vertices, padding=0.06):
    """Fit each model axis independently instead of forcing a max_b cube."""
    pts = list(vertices or ())
    if not pts:
        return ((-50.0, 50.0), (-50.0, 50.0), (-50.0, 50.0))
    axes = list(zip(*pts))
    limits = []
    largest = max(max(a) - min(a) for a in axes)
    minimum_span = max(1.0, largest * 0.01)
    for values in axes:
        lo, hi = float(min(values)), float(max(values))
        span = max(hi - lo, minimum_span)
        center = (lo + hi) / 2.0
        half = span * (0.5 + float(padding))
        limits.append((center - half, center + half))
    return tuple(limits)


def _phase6_scene_fold_boundaries(scene, material):
    """Use final BEND primitives as unfolded fold positions."""
    from ae_engine.sheetmetal_drawing import LinePrimitive
    minx, miny, maxx, maxy = (float(v) for v in material.bounds)
    xs, ys = [], []
    for primitive in getattr(scene, "primitives", ()):
        if not isinstance(primitive, LinePrimitive) or str(getattr(primitive, "layer", "")).upper() != "BEND":
            continue
        x1, y1 = float(primitive.p1.x), float(primitive.p1.y)
        x2, y2 = float(primitive.p2.x), float(primitive.p2.y)
        if abs(x1 - x2) <= 1e-6 and minx + 1e-7 < x1 < maxx - 1e-7:
            xs.append((x1 + x2) / 2.0)
        elif abs(y1 - y2) <= 1e-6 and miny + 1e-7 < y1 < maxy - 1e-7:
            ys.append((y1 + y2) / 2.0)

    def uniq(values):
        out = []
        for value in sorted(values):
            if not out or abs(value - out[-1]) > 1e-6:
                out.append(value)
        return out

    return (tuple([minx] + uniq(xs) + [maxx]), tuple([miny] + uniq(ys) + [maxy]))


def _phase6_profile_to_scene_boundaries(profile, boundaries):
    """Keep only bend angles from UI; material segment lengths come from final BENDs."""
    segs = [dict(seg) for seg in (profile or ())]
    if len(segs) != len(boundaries) - 1:
        return segs
    for i, seg in enumerate(segs):
        seg["len"] = float(boundaries[i + 1]) - float(boundaries[i])
        seg.pop("ui_len_add", None)
    return segs


def _phase6_fold_ownership_exemptions(material, xb, yb):
    """Infer double-fold corner ownership from final CUTTING topology only.

    Material in a corner fold cell that touches only the horizontal outside edge
    belongs to the top/bottom flange and must not also receive the X fold.  The
    vertical-only case analogously suppresses the Y fold.
    """
    from shapely.geometry import box, LineString

    if len(xb) < 3 or len(yb) < 3:
        return []
    x0, x1, xr1, xr0 = map(float, (xb[0], xb[1], xb[-2], xb[-1]))
    y0, y1, yt1, yt0 = map(float, (yb[0], yb[1], yb[-2], yb[-1]))
    specs = (
        (box(x0, y0, x1, y1), LineString(((x0, y0), (x0, y1))), LineString(((x0, y0), (x1, y0)))),
        (box(xr1, y0, xr0, y1), LineString(((xr0, y0), (xr0, y1))), LineString(((xr1, y0), (xr0, y0)))),
        (box(x0, yt1, x1, yt0), LineString(((x0, yt1), (x0, yt0))), LineString(((x0, yt0), (x1, yt0)))),
        (box(xr1, yt1, xr0, yt0), LineString(((xr0, yt1), (xr0, yt0))), LineString(((xr1, yt0), (xr0, yt0)))),
    )

    def polygon_parts(geom):
        if geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            return [geom] if geom.area > 1e-9 else []
        return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "Polygon" and g.area > 1e-9]

    out = []
    tol = 1e-7
    for cell, vertical_edge, horizontal_edge in specs:
        for piece in polygon_parts(material.intersection(cell)):
            touches_v = piece.boundary.intersection(vertical_edge).length > tol
            touches_h = piece.boundary.intersection(horizontal_edge).length > tol
            if touches_h and not touches_v:
                out.append(("x", piece))
            elif touches_v and not touches_h:
                out.append(("y", piece))
    return out


def _default_number_text(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    nearest_int = round(number)
    if abs(number - nearest_int) <= 1e-9:
        return str(int(nearest_int))
    return str(number)


def _phase6_folded_outside_envelope(triangles, thickness):
    """Compatibility wrapper around the shared 2D/3D dimension provider."""
    return folded_outside_envelope(triangles, thickness)


def _phase6_profile_operator_fold_values(profile):
    out = []
    for seg in profile or ():
        if seg.get("core"):
            continue
        try:
            out.append(float(engine_segment_length_to_ui(seg)))
        except Exception:
            out.append(float(_num(seg.get("len", 0.0))))
    return out


def _phase6_contract_profile_rows(profile):
    rows = []
    for seg in profile or ():
        row = {"len": float(getattr(seg, "length", 0.0))}
        angle = getattr(seg, "angle", None)
        if angle is not None:
            row["angle"] = float(angle)
        core = getattr(seg, "core", None)
        if core:
            row["core"] = str(core)
        key = getattr(seg, "phase6_key", None)
        if key:
            row["phase6_key"] = str(key)
        rows.append(row)
    return rows


def _phase6_box_body_piece_world_mapper(piece, *, total_w, thickness, x_profile):
    """Compatibility adapter to the shared assembly-geometry role transform."""
    from ae_engine.assembly_geometry import place_box_body_structure_points

    def world(point):
        placed = place_box_body_structure_points(
            (point,), piece, total_w=total_w, thickness=thickness, x_profile=x_profile
        )
        return placed[0]
    return world


def _phase6_box_body_piece_dimension_lines(render_data) -> tuple[str, ...]:
    """Operator text for each authoritative physical Box Body piece."""
    labels = {
        "left_side": "左側板", "back": "後面板", "right_side": "右側板",
        "left": "左箱身", "middle": "中箱身", "right": "右箱身",
    }
    rows = []
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        label = labels.get(str(getattr(piece, "role", "") or ""), "箱身板件")
        fw, fh = tuple(float(v) for v in piece.formed_outer_dimensions)
        bw, bh = tuple(float(v) for v in piece.material_dimensions)
        rows.append(
            f"{label}：成形 {_default_number_text(fw)} × {_default_number_text(fh)} mm；"
            f"展開 {_default_number_text(bw)} × {_default_number_text(bh)} mm"
        )
    return tuple(rows)


def _phase6_box_body_structure_meshes(render_data, *, thickness):
    """Return assembled Box Body structure meshes in structure-local coordinates."""
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if not pieces:
        return []
    total_w = max(float(getattr(p, "formed_w_end", 0.0)) for p in pieces)
    out = []

    for piece in pieces:
        data = piece.render_data
        x_profile = _phase6_contract_profile_rows(piece.fold_profile)
        minx, miny, maxx, maxy = map(float, data.material.bounds)
        y_profile = [{"len": maxy - miny}]
        local = _phase6_folded_mesh_from_polygon(
            data.material, x_profile, y_profile,
            fold_guides=tuple(getattr(data, "fold_guides", ()) or ()),
        )
        world = _phase6_box_body_piece_world_mapper(
            piece, total_w=total_w, thickness=thickness, x_profile=x_profile
        )
        transformed = [tuple(world(point) for point in tri) for tri in local]
        out.append((piece, tuple(transformed)))
    return out


def format_operator_info_text(request, *, dimensions=None, number_text=None):
    """Format already-resolved operator display information for every View sink."""
    number_text = number_text or _default_number_text
    dims = tuple(dimensions or getattr(request, "finished_dimensions", ()) or ())
    if len(dims) < 2:
        return ""
    width, height = dims[:2]
    depth = dims[2] if len(dims) > 2 else None
    xfold = " / ".join(number_text(v) for v in _phase6_profile_operator_fold_values(request.x_profile)) or "-"
    yfold = " / ".join(number_text(v) for v in _phase6_profile_operator_fold_values(request.y_profile)) or "-"
    finished = (
        f"折後包外：W {number_text(width)} × H {number_text(height)} × D {number_text(depth)} mm"
        if depth is not None else
        f"折後包外：W {number_text(width)} × H {number_text(height)} mm"
    )
    lines = [finished, f"X折：{xfold}   Y折：{yfold}"]
    if request.corner_dimension_text:
        lines.append(request.corner_dimension_text)
    if request.unfolded_blank_text:
        lines.append(request.unfolded_blank_text)
    if str(getattr(request, "part_key", "") or "") == "box_body":
        lines.extend(_phase6_box_body_piece_dimension_lines(getattr(request, "render_data", None)))
    return "\n".join(lines)


def _phase6_triangle_bounds(triangles):
    from ae_engine.assembly_geometry import triangle_bounds

    return triangle_bounds(triangles)


def _phase6_place_assembly_triangles(triangles, placement, dimensions, offset):
    """Compatibility wrapper around the shared assembly-space transform."""
    from ae_engine.assembly_geometry import place_assembly_triangles

    return place_assembly_triangles(triangles, placement, dimensions, offset)


def make_assembly_scene_render_data(
    *,
    assembly_parts,
    visible_part_keys=None,
    visible_box_body_piece_keys=None,
    show_interference=False,
    ignore_fixed_corner_relief=False,
    interference_probe_parts=(),
    joint_diagnostics=(),
    selected_joint_id=None,
    preserve_endcap_core_origin=False,
    render_data_cls=None,
):
    """Construct the UI-only assembly bundle across old/new view contracts."""
    from inspect import Parameter, signature

    cls = render_data_cls or AssemblySceneRenderData
    values = {
        "assembly_parts": tuple(assembly_parts),
        "visible_part_keys": (
            None
            if visible_part_keys is None
            else tuple(str(key) for key in visible_part_keys)
        ),
        "visible_box_body_piece_keys": (
            None
            if visible_box_body_piece_keys is None
            else tuple(str(key) for key in visible_box_body_piece_keys)
        ),
        "show_interference": bool(show_interference),
        "ignore_fixed_corner_relief": bool(ignore_fixed_corner_relief),
        "interference_probe_parts": tuple(interference_probe_parts or ()),
        "joint_diagnostics": tuple(joint_diagnostics or ()),
        "selected_joint_id": (
            None if selected_joint_id is None else str(selected_joint_id)
        ),
        "preserve_endcap_core_origin": bool(preserve_endcap_core_origin),
    }
    try:
        params = signature(cls).parameters
    except (TypeError, ValueError):
        params = {}
    accepts_kwargs = any(
        parameter.kind is Parameter.VAR_KEYWORD
        for parameter in params.values()
    )
    if accepts_kwargs:
        kwargs = values
    else:
        if (
            "visible_part_keys" not in params
            and values["visible_part_keys"] is not None
        ):
            visible = set(values["visible_part_keys"])
            values["assembly_parts"] = tuple(
                part
                for part in values["assembly_parts"]
                if str(getattr(part, "part_key", "")) in visible
            )
        kwargs = {
            key: value
            for key, value in values.items()
            if key in params
        }
        kwargs.setdefault("assembly_parts", values["assembly_parts"])
    return cls(**kwargs)


__all__ = [
    '_phase6_profile_base_index',
    '_phase6_profile_geometry',
    '_phase6_fold_mask_for_cross_coordinate',
    '_phase6_profile_map_with_guides',
    '_phase6_profile_map',
    '_phase6_profile_flat_map',
    '_phase6_folded_mesh_from_polygon',
    '_phase6_mesh_feature_segments',
    '_phase6_fitted_limits_from_vertices',
    '_phase6_scene_fold_boundaries',
    '_phase6_profile_to_scene_boundaries',
    '_phase6_fold_ownership_exemptions',
    '_default_number_text',
    '_phase6_folded_outside_envelope',
    '_phase6_profile_operator_fold_values',
    '_phase6_contract_profile_rows',
    '_phase6_box_body_piece_world_mapper',
    '_phase6_box_body_piece_dimension_lines',
    '_phase6_box_body_structure_meshes',
    'format_operator_info_text',
    '_phase6_triangle_bounds',
    '_phase6_place_assembly_triangles',
    'make_assembly_scene_render_data'
]
