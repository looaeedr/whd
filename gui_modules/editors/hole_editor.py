"""Thin routing helpers for hole-editor entry points.

This module owns transient editor routing/context assembly only. Committed
project, part, geometry, manufacturing, session, and canvas authority stays in
existing controllers/AE/session seams.
"""

from __future__ import annotations

from dataclasses import replace
from tkinter import messagebox

from phase6_hole_editor_session import HoleEditorAction

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.contracts import ManufacturingContext
from ae_engine.corner_type_ui import is_unknown_model
from ae_engine.sheetmetal_features import (
    DoorIndicatorContext,
    RectGuide,
    Vec2,
    feature_surface_from_rect,
    feature_surface_from_structural_result,
    feature_to_legacy_hole,
    legacy_hole_to_feature,
    resolve_endcap_finished_face_guide,
)
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    build_base_plate_result,
    build_door_result,
    build_finished_reference_guide,
    build_indicator_box_result,
    build_unknown_base_plate_result,
    build_unknown_door_result,
    build_unknown_indicator_box_result,
)


class HoleEditorTransientActions:
    """Own transient editor transaction commands while reusing session authority."""

    def __init__(
        self, *, hole_session, feature_list=None, feature_list_provider=None, var_rotation,
        refresh_created, refresh_reference_fields, redraw, sync_all,
    ):
        self.hole_session = hole_session
        self.feature_list_provider = feature_list_provider or (lambda: feature_list)
        self.var_rotation = var_rotation
        self.refresh_created = refresh_created
        self.refresh_reference_fields = refresh_reference_fields
        self.redraw = redraw
        self.sync_all = sync_all

    def commit_active_edit(self, keep_selected=True):
        self.hole_session.execute(
            HoleEditorAction.commit_active(keep_selected=keep_selected)
        )
        self.refresh_created()
        self.refresh_reference_fields()
        self.redraw()

    def undo_last_action(self, event=None):
        self.hole_session.execute(HoleEditorAction.undo())
        self.refresh_created()
        self.refresh_reference_fields()
        self.redraw()
        self.sync_all()
        return "break"

    def cancel_active_edit(self):
        had_active = self.hole_session.has_active_edit
        self.hole_session.execute(HoleEditorAction.cancel_active())
        if not had_active:
            return False
        self.refresh_created()
        self.refresh_reference_fields()
        self.sync_all()
        self.redraw()
        return True

    def begin_edit(self, idx, old_feature_marker="existing"):
        if old_feature_marker == "new":
            if self.hole_session.selected_index != idx:
                self.hole_session.execute(HoleEditorAction.select(idx))
        else:
            self.hole_session.execute(HoleEditorAction.select(idx))
        feature_list = self.feature_list_provider()
        if 0 <= idx < len(feature_list):
            rotation = int(
                getattr(feature_list[idx], "rotation_deg", 0) or 0
            ) % 360
            self.var_rotation.set(f"{360 if rotation == 0 else rotation}°")
        self.refresh_created()
        self.refresh_reference_fields()
        self.redraw()

    def select_feature(self, idx):
        self.begin_edit(idx, "existing")


class HoleEditorCreatedListActions:
    """Own created-list selection/process/delete commands via session authority."""

    def __init__(
        self, *, hole_session, feature_list=None, feature_list_provider=None, created_list, select_feature,
        feature_with_process, refresh_created, refresh_reference_fields,
        redraw, sync_all,
    ):
        self.hole_session = hole_session
        self.feature_list_provider = feature_list_provider or (lambda: feature_list)
        self.created_list = created_list
        self.select_feature = select_feature
        self.feature_with_process = feature_with_process
        self.refresh_created = refresh_created
        self.refresh_reference_fields = refresh_reference_fields
        self.redraw = redraw
        self.sync_all = sync_all

    def on_created_select(self, event=None):
        selected = self.created_list.curselection()
        if selected:
            self.select_feature(selected[0])

    def toggle_created_process(self, event=None):
        selected = self.created_list.curselection()
        if not selected:
            return
        idx = selected[0]
        self.hole_session.execute(HoleEditorAction.select(idx))
        feature_list = self.feature_list_provider()
        old = feature_list[idx]
        process = (
            "CUTTING"
            if getattr(old, "layer", "CUTTING") == "BLIND_HOLE"
            else "BLIND_HOLE"
        )
        replacement = self.feature_with_process(old, process)
        self.hole_session.execute(
            HoleEditorAction.replace_selected_committed(replacement)
        )
        self._refresh_all()

    def delete_selected(self):
        idx = self.hole_session.selected_index
        feature_list = self.feature_list_provider()
        if not (0 <= idx < len(feature_list)):
            return
        self.hole_session.execute(HoleEditorAction.delete_selected())
        self._refresh_all()

    def _refresh_all(self):
        self.refresh_created()
        self.refresh_reference_fields()
        self.redraw()
        self.sync_all()


