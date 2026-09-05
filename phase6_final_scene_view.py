# -*- coding: utf-8 -*-
"""Phase6 FinalScene 的 3D 顯示深模組。

此模組只消費 manufacturing 已完成的 ``PartRenderData`` 與 Fold Profile。
不得建立 PartSpec、重建 CUTTING material、解析 CornerType，或重新呼叫製造引擎。
"""
from __future__ import annotations

# Complete Matplotlib projection registration before any lazy art3d import.
# Importing mpl_toolkits.mplot3d.art3d first can circularly import
# matplotlib.projections and leave the global registry without Axes3D.
import matplotlib.projections as _matplotlib_projections  # noqa: F401

from phase6_fold_profiles import _num

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


from dataclasses import dataclass
from typing import Callable, Mapping

from phase6_fold_profiles import engine_segment_length_to_ui


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
    """Return compensated outside AABB for the already-folded FinalScene mesh."""
    import math

    tris = [tuple(tri) for tri in (triangles or ()) if len(tuple(tri)) >= 3]
    points = [tuple(float(v) for v in point) for tri in tris for point in tri[:3]]
    if not points:
        return None
    mins = [min(point[axis] for point in points) for axis in range(3)]
    maxs = [max(point[axis] for point in points) for axis in range(3)]
    normal_extent = [0.0, 0.0, 0.0]
    for tri in tris:
        a, b, c = (tuple(float(v) for v in point) for point in tri[:3])
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(c[i] - a[i] for i in range(3))
        n = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        mag = math.sqrt(sum(value * value for value in n))
        if mag <= 1e-12:
            continue
        for axis in range(3):
            normal_extent[axis] = max(normal_extent[axis], abs(n[axis] / mag))
    t = max(0.0, float(_num(thickness, 0.0)))
    bounds = tuple(
        (mins[axis] - t * normal_extent[axis], maxs[axis] + t * normal_extent[axis])
        for axis in range(3)
    )
    dims = tuple(hi - lo for lo, hi in bounds)
    return dims, bounds


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


@dataclass(frozen=True)
class AssemblyScenePart:
    """One authoritative part scene placed into the UI-only assembly view."""

    part_key: str
    render_data: object
    x_profile: tuple[Mapping[str, object], ...]
    y_profile: tuple[Mapping[str, object], ...]
    placement: str = "offset"
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class AssemblySceneRenderData:
    """UI-only bundle of already-built part render data for combined 3D display.

    ``interference_probe_parts`` keeps the pre-solve EndCap geometry used only
    for collision diagnostics.  The visible ``assembly_parts`` may already be
    solved/canonical material; using those solved parts for diagnostics would
    erase the evidence of the collision that caused the relief.
    """

    assembly_parts: tuple[AssemblyScenePart, ...]
    warnings: tuple[object, ...] = ()
    show_interference: bool = False
    ignore_fixed_corner_relief: bool = False
    interference_probe_parts: tuple[AssemblyScenePart, ...] = ()
    joint_diagnostics: tuple[object, ...] = ()
    selected_joint_id: str | None = None
    preserve_endcap_core_origin: bool = False


def _phase6_triangle_bounds(triangles):
    from ae_engine.assembly_geometry import triangle_bounds

    return triangle_bounds(triangles)


def _phase6_place_assembly_triangles(triangles, placement, dimensions, offset):
    """Compatibility wrapper around the shared assembly-space transform."""
    from ae_engine.assembly_geometry import place_assembly_triangles

    return place_assembly_triangles(triangles, placement, dimensions, offset)


@dataclass(frozen=True)
class FinalSceneViewRequest:
    """Already-resolved inputs required to display one FinalScene."""

    render_data: object
    x_profile: tuple[Mapping[str, object], ...]
    y_profile: tuple[Mapping[str, object], ...]
    part_key: str
    alpha_bend: float = 0.85
    finished_dimensions: tuple[float, ...] | None = None
    thickness: float = 2.0
    corner_dimension_text: str | None = None
    unfolded_blank_text: str | None = None


