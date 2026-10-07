# -*- coding: utf-8 -*-
"""Door/Indicator/Base render projection adapter for Phase6ApplicationHost.

This module intentionally owns no editor lifecycle, Receiving inner-door state,
navigation, or project transactions.
"""
from __future__ import annotations

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.engineering_drawing import build_engineering_drawing_projection
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CanvasTransform,
    DoorIndicatorContext,
    ResolvedRect,
    feature_surface_from_structural_result,
    resolve_door_indicator_features,
    resolve_door_indicator_layout,
    resolve_surface_features,
)
from ae_engine.sheetmetal_part_adapters import build_door_result

from gui_modules.application.render_snapshots import (
    indicator_box_render_snapshot as _indicator_box_render_snapshot_impl,
    indicator_door_render_snapshot as _indicator_door_render_snapshot_impl,
    door_layout_overview_snapshot as _door_layout_overview_snapshot_impl,
    door_layout_divider_frame_snapshot as _door_layout_divider_frame_snapshot_impl,
    single_door_render_snapshot as _single_door_render_snapshot_impl,
    base_plate_render_snapshot as _base_plate_render_snapshot_impl,
)
from gui_modules.parts.panels.door import normalize_door_indicator_state as _normalize_door_indicator_state_impl
from gui_modules.rendering import (
    phase6_2d_material_viewport as _phase6_2d_material_viewport_impl,
    draw_phase6_annotation_projection as _draw_phase6_annotation_projection_impl,
    draw_preview_error as _draw_preview_error_impl,
    draw_indicator_box_preview as _draw_indicator_box_preview_impl,
    draw_indicator_door_preview as _draw_indicator_door_preview_impl,
    draw_single_door_preview as _draw_single_door_preview_impl,
    draw_base_plate_preview as _draw_base_plate_preview_impl,
    draw_door_layout_error as _draw_door_layout_error_impl,
    draw_door_layout_overview_preview as _draw_door_layout_overview_preview_impl,
    draw_door_layout_dividers_and_frames_preview as _draw_door_layout_dividers_and_frames_preview_impl,
)
from gui_modules.drawing import render_drawing_scene
from gui_modules.editors.hole_editor_view import draw_hole_editor_hint
from phase6_corner_dimension_display import render_data_corner_dimension_text


def _phase6_2d_material_viewport(bounds, canvas_width, canvas_height, *, top_gutter=175.0,
                                 right_gutter=82.0, bottom_gutter=48.0, left_gutter=48.0):
    return _phase6_2d_material_viewport_impl(
        bounds, canvas_width, canvas_height,
        top_gutter=top_gutter, right_gutter=right_gutter,
        bottom_gutter=bottom_gutter, left_gutter=left_gutter,
        transform_type=CanvasTransform,
    )


def _draw_phase6_annotation_projection(
    canvas, render_data, transform, *, part_key="", strict=False,
):
    return _draw_phase6_annotation_projection_impl(
        canvas, render_data, transform,
        part_key=part_key, strict=strict,
        projection_builder=build_engineering_drawing_projection,
    )


def _indicator_box_render_snapshot(self, val):
    return _indicator_box_render_snapshot_impl(self, val)


def draw_indicator_box(self, val):
    canvas = self.canvas_indicator_box; canvas.delete("all")
    cw = canvas.winfo_width(); ch = canvas.winfo_height()
    if cw <= 1 or ch <= 1: return
    self.draw_grid(canvas, cw, ch)
    try: snapshot = self._indicator_box_render_snapshot(val)
    except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "指示燈盒", exc)
    return _draw_indicator_box_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)


def _normalize_door_indicator_state(self, state):
    return _normalize_door_indicator_state_impl(state)


def _door_layout_indicator_state_for_key(self, key):
    state = self.door_layout_indicator_states.get(key)
    normalized = self._normalize_door_indicator_state(state)
    if state is None:
        state = normalized
        self.door_layout_indicator_states[key] = state
    else:
        state.clear()
        state.update(normalized)
    return state


def _door_layout_cell_result(self, cell, val=None):
    val = val or self.get_float_values()
    return build_door_result(
        w=cell.start_width, h=cell.start_height, t=val['t'],
        fw=self._door_material_frame_width(val['fw'], val['t']),
        gap_w=val['door_gap_w'], gap_h=val['door_gap_h'],
        fold_left=val['door_fold_l'], fold_right=val['door_fold_r'],
        fold_top=val['door_fold_t'], fold_bottom=val['door_fold_b'],
        frame_edges=cell.edges,
    )