class HoleEditorCanvasPointerActions:
    """Own canvas pointer orchestration while delegating geometry and session authority."""

    def __init__(
        self, *, hole_session, canvas_view, dragging, insert_mode, context_provider,
        select_feature, make_feature, feature_is_within_surface,
        move_feature_within_surface, begin_edit, refresh_reference_fields,
        redraw, sync_all, warn_out_of_bounds,
    ):
        self.hole_session = hole_session
        self.canvas_view = canvas_view
        self.dragging = dragging
        self.insert_mode = insert_mode
        self.context_provider = context_provider
        self.select_feature = select_feature
        self.make_feature = make_feature
        self.feature_is_within_surface = feature_is_within_surface
        self.move_feature_within_surface = move_feature_within_surface
        self.begin_edit = begin_edit
        self.refresh_reference_fields = refresh_reference_fields
        self.redraw = redraw
        self.sync_all = sync_all
        self.warn_out_of_bounds = warn_out_of_bounds

    def on_canvas_down(self, event):
        point = self.canvas_view.canvas_to_world(event.x, event.y)
        if point is None:
            return
        hit = self.canvas_view.hit_test(event.x, event.y)
        if hit is not None:
            self.dragging[0] = True
            self.select_feature(hit)
            return
        if not self.insert_mode[0]:
            return
        feature = self.make_feature(point)
        if feature is None:
            return
        context = self.context_provider()
        if not self.feature_is_within_surface(
            context["surface"], feature, context["width"], context["height"]
        ):
            self.warn_out_of_bounds()
            return
        self.hole_session.execute(HoleEditorAction.insert(feature))
        self.begin_edit(self.hole_session.selected_index, "new")
        self.sync_all()

    def on_canvas_drag(self, event):
        context = self.context_provider()
        feature_list = context["feature_list"]
        if not self.dragging[0] or not (
            0 <= self.hole_session.selected_index < len(feature_list)
        ):
            return
        point = self.canvas_view.canvas_to_world(event.x, event.y)
        if point is None:
            return
        idx = self.hole_session.selected_index
        moved = self.move_feature_within_surface(
            feature_list[idx], point,
            context["width"], context["height"], context["surface"],
        )
        self.hole_session.execute(HoleEditorAction.replace_selected(moved))
        self.refresh_reference_fields()
        self.redraw()

    def on_canvas_up(self, event):
        if self.dragging[0]:
            self.dragging[0] = False
            self.sync_all()

