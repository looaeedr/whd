# -*- coding: utf-8 -*-
"""Helper rendering mixin for Phase6 authoritative FinalScene 3D views."""
from __future__ import annotations

from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from whd_theme import WHD_THEME
from phase6_final_scene_projection import (
    _phase6_profile_base_index,
    _phase6_profile_geometry,
    _phase6_profile_map_with_guides,
    _phase6_profile_map,
    _phase6_mesh_feature_segments,
    _phase6_folded_outside_envelope,
    _phase6_contract_profile_rows,
    _phase6_box_body_piece_world_mapper,
    format_operator_info_text,
)


class Phase6FinalSceneRenderHelpersMixin:
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
            piece_role = str(getattr(piece, "role", "") or "").strip()
            piece_key = f"box_body:{piece_role}"
            if visible_set is not None and piece_key not in visible_set:
                continue
            # The back panel is a broad operator-facing reference surface.
            # Keep its physical CUTTING geometry/holes, but suppress display-only
            # bend overlays that make the panel look like a wireframe.
            if piece_role == "back":
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
                    linewidth=(2.2 if layer == "MARKING" else 1.0),
                    linestyle=("-" if layer == "MARKING" else "--"),
                    alpha=(1.0 if layer == "MARKING" else 0.9),
                    zorder=(20 if layer == "MARKING" else 8),
                )

    @staticmethod
    def _marking_line_signature(p1, p2):
        a = (round(float(p1[0]), 9), round(float(p1[1]), 9))
        b = (round(float(p2[0]), 9), round(float(p2[1]), 9))
        return tuple(sorted((a, b)))

    def _joint_marking_flat_signatures(self, render_data):
        metadata = dict(getattr(render_data, "metadata", {}) or {})
        signatures = set()
        for row in tuple(metadata.get("joint_markings") or ()):
            if not isinstance(row, dict):
                try:
                    row = dict(row)
                except Exception:
                    continue
            if str(row.get("source") or "") != "JOINT_PLACEMENT_MARKING":
                continue
            if row.get("p1") is None or row.get("p2") is None:
                continue
            signatures.add(self._marking_line_signature(row["p1"], row["p2"]))
        return signatures

    def _draw_joint_marking_world_rows(self, render_data):
        """Draw contact-derived joint MARKING in canonical assembly world space.

        The manufacturing solver stores both the flat primitive and the exact
        world contact boundary in the same metadata row.  Assembly 3D consumes
        that row instead of re-deriving placement from renderer coordinates, so
        composite pieces and EndCaps preserve the manufacturing geometry owner.
        """
        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        metadata = dict(getattr(render_data, "metadata", {}) or {})
        for raw in tuple(metadata.get("joint_markings") or ()):
            if not isinstance(raw, dict):
                try:
                    raw = dict(raw)
                except Exception:
                    continue
            if str(raw.get("source") or "") != "JOINT_PLACEMENT_MARKING":
                continue
            a = raw.get("world_p1")
            b = raw.get("world_p2")
            if a is None or b is None or len(a) != 3 or len(b) != 3:
                continue
            self.renderer.ax3d.plot(
                [float(a[0]), float(b[0])],
                [float(a[1]), float(b[1])],
                [float(a[2]), float(b[2])],
                color="#f59e0b",
                linewidth=2.2,
                linestyle="-",
                alpha=1.0,
                zorder=20,
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
        joint_marking_signatures=(),
    ):
        """Project non-contact flat MARKING through the ordinary assembly placement.

        Contact-derived JOINT_PLACEMENT_MARKING is drawn from the exact world
        boundary stored by the manufacturing solver and is skipped here.
        """
        from ae_engine.assembly_geometry import place_assembly_points
        from ae_engine.sheetmetal_drawing import LinePrimitive

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        placement_key = str(placement or "offset").lower()
        joint_marking_signatures = set(joint_marking_signatures or ())
        if placement_key in {"top", "head", "bottom", "tail"}:
            # EndCaps use a dedicated mating transform. Their contact-derived
            # joint marks are rendered from canonical world metadata above;
            # do not guess a second flat-point transform for other marks here.
            return

        for primitive in getattr(scene, "primitives", ()):
            if (
                not isinstance(primitive, LinePrimitive)
                or str(getattr(primitive, "layer", "") or "").upper() != "MARKING"
            ):
                continue
            signature = self._marking_line_signature(
                (primitive.p1.x, primitive.p1.y),
                (primitive.p2.x, primitive.p2.y),
            )
            if signature in joint_marking_signatures:
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
                linewidth=2.2,
                linestyle="-",
                alpha=1.0,
                zorder=20,
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
