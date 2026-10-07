"""Presentation-only helpers for the hole editor.

This module owns transient Tk view/modal wiring only. Transaction state remains
owned by :mod:`phase6_hole_editor_session`; geometry/manufacturing authorities
remain in their existing AE modules.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ae_engine.sheetmetal_features import (
    CircleFeature,
    RectFeature,
    align_circle_to_neighbor,
    circle_center_distance_from_gap,
    circle_gap_from_center_distance,
    feature_finished_point,
    feature_is_within_surface,
    generate_round_fill,
    generate_round_refill,
)
from phase6_hole_editor_session import HoleEditorAction
from phase6_hole_editor_canvas_view import Phase6HoleEditorCanvasView

class HoleEditorCatalogControls:
    """Own transient catalog selection / insert-mode presentation only."""

    def __init__(
        self, *, catalog_list, pipe_catalog_list, selected_catalog_text,
        insert_mode, insert_btn, canvas, redraw,
    ):
        self.catalog_list = catalog_list
        self.pipe_catalog_list = pipe_catalog_list
        self.selected_catalog_text = selected_catalog_text
        self.insert_mode = insert_mode
        self.insert_btn = insert_btn
        self.canvas = canvas
        self.redraw = redraw

    def on_catalog_select(self, event=None, source_list=None):
        source = source_list
        if source is None and event is not None:
            source = event.widget
        if source is None:
            source = self.catalog_list
        selected = source.curselection()
        if not selected:
            return
        self.selected_catalog_text.set(source.get(selected[0]))
        other = self.pipe_catalog_list if source is self.catalog_list else self.catalog_list
        other.selection_clear(0, "end")

    def set_insert_mode(self, force=None):
        if force is None:
            self.insert_mode[0] = not self.insert_mode[0]
        else:
            self.insert_mode[0] = bool(force)
        self.insert_btn.configure(
            text=("停止插入" if self.insert_mode[0] else "插入"),
            bg=("#ff9f0a" if self.insert_mode[0] else "#30d158"),
        )
        self.redraw()

    def on_catalog_double_click(self, event=None, source_list=None):
        source = source_list or (event.widget if event is not None else self.catalog_list)
        if event is not None:
            idx = source.nearest(event.y)
            if 0 <= idx < source.size():
                source.selection_clear(0, "end")
                source.selection_set(idx)
                source.activate(idx)
        self.on_catalog_select(source_list=source)
        if self.selected_catalog_text.get().startswith("＋ 自訂"):
            return "break"
        self.set_insert_mode(True)
        self.canvas.focus_set()
        return "break"


class HoleEditorReferencePresentation:
    """Own presentation-only reference-distance field refresh behavior."""

    def __init__(
        self, *, selection_provider, context_provider,
        feature_reference_anchor, reference_distances,
        door_enclosure_reference_guide, door_frame_edges_factory,
        round_settings_btn, labels, values, ref_entries, side_labels,
        last_distances, suppress_entry_events,
    ):
        self.selection_provider = selection_provider
        self.context_provider = context_provider
        self.feature_reference_anchor = feature_reference_anchor
        self.reference_distances = reference_distances
        self.door_enclosure_reference_guide = door_enclosure_reference_guide
        self.door_frame_edges_factory = door_frame_edges_factory
        self.round_settings_btn = round_settings_btn
        self.labels = labels
        self.values = values
        self.ref_entries = ref_entries
        self.side_labels = side_labels
        self.last_distances = last_distances
        self.suppress_entry_events = suppress_entry_events

    def active_reference_guide(self):
        context = self.context_provider()
        if (
            context["active_part_key"] == "door"
            and context["indicator_box_dist_enabled"]
            and context["door_frame_width"] is not None
            and context["door_thickness"] is not None
            and context["door_gap_w"] is not None
            and context["door_gap_h"] is not None
        ):
            return self.door_enclosure_reference_guide(
                context["reference_guide"],
                context["door_frame_edges"] or self.door_frame_edges_factory(),
                frame_width=context["door_frame_width"],
                thickness=context["door_thickness"],
                gap_w=context["door_gap_w"],
                gap_h=context["door_gap_h"],
            )
        return context["reference_guide"]

    def refresh_reference_fields(self):
        idx, feature_list = self.selection_provider()
        self.suppress_entry_events[0] = True
        try:
            if not (0 <= idx < len(feature_list)):
                for variable in self.values.values():
                    variable.set("")
                self.last_distances[0] = None
                self.round_settings_btn.configure(state=tk.DISABLED)
                return
            feature = feature_list[idx]
            anchor = self.feature_reference_anchor(feature)
            self.round_settings_btn.configure(
                state=(tk.NORMAL if isinstance(feature, CircleFeature) else tk.DISABLED)
            )
            context = self.context_provider()
            distances = self.reference_distances(
                context["surface"], feature_list, idx, anchor,
                context["width"], context["height"],
                reference_guide=self.active_reference_guide(),
            )
            self.last_distances[0] = distances
            x_side = self.side_labels[distances.x_side]
            y_side = self.side_labels[distances.y_side]
            self.labels["x_edge"].set(f"X 到{x_side}邊框")
            self.labels["x_neighbor"].set(f"X 到{x_side}側鄰近孔")
            self.labels["y_edge"].set(f"Y 到{y_side}邊框")
            self.labels["y_neighbor"].set(f"Y 到{y_side}側鄰近孔")
            self.values["x_edge"].set(f"{distances.x_edge_distance:.2f}")
            self.values["y_edge"].set(f"{distances.y_edge_distance:.2f}")
            self.values["x_neighbor"].set(
                "" if distances.x_neighbor_distance is None else f"{distances.x_neighbor_distance:.2f}"
            )
            self.values["y_neighbor"].set(
                "" if distances.y_neighbor_distance is None else f"{distances.y_neighbor_distance:.2f}"
            )
            self.ref_entries[("x", "neighbor")].configure(
                state=(tk.NORMAL if distances.x_neighbor_index is not None else tk.DISABLED)
            )
            self.ref_entries[("y", "neighbor")].configure(
                state=(tk.NORMAL if distances.y_neighbor_index is not None else tk.DISABLED)
            )
        finally:
            self.suppress_entry_events[0] = False

class HoleEditorIndicatorStateCollector:
    """Collect live indicator UI state and delegate normalization."""

    def __init__(
        self, *, mode_var_provider, layers_var_provider, group_vars_provider,
        offset_x_var_provider, offset_y_var_provider, box_dist_var_provider,
        normalize_state,
    ):
        self.mode_var_provider = mode_var_provider
        self.layers_var_provider = layers_var_provider
        self.group_vars_provider = group_vars_provider
        self.offset_x_var_provider = offset_x_var_provider
        self.offset_y_var_provider = offset_y_var_provider
        self.box_dist_var_provider = box_dist_var_provider
        self.normalize_state = normalize_state

    def collect(self):
        mode_var = self.mode_var_provider()
        if mode_var is None:
            return None
        try:
            layers = max(1, min(6, int(self.layers_var_provider().get())))
        except (TypeError, ValueError):
            layers = 1
        groups = []
        for var in self.group_vars_provider():
            try:
                groups.append(max(1, int(var.get())))
            except ValueError:
                groups.append(2)
        while len(groups) < 6:
            groups.append(2)
        try:
            offset_x = float(self.offset_x_var_provider().get())
        except ValueError:
            offset_x = 0.0
        try:
            offset_y = float(self.offset_y_var_provider().get())
        except ValueError:
            offset_y = 0.0
        return self.normalize_state({
            "mode": mode_var.get(),
            "layers": layers,
            "groups": groups[:6],
            "offset_x": offset_x,
            "offset_y": offset_y,
            "is_box_dist": bool(self.box_dist_var_provider().get()),
        })

class HoleEditorIndicatorGroupControls:
    """Own presentation-only rebuilding of indicator group rows."""

    def __init__(self, *, groups_frame, layers_var, group_vars, request_redraw, panel_bg, muted_color):
        self.groups_frame = groups_frame
        self.layers_var = layers_var
        self.group_vars = group_vars
        self.request_redraw = request_redraw
        self.panel_bg = panel_bg
        self.muted_color = muted_color

    def rebuild(self, *_args):
        for child in self.groups_frame.winfo_children():
            child.destroy()
        try:
            layers = max(1, min(6, int(self.layers_var.get())))
        except ValueError:
            layers = 1
        for i in range(layers):
            tk.Label(
                self.groups_frame, text=f"{i+1}層", bg=self.panel_bg, fg=self.muted_color,
                font=('Microsoft JhengHei', 8),
            ).grid(row=i, column=0, sticky="w", padx=(0, 3), pady=1)
            cb = ttk.Combobox(
                self.groups_frame, textvariable=self.group_vars[i],
                values=[str(v) for v in range(1, 9)], width=3, state="readonly",
            )
            cb.grid(row=i, column=1, sticky="w", pady=1)
            cb.bind("<<ComboboxSelected>>", self.request_redraw)
        self.request_redraw()

class HoleEditorSyncCoordinator:
    """Own hole-editor external-sync then preview coordination."""

    def __init__(self, *, sync_callback, draw_preview):
        self.sync_callback = sync_callback
        self.draw_preview = draw_preview

    def sync_all(self):
        if self.sync_callback is not None:
            self.sync_callback()
        self.draw_preview()

class HoleEditorIndicatorContextRefresh:
    """Own indicator-context refresh presentation/routing only."""

    def __init__(
        self, *, component_context_provider, indicator_mode_available,
        collect_indicator_state, component_contexts, baseline_status_var,
        baseline_status_label, set_indicator_page_visible,
        active_context_key_provider, switch_editor_context, redraw,
        editor_tabs, indicator_page, component_tabs, toolbar,
        selected_component_key_provider,
    ):
        self.component_context_provider = component_context_provider
        self.indicator_mode_available = indicator_mode_available
        self.collect_indicator_state = collect_indicator_state
        self.component_contexts = component_contexts
        self.baseline_status_var = baseline_status_var
        self.baseline_status_label = baseline_status_label
        self.set_indicator_page_visible = set_indicator_page_visible
        self.active_context_key_provider = active_context_key_provider
        self.switch_editor_context = switch_editor_context
        self.redraw = redraw
        self.editor_tabs = editor_tabs
        self.indicator_page = indicator_page
        self.component_tabs = component_tabs
        self.toolbar = toolbar
        self.selected_component_key_provider = selected_component_key_provider

    @staticmethod
    def baseline_status_color(text):
        return "#64d2ff" if str(text or "").startswith("基準檔：") else "#ff9f0a"

    def refresh(self):
        if self.component_context_provider is None or not self.indicator_mode_available:
            return
        state_now = self.collect_indicator_state()
        if state_now is None or state_now.get("mode") != "indicator_box":
            if self.component_tabs is not None:
                self.component_tabs.pack_forget()
            if self.active_context_key_provider() != "door":
                self.switch_editor_context("door")
            self.set_indicator_page_visible(False)
            if self.active_context_key_provider() == "door":
                self.redraw()
            return
        try:
            contexts = self.component_context_provider(state_now) or {}
        except Exception as exc:
            self.baseline_status_var.set(f"指示燈盒資料錯誤：{exc}")
            if self.baseline_status_label is not None:
                self.baseline_status_label.configure(fg="#ff453a")
            self.set_indicator_page_visible(True)
            if self.active_context_key_provider() == "door":
                self.redraw()
            return
        for context_key in ("indicator_box", "indicator_door"):
            context = contexts.get(context_key)
            if context:
                self.component_contexts[context_key] = context
        self.set_indicator_page_visible(True)
        if (
            self.editor_tabs is not None
            and self.indicator_page is not None
            and self.editor_tabs.select() == str(self.indicator_page)
        ):
            if self.component_tabs is not None and not self.component_tabs.winfo_manager():
                self.component_tabs.pack(fill=tk.X, pady=(0, 4), before=self.toolbar)
            self.switch_editor_context(self.selected_component_key_provider())
        elif self.active_context_key_provider() != "door":
            self.switch_editor_context("door")
        else:
            self.redraw()

class HoleEditorPageNavigation:
    """Own transient notebook/page routing for the shared hole editor."""

    def __init__(
        self, *, editor_tabs, main_page, indicator_page,
        component_tabs, indicator_door_page, toolbar,
        refresh_indicator_component_contexts, switch_editor_context,
    ):
        self.editor_tabs = editor_tabs
        self.main_page = main_page
        self.indicator_page = indicator_page
        self.component_tabs = component_tabs
        self.indicator_door_page = indicator_door_page
        self.toolbar = toolbar
        self.refresh_indicator_component_contexts = refresh_indicator_component_contexts
        self.switch_editor_context = switch_editor_context

    def selected_indicator_component_key(self):
        if self.component_tabs is None:
            return "indicator_box"
        selected_tab = self.component_tabs.select()
        if self.indicator_door_page is not None and selected_tab == str(self.indicator_door_page):
            return "indicator_door"
        return "indicator_box"

    def on_editor_page_changed(self, event=None):
        if self.editor_tabs is None or self.main_page is None:
            return
        selected_page = self.editor_tabs.select()
        if self.indicator_page is not None and selected_page == str(self.indicator_page):
            if self.component_tabs is not None and not self.component_tabs.winfo_manager():
                self.component_tabs.pack(fill=tk.X, pady=(0, 4), before=self.toolbar)
            self.refresh_indicator_component_contexts()
        else:
            if self.component_tabs is not None:
                self.component_tabs.pack_forget()
            self.switch_editor_context("door")

    def on_indicator_component_page_changed(self, event=None):
        if (
            self.editor_tabs is None
            or self.indicator_page is None
            or self.editor_tabs.select() != str(self.indicator_page)
        ):
            return
        self.switch_editor_context(self.selected_indicator_component_key())

class HoleEditorFormRowBuilders:
    """Own presentation-only construction of compact editor input rows."""

    def __init__(
        self, *, panel_bg, text_color, normal_font,
        entry_font, ref_entries_provider,
    ):
        self.panel_bg = panel_bg
        self.text_color = text_color
        self.normal_font = normal_font
        self.entry_font = entry_font
        self.ref_entries_provider = ref_entries_provider

    def small_row(self, parent, label, variable):
        row = tk.Frame(parent, bg=self.panel_bg)
        row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(
            row, text=label, bg=self.panel_bg, fg=self.text_color,
            width=7, anchor=tk.W, font=self.normal_font,
        ).pack(side=tk.LEFT)
        tk.Entry(
            row, textvariable=variable, font=('Consolas', 13), width=9,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def add_group_entry(self, group, label_var, value_var, axis, mode):
        row = tk.Frame(group, bg="#24242c")
        row.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(
            row, textvariable=label_var, bg="#24242c", fg="#ffd60a",
            font=('Microsoft JhengHei', 10, 'bold'), width=13, anchor=tk.W,
        ).pack(side=tk.LEFT)
        ent = tk.Entry(
            row, textvariable=value_var, font=self.entry_font,
            justify=tk.RIGHT, width=8,
        )
        ent.pack(side=tk.LEFT, padx=(4, 0), ipady=2)
        self.ref_entries_provider()[(axis, mode)] = ent
        return ent

class HoleEditorFullscreenActions:
    """Own transient fullscreen-window presentation state only."""

    def __init__(
        self, *, editor, fullscreen_button, fullscreen_state,
        restore_geometry, redraw_provider,
    ):
        self.editor = editor
        self.fullscreen_button = fullscreen_button
        self.fullscreen_state = fullscreen_state
        self.restore_geometry = restore_geometry
        self.redraw_provider = redraw_provider

    def toggle_fullscreen(self, event=None):
        entering = not self.fullscreen_state[0]
        if entering:
            self.restore_geometry[0] = self.editor.geometry()
            self.fullscreen_state[0] = True
            try:
                self.editor.attributes("-fullscreen", True)
                self.editor.update_idletasks()
            except tk.TclError:
                pass
            try:
                native_fullscreen = bool(self.editor.attributes("-fullscreen"))
            except tk.TclError:
                native_fullscreen = False
            if not native_fullscreen:
                self.editor.geometry(
                    f"{self.editor.winfo_screenwidth()}x{self.editor.winfo_screenheight()}+0+0"
                )
        else:
            self.fullscreen_state[0] = False
            try:
                self.editor.attributes("-fullscreen", False)
            except tk.TclError:
                pass
            if self.restore_geometry[0]:
                self.editor.geometry(self.restore_geometry[0])
        self.fullscreen_button.configure(
            text=("還原視窗" if self.fullscreen_state[0] else "全螢幕")
        )
        self.editor.after_idle(self.redraw_provider())
        return "break"

class HoleEditorCreatedListPresentation:
    """Own presentation-only rendering of the created-hole list."""

    def __init__(
        self, *, created_list, feature_list_provider,
        selected_index_provider, end_token,
    ):
        self.created_list = created_list
        self.feature_list_provider = feature_list_provider
        self.selected_index_provider = selected_index_provider
        self.end_token = end_token

    def feature_display(self, feature, i):
        process = (
            "盲孔" if getattr(feature, "layer", "CUTTING") == "BLIND_HOLE" else ""
        )
        if isinstance(feature, CircleFeature):
            desc = f"Ø{feature.diameter:g}"
        elif isinstance(feature, RectFeature):
            desc = f"{feature.width:g}×{feature.height:g}"
        else:
            desc = feature.source_type or "DXF孔型"
        return f"{i+1:02d}  {desc:<14}  {process}"

    def refresh_created(self):
        feature_list = self.feature_list_provider()
        self.created_list.delete(0, self.end_token)
        for i, feature in enumerate(feature_list):
            self.created_list.insert(
                self.end_token, self.feature_display(feature, i)
            )
        selected_index = self.selected_index_provider()
        if 0 <= selected_index < len(feature_list):
            self.created_list.selection_set(selected_index)
            self.created_list.see(selected_index)

class HoleEditorIndicatorUiActions:
    """Own transient indicator-page visibility and redraw scheduling."""

    def __init__(
        self, *, editor_tabs, indicator_page, main_page, indicator_page_visible,
        mode_provider, context_refresh_provider, redraw_provider,
        schedule_idle, refresh_reference_fields,
    ):
        self.editor_tabs = editor_tabs
        self.indicator_page = indicator_page
        self.main_page = main_page
        self.indicator_page_visible = indicator_page_visible
        self.mode_provider = mode_provider
        self.context_refresh_provider = context_refresh_provider
        self.redraw_provider = redraw_provider
        self.schedule_idle = schedule_idle
        self.refresh_reference_fields = refresh_reference_fields

    def set_indicator_page_visible(self, visible):
        if self.editor_tabs is None or self.indicator_page is None or self.main_page is None:
            return
        visible = bool(visible)
        tabs = set(self.editor_tabs.tabs())
        page_name = str(self.indicator_page)
        if visible and page_name not in tabs:
            self.editor_tabs.add(self.indicator_page, text="  指示燈盒  ")
            self.indicator_page_visible[0] = True
        elif not visible and page_name in tabs:
            if self.editor_tabs.select() == page_name:
                self.editor_tabs.select(self.main_page)
            self.editor_tabs.forget(self.indicator_page)
            self.indicator_page_visible[0] = False

    def request_indicator_redraw(self, *_args):
        self.set_indicator_page_visible(self.mode_provider() == "indicator_box")
        callback = self.context_refresh_provider()
        if callback is None:
            callback = self.redraw_provider()
        if callback is not None:
            self.schedule_idle(callback)

    def on_box_distance_toggle(self):
        self.request_indicator_redraw()
        self.schedule_idle(self.refresh_reference_fields)

def draw_hole_editor_hint(canvas, canvas_width, *, endcap=False):
    """Draw the existing double-click hole-editor hint without owning state."""
    text = "雙擊：開孔"
    canvas.create_text(
        canvas_width - 18,
        18,
        text=text,
        anchor=tk.NE,
        fill="#ff9f0a",
        font=("Microsoft JhengHei", 9, "bold"),
        tags=("phase6_hole_hint",),
    )
