# -*- coding: utf-8 -*-
"""Final Scene renderer/runtime owner extracted in Phase 4 T6.

Owns Matplotlib renderer mutation and mutable 3D runtime state only.
It consumes immutable FinalSceneViewRequest plus pure projection helpers.
"""
from __future__ import annotations

import matplotlib.projections as _matplotlib_projections  # noqa: F401

from typing import Callable

from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS, apply_mpl_dark_theme
from phase6_final_scene_contracts import (
    AssemblyScenePart,
    AssemblySceneRenderData,
    FinalSceneViewRequest,
)
from phase6_final_scene_projection import (
    _phase6_profile_base_index,
    _phase6_profile_geometry,
    _phase6_fold_mask_for_cross_coordinate,
    _phase6_profile_map_with_guides,
    _phase6_profile_map,
    _phase6_profile_flat_map,
    _phase6_folded_mesh_from_polygon,
    _phase6_mesh_feature_segments,
    _phase6_fitted_limits_from_vertices,
    _phase6_scene_fold_boundaries,
    _phase6_profile_to_scene_boundaries,
    _phase6_fold_ownership_exemptions,
    _default_number_text,
    _phase6_folded_outside_envelope,
    _phase6_profile_operator_fold_values,
    _phase6_contract_profile_rows,
    _phase6_box_body_piece_world_mapper,
    _phase6_box_body_piece_dimension_lines,
    _phase6_box_body_structure_meshes,
    format_operator_info_text,
    _phase6_place_assembly_triangles,
)