def _door_layout_cell_resolved_features(self, cell, result, key):
    resolved = []
    features = self.door_layout_features.setdefault(key, [])
    if features:
        surface = feature_surface_from_structural_result("door", result)
        try:
            resolved.extend(resolve_surface_features(surface, features, result.width, result.height))
        except ValueError:
            pass
    state = self._door_layout_indicator_state_for_key(key)
    mode = state.get("mode", "indicator" if state.get("enabled") else "none")
    if mode in {"indicator", "indicator_box"}:
        try:
            material_fw = self._door_material_frame_width(
                self.fw_z_var.get(), self.t_var.get()
            )
            finished_w, finished_h = ae.calculate_door_finished_size(
                cell.start_width, cell.start_height, material_fw,
                self.door_gap_w_var.get(), self.door_gap_h_var.get(), self.t_var.get(),
                frame_edges=cell.edges,
            )
            context = DoorIndicatorContext(
                finished_width=float(finished_w), finished_height=float(finished_h),
                left_fold=float(self.door_fold_l_var.get()), bottom_fold=float(self.door_fold_b_var.get()),
            )
            groups = tuple(int(v) for v in state.get("groups", [2])[:int(state.get("layers", 1))])
            if mode == "indicator":
                layout = resolve_door_indicator_layout(
                    context, groups,
                    Vec2(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
                )
                resolved.extend(layout.features)
            else:
                hole_w, hole_h = manufacturing_api.indicator_box_opening_size(groups, thickness=float(self.t_var.get()))
                resolved.append(ResolvedRect(
                    center=Vec2(
                        context.left_fold + context.finished_width / 2.0 + float(state.get("offset_x", 0.0)),
                        context.bottom_fold + context.finished_height / 2.0 + float(state.get("offset_y", 0.0)),
                    ),
                    width=hole_w, height=hole_h, layer="CUTTING", source_type="indicator_box_opening",
                ))
        except Exception:
            pass
    return resolved


def _door_layout_baseline_scene(self, cell, val):
    family_model = self._baseline_source_model()
    baseline_model = (
        cabinet_family_policy.baseline_feature_model_name(family_model)
        if family_model else None
    )
    if not baseline_model or not ae.has_baseline_part(baseline_model, "門.dxf"):
        return None, ae.baseline_source_label("", "門.dxf")
    source_fp = ae.baseline_source_fingerprint(
        ae.baseline_expected_path(baseline_model, "門.dxf")
    )
    cache_key = (
        source_fp, family_model, baseline_model,
        float(cell.start_width), float(cell.start_height),
        float(val['t']), float(val['fw']),
        float(val['door_gap_w']), float(val['door_gap_h']),
        float(val['door_fold_l']), float(val['door_fold_r']),
        float(val['door_fold_t']), float(val['door_fold_b']),
        bool(cell.edges.left), bool(cell.edges.right),
        bool(cell.edges.top), bool(cell.edges.bottom),
    )
    if cache_key in self._door_layout_baseline_cache:
        return (
            self._door_layout_baseline_cache[cache_key],
            ae.baseline_source_label(baseline_model, "門.dxf"),
        )
    try:
        # FW conversion belongs to the cabinet family (Receiving), while
        # fixed certified Door features may come from its shared Vault baseline.
        material_fw = self._door_material_frame_width(
            val['fw'], val['t'], model_name=family_model
        )
        data = ae.get_stretched_door_data(
            baseline_model,
            cell.start_width, cell.start_height, val['t'], material_fw,
            val['door_gap_w'], val['door_gap_h'],
            val['door_fold_l'], val['door_fold_r'],
            val['door_fold_t'], val['door_fold_b'],
            frame_edges=cell.edges,
            nameplate_center_datum_top=(
                cabinet_family_policy.door_nameplate_center_datum_top(
                    family_model
                )
            ),
        )
        self._door_layout_baseline_cache[cache_key] = data.scene
        return data.scene, ae.baseline_source_label(
            baseline_model, "門.dxf"
        )
    except Exception:
        return None, "未使用基準檔（程式計算生成）"


def _door_layout_overview_snapshot(self, render_data_by_part_key=None):
    return _door_layout_overview_snapshot_impl(self, render_data_by_part_key)


def draw_door_layout_overview(self, *, canvas=None, render_data_by_part_key=None):
    if canvas is None:
        self._sync_door_canvas_double_click_binding()
        canvas = getattr(self, "canvas_door", None)
    # Phase6PrimaryApplication does not own the legacy 2D Door canvas.  Hole
    # editor close callbacks must therefore be a safe no-op on that host.
    if canvas is None:
        return None
    self._destroy_door_layout_entry_widgets()
    snapshot = self._door_layout_overview_snapshot(render_data_by_part_key)
    if snapshot.get("error") is not None:
        return _draw_door_layout_error_impl(self, canvas, snapshot["error"])
    return _draw_door_layout_overview_preview_impl(self, snapshot, canvas)


def _door_layout_divider_frame_snapshot(self, columns, val):
    return _door_layout_divider_frame_snapshot_impl(self, columns, val)


def _draw_door_layout_dividers_and_frames(self, canvas, scale, x0, y0, columns, cells, val):
    snapshot = self._door_layout_divider_frame_snapshot(columns, val)
    return _draw_door_layout_dividers_and_frames_preview_impl(canvas, snapshot, scale, x0, y0)


def _single_door_render_snapshot(self):
    return _single_door_render_snapshot_impl(self)


def draw_door(self, val):
    if self.multi_door_enabled_var.get(): return self.draw_door_layout_overview()
    canvas = self.canvas_door; canvas.delete("all"); cw = canvas.winfo_width(); ch = canvas.winfo_height()
    if cw <= 1 or ch <= 1: return
    self.draw_grid(canvas, cw, ch)
    try: snapshot = self._single_door_render_snapshot()
    except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "門板", exc, width=cw-40, font_size=10)
    return _draw_single_door_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)


def _base_plate_render_snapshot(self, val):
    return _base_plate_render_snapshot_impl(self, val)


def draw_base_plate(self, val):
    canvas = self.canvas_base_plate; canvas.delete("all"); cw = canvas.winfo_width(); ch = canvas.winfo_height()
    if cw <= 1 or ch <= 1: return
    self.draw_grid(canvas, cw, ch)
    try: snapshot = self._base_plate_render_snapshot(val)
    except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "底板", exc, font_size=10)
    return _draw_base_plate_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)


def _indicator_door_render_snapshot(self, val):
    return _indicator_door_render_snapshot_impl(self, val)


def draw_indicator_door(self, val):
    canvas = self.canvas_indicator_door; canvas.delete("all")
    cw = canvas.winfo_width(); ch = canvas.winfo_height()
    if cw <= 1 or ch <= 1: return
    self.draw_grid(canvas, cw, ch)
    try: snapshot = self._indicator_door_render_snapshot(val)
    except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "指示燈小門", exc)
    return _draw_indicator_door_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)