class HoleEditorModalLifecycle:
    """Own modal confirm/cancel/Escape flow while delegating all authorities."""

    def __init__(
        self, *, hole_session, has_selected_feature, position_authority,
        commit_active_edit, sync_all, validate_current_indicator_fit,
        door_indicator_state, collect_indicator_state, door_indicator_commit,
        editor_closed, editor, on_close, insert_mode, set_insert_mode,
        cancel_active_edit,
    ):
        self.hole_session = hole_session
        self.has_selected_feature = has_selected_feature
        self.position_authority = position_authority
        self.commit_active_edit = commit_active_edit
        self.sync_all = sync_all
        self.validate_current_indicator_fit = validate_current_indicator_fit
        self.door_indicator_state = door_indicator_state
        self.collect_indicator_state = collect_indicator_state
        self.door_indicator_commit = door_indicator_commit
        self.editor_closed = editor_closed
        self.editor = editor
        self.on_close = on_close
        self.insert_mode = insert_mode
        self.set_insert_mode = set_insert_mode
        self.cancel_active_edit = cancel_active_edit

    def confirm_reference_edit(self):
        if not self.has_selected_feature():
            return
        self.position_authority[0] = "reference"
        self.commit_active_edit(keep_selected=False)
        self.sync_all()

    def confirm_all(self):
        if not self.validate_current_indicator_fit(show_error=True):
            return
        self.hole_session.finish(commit=True)
        if self.door_indicator_state is not None:
            committed = self.collect_indicator_state()
            if committed is not None:
                self.door_indicator_state.clear()
                self.door_indicator_state.update(committed)
                if self.door_indicator_commit is not None:
                    self.door_indicator_commit(committed)
        self.editor_closed[0] = True
        self.sync_all()
        self.editor.destroy()
        if self.on_close is not None:
            self.on_close()

    def cancel_all(self):
        if self.editor_closed[0]:
            return
        self.hole_session.finish(commit=False)
        self.editor_closed[0] = True
        self.sync_all()
        self.editor.destroy()
        if self.on_close is not None:
            self.on_close()

    def on_escape(self, event=None):
        if self.insert_mode[0]:
            self.set_insert_mode(False)
            return "break"
        if self.hole_session.has_active_edit:
            self.cancel_active_edit()
            return "break"
        self.cancel_all()
        return "break"


def open_hole_editor(host, key):
    """Route the legacy head/tail command into the host's unified editor."""
    label_map = {"head": "封頭", "tail": "封尾"}
    if key not in label_map:
        messagebox.showerror("開孔失敗", f"未知板面: {key}")
        return

    try:
        values = host.get_float_values()
    except ValueError:
        messagebox.showerror("輸入錯誤", "請先確保主畫面所有數值輸入正確")
        return

    width = float(values["w"])
    height = float(values["d"])
    thickness = float(values["t"])
    face_guide = resolve_endcap_finished_face_guide(width, height, thickness)
    surface = feature_surface_from_rect(
        f"{key}_finished_face",
        face_guide.min_point,
        face_guide.max_point,
    )

    legacy = host.tail_holes if key == "tail" else host.head_holes
    host.surface_features[key] = [legacy_hole_to_feature(hole) for hole in legacy]

    def sync_legacy():
        legacy[:] = [
            feature_to_legacy_hole(feature, width, height)
            for feature in host.surface_features[key]
        ]

    reference_guide = RectGuide(
        Vec2(0.0, 0.0),
        Vec2(width, height),
        "finished_boundary",
    )
    host._open_unified_hole_editor(
        key,
        label_map[key],
        surface,
        width,
        height,
        sync_callback=sync_legacy,
        reference_guide=reference_guide,
    )


