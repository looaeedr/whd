# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Helper rendering mixin for Phase6 authoritative FinalScene 3D views."""
from __future__ import annotations

from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from whd_theme import WHD_THEME
from phase6_final_scene_projection import (
    _phase6_profile_map_with_guides,
    _phase6_profile_map,
    _phase6_mesh_feature_segments,
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

    def _draw_cutting_hole_rims(
        self, material, x_profile, y_profile, fold_guides=(), *,
        local_reference=None, placement=None, dimensions=None,
        offset=(0.0, 0.0, 0.0),
    ):
        """Paint only actual CUTTING inner-rings projected by public Engine."""
        from ae_engine import manufacturing_api
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        segments = manufacturing_api.project_independent_cutting_hole_rim_segments(
            material, x_profile, y_profile, fold_guides,
            local_reference=local_reference, placement=placement,
            dimensions=dimensions, offset=offset,
        )
        if segments:
            self.renderer.ax3d.add_collection3d(Line3DCollection(
                segments, colors="#22d3ee", linewidths=2.2,
                linestyles="solid", zorder=20,
            ))
        return len(segments)

    def _add_mesh_boundary_and_crease_lines(self, triangles, color, *, creases_only=False):
        """Draw real folded-sheet creases without exposing triangulation seams.

        In smooth mode, unmatched triangle sides are not reliable physical
        boundaries: fragmented tessellation exposed them as diagonal artifacts.
        Draw only edges shared by different physical face normals, while BEND,
        MARKING and CUTTING retain their original source geometry.  Legacy
        mode continues to support drawing actual open mesh perimeters.
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
            # Unmatched polygon/triangulation edges are NOT proof of a
            # real external outline.  In smooth 3D mode draw ONLY crease
            # edges shared by genuine non-coplanar faces.  Authoritative
            # BEND, CUTTING, and MARKING geometry remains separate.
            visible = not creases_only and len(normals) == 1
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
        """Render-only memo for canonical Engine Fold chains; never persist truth.

        GUI caches only the prepared callable and a detached INPUT snapshot.
        A modified profile, angle, formed length or BEND span invalidates the
        mapping before the next point; Engine alone owns Fold calculations.
        """
        from copy import deepcopy
        from ae_engine import manufacturing_api

        source = (
            tuple(x_profile or ()),
            tuple(y_profile or ()),
            tuple(fold_guides or ()),
        )
        cached = getattr(self, "_phase6_prepared_fold_mapping", None)
        if cached is None or cached[0] != source:
            x_mapper = manufacturing_api.prepare_fold_profile_mapper(
                source[0], axis="x", fold_guides=source[2],
            )
            y_mapper = manufacturing_api.prepare_fold_profile_mapper(
                source[1], axis="y", fold_guides=source[2],
            )
            cached = (deepcopy(source), x_mapper, y_mapper)
            self._phase6_prepared_fold_mapping = cached
        ux, zx = cached[1](float(x), float(y))
        uy, zy = cached[2](float(y), float(x))
        return (ux, uy, zx + zy)

    def _draw_assembly_box_body_bends(
        self, scene, x_profile, y_profile, fold_guides, local_reference,
        placement, dimensions, offset,
    ):
        """Paint Engine-projected physical BoxBody BEND world segments."""
        from ae_engine import manufacturing_api

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        segments = manufacturing_api.project_assembly_box_body_bend_segments(
            scene, x_profile, y_profile, fold_guides,
            local_reference, placement, dimensions, offset,
        )
        for a, b in segments:
            self.renderer.ax3d.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color="#2563eb", linewidth=1.35, linestyle="-", alpha=0.98,
            )

    def _draw_scene_bends(self, scene, x_profile, y_profile, fold_guides=()):
        """Draw only Engine-projected true single-part BEND segments."""
        from ae_engine import manufacturing_api

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        for a, b in manufacturing_api.project_independent_scene_bend_segments(
            scene, x_profile, y_profile, fold_guides,
        ):
            self.renderer.ax3d.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color="#2563eb", linewidth=1.15, linestyle="-", alpha=0.95,
            )

    def _draw_box_body_structure_bends(
        self, render_data, *, thickness, local_reference=None,
        placement="box_body", dimensions=None, offset=(0.0, 0.0, 0.0),
        visible_piece_keys=None,
    ):
        """Draw the canonical Engine world BEND lines; never manufacture them."""
        from ae_engine import manufacturing_api

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        segments = manufacturing_api.project_box_body_structure_bend_segments(
            render_data, thickness=thickness, local_reference=local_reference,
            placement=placement, dimensions=dimensions, offset=offset,
            visible_piece_keys=visible_piece_keys,
        )
        for a, b in segments:
            self.renderer.ax3d.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color="#2563eb", linewidth=1.35, linestyle="-", alpha=0.98,
            )

    def _draw_scene_markings(self, scene, x_profile, y_profile, fold_guides=()):
        """Paint real MARKING and BLIND_HOLE paths projected by Engine."""
        from ae_engine import manufacturing_api

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        paths = manufacturing_api.project_independent_scene_annotation_paths(
            scene, x_profile, y_profile, fold_guides,
        )
        for layer, pts in paths:
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
        """Legacy GUI import, Engine owns canonical MARKING identity."""
        from ae_engine import manufacturing_api
        return manufacturing_api.marking_line_signature(p1, p2)

    def _joint_marking_flat_signatures(self, render_data):
        """Forward the existing Engine verified Joint source identities."""
        from ae_engine import manufacturing_api
        return manufacturing_api.joint_marking_flat_signatures(render_data)

    def _draw_joint_marking_world_rows(self, render_data):
        """Draw Engine-resolved contact Joint world MARKING; no GUI source logic."""
        from ae_engine import manufacturing_api

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        segments = manufacturing_api.project_joint_marking_world_segments(
            render_data,
        )
        for a, b in segments:
            self.renderer.ax3d.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color="#f59e0b",
                linewidth=2.2,
                linestyle="-",
                alpha=1.0,
                zorder=20,
            )

    def _draw_endcap_cutting_hole_rims(
        self, material, x_profile, y_profile, fold_guides,
        local_surface, placed_surface, placement, color,
    ):
        """Draw only Engine-projected physical CUTTING inner rings."""
        from ae_engine import manufacturing_api
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        segments = manufacturing_api.project_endcap_cutting_hole_rim_segments(
            material, x_profile, y_profile, fold_guides,
            local_surface, placed_surface, placement,
        )
        if segments:
            self.renderer.ax3d.add_collection3d(Line3DCollection(
                segments, colors=color, linewidths=1.4, linestyles="solid",
            ))

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
        """Paint Engine-projected non-contact MARKING, no GUI Fold/world math."""
        from ae_engine import manufacturing_api

        if not callable(getattr(self.renderer.ax3d, "plot", None)):
            return
        segments = manufacturing_api.project_assembly_scene_marking_segments(
            scene, x_profile, y_profile, fold_guides,
            local_reference, placement, dimensions, offset,
            joint_marking_signatures=joint_marking_signatures,
        )
        for a, b in segments:
            self.renderer.ax3d.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color="#f59e0b", linewidth=2.2, linestyle="-",
                alpha=1.0, zorder=20,
            )


    def _draw_receiving_ear_side_markings(
        self, formed_ear_skins, *, visible_side_piece_keys=None,
    ):
        """Only paint source-verified Engine world segments for Receiving EAR."""
        from ae_engine import manufacturing_api

        segments = manufacturing_api.project_receiving_ear_side_marking_segments(
            formed_ear_skins, visible_side_piece_keys=visible_side_piece_keys,
        )
        # Source-verified side positioning, NOT manufacturing UV MARKING.
        ax = self.renderer.ax3d
        if callable(getattr(ax, "plot", None)):
            for a, b in segments:
                ax.plot(
                    (a[0], b[0]), (a[1], b[1]), (a[2], b[2]),
                    color="#facc15", linewidth=3.0,
                    linestyle="-", alpha=1.0, zorder=30,
                )
        return segments

    def _resolved_finished_dimensions(self, request, triangles):
        return resolve_operator_finished_dimensions(
            request.part_key,
            triangles=triangles,
            thickness=request.thickness,
            fallback_dimensions=request.finished_dimensions,
        )

    def _draw_operator_dimensions(self, request, triangles):
        """Paint the Engine's physical Fold/outside-world dimension guides."""
        from ae_engine import manufacturing_api

        ax = self.renderer.ax3d
        dims = self._resolved_finished_dimensions(request, triangles)
        if not dims or not all(callable(getattr(ax, name, None))
                               for name in ("plot", "text", "text2D")):
            return
        guides = manufacturing_api.project_operator_dimension_guides(
            request.x_profile, request.y_profile,
            triangles=triangles, thickness=request.thickness,
        )
        width, height = dims[:2]
        for a, b in guides.width_segments:
            ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                    linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.text(*guides.width_label_position,
                f"W {self._number_text(width)} mm",
                ha="center", va="top", color=WHD_THEME["text"])
        for a, b in guides.height_segments:
            ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                    linewidth=1.0, color=WHD_THEME["muted_text"])
        ax.text(*guides.height_label_position,
                f"H {self._number_text(height)} mm",
                ha="right", va="center", color=WHD_THEME["text"])
        info = format_operator_info_text(
            request, dimensions=dims, number_text=self._number_text
        )
        ax.text2D(0.015, 0.985, info, transform=ax.transAxes,
                  ha="left", va="top", color=WHD_THEME["text"])

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