class Phase6FinalSceneRenderer:
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
        self.visible_commit_hook = None

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
        visible_piece_keys=None,
    ):
        """Draw BEND lines only for visible BoxBody pieces while retaining full geometry."""
        from ae_engine.sheetmetal_drawing import LinePrimitive
        from ae_engine.assembly_geometry import place_assembly_points

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        pieces = tuple(getattr(render_data, "pieces", ()) or ())
        if not pieces:
            return
        total_w = max(float(getattr(p, "formed_w_end", 0.0)) for p in pieces)
        visible_set = None if visible_piece_keys is None else set(visible_piece_keys)
        for piece in pieces:
            piece_key = f"box_body:{str(getattr(piece, 'role', '') or '').strip()}"
            if visible_set is not None and piece_key not in visible_set:
                continue
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

    def _draw_assembly_scene_markings(
        self,
        scene,
        x_profile,
        y_profile,
        fold_guides,
        local_reference,
        placement,
        dimensions,
        offset,
    ):
        """Project canonical flat MARKING through the same assembly placement as the part."""
        from ae_engine.assembly_geometry import place_assembly_points
        from ae_engine.sheetmetal_drawing import LinePrimitive

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        placement_key = str(placement or "offset").lower()
        if placement_key in {"top", "head", "bottom", "tail"}:
            # EndCaps use the dedicated box-body mating transform. Do not guess a
            # second point transform here; current Receiving frame markings never
            # use these placements.
            return

        for primitive in getattr(scene, "primitives", ()):
            if (
                not isinstance(primitive, LinePrimitive)
                or str(getattr(primitive, "layer", "") or "").upper() != "MARKING"
            ):
                continue
            local_points = (
                self._map_xy(
                    primitive.p1.x,
                    primitive.p1.y,
                    x_profile,
                    y_profile,
                    fold_guides,
                ),
                self._map_xy(
                    primitive.p2.x,
                    primitive.p2.y,
                    x_profile,
                    y_profile,
                    fold_guides,
                ),
            )
            world_points = place_assembly_points(
                local_points,
                local_reference,
                placement,
                dimensions,
                offset,
            )
            if len(world_points) != 2:
                continue
            a, b = world_points
            self.renderer.ax3d.plot(
                [a[0], b[0]],
                [a[1], b[1]],
                [a[2], b[2]],
                color="#f59e0b",
                linewidth=1.0,
                linestyle="-",
                alpha=0.9,
            )

    def _resolved_finished_dimensions(self, request, triangles):
        return resolve_operator_finished_dimensions(
            request.part_key,
            triangles=triangles,
            thickness=request.thickness,
            fallback_dimensions=request.finished_dimensions,
        )

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
        ax.plot([x0, x1], [wy, wy], [0.0, 0.0], linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.plot([x0, x0], [wy - tick, wy + tick], [0.0, 0.0], linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.plot([x1, x1], [wy - tick, wy + tick], [0.0, 0.0], linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.text((x0 + x1) / 2.0, wy, 0.0, f"W {self._number_text(width)} mm", ha="center", va="top", color=WHD_THEME["text"])
        ax.plot([hx, hx], [y0, y1], [0.0, 0.0], linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.plot([hx - tick, hx + tick], [y0, y0], [0.0, 0.0], linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.plot([hx - tick, hx + tick], [y1, y1], [0.0, 0.0], linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.text(hx, (y0 + y1) / 2.0, 0.0, f"H {self._number_text(height)} mm", ha="right", va="center", color=WHD_THEME["text"])
        info = format_operator_info_text(
            request, dimensions=dims, number_text=self._number_text
        )
        ax.text2D(0.015, 0.985, info, transform=ax.transAxes, ha="left", va="top", color=WHD_THEME["text"])

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
        visible_raw = getattr(render_data, "visible_part_keys", None)
        visible_part_keys = (
            None if visible_raw is None
            else frozenset(str(key) for key in tuple(visible_raw or ()))
        )
        visible_piece_raw = getattr(render_data, "visible_box_body_piece_keys", None)
        visible_box_body_piece_keys = (
            None if visible_piece_raw is None
            else frozenset(str(key) for key in tuple(visible_piece_raw or ()))
        )
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
                part_key = str(getattr(part, "part_key", ""))
                part_visible = visible_part_keys is None or part_key in visible_part_keys
                part_data = part.render_data
                diagnostic_relief_delta = None
                if getattr(part_data, "pieces", None):
                    piece_meshes = _phase6_box_body_structure_meshes(part_data, thickness=request.thickness)
                    local = [tri for _piece, piece_tris in piece_meshes for tri in piece_tris]
                    part_material = tuple(piece.render_data.material for piece in part_data.pieces)
                    if part_visible:
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
                placed_piece_meshes = ()
                if getattr(part_data, "pieces", None):
                    rows = []
                    cursor = 0
                    for piece, piece_tris in piece_meshes:
                        count = len(piece_tris)
                        rows.append((piece, tuple(placed[cursor:cursor + count])))
                        cursor += count
                    placed_piece_meshes = tuple(rows)
                if part_key == "box_body":
                    box_body_world = tuple(placed)
                    if part_visible:
                        if getattr(part_data, "pieces", None):
                            self._draw_box_body_structure_bends(
                                part_data, thickness=request.thickness, local_reference=local,
                                placement=placement, dimensions=request.finished_dimensions, offset=offset,
                                visible_piece_keys=visible_box_body_piece_keys,
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
                    if getattr(part_data, "pieces", None):
                        if part_visible:
                            face, edge = self._COLORS.get(str(part.part_key), ("#64748b", "#334155"))
                            visible_rows = []
                            for piece, piece_placed in placed_piece_meshes:
                                piece_key = f"box_body:{str(getattr(piece, 'role', '') or '').strip()}"
                                if visible_box_body_piece_keys is not None and piece_key not in visible_box_body_piece_keys:
                                    continue
                                visible_rows.append(piece)
                                if not piece_placed:
                                    continue
                                poly = Poly3DCollection(
                                    piece_placed,
                                    alpha=float(request.alpha_bend),
                                    facecolor=face,
                                    edgecolor="none",
                                    linewidths=0.0,
                                )
                                ax.add_collection3d(poly)
                                self._add_mesh_boundary_lines(piece_placed, edge)
                                triangles.extend(piece_placed)
                            if visible_rows:
                                materials.append(tuple(piece.render_data.material for piece in visible_rows))
                        continue
                    if not part_visible:
                        continue
                elif not part_visible:
                    continue
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
                self._draw_assembly_scene_markings(
                    part_data.scene,
                    tuple(dict(seg) for seg in part.x_profile),
                    tuple(dict(seg) for seg in part.y_profile),
                    tuple(getattr(part_data, "fold_guides", ()) or ()),
                    local,
                    placement,
                    request.finished_dimensions,
                    offset,
                )
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
                    transform=ax.transAxes, ha="left", va="top", color=WHD_THEME["text"],
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
                    transform=ax.transAxes, ha="left", va="top", color=WHD_THEME["text"]
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
            apply_mpl_dark_theme(getattr(ax, "figure", None), (ax, ax2d))
            self.configure_3d_only_figure()
            request = None
            try:
                request = request_provider()
                self.render(request)
                self.cutting_mesh_error = None
            except Exception as exc:
                self.last_cutting_mesh = []
                self.last_cutting_material = None
                self.cutting_mesh_error = str(exc)
                try:
                    ax.text2D(
                        0.5, 0.5, f"3D Final Part Geometry 載入失敗\n{exc}",
                        transform=ax.transAxes, ha="center", va="center", color=WHD_SEMANTIC_COLORS["error"],
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
            visible_commit_hook = getattr(self, "visible_commit_hook", None)
            if callable(visible_commit_hook):
                visible_commit_hook(request)
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


# Compatibility name retained for existing imports/tests. Runtime ownership is
# Phase6FinalSceneRenderer.
Phase6FinalSceneView = Phase6FinalSceneRenderer


__all__ = [
    "Phase6FinalSceneRenderer",
    "Phase6FinalSceneView",
    "AssemblyScenePart",
    "AssemblySceneRenderData",
    "_PHASE6_DEFAULT_VIEW",
    "_PHASE6_ZOOM_MIN",
    "_PHASE6_ZOOM_MAX",
    "_PHASE6_ZOOM_STEP",
    "_configure_3d_only_figure",
    "_scale_current_3d_limits",
]
