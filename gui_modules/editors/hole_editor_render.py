"""Presentation-only canvas renderer for the unified hole editor.

This module owns transient canvas orchestration only. Geometry, measurement,
indicator layout, and manufacturing calculations remain delegated to injected
authorities.
"""

from __future__ import annotations

from functools import partial


class HoleEditorCanvasRenderer:
    """Render the live hole-editor frame without owning domain state."""

    def __init__(
        self, *, context_provider, canvas_view,
        selected_index_provider, reference_distances_provider,
        measure_guide_provider, selected_catalog_text_provider,
        insert_mode_provider, error_text_provider,
        collect_indicator_state, validate_current_indicator_fit,
        door_enclosure_reference_offsets, door_frame_edges_factory,
        vec2_factory, resolve_door_indicator_layout,
        render_resolved_features, measure_door_indicator_position,
        resolve_door_indicator_dimension_guides, indicator_box_opening_size,
        resolved_rect_factory, canvas_frame_factory, arrow_both,
    ):
        self.context_provider = context_provider
        self.canvas_view = canvas_view
        self.selected_index_provider = selected_index_provider
        self.reference_distances_provider = reference_distances_provider
        self.measure_guide_provider = measure_guide_provider
        self.selected_catalog_text_provider = selected_catalog_text_provider
        self.insert_mode_provider = insert_mode_provider
        self.error_text_provider = error_text_provider
        self.collect_indicator_state = collect_indicator_state
        self.validate_current_indicator_fit = validate_current_indicator_fit
        self.door_enclosure_reference_offsets = door_enclosure_reference_offsets
        self.door_frame_edges_factory = door_frame_edges_factory
        self.vec2_factory = vec2_factory
        self.resolve_door_indicator_layout = resolve_door_indicator_layout
        self.render_resolved_features = render_resolved_features
        self.measure_door_indicator_position = measure_door_indicator_position
        self.resolve_door_indicator_dimension_guides = resolve_door_indicator_dimension_guides
        self.indicator_box_opening_size = indicator_box_opening_size
        self.resolved_rect_factory = resolved_rect_factory
        self.canvas_frame_factory = canvas_frame_factory
        self.arrow_both = arrow_both

    def _enclosure_bounds(self, context):
        if not (
            context["active_part_key"] == "door"
            and context["indicator_box_dist_enabled"]
            and context["door_frame_width"] is not None
            and context["door_thickness"] is not None
            and context["door_gap_w"] is not None
            and context["door_gap_h"] is not None
        ):
            return None
        guide = context["reference_guide"]
        offsets = self.door_enclosure_reference_offsets(
            context["door_frame_edges"] or self.door_frame_edges_factory(),
            frame_width=context["door_frame_width"],
            thickness=context["door_thickness"],
            gap_w=context["door_gap_w"], gap_h=context["door_gap_h"],
        )
        return (
            float(guide.min_point.x) - offsets["left"],
            float(guide.min_point.y) - offsets["bottom"],
            float(guide.max_point.x) + offsets["right"],
            float(guide.max_point.y) + offsets["top"],
        )

    def redraw(self):
        context = self.context_provider()
        enclosure_bounds = self._enclosure_bounds(context)
        self.validate_current_indicator_fit(False)
        self.canvas_view.render(self.canvas_frame_factory(
            surface=context["surface"],
            features=context["feature_list"],
            width=context["width"],
            height=context["height"],
            reference_guide=context["reference_guide"],
            selected_index=self.selected_index_provider(),
            reference_distances=self.reference_distances_provider(),
            measure_guide=self.measure_guide_provider(),
            baseline_scene=context["baseline_scene"],
            extra_bounds=enclosure_bounds,
            insert_label=(
                self.selected_catalog_text_provider()
                if self.insert_mode_provider() else None
            ),
            error_text=self.error_text_provider(),
            draw_extra=partial(self.draw_extra, enclosure_bounds),
        ))

    def _draw_enclosure(self, enclosure_bounds, canvas_obj, tr, context):
        if enclosure_bounds is None:
            return
        ex0, ey0, ex1, ey1 = enclosure_bounds
        edges = context["door_frame_edges"] or self.door_frame_edges_factory()
        sides = (
            (self.vec2_factory(ex0, ey0), self.vec2_factory(ex0, ey1), edges.left),
            (self.vec2_factory(ex1, ey0), self.vec2_factory(ex1, ey1), edges.right),
            (self.vec2_factory(ex0, ey1), self.vec2_factory(ex1, ey1), edges.top),
            (self.vec2_factory(ex0, ey0), self.vec2_factory(ex1, ey0), edges.bottom),
        )
        for p1, p2, present in sides:
            canvas_obj.create_line(
                *tr.world_to_canvas(p1), *tr.world_to_canvas(p2),
                fill=("#64d2ff" if present else "#8e8e93"), width=2,
                dash=(None if present else (4, 4)),
                tags=("door_enclosure_reference",),
            )

    def _draw_dimension(self, canvas_obj, tr, guide, axis, *, dx=0, dy=0, angle=0):
        p1 = tr.world_to_canvas(guide.start)
        p2 = tr.world_to_canvas(guide.end)
        canvas_obj.create_line(
            *p1, *p2, fill="#ff9f0a", width=2, arrow=self.arrow_both,
            tags=("door_enclosure_reference", "indicator_dimension"),
        )
        canvas_obj.create_text(
            (p1[0] + p2[0]) / 2 + dx, (p1[1] + p2[1]) / 2 + dy,
            text=f"{axis}={guide.value:.1f}", fill="#ff9f0a",
            font=("Consolas", 10, "bold"), angle=angle,
            tags=("indicator_dimension",),
        )

    def draw_extra(self, enclosure_bounds, canvas_obj, tr, _cw, _ch):
        context = self.context_provider()
        self._draw_enclosure(enclosure_bounds, canvas_obj, tr, context)
        if (
            context["active_part_key"] != "door"
            or not context["indicator_mode_available"]
            or context["door_indicator_context"] is None
        ):
            return
        try:
            state = self.collect_indicator_state()
            groups = tuple(int(v) for v in state["groups"][:state["layers"]])
            indicator_context = context["door_indicator_context"]
            if state["mode"] == "indicator":
                layout = self.resolve_door_indicator_layout(
                    indicator_context, groups,
                    self.vec2_factory(state["offset_x"], state["offset_y"]),
                )
                self.render_resolved_features(
                    canvas_obj, layout.features, tr, color="#64d2ff"
                )
                if (
                    state["is_box_dist"]
                    and context["door_frame_width"] is not None
                    and context["door_thickness"] is not None
                ):
                    position = self.measure_door_indicator_position(
                        layout, indicator_context,
                        frame_width=context["door_frame_width"],
                        thickness=context["door_thickness"],
                        use_box_distance=True,
                        frame_edges=(
                            context["door_frame_edges"]
                            or self.door_frame_edges_factory()
                        ),
                        gap_w=context["door_gap_w"], gap_h=context["door_gap_h"],
                    )
                    x_guide, y_guide = self.resolve_door_indicator_dimension_guides(position)
                    self._draw_dimension(canvas_obj, tr, x_guide, "X", dy=-12)
                    self._draw_dimension(canvas_obj, tr, y_guide, "Y", dx=-28, angle=90)
            elif state["mode"] == "indicator_box":
                hole_w, hole_h = self.indicator_box_opening_size(
                    groups, thickness=float(context["door_thickness"] or 0.0)
                )
                center = self.vec2_factory(
                    indicator_context.left_fold
                    + indicator_context.finished_width / 2.0 + state["offset_x"],
                    indicator_context.bottom_fold
                    + indicator_context.finished_height / 2.0 + state["offset_y"],
                )
                feature = self.resolved_rect_factory(
                    center=center, width=hole_w, height=hole_h,
                    layer="CUTTING", source_type="indicator_box_opening",
                )
                self.render_resolved_features(
                    canvas_obj, [feature], tr, color="#64d2ff"
                )
        except Exception:
            pass