class Phase6FinalSceneView:
    """Deep 3D view module for one authoritative manufacturing FinalScene."""

    _COLORS = {
        "box_body": ("#3b82f6", "#1e40af"),
        "head": ("#10b981", "#047857"),
        "tail": ("#0ea5e9", "#0369a1"),
        "door": ("#8b5cf6", "#5b21b6"),
        "base_plate": ("#f59e0b", "#92400e"),
        "indicator_box": ("#14b8a6", "#0f766e"),
        "indicator_door": ("#ec4899", "#9d174d"),
    }

    def __init__(self, renderer, *, number_text: Callable[[object], str] | None = None):
        self.renderer = renderer
        self._number_text = number_text or _default_number_text
        self.last_cutting_mesh = []
        self.last_cutting_material = None
        self.cutting_mesh_error = None
        self.zoom_scale = 1.0
        self.view_initialized = False
        self.base_renderer_render = None
        self.scroll_cid = None
        self.last_interference_diagnostic = None

    def _remove_original_bend_surfaces(self):
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        for collection in list(getattr(self.renderer.ax3d, "collections", ())):
            if not isinstance(collection, Poly3DCollection):
                continue
            try:
                collection.remove()
            except Exception:
                pass

    def _add_mesh_boundary_lines(self, triangles, color):
        from collections import Counter
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        def key(point):
            return tuple(round(float(v), 6) for v in point)

        edges = Counter()
        original_points = {}
        for tri in triangles:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                ka, kb = key(a), key(b)
                edge = tuple(sorted((ka, kb)))
                edges[edge] += 1
                original_points[ka] = a
                original_points[kb] = b
        segments = []
        for edge, count in edges.items():
            if count == 1:
                segments.append((original_points[edge[0]], original_points[edge[1]]))
        if segments:
            self.renderer.ax3d.add_collection3d(
                Line3DCollection(segments, colors=color, linewidths=1.15)
            )

    def _add_mesh_feature_lines(self, triangles, color):
        """Draw physical skin feature edges as explicit solid lines."""
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        segments = _phase6_mesh_feature_segments(triangles)
        if segments:
            self.renderer.ax3d.add_collection3d(
                Line3DCollection(
                    segments, colors=color, linewidths=1.5, linestyles="solid"
                )
            )

    def _add_mesh_boundary_and_crease_lines(self, triangles, color):
        """Draw formed-sheet perimeter, through-hole edges, and real fold creases.

        A thickened sheet is a closed solid, so its CUTTING-hole perimeter and
        mid-surface fold crease are no longer open mesh boundaries.  Assembly
        rendering therefore derives these diagnostic/visual edges from the
        already-folded authoritative mid-surface before physical thickening.
        Coplanar triangulation diagonals are excluded.
        """
        import math
        from collections import defaultdict
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        def key(point):
            return tuple(round(float(v), 6) for v in point)

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
        original_points = {}
        for tri in triangles or ():
            if len(tri) < 3:
                continue
            n = normal(tri)
            if n is None:
                continue
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                ka, kb = key(a), key(b)
                edge = tuple(sorted((ka, kb)))
                edges[edge].append(n)
                original_points[ka] = a
                original_points[kb] = b

        segments = []
        for edge, normals in edges.items():
            visible = len(normals) == 1
            if not visible and len(normals) >= 2:
                base = normals[0]
                for other in normals[1:]:
                    dot = sum(base[i] * other[i] for i in range(3))
                    if abs(dot) < 1.0 - 1e-6:
                        visible = True
                        break
            if visible:
                segments.append((original_points[edge[0]], original_points[edge[1]]))

        if segments:
            self.renderer.ax3d.add_collection3d(
                Line3DCollection(segments, colors=color, linewidths=1.35, linestyles="solid")
            )

    def _map_xy(self, x, y, x_profile, y_profile, fold_guides):
        if fold_guides:
            ux, zx = _phase6_profile_map_with_guides(
                float(x), float(y), x_profile, axis="x", fold_guides=fold_guides
            )
            uy, zy = _phase6_profile_map_with_guides(
                float(y), float(x), y_profile, axis="y", fold_guides=fold_guides
            )
        else:
            xb, xf = _phase6_profile_geometry(x_profile)
            yb, yf = _phase6_profile_geometry(y_profile)
            ux, zx = _phase6_profile_map(float(x), xb, xf)
            uy, zy = _phase6_profile_map(float(y), yb, yf)
        return (ux, uy, zx + zy)

    def _draw_assembly_box_body_bends(
        self, scene, x_profile, y_profile, fold_guides, local_reference,
        placement, dimensions, offset,
    ):
        """Draw Box Body manufacturing BEND guides in shared assembly coordinates."""
        from ae_engine.sheetmetal_drawing import LinePrimitive
        from ae_engine.assembly_geometry import place_assembly_points

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        for primitive in getattr(scene, "primitives", ()):
            if not isinstance(primitive, LinePrimitive) or str(primitive.layer).upper() != "BEND":
                continue
            local_points = (
                self._map_xy(primitive.p1.x, primitive.p1.y, x_profile, y_profile, fold_guides),
                self._map_xy(primitive.p2.x, primitive.p2.y, x_profile, y_profile, fold_guides),
            )
            world_points = place_assembly_points(
                local_points, local_reference, placement, dimensions, offset
            )
            if len(world_points) != 2:
                continue
            a, b = world_points
            self.renderer.ax3d.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color="#2563eb", linewidth=1.35, linestyle="-", alpha=0.98,
            )

    def _draw_scene_bends(self, scene, x_profile, y_profile, fold_guides=()):
        from ae_engine.sheetmetal_drawing import LinePrimitive

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        for primitive in getattr(scene, "primitives", ()):
            if not isinstance(primitive, LinePrimitive) or str(primitive.layer).upper() != "BEND":
                continue
            a = self._map_xy(primitive.p1.x, primitive.p1.y, x_profile, y_profile, fold_guides)
            b = self._map_xy(primitive.p2.x, primitive.p2.y, x_profile, y_profile, fold_guides)
            self.renderer.ax3d.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color="#2563eb", linewidth=1.15, linestyle="-", alpha=0.95,
            )

    def _draw_box_body_structure_bends(
        self, render_data, *, thickness, local_reference=None,
        placement="box_body", dimensions=None, offset=(0.0, 0.0, 0.0),
    ):
        """Draw every authoritative piece BEND using the same transform as its mesh."""
        from ae_engine.sheetmetal_drawing import LinePrimitive
        from ae_engine.assembly_geometry import place_assembly_points

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        pieces = tuple(getattr(render_data, "pieces", ()) or ())
        if not pieces:
            return
        total_w = max(float(getattr(p, "formed_w_end", 0.0)) for p in pieces)
        for piece in pieces:
            data = piece.render_data
            x_profile = _phase6_contract_profile_rows(piece.fold_profile)
            minx, miny, maxx, maxy = map(float, data.material.bounds)
            y_profile = [{"len": maxy - miny}]
            fold_guides = tuple(getattr(data, "fold_guides", ()) or ())
            world = _phase6_box_body_piece_world_mapper(
                piece, total_w=total_w, thickness=thickness, x_profile=x_profile
            )
            for primitive in getattr(data.scene, "primitives", ()):
                if not isinstance(primitive, LinePrimitive) or str(primitive.layer).upper() != "BEND":
                    continue
                points = (
                    world(self._map_xy(primitive.p1.x, primitive.p1.y, x_profile, y_profile, fold_guides)),
                    world(self._map_xy(primitive.p2.x, primitive.p2.y, x_profile, y_profile, fold_guides)),
                )
                if local_reference is not None:
                    points = place_assembly_points(
                        points, local_reference, placement, dimensions, offset
                    )
                if len(points) != 2:
                    continue
                a, b = points
                self.renderer.ax3d.plot(
                    [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                    color="#2563eb", linewidth=1.35, linestyle="-", alpha=0.98,
                )

    def _draw_scene_markings(self, scene, x_profile, y_profile, fold_guides=()):
        import math
        from ae_engine.sheetmetal_drawing import PolylinePrimitive, CirclePrimitive, LinePrimitive

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        for primitive in getattr(scene, "primitives", ()):
            layer = str(getattr(primitive, "layer", "") or "").upper()
            if layer not in {"MARKING", "BLIND_HOLE"}:
                continue
            paths = []
            if isinstance(primitive, CirclePrimitive):
                pts = []
                for i in range(65):
                    angle = 2.0 * math.pi * i / 64.0
                    pts.append(self._map_xy(
                        float(primitive.center.x) + float(primitive.radius) * math.cos(angle),
                        float(primitive.center.y) + float(primitive.radius) * math.sin(angle),
                        x_profile, y_profile, fold_guides,
                    ))
                paths.append(pts)
            elif isinstance(primitive, LinePrimitive):
                paths.append([
                    self._map_xy(primitive.p1.x, primitive.p1.y, x_profile, y_profile, fold_guides),
                    self._map_xy(primitive.p2.x, primitive.p2.y, x_profile, y_profile, fold_guides),
                ])
            elif isinstance(primitive, PolylinePrimitive):
                pts = [self._map_xy(p.x, p.y, x_profile, y_profile, fold_guides) for p in primitive.points]
                if primitive.closed and pts:
                    pts.append(pts[0])
                paths.append(pts)
            for pts in paths:
                if len(pts) < 2:
                    continue
                self.renderer.ax3d.plot(
                    [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts],
                    color=("#f59e0b" if layer == "MARKING" else "#ef4444"),
                    linewidth=1.0, linestyle=("-" if layer == "MARKING" else "--"), alpha=0.9,
                )

    def _resolved_finished_dimensions(self, request, triangles):
        envelope = _phase6_folded_outside_envelope(triangles, request.thickness)
        if envelope is not None:
            measured, _ = envelope
            if request.part_key == "box_body":
                return tuple(float(v) for v in measured)
            return (float(measured[0]), float(measured[1]))
        return request.finished_dimensions

    def _draw_operator_dimensions(self, request, triangles):
        ax = self.renderer.ax3d
        dims = self._resolved_finished_dimensions(request, triangles)
        if not dims or not all(callable(getattr(ax, name, None)) for name in ("plot", "text", "text2D")):
            return
        width, height = dims[:2]
        depth = dims[2] if len(dims) > 2 else None
        xb, xf = _phase6_profile_geometry(request.x_profile)
        yb, yf = _phase6_profile_geometry(request.y_profile)
        xi = _phase6_profile_base_index(request.x_profile)
        yi = _phase6_profile_base_index(request.y_profile)
        x0, x1 = float(xf[xi][0]), float(xf[xi + 1][0])
        y0, y1 = float(yf[yi][0]), float(yf[yi + 1][0])
        envelope = _phase6_folded_outside_envelope(triangles, request.thickness)
        if envelope is not None:
            _, bounds = envelope
            x0, x1 = bounds[0]
            y0, y1 = bounds[1]
        span = max(abs(x1 - x0), abs(y1 - y0), 1.0)
        off = span * 0.055
        tick = span * 0.012
        wy = min(y0, y1) - off
        hx = min(x0, x1) - off
        ax.plot([x0, x1], [wy, wy], [0.0, 0.0], linewidth=1.0)
        ax.plot([x0, x0], [wy - tick, wy + tick], [0.0, 0.0], linewidth=1.0)
        ax.plot([x1, x1], [wy - tick, wy + tick], [0.0, 0.0], linewidth=1.0)
        ax.text((x0 + x1) / 2.0, wy, 0.0, f"W {self._number_text(width)} mm", ha="center", va="top")
        ax.plot([hx, hx], [y0, y1], [0.0, 0.0], linewidth=1.0)
        ax.plot([hx - tick, hx + tick], [y0, y0], [0.0, 0.0], linewidth=1.0)
        ax.plot([hx - tick, hx + tick], [y1, y1], [0.0, 0.0], linewidth=1.0)
        ax.text(hx, (y0 + y1) / 2.0, 0.0, f"H {self._number_text(height)} mm", ha="right", va="center")
        xfold = " / ".join(self._number_text(v) for v in _phase6_profile_operator_fold_values(request.x_profile)) or "-"
        yfold = " / ".join(self._number_text(v) for v in _phase6_profile_operator_fold_values(request.y_profile)) or "-"
        finished = (
            f"折後包外：W {self._number_text(width)} × H {self._number_text(height)} × D {self._number_text(depth)} mm"
            if depth is not None else
            f"折後包外：W {self._number_text(width)} × H {self._number_text(height)} mm"
        )
        info = f"{finished}\nX折：{xfold}   Y折：{yfold}"
        if request.corner_dimension_text:
            info += f"\n{request.corner_dimension_text}"
        if request.unfolded_blank_text:
            info += f"\n{request.unfolded_blank_text}"
        ax.text2D(0.015, 0.985, info, transform=ax.transAxes, ha="left", va="top")

    def _draw_joint_diagnostic_overlays(self, render_data):
        diagnostics = tuple(getattr(render_data, "joint_diagnostics", ()) or ())
        selected = str(getattr(render_data, "selected_joint_id", "") or "")
        if selected:
            diagnostics = tuple(d for d in diagnostics if str(getattr(d, "joint_id", "")) == selected)
        if not diagnostics:
            return
        from mpl_toolkits.mplot3d.art3d import Line3DCollection
        styles = (
            ("contact_segments", "#22c55e", 2.5, 0.85),
            ("penetration_segments", "#ef4444", 3.2, 0.95),
            ("preserve_segments", "#3b82f6", 2.5, 0.85),
            ("relief_segments", "#eab308", 2.8, 0.9),
        )
        for diag in diagnostics:
            for field, color, width, alpha in styles:
                segments = tuple(
                    segment for segment in tuple(getattr(diag, field, ()) or ())
                    if len(segment) == 2 and all(len(point) >= 3 for point in segment)
                )
                if segments:
                    self.renderer.ax3d.add_collection3d(Line3DCollection(
                        segments, colors=color, linewidths=width, alpha=alpha,
                    ))
            direction = getattr(diag, "direction_segment", None)
            if direction and len(direction) == 2:
                a, b = direction
                dx, dy, dz = (float(b[i]) - float(a[i]) for i in range(3))
                try:
                    self.renderer.ax3d.quiver(
                        float(a[0]), float(a[1]), float(a[2]), dx, dy, dz,
                        color="#a855f7", arrow_length_ratio=0.18, linewidth=2.0,
                    )
                except Exception:
                    pass

    def render(self, request: FinalSceneViewRequest | None):
        if request is None:
            self.last_cutting_mesh = []
            self.last_cutting_material = None
            return []
        render_data = request.render_data
        assembly_parts = tuple(getattr(render_data, "assembly_parts", ()) or ())
        if assembly_parts:
            self._remove_original_bend_surfaces()
            for line in list(getattr(self.renderer.ax3d, "lines", ())):
                try:
                    line.remove()
                except Exception:
                    pass
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            triangles = []
            materials = []
            box_body_piece_dimension_lines = []
            box_body_world = None
            box_body_collision_mesh = None
            interference_targets = []
            interference_points = []
            interference_segments = []
            interference_pairs = 0
            self.last_interference_diagnostic = None
            ax = self.renderer.ax3d
            probe_parts = {
                str(getattr(item, "part_key", "")): item
                for item in tuple(getattr(render_data, "interference_probe_parts", ()) or ())
            }
            for part in assembly_parts:
                part_data = part.render_data
                diagnostic_relief_delta = None
                if getattr(part_data, "pieces", None):
                    piece_meshes = _phase6_box_body_structure_meshes(part_data, thickness=request.thickness)
                    local = [tri for _piece, piece_tris in piece_meshes for tri in piece_tris]
                    part_material = tuple(piece.render_data.material for piece in part_data.pieces)
                    box_body_piece_dimension_lines.extend(_phase6_box_body_piece_dimension_lines(part_data))
                else:
                    part_material = part_data.material
                    fold_material = part_material
                    if (
                        bool(getattr(render_data, "ignore_fixed_corner_relief", False))
                        and str(getattr(part, "part_key", "")) in {"head", "tail"}
                    ):
                        from ae_engine.assembly_geometry import (
                            restore_unrelieved_endcap_material,
                            restored_endcap_relief_delta,
                        )
                        fold_material = restore_unrelieved_endcap_material(part_material)
                        diagnostic_relief_delta = restored_endcap_relief_delta(part_material)
                    local = _phase6_folded_mesh_from_polygon(
                        fold_material,
                        tuple(dict(seg) for seg in part.x_profile),
                        tuple(dict(seg) for seg in part.y_profile),
                        fold_guides=tuple(getattr(part_data, "fold_guides", ()) or ()),
                    )
                placement = str(getattr(part, "placement", "offset") or "offset")
                offset = getattr(part, "offset", (0.0, 0.0, 0.0))
                formed_surface_for_edges = None
                if placement in {"top", "head", "bottom", "tail"} and box_body_world:
                    from ae_engine.assembly_geometry import (
                        place_endcap_against_box_body,
                        thicken_triangle_surface,
                    )
                    # EndCaps are physical sheet, not a zero-thickness mid-surface.
                    # Shift the semantic mid-plane outward by T/2 so the inside
                    # skin mates the Box Body, then build both formed skins +
                    # boundary/fold walls from the shared folded surface.
                    mate_kwargs = {"sheet_thickness": request.thickness}
                    if bool(getattr(render_data, "preserve_endcap_core_origin", False)):
                        mate_kwargs["preserve_core_origin"] = True
                    placed_surface = place_endcap_against_box_body(
                        local, placement, box_body_world, offset, **mate_kwargs
                    )
                    formed_surface_for_edges = placed_surface
                    placed = thicken_triangle_surface(
                        placed_surface, request.thickness
                    )
                else:
                    placed = _phase6_place_assembly_triangles(
                        local, placement, request.finished_dimensions, offset
                    )
                if not placed:
                    continue
                part_key = str(getattr(part, "part_key", ""))
                if part_key == "box_body":
                    box_body_world = tuple(placed)
                    if getattr(part_data, "pieces", None):
                        self._draw_box_body_structure_bends(
                            part_data, thickness=request.thickness, local_reference=local,
                            placement=placement, dimensions=request.finished_dimensions, offset=offset,
                        )
                    else:
                        self._draw_assembly_box_body_bends(
                            part_data.scene,
                            tuple(dict(seg) for seg in part.x_profile),
                            tuple(dict(seg) for seg in part.y_profile),
                            tuple(getattr(part_data, "fold_guides", ()) or ()),
                            local, placement, request.finished_dimensions, offset,
                        )
                    if bool(getattr(render_data, "show_interference", False)):
                        from ae_engine.assembly_geometry import thicken_triangle_surface
                        if getattr(part_data, "pieces", None):
                            collision = []
                            for _piece, piece_tris in piece_meshes:
                                collision.extend(thicken_triangle_surface(piece_tris, request.thickness))
                            box_body_collision_mesh = tuple(collision)
                        else:
                            box_body_collision_mesh = thicken_triangle_surface(
                                box_body_world, request.thickness
                            )
                elif (
                    bool(getattr(render_data, "show_interference", False))
                    and box_body_collision_mesh
                    and part_key in {"head", "tail"}
                ):
                    from ae_engine.assembly_geometry import (
                        detect_world_mesh_surface_interference,
                        place_endcap_against_box_body,
                        thicken_triangle_surface,
                    )
                    # Collision diagnostics must use the pre-solve EndCap probe,
                    # never the already-relieved display material.  We still probe
                    # only the fixed-relief delta so intended mating seams on the full
                    # sheet are not reported as broad false positives.
                    collision_target = ()
                    probe_part = probe_parts.get(part_key)
                    probe_data = getattr(probe_part, "render_data", None) if probe_part is not None else None
                    if probe_data is not None and getattr(probe_data, "material", None) is not None:
                        from ae_engine.assembly_geometry import restored_endcap_relief_delta
                        delta_material = restored_endcap_relief_delta(probe_data.material)
                        probe_x = tuple(dict(seg) for seg in getattr(probe_part, "x_profile", ()) or ())
                        probe_y = tuple(dict(seg) for seg in getattr(probe_part, "y_profile", ()) or ())
                        probe_guides = tuple(getattr(probe_data, "fold_guides", ()) or ())
                    elif bool(getattr(render_data, "ignore_fixed_corner_relief", False)):
                        delta_material = diagnostic_relief_delta
                        probe_x = tuple(dict(seg) for seg in part.x_profile)
                        probe_y = tuple(dict(seg) for seg in part.y_profile)
                        probe_guides = tuple(getattr(part_data, "fold_guides", ()) or ())
                    else:
                        delta_material = None
                        probe_x = probe_y = probe_guides = ()
                    if delta_material is not None and not getattr(delta_material, "is_empty", True):
                        delta_local = _phase6_folded_mesh_from_polygon(
                            delta_material, probe_x, probe_y, fold_guides=probe_guides,
                        )
                        probe_mate_kwargs = {"sheet_thickness": request.thickness}
                        if bool(getattr(render_data, "preserve_endcap_core_origin", False)):
                            probe_mate_kwargs["preserve_core_origin"] = True
                        delta_surface = place_endcap_against_box_body(
                            delta_local, placement, box_body_world, offset, **probe_mate_kwargs
                        )
                        collision_target = thicken_triangle_surface(
                            delta_surface, request.thickness
                        )
                    diagnostic = detect_world_mesh_surface_interference(
                        box_body_collision_mesh, collision_target
                    ) if collision_target else None
                    if diagnostic is not None and diagnostic.has_interference:
                        interference_targets.extend(diagnostic.target_triangles)
                        interference_points.extend(diagnostic.intersection_points)
                        interference_segments.extend(diagnostic.intersection_segments)
                        interference_pairs += int(diagnostic.pair_count)
                face, edge = self._COLORS.get(str(part.part_key), ("#64748b", "#334155"))
                poly = Poly3DCollection(
                    placed,
                    alpha=float(request.alpha_bend),
                    facecolor=face,
                    edgecolor="none",
                    linewidths=0.0,
                )
                ax.add_collection3d(poly)
                if formed_surface_for_edges is not None:
                    # The folded mid-surface sits inside the physical T-thick
                    # sheet and can be depth-occluded.  Draw the feature edges
                    # of the thickened solid itself so through-hole rims and
                    # bend/miter edges live on the visible skins.  Keep the
                    # authoritative mid-surface crease overlay as a fallback
                    # for long fold spans that do not coincide with a skin rim.
                    self._add_mesh_feature_lines(placed, edge)
                    self._add_mesh_boundary_and_crease_lines(
                        formed_surface_for_edges, edge
                    )
                else:
                    self._add_mesh_boundary_lines(placed, edge)
                triangles.extend(placed)
                materials.append(part_material)
            if interference_segments:
                from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
                from ae_engine.assembly_geometry import MeshInterferenceDiagnostic
                if interference_targets:
                    ax.add_collection3d(Poly3DCollection(
                        interference_targets,
                        facecolor="#ef4444",
                        edgecolor="none",
                        linewidths=0.0,
                        alpha=0.42,
                    ))
                ax.add_collection3d(Line3DCollection(
                    interference_segments, colors="#ef4444", linewidths=3.2,
                    linestyles="solid", alpha=0.95,
                ))
                self.last_interference_diagnostic = MeshInterferenceDiagnostic(
                    tuple(interference_targets), tuple(interference_points),
                    interference_pairs, tuple(interference_segments)
                )
            else:
                from ae_engine.assembly_geometry import MeshInterferenceDiagnostic
                self.last_interference_diagnostic = MeshInterferenceDiagnostic((), (), 0, ())
            self._draw_joint_diagnostic_overlays(render_data)
            if not triangles:
                raise ValueError("3D assembly CUTTING mesh is empty")
            vertices = [point for tri in triangles for point in tri]
            xlim, ylim, zlim = _phase6_fitted_limits_from_vertices(vertices)
            ax.set_xlim3d(*xlim); ax.set_ylim3d(*ylim); ax.set_zlim3d(*zlim)
            spans = [max(1e-9, lim[1] - lim[0]) for lim in (xlim, ylim, zlim)]
            try:
                ax.set_box_aspect(spans, zoom=1.05)
            except TypeError:
                ax.set_box_aspect(spans)
            if request.finished_dimensions and callable(getattr(ax, "text2D", None)):
                text = " × ".join(self._number_text(v) for v in request.finished_dimensions)
                warnings = tuple(getattr(render_data, "warnings", ()) or ())
                warning_text = "\n⚠ " + "；".join(str(getattr(w, "message", w)) for w in warnings) if warnings else ""
                diagnostic = self.last_interference_diagnostic
                collision_text = ""
                if bool(getattr(render_data, "show_interference", False)):
                    count = len(tuple(getattr(diagnostic, "intersection_segments", ()) or ()))
                    collision_text = f"\n干涉碰撞區：{count} 段交線" if count else "\n干涉碰撞區：未偵測到穿越"
                ax.text2D(
                    0.015, 0.985,
                    f"組合體 3D：W × H × D = {text} mm{warning_text}{collision_text}"
                    + (("\n" + "\n".join(box_body_piece_dimension_lines)) if box_body_piece_dimension_lines else "")
                    + (f"\n{request.unfolded_blank_text}" if request.unfolded_blank_text else ""),
                    transform=ax.transAxes, ha="left", va="top",
                )
            self.last_cutting_mesh = triangles
            self.last_cutting_material = tuple(materials)
            return triangles
        if getattr(render_data, "pieces", None):
            meshes = _phase6_box_body_structure_meshes(render_data, thickness=request.thickness)
            triangles = [tri for _piece, piece_tris in meshes for tri in piece_tris]
            if not triangles:
                raise ValueError("3D multi-piece CUTTING mesh is empty")
            self._remove_original_bend_surfaces()
            for line in list(getattr(self.renderer.ax3d, "lines", ())):
                try:
                    line.remove()
                except Exception:
                    pass
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            face, edge = self._COLORS.get(str(request.part_key), ("#64748b", "#334155"))
            for _piece, piece_tris in meshes:
                poly = Poly3DCollection(
                    piece_tris, alpha=float(request.alpha_bend), facecolor=face,
                    edgecolor="none", linewidths=0.0,
                )
                self.renderer.ax3d.add_collection3d(poly)
                self._add_mesh_boundary_lines(piece_tris, edge)
            self._draw_box_body_structure_bends(
                render_data, thickness=request.thickness
            )
            vertices = [point for tri in triangles for point in tri]
            xlim, ylim, zlim = _phase6_fitted_limits_from_vertices(vertices)
            ax = self.renderer.ax3d
            ax.set_xlim3d(*xlim); ax.set_ylim3d(*ylim); ax.set_zlim3d(*zlim)
            spans = [max(1e-9, lim[1] - lim[0]) for lim in (xlim, ylim, zlim)]
            try:
                ax.set_box_aspect(spans, zoom=1.05)
            except TypeError:
                ax.set_box_aspect(spans)
            dims = request.finished_dimensions
            if dims and callable(getattr(ax, "text2D", None)):
                text = " × ".join(self._number_text(v) for v in dims)
                warnings = tuple(getattr(render_data, "warnings", ()) or ())
                warning_text = "\n⚠ " + "；".join(str(getattr(w, "message", w)) for w in warnings) if warnings else ""
                corner_text = f"\n{request.corner_dimension_text}" if request.corner_dimension_text else ""
                piece_text = "\n".join(_phase6_box_body_piece_dimension_lines(render_data))
                ax.text2D(
                    0.015, 0.985,
                    f"折後包外：{text} mm{warning_text}{corner_text}" + (f"\n{piece_text}" if piece_text else ""),
                    transform=ax.transAxes, ha="left", va="top"
                )
            self.last_cutting_mesh = triangles
            self.last_cutting_material = tuple(piece.render_data.material for piece in render_data.pieces)
            return triangles

        scene = render_data.scene
        material = render_data.material
        fold_guides = tuple(getattr(render_data, "fold_guides", ()) or ())
        triangles = _phase6_folded_mesh_from_polygon(
            material,
            request.x_profile,
            request.y_profile,
            fold_guides=fold_guides,
        )
        if not triangles:
            raise ValueError("3D CUTTING mesh is empty")
        self._remove_original_bend_surfaces()
        for line in list(getattr(self.renderer.ax3d, "lines", ())):
            try:
                line.remove()
            except Exception:
                pass
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        face, edge = self._COLORS.get(str(request.part_key), ("#64748b", "#334155"))
        poly = Poly3DCollection(
            triangles,
            alpha=float(request.alpha_bend),
            facecolor=face,
            edgecolor="none",
            linewidths=0.0,
        )
        self.renderer.ax3d.add_collection3d(poly)
        self._add_mesh_boundary_lines(triangles, edge)
        self._draw_scene_bends(scene, request.x_profile, request.y_profile, fold_guides=fold_guides)
        self._draw_scene_markings(scene, request.x_profile, request.y_profile, fold_guides=fold_guides)
        self._draw_operator_dimensions(request, triangles)
        vertices = [point for tri in triangles for point in tri]
        xlim, ylim, zlim = _phase6_fitted_limits_from_vertices(vertices)
        ax = self.renderer.ax3d
        ax.set_xlim3d(*xlim)
        ax.set_ylim3d(*ylim)
        ax.set_zlim3d(*zlim)
        spans = [max(1e-9, lim[1] - lim[0]) for lim in (xlim, ylim, zlim)]
        try:
            ax.set_box_aspect(spans, zoom=1.05)
        except TypeError:
            ax.set_box_aspect(spans)
        self.last_cutting_mesh = triangles
        self.last_cutting_material = material
        return triangles

    def configure_3d_only_figure(self):
        _configure_3d_only_figure(self.renderer)

    def scale_current_3d_limits(self, ratio):
        _scale_current_3d_limits(self.renderer, ratio)

    def adjust_zoom_scale(self, direction):
        old = float(self.zoom_scale or 1.0)
        if str(direction).lower() == "up":
            new = max(_PHASE6_ZOOM_MIN, old * _PHASE6_ZOOM_STEP)
        elif str(direction).lower() == "down":
            new = min(_PHASE6_ZOOM_MAX, old / _PHASE6_ZOOM_STEP)
        else:
            return old
        self.zoom_scale = new
        return new

    def on_scroll(self, event):
        if getattr(event, "inaxes", None) is not self.renderer.ax3d:
            return
        old = float(self.zoom_scale or 1.0)
        new = self.adjust_zoom_scale(getattr(event, "button", ""))
        if abs(new - old) <= 1e-12:
            return
        self.scale_current_3d_limits(new / old)
        self.renderer.canvas.draw_idle()

    def install(self, request_provider, *, after_render=None):
        self.zoom_scale = 1.0
        self.view_initialized = False
        self.configure_3d_only_figure()
        self.base_renderer_render = self.renderer.render

        def render_3d_only():
            canvas = self.renderer.canvas
            requested_draw = getattr(canvas, "draw", None)
            ax = self.renderer.ax3d
            try:
                elev, azim = ax.elev, ax.azim
            except AttributeError:
                elev, azim = 30, -45
            ax.clear()
            ax2d = getattr(self.renderer, "ax2d", None)
            if ax2d is not None:
                ax2d.clear()
                ax2d.axis("off")
            self.configure_3d_only_figure()
            try:
                self.render(request_provider())
                self.cutting_mesh_error = None
            except Exception as exc:
                self.last_cutting_mesh = []
                self.last_cutting_material = None
                self.cutting_mesh_error = str(exc)
                try:
                    ax.text2D(
                        0.5, 0.5, f"3D Final Part Geometry 載入失敗\n{exc}",
                        transform=ax.transAxes, ha="center", va="center",
                    )
                except Exception:
                    pass
            try:
                if self.view_initialized:
                    ax.view_init(elev=elev, azim=azim)
                else:
                    ax.view_init(elev=_PHASE6_DEFAULT_VIEW[0], azim=_PHASE6_DEFAULT_VIEW[1])
                    self.view_initialized = True
            except Exception:
                pass
            scale = float(self.zoom_scale or 1.0)
            if abs(scale - 1.0) > 1e-12 and not self.cutting_mesh_error:
                self.scale_current_3d_limits(scale)
            if callable(after_render):
                after_render()
            if callable(requested_draw):
                requested_draw()
            return None

        self.renderer.render = render_3d_only
        self.scroll_cid = self.renderer.canvas.mpl_connect("scroll_event", self.on_scroll)
        return self

_PHASE6_DEFAULT_VIEW = (50.0, -90.0)
_PHASE6_ZOOM_MIN = 0.35
_PHASE6_ZOOM_MAX = 3.0
_PHASE6_ZOOM_STEP = 0.85


def _configure_3d_only_figure(renderer):
    """Hide legacy 2D and let 3D use the full rectangular preview viewport."""
    import types

    ax2d = getattr(renderer, "ax2d", None)
    if ax2d is not None:
        ax2d.set_visible(False)
    ax = renderer.ax3d
    if callable(getattr(ax, "set_axis_off", None)):
        ax.set_axis_off()
    if not getattr(ax, "_phase6_rectangular_viewport", False) and callable(getattr(ax, "set_position", None)):
        def apply_rectangular_aspect(axis_self, position=None):
            if position is None:
                position = axis_self.get_position(original=True)
            axis_self._set_position(position, "active")
        ax.apply_aspect = types.MethodType(apply_rectangular_aspect, ax)
        ax._phase6_rectangular_viewport = True
    if callable(getattr(ax, "set_position", None)):
        ax.set_position([0.0, 0.02, 1.0, 0.96])


def _scale_current_3d_limits(renderer, ratio):
    ax = renderer.ax3d
    ratio = float(ratio)
    for getter, setter in (
        (ax.get_xlim3d, ax.set_xlim3d),
        (ax.get_ylim3d, ax.set_ylim3d),
        (ax.get_zlim3d, ax.set_zlim3d),
    ):
        lo, hi = getter()
        center = (lo + hi) / 2.0
        half = max(1e-9, (hi - lo) / 2.0) * ratio
        setter(center - half, center + half)



# Legacy helper compatibility. Production code uses Phase6FinalSceneView directly.
def _compat_view(owner):
    view = getattr(owner, "final_scene_view", None)
    if view is None:
        view = Phase6FinalSceneView(owner.renderer)
    return view


def _phase6_remove_original_bend_surfaces(owner):
    return _compat_view(owner)._remove_original_bend_surfaces()


def _phase6_add_mesh_boundary_lines(owner, triangles, color):
    return _compat_view(owner)._add_mesh_boundary_lines(triangles, color)


def _phase6_draw_scene_bends(owner, scene, x_profile, y_profile, fold_guides=()):
    return _compat_view(owner)._draw_scene_bends(scene, x_profile, y_profile, fold_guides=fold_guides)


def _phase6_draw_scene_markings(owner, scene, x_profile, y_profile, fold_guides=()):
    return _compat_view(owner)._draw_scene_markings(scene, x_profile, y_profile, fold_guides=fold_guides)


def _phase6_configure_3d_only_figure(owner):
    return _configure_3d_only_figure(owner.renderer)


def _phase6_scale_current_3d_limits(owner, ratio):
    view = getattr(owner, "final_scene_view", None)
    if view is not None:
        return view.scale_current_3d_limits(ratio)
    return _scale_current_3d_limits(owner.renderer, ratio)


def _phase6_adjust_zoom_scale(owner, direction):
    view = getattr(owner, "final_scene_view", None)
    if view is not None:
        return view.adjust_zoom_scale(direction)
    old = float(getattr(owner, "_phase6_zoom_scale", 1.0) or 1.0)
    if str(direction).lower() == "up":
        new = max(_PHASE6_ZOOM_MIN, old * _PHASE6_ZOOM_STEP)
    elif str(direction).lower() == "down":
        new = min(_PHASE6_ZOOM_MAX, old / _PHASE6_ZOOM_STEP)
    else:
        return old
    owner._phase6_zoom_scale = new
    return new