def _door_context(host, values):
    material_fw = host._door_material_frame_width(values["fw"], values["t"])
    if is_unknown_model(host.baseline_var.get()):
        result = build_unknown_door_result(
            w=values["w"], h=values["h"], t=values["t"], fw=material_fw,
            gap_w=values["door_gap_w"], gap_h=values["door_gap_h"],
            fold_left=values["door_fold_l"], fold_right=values["door_fold_r"],
            fold_top=values["door_fold_t"], fold_bottom=values["door_fold_b"],
            corner_policy=host._manual_corner_policy("door", material_fw),
        )
    else:
        result = build_door_result(
            w=values["w"], h=values["h"], t=values["t"], fw=material_fw,
            gap_w=values["door_gap_w"], gap_h=values["door_gap_h"],
            fold_left=values["door_fold_l"], fold_right=values["door_fold_r"],
            fold_top=values["door_fold_t"], fold_bottom=values["door_fold_b"],
        )
    surface = feature_surface_from_structural_result("door", result)
    finished_w, finished_h = ae.calculate_door_finished_size(
        values["w"], values["h"], material_fw,
        values["door_gap_w"], values["door_gap_h"], values["t"],
    )
    reference_guide = build_finished_reference_guide(
        "door", result, finished_width=finished_w, finished_height=finished_h
    )
    baseline_scene = None
    baseline_status_text = "未使用基準檔（程式計算生成）"
    model = host._baseline_source_model()
    if model and ae.has_baseline_part(model, "門.dxf"):
        try:
            data = ae.get_stretched_door_data(
                model, values["w"], values["h"], values["t"], material_fw,
                values["door_gap_w"], values["door_gap_h"],
                values["door_fold_l"], values["door_fold_r"],
                values["door_fold_t"], values["door_fold_b"],
                frame_edges=DoorFrameEdges(),
            )
            baseline_scene = data.scene
            baseline_status_text = ae.baseline_source_label(model, "門.dxf")
        except Exception:
            baseline_status_text = "未使用基準檔（程式計算生成）"
    return {
        "title": "門板", "surface": surface, "width": result.width,
        "height": result.height, "reference_guide": reference_guide,
        "door_indicator_state": host._single_door_indicator_state_snapshot(),
        "door_indicator_context": DoorIndicatorContext(
            finished_width=finished_w, finished_height=finished_h,
            left_fold=values["door_fold_l"], bottom_fold=values["door_fold_b"],
        ),
        "door_indicator_commit": host._apply_single_door_indicator_state,
        "door_frame_edges": DoorFrameEdges(),
        "door_gap_w": values["door_gap_w"], "door_gap_h": values["door_gap_h"],
        "door_frame_width": values["fw"], "door_thickness": values["t"],
        "baseline_scene": baseline_scene,
        "baseline_status_text": baseline_status_text,
        "indicator_component_context_provider": lambda state, val=values: host._indicator_component_editor_contexts(
            state, val,
            box_features=host.surface_features["indicator_box"],
            door_features=host.surface_features["indicator_door"],
        ),
    }


def _base_plate_context(host, values):
    baseline_status_text = "未使用基準檔（程式計算生成）"
    if is_unknown_model(host.baseline_var.get()):
        baseline_status_text = "自訂 / 手動截角"
        result = build_unknown_base_plate_result(
            w=values["w"], h=values["h"], t=values["t"],
            shrink_top=values["base_plate_shrink_top"],
            shrink_bottom=values["base_plate_shrink_bottom"],
            shrink_left=values["base_plate_shrink_left"],
            shrink_right=values["base_plate_shrink_right"],
            bend=values["base_plate_bend"],
            corner_policy=host._manual_corner_policy("base_plate", values["fw"]),
        )
    else:
        result = build_base_plate_result(
            w=values["w"], h=values["h"], t=values["t"],
            shrink_top=values["base_plate_shrink_top"],
            shrink_bottom=values["base_plate_shrink_bottom"],
            shrink_left=values["base_plate_shrink_left"],
            shrink_right=values["base_plate_shrink_right"],
            bend=values["base_plate_bend"],
        )
    finished_w = values["w"] - values["base_plate_shrink_left"] - values["base_plate_shrink_right"]
    finished_h = values["h"] - values["base_plate_shrink_top"] - values["base_plate_shrink_bottom"]
    return {
        "title": "底板",
        "surface": feature_surface_from_structural_result("base_plate", result),
        "width": result.width, "height": result.height,
        "reference_guide": build_finished_reference_guide(
            "base_plate", result, finished_width=finished_w, finished_height=finished_h
        ),
        "baseline_status_text": baseline_status_text,
    }


def _indicator_box_context(host, values):
    try:
        layers = int(host.indicator_l_var.get())
        groups = [int(host.indicator_layer_g_vars[i].get()) for i in range(layers)]
    except ValueError:
        messagebox.showerror("輸入錯誤", "指示燈排列參數無效")
        return None
    try:
        data = ae.get_stretched_indicator_box_data(
            "指示燈", groups, values["t"], corner_policy=None
        )
    except Exception as exc:
        messagebox.showerror("開孔失敗", f"指示燈盒基準載入失敗: {exc}")
        return None
    surface = ae.feature_surface_from_drawing_scene("indicator_box", data.scene)
    width, height = data.params["w"], data.params["h"]
    fold = float(getattr(ae, "indicator_box_fold_def", 49.0))
    indicator_corner_policy = None
    result = (
        build_unknown_indicator_box_result(
            total_width=width, total_height=height, t=values["t"], fold=fold,
            corner_policy=indicator_corner_policy,
        ) if indicator_corner_policy is not None else
        build_indicator_box_result(total_width=width, total_height=height, t=values["t"], fold=fold)
    )
    return {
        "title": "指示燈盒", "surface": surface, "width": width, "height": height,
        "reference_guide": build_finished_reference_guide(
            "indicator_box", result,
            finished_width=width - 2.0 * fold + values["t"],
            finished_height=height - 2.0 * fold + values["t"],
        ),
        "baseline_scene": data.scene,
        "baseline_status_text": ae.indicator_shared_baseline_source_label("盒子.dxf"),
    }


