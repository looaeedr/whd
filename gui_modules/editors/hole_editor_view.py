"""Presentation-only helpers for the hole editor.

This module owns transient Tk view/modal wiring only. Transaction state remains
owned by :mod:`phase6_hole_editor_session`; geometry/manufacturing authorities
remain in their existing AE modules.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

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


def open_round_hole_settings(
    *, editor, theme, hole_session, feature_list, surface, width, height,
    round_window, position_authority, refresh_created, refresh_reference_fields,
    redraw, sync_all,
):
    """Open the round-hole fill/refill modal without owning committed state."""
    idx = hole_session.selected_index
    if not (0 <= idx < len(feature_list)) or not isinstance(feature_list[idx], CircleFeature):
        return
    if round_window[0] is not None and round_window[0].winfo_exists():
        round_window[0].lift()
        return

    hole_session.execute(HoleEditorAction.commit_active(keep_selected=True))
    controller = _RoundHoleSettingsDialog(
        editor=editor,
        theme=theme,
        hole_session=hole_session,
        feature_list=feature_list,
        surface=surface,
        width=width,
        height=height,
        round_window=round_window,
        position_authority=position_authority,
        refresh_created=refresh_created,
        refresh_reference_fields=refresh_reference_fields,
        redraw=redraw,
        sync_all=sync_all,
        selected_index=idx,
    )
    controller.open()


class _RoundHoleSettingsDialog:
    def __init__(
        self, *, editor, theme, hole_session, feature_list, surface, width, height,
        round_window, position_authority, refresh_created, refresh_reference_fields,
        redraw, sync_all, selected_index,
    ):
        self.editor = editor
        self.theme = theme
        self.hole_session = hole_session
        self.feature_list = feature_list
        self.surface = surface
        self.width = width
        self.height = height
        self.round_window = round_window
        self.position_authority = position_authority
        self.refresh_created = refresh_created
        self.refresh_reference_fields = refresh_reference_fields
        self.redraw = redraw
        self.sync_all = sync_all
        self.idx = selected_index
        self.seed_snapshot = list(feature_list)
        self.selected_feature = self.seed_snapshot[selected_index]
        self.dialog = None
        self.neighbor_index = None
        self.direction_map = {
            "向左": "left", "向右": "right", "向上": "up", "向下": "down",
            "左右兩側": "both_horizontal", "上下兩側": "both_vertical",
        }

    def open(self):
        self.dialog = tk.Toplevel(self.editor)
        self.round_window[0] = self.dialog
        self.dialog.title("圓孔排列設定")
        self.dialog.configure(bg=self.theme["bg"])
        self.dialog.transient(self.editor)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        self.round_direction = tk.StringVar(value="向右")
        self.round_driver = tk.StringVar(value="center")
        self.round_center = tk.StringVar(value=f"{max(float(self.selected_feature.diameter) * 2.0, 50.0):.2f}")
        self.round_gap = tk.StringVar()
        self.round_alignment = tk.StringVar(value="center")
        self.sync_guard = False
        self._sync_from_center()
        self._find_neighbor()
        self._build_body()
        self._bind_close_contract()

    def _find_neighbor(self):
        seed_point = feature_finished_point(self.selected_feature, self.width, self.height)
        nearest_distance = None
        for other_i, other in enumerate(self.seed_snapshot):
            if other_i == self.idx or not isinstance(other, CircleFeature):
                continue
            point = feature_finished_point(other, self.width, self.height)
            distance = (point.x - seed_point.x) ** 2 + (point.y - seed_point.y) ** 2
            if nearest_distance is None or distance < nearest_distance:
                self.neighbor_index = other_i
                nearest_distance = distance

    def _build_body(self):
        outer = tk.Frame(self.dialog, bg=self.theme["bg"])
        outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
        tk.Label(
            outer, text=f"目前圓孔：Ø{self.selected_feature.diameter:g}",
            bg=self.theme["bg"], fg="#ffd60a",
            font=("Microsoft JhengHei", 13, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))
        self._build_direction_controls(outer)
        self._build_spacing_controls(outer)
        self._build_alignment_controls(outer)
        self.status_var = tk.StringVar(value="設定後可先預覽，再按確定。")
        tk.Label(
            outer, textvariable=self.status_var, bg=self.theme["bg"], fg="#64d2ff",
            font=("Microsoft JhengHei", 10),
        ).pack(fill=tk.X, pady=(4, 2))
        self._build_action_controls(outer)
        self._build_footer(outer)

    def _build_direction_controls(self, outer):
        frame = tk.LabelFrame(
            outer, text=" 填滿方向 ", bg=self.theme["panel"], fg=self.theme["text"],
            font=("Microsoft JhengHei", 11, "bold"),
        )
        frame.pack(fill=tk.X, pady=4)
        labels = ("向左", "向右", "向上", "向下", "左右兩側", "上下兩側")
        for col, label in enumerate(labels):
            tk.Radiobutton(
                frame, text=label, variable=self.round_direction, value=label,
                bg=self.theme["panel"], fg=self.theme["text"],
                selectcolor=self.theme["input_bg"], activebackground=self.theme["panel"],
                font=("Microsoft JhengHei", 10, "bold"),
            ).grid(row=col // 3, column=col % 3, sticky="w", padx=8, pady=4)

    def _build_spacing_controls(self, outer):
        spacing = tk.LabelFrame(
            outer, text=" 排列距離（兩欄同步） ", bg=self.theme["panel"], fg=self.theme["text"],
            font=("Microsoft JhengHei", 11, "bold"),
        )
        spacing.pack(fill=tk.X, pady=6)
        tk.Radiobutton(
            spacing, text="孔心距為主", variable=self.round_driver, value="center",
            bg=self.theme["panel"], fg=self.theme["text"], selectcolor=self.theme["input_bg"],
            activebackground=self.theme["panel"], font=("Microsoft JhengHei", 10, "bold"),
            command=self._sync_from_center,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        center_entry = tk.Entry(
            spacing, textvariable=self.round_center, font=("Consolas", 13, "bold"),
            width=10, justify=tk.RIGHT,
        )
        center_entry.grid(row=0, column=1, padx=6, pady=4)
        tk.Label(spacing, text="mm", bg=self.theme["panel"], fg=self.theme["muted"]).grid(row=0, column=2, sticky="w")
        tk.Radiobutton(
            spacing, text="間距為主", variable=self.round_driver, value="gap",
            bg=self.theme["panel"], fg=self.theme["text"], selectcolor=self.theme["input_bg"],
            activebackground=self.theme["panel"], font=("Microsoft JhengHei", 10, "bold"),
            command=self._sync_from_gap,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        gap_entry = tk.Entry(
            spacing, textvariable=self.round_gap, font=("Consolas", 13, "bold"),
            width=10, justify=tk.RIGHT,
        )
        gap_entry.grid(row=1, column=1, padx=6, pady=4)
        tk.Label(spacing, text="mm", bg=self.theme["panel"], fg=self.theme["muted"]).grid(row=1, column=2, sticky="w")
        center_entry.bind("<KeyRelease>", self._sync_from_center)
        center_entry.bind("<FocusIn>", lambda _e: self.round_driver.set("center"))
        gap_entry.bind("<KeyRelease>", self._sync_from_gap)
        gap_entry.bind("<FocusIn>", lambda _e: self.round_driver.set("gap"))

    def _build_alignment_controls(self, outer):
        frame = tk.LabelFrame(
            outer, text=" 鄰近圓孔對齊 ", bg=self.theme["panel"], fg=self.theme["text"],
            font=("Microsoft JhengHei", 11, "bold"),
        )
        if self.neighbor_index is None:
            return
        frame.pack(fill=tk.X, pady=6)
        for label, value in (("孔心齊", "center"), ("管頂齊", "top"), ("管底齊", "bottom")):
            tk.Radiobutton(
                frame, text=label, variable=self.round_alignment, value=value,
                bg=self.theme["panel"], fg=self.theme["text"], selectcolor=self.theme["input_bg"],
                activebackground=self.theme["panel"], font=("Microsoft JhengHei", 10, "bold"),
            ).pack(side=tk.LEFT, padx=10, pady=6)

    def _build_action_controls(self, outer):
        row = tk.Frame(outer, bg=self.theme["bg"])
        row.pack(fill=tk.X, pady=(7, 4))
        tk.Button(
            row, text="填滿", command=lambda: self._apply_pattern(False), bg="#0a84ff", fg="white", bd=0,
            font=("Microsoft JhengHei", 11, "bold"), padx=18, pady=6,
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            row, text="重新填滿", command=lambda: self._apply_pattern(True), bg="#bf5af2", fg="white", bd=0,
            font=("Microsoft JhengHei", 11, "bold"), padx=18, pady=6,
        ).pack(side=tk.LEFT, padx=6)

    def _build_footer(self, outer):
        footer = tk.Frame(outer, bg=self.theme["bg"])
        footer.pack(fill=tk.X, pady=(8, 0))
        tk.Button(
            footer, text="確定", command=self._confirm, bg="#30d158", fg="white", bd=0,
            font=("Microsoft JhengHei", 12, "bold"), padx=28, pady=7,
        ).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            footer, text="取消", command=self._cancel, bg="#ff453a", fg="white", bd=0,
            font=("Microsoft JhengHei", 12, "bold"), padx=28, pady=7,
        ).pack(side=tk.RIGHT, padx=6)

    def _sync_from_center(self, _event=None):
        if self.sync_guard:
            return
        try:
            value = float(self.round_center.get())
        except ValueError:
            return
        self.round_driver.set("center")
        self.sync_guard = True
        try:
            gap = circle_gap_from_center_distance(value, self.selected_feature.diameter, self.selected_feature.diameter)
            self.round_gap.set(f"{gap:.2f}")
        finally:
            self.sync_guard = False

    def _sync_from_gap(self, _event=None):
        if self.sync_guard:
            return
        try:
            value = float(self.round_gap.get())
        except ValueError:
            return
        self.round_driver.set("gap")
        self.sync_guard = True
        try:
            center = circle_center_distance_from_gap(value, self.selected_feature.diameter, self.selected_feature.diameter)
            self.round_center.set(f"{center:.2f}")
        finally:
            self.sync_guard = False

    def _driver_value(self):
        try:
            value = float(self.round_center.get() if self.round_driver.get() == "center" else self.round_gap.get())
        except ValueError as exc:
            raise ValueError("孔心距 / 間距必須是數字") from exc
        if self.round_driver.get() == "center" and value <= 0:
            raise ValueError("孔心距必須大於 0")
        if self.round_driver.get() == "gap" and value < 0:
            raise ValueError("間距不可小於 0")
        return value

    def _aligned_seed(self):
        seed = self.selected_feature
        if self.neighbor_index is None:
            return seed
        direction = self.direction_map[self.round_direction.get()]
        axis = "x" if direction in {"left", "right", "both_horizontal"} else "y"
        neighbor = self.seed_snapshot[self.neighbor_index]
        candidate = align_circle_to_neighbor(seed, neighbor, self.round_alignment.get(), axis, self.width, self.height)
        return candidate if feature_is_within_surface(self.surface, candidate, self.width, self.height) else seed

    def _apply_pattern(self, refill=False):
        try:
            value = self._driver_value()
            direction = self.direction_map[self.round_direction.get()]
            seed = self._aligned_seed()
            generator = generate_round_refill if refill else generate_round_fill
            result = generator(
                seed, self.surface, width=self.width, height=self.height,
                direction=direction, driver=self.round_driver.get(), value=value,
            )
            if not result:
                raise ValueError("目前設定無法在合法板面內產生圓孔排列")
        except ValueError as exc:
            messagebox.showerror("圓孔排列", str(exc), parent=self.dialog)
            return
        original_point = feature_finished_point(self.selected_feature, self.width, self.height)
        seed_result = min(
            result,
            key=lambda feature: (
                (feature_finished_point(feature, self.width, self.height).x - original_point.x) ** 2
                + (feature_finished_point(feature, self.width, self.height).y - original_point.y) ** 2
            ),
        )
        preview_features = list(self.seed_snapshot)
        preview_features[self.idx] = seed_result
        preview_features.extend(feature for feature in result if feature is not seed_result)
        self.hole_session.execute(HoleEditorAction.preview_all(preview_features, selected_index=self.idx))
        self._refresh_all()
        self.status_var.set(f"預覽：{len(result)} 孔；{'重新填滿' if refill else '填滿'}。")

    def _refresh_all(self):
        self.refresh_created()
        self.refresh_reference_fields()
        self.redraw()
        self.sync_all()

    def _close(self):
        if self.round_window[0] is self.dialog:
            self.round_window[0] = None
        try:
            self.dialog.grab_release()
        except tk.TclError:
            pass
        self.dialog.destroy()

    def _cancel(self):
        self.hole_session.execute(HoleEditorAction.cancel_active())
        self._refresh_all()
        self._close()

    def _confirm(self):
        self.hole_session.execute(HoleEditorAction.commit_active(keep_selected=True))
        self.position_authority[0] = "round"
        self._refresh_all()
        self._close()

    def _bind_close_contract(self):
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)
        self.dialog.bind("<Escape>", lambda _e: (self._cancel(), "break")[1])
        self.dialog.update_idletasks()
        width = min(560, max(480, self.dialog.winfo_reqwidth()))
        height = min(650, max(430, self.dialog.winfo_reqheight()))
        x = max(0, self.editor.winfo_rootx() + 60)
        y = max(0, self.editor.winfo_rooty() + 60)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