def _indicator_door_context(host, values):
    try:
        layers = int(host.indicator_l_var.get())
        groups = [int(host.indicator_layer_g_vars[i].get()) for i in range(layers)]
    except ValueError:
        messagebox.showerror("輸入錯誤", "指示燈排列參數無效")
        return None
    policy = replace(
        manufacturing_api.resolve_policy(),
        frame_width=float(values["fw"]),
        door_gap_w=float(values["door_gap_w"]),
        door_gap_h=float(values["door_gap_h"]),
        indicator_small_door_fold=float(getattr(ae, "indicator_small_door_fold_def", 19.0)),
    )
    context = ManufacturingContext(policy=policy)
    spec = manufacturing_api.indicator_small_door_spec(
        groups, thickness=values["t"], context=context
    )
    finished_w, finished_h = manufacturing_api.door_finished_face_size(spec, context)
    try:
        data = ae.get_stretched_door_data(
            None, spec.width, spec.height, values["t"], values["fw"],
            values["door_gap_w"], values["door_gap_h"],
            spec.fold_left, spec.fold_right, spec.fold_top, spec.fold_bottom,
            indicator_window_groups=groups,
        )
    except Exception as exc:
        messagebox.showerror("開孔失敗", f"指示燈小門基準載入失敗: {exc}")
        return None
    try:
        surface = ae.feature_surface_from_drawing_scene("indicator_door", data.scene)
    except ValueError as exc:
        messagebox.showerror("開孔失敗", str(exc))
        return None
    result = build_door_result(
        w=spec.width, h=spec.height, t=values["t"], fw=values["fw"],
        gap_w=values["door_gap_w"], gap_h=values["door_gap_h"],
        fold_left=19.0, fold_right=19.0, fold_top=19.0, fold_bottom=19.0,
    )
    return {
        "title": "指示燈小門", "surface": surface,
        "width": data.params["total_width"], "height": data.params["total_depth"],
        "reference_guide": build_finished_reference_guide(
            "indicator_door", result, finished_width=finished_w, finished_height=finished_h
        ),
        "baseline_scene": data.scene,
        "baseline_status_text": ae.indicator_shared_baseline_source_label("小門.dxf"),
    }


def open_part_hole_editor(host, part_key):
    """Route one physical-part editor while preserving existing authority seams."""
    host.workspace_controller.set_active_part(part_key)
    if part_key == "door" and host.multi_door_enabled_var.get():
        cell = host.get_selected_door_layout_cell()
        host.open_door_layout_cell_editor(cell.column_index, cell.row_index)
        return
    if part_key == "box_body":
        host.open_box_body_face_editor(host.box_body_face_selected_var.get() or "back")
        return
    try:
        values = host.get_float_values()
    except ValueError as exc:
        messagebox.showerror("輸入錯誤", str(exc))
        return
    builders = {
        "door": _door_context,
        "base_plate": _base_plate_context,
        "indicator_box": _indicator_box_context,
        "indicator_door": _indicator_door_context,
    }
    builder = builders.get(part_key)
    if builder is None:
        messagebox.showerror("開孔失敗", f"未知板面: {part_key}")
        return
    editor_context = builder(host, values)
    if editor_context is None:
        return
    host._open_unified_hole_editor(
        part_key,
        editor_context.pop("title"),
        editor_context.pop("surface"),
        editor_context.pop("width"),
        editor_context.pop("height"),
        **editor_context,
    )
