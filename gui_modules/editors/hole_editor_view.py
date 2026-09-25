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


class HoleEditorCenterWorkspaceBuilder:
    """Build center workspace widgets without owning editor actions."""

    def __init__(self, host):
        self.host = host

    def build(self, *, center):
        host = self.host
        toolbar = tk.Frame(center, bg=host.COLOR_PANEL)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            toolbar, text="旋轉", bg=host.COLOR_PANEL, fg="#ffd60a",
            font=('Microsoft JhengHei', 12, 'bold'),
        ).pack(side=tk.LEFT, padx=(10, 6), pady=6)
        rotation_buttons = []
        for angle in (90, 180, 270, 360):
            btn = tk.Button(
                toolbar, text=f"{angle}°", bg="#3a3a44", fg="white", bd=0,
                font=('Microsoft JhengHei', 11, 'bold'), padx=10, pady=4,
            )
            btn.pack(side=tk.LEFT, padx=3, pady=4)
            rotation_buttons.append((angle, btn))
        fullscreen_btn = tk.Button(
            toolbar, text="全螢幕", bg="#0a84ff", fg="white", bd=0,
            font=('Microsoft JhengHei', 11, 'bold'), padx=12, pady=4,
        )
        fullscreen_btn.pack(side=tk.LEFT, padx=(12, 3), pady=4)
        undo_btn = tk.Button(
            toolbar, text="↶ 回上一步", bg="#636366", fg="white", bd=0,
            font=('Microsoft JhengHei', 11, 'bold'), padx=12, pady=4,
        )
        undo_btn.pack(side=tk.LEFT, padx=(8, 3), pady=4)
        tk.Label(
            toolbar, text="雙擊已開孔：切穿 ⇄ 盲孔　右鍵孔：選十字基準",
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 10),
        ).pack(side=tk.RIGHT, padx=10)

        canvas = tk.Canvas(center, bg=host.COLOR_CANVAS_BG, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        host.last_hole_editor_canvas = canvas

        footer = tk.Frame(center, bg=host.COLOR_PANEL)
        footer.pack(fill=tk.X, pady=(6, 0))
        confirm_all_btn = tk.Button(
            footer, text="確定全部", bg="#30d158", fg="white", bd=0,
            font=('Microsoft JhengHei', 13, 'bold'), padx=22, pady=7,
        )
        confirm_all_btn.pack(side=tk.RIGHT, padx=(6, 10), pady=6)
        cancel_all_btn = tk.Button(
            footer, text="取消全部", bg="#ff453a", fg="white", bd=0,
            font=('Microsoft JhengHei', 13, 'bold'), padx=22, pady=7,
        )
        cancel_all_btn.pack(side=tk.RIGHT, padx=6, pady=6)
        tk.Label(
            footer, text="Esc：取消目前插入／定位；沒有進行中的操作時則取消全部",
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 10),
        ).pack(side=tk.LEFT, padx=10)
        return (
            toolbar, rotation_buttons, fullscreen_btn, undo_btn,
            canvas, confirm_all_btn, cancel_all_btn,
        )


class HoleEditorCatalogSidebarBuilder:
    """Build catalog/custom/created-list widgets without owning editor behavior."""

    def __init__(self, host):
        self.host = host

    def build(
        self, *, left, left_insert_bar, big_font, normal_font, entry_font,
        catalog_label_by_definition, general_catalog_defs, pipe_catalog_defs,
        ref_entries_provider,
    ):
        host = self.host
        tk.Label(
            left, text="一般開孔", bg=host.COLOR_PANEL, fg="#30d158",
            font=('Microsoft JhengHei', 13, 'bold'),
        ).pack(fill=tk.X, padx=10, pady=(10, 3))
        catalog_list = tk.Listbox(
            left, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            selectbackground="#0a84ff", font=('Microsoft JhengHei', 11),
            height=6, exportselection=False,
        )
        catalog_list.pack(fill=tk.X, padx=10, pady=(0, 4))
        general_labels = [
            catalog_label_by_definition[id(definition)]
            for definition in general_catalog_defs
        ] + ["＋ 自訂圓孔", "＋ 自訂方孔"]
        for label in general_labels:
            catalog_list.insert(tk.END, label)

        tk.Label(
            left, text="管孔清單", bg=host.COLOR_PANEL, fg="#ffd60a",
            font=('Microsoft JhengHei', 13, 'bold'),
        ).pack(fill=tk.X, padx=10, pady=(5, 3))
        pipe_catalog_list = tk.Listbox(
            left, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            selectbackground="#bf5af2", font=('Microsoft JhengHei', 11),
            height=5, exportselection=False,
        )
        pipe_catalog_list.pack(fill=tk.X, padx=10, pady=(0, 4))
        pipe_labels = [
            catalog_label_by_definition[id(definition)]
            for definition in pipe_catalog_defs
        ]
        for label in pipe_labels:
            pipe_catalog_list.insert(tk.END, label)

        first_label = general_labels[0] if general_labels else (pipe_labels[0] if pipe_labels else "")
        if general_labels:
            catalog_list.selection_set(0)
        elif pipe_labels:
            pipe_catalog_list.selection_set(0)
        selected_catalog_text = tk.StringVar(value=first_label)
        tk.Label(
            left, textvariable=selected_catalog_text, bg="#2c2c34", fg="#ffd60a",
            anchor=tk.W, font=('Microsoft JhengHei', 10, 'bold'), wraplength=285,
            padx=8, pady=5,
        ).pack(fill=tk.X, padx=10, pady=(2, 5))

        custom_frame = tk.LabelFrame(
            left, text=" 自訂尺寸 ", bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT_MUTED, font=normal_font,
        )
        custom_frame.pack(fill=tk.X, padx=10, pady=4)
        var_d = tk.StringVar(value="22.0")
        var_w = tk.StringVar(value="40.0")
        var_h = tk.StringVar(value="40.0")
        var_blind = tk.BooleanVar(value=False)
        var_rotation = tk.StringVar(value="360°")
        form_row_builders = HoleEditorFormRowBuilders(
            panel_bg=host.COLOR_PANEL,
            text_color=host.COLOR_TEXT,
            normal_font=normal_font,
            entry_font=entry_font,
            ref_entries_provider=ref_entries_provider,
        )
        form_row_builders.small_row(custom_frame, "直徑", var_d)
        form_row_builders.small_row(custom_frame, "寬 W", var_w)
        form_row_builders.small_row(custom_frame, "高 H", var_h)
        tk.Checkbutton(
            custom_frame, text="盲孔", variable=var_blind,
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
            selectcolor=host.COLOR_INPUT_BG, activebackground=host.COLOR_PANEL,
            font=('Microsoft JhengHei', 12, 'bold'),
        ).pack(anchor=tk.W, padx=6, pady=3)

        insert_mode = [False]
        insert_btn = tk.Button(
            left_insert_bar, text="插入", bg="#30d158", fg="white",
            font=big_font, bd=0, pady=8,
        )
        insert_btn.pack(fill=tk.X, padx=10, pady=(7, 8))
        host.last_hole_editor_insert_button = insert_btn

        tk.Label(
            left, text="已開孔（雙擊：切穿 ⇄ 盲孔）", bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 12, 'bold'),
        ).pack(fill=tk.X, padx=10, pady=(5, 3))
        created_list = tk.Listbox(
            left, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            selectbackground="#5e5ce6", font=('Microsoft JhengHei', 12),
            height=9, exportselection=False,
        )
        created_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        delete_btn = tk.Button(
            left, text="刪除選中", bg="#ff453a", fg="white",
            font=('Microsoft JhengHei', 12, 'bold'), bd=0, pady=6,
        )
        delete_btn.pack(fill=tk.X, padx=10, pady=(3, 10))
        return (
            catalog_list, pipe_catalog_list, selected_catalog_text,
            var_d, var_w, var_h, var_blind, var_rotation,
            form_row_builders, insert_mode, insert_btn, created_list, delete_btn,
        )


class HoleEditorIndicatorPanelBuilder:
    """Build Door indicator controls while leaving state/validation elsewhere."""

    def __init__(self, host):
        self.host = host

    def build(
        self, *, left, part_key, door_indicator_state,
        request_redraw, on_box_distance_toggle,
    ):
        if part_key != "door" or door_indicator_state is None:
            return None, None, [], None, None, None

        host = self.host
        seed_state = host._normalize_door_indicator_state(door_indicator_state)
        mode_var = tk.StringVar(value=seed_state["mode"])
        layers_var = tk.StringVar(value=str(seed_state["layers"]))
        group_vars = [
            tk.StringVar(value=str(int(seed_state["groups"][i])))
            for i in range(6)
        ]
        offset_x_var = tk.StringVar(
            value=host._door_layout_number_text(seed_state["offset_x"])
        )
        offset_y_var = tk.StringVar(
            value=host._door_layout_number_text(seed_state["offset_y"])
        )
        box_dist_var = tk.BooleanVar(value=seed_state["is_box_dist"])

        frame = tk.LabelFrame(
            left, text=" 門指示燈 / 指示燈盒子 ",
            bg=host.COLOR_PANEL, fg="#ffd60a",
            font=('Microsoft JhengHei', 11, 'bold'),
        )
        frame.pack(fill=tk.X, padx=10, pady=(8, 4))
        mode_row = tk.Frame(frame, bg=host.COLOR_PANEL)
        mode_row.pack(fill=tk.X, padx=5, pady=(3, 2))
        for text, value in (
            ("不使用", "none"),
            ("直接指示燈", "indicator"),
            ("指示燈盒子", "indicator_box"),
        ):
            tk.Radiobutton(
                mode_row, text=text, value=value, variable=mode_var,
                bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
                selectcolor=host.COLOR_INPUT_BG,
                activebackground=host.COLOR_PANEL, activeforeground=host.COLOR_TEXT,
                font=('Microsoft JhengHei', 9, 'bold'), command=request_redraw,
            ).pack(side=tk.LEFT, padx=(0, 5))

        layer_row = tk.Frame(frame, bg=host.COLOR_PANEL)
        layer_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(
            layer_row, text="層數", bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT, width=5, anchor=tk.W,
        ).pack(side=tk.LEFT)
        layer_combo = ttk.Combobox(
            layer_row, textvariable=layers_var,
            values=["1", "2", "3", "4", "5", "6"], width=4, state="readonly",
        )
        layer_combo.pack(side=tk.LEFT)

        groups_frame = tk.Frame(frame, bg=host.COLOR_PANEL)
        groups_frame.pack(fill=tk.X, padx=6, pady=2)
        group_controls = HoleEditorIndicatorGroupControls(
            groups_frame=groups_frame, layers_var=layers_var,
            group_vars=group_vars, request_redraw=request_redraw,
            panel_bg=host.COLOR_PANEL, muted_color=host.COLOR_TEXT_MUTED,
        )
        layer_combo.bind("<<ComboboxSelected>>", group_controls.rebuild)
        group_controls.rebuild()

        pos_row = tk.Frame(frame, bg=host.COLOR_PANEL)
        pos_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(pos_row, text="X", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
        x_entry = tk.Entry(pos_row, textvariable=offset_x_var, width=6, justify=tk.CENTER)
        x_entry.pack(side=tk.LEFT, padx=(2, 6))
        tk.Label(pos_row, text="Y", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
        y_entry = tk.Entry(pos_row, textvariable=offset_y_var, width=6, justify=tk.CENTER)
        y_entry.pack(side=tk.LEFT, padx=(2, 6))
        tk.Button(
            pos_row, text="置中",
            command=lambda: (offset_x_var.set("0"), offset_y_var.set("0"), request_redraw()),
            bg="#3a3a44", fg="white", bd=0,
        ).pack(side=tk.LEFT)
        x_entry.bind("<KeyRelease>", request_redraw)
        y_entry.bind("<KeyRelease>", request_redraw)
        tk.Checkbutton(
            frame, text="箱體定位距離", variable=box_dist_var,
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
            selectcolor=host.COLOR_INPUT_BG, activebackground=host.COLOR_PANEL,
            command=on_box_distance_toggle, font=('Microsoft JhengHei', 9),
        ).pack(anchor=tk.W, padx=6, pady=(1, 4))
        return mode_var, layers_var, group_vars, offset_x_var, offset_y_var, box_dist_var


class HoleEditorWindowShellBuilder:
    """Build the transient editor window shell without owning editor state."""

    def __init__(self, host):
        self.host = host

    @staticmethod
    def window_geometry(screen_w, screen_h):
        win_w = max(720, min(1280, screen_w - 80))
        win_h = max(560, min(820, screen_h - 120))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        return win_w, win_h, pos_x, pos_y, f"{win_w}x{win_h}+{pos_x}+{pos_y}"

    def build(
        self, title, *, part_key, door_indicator_state,
        indicator_component_context_provider, baseline_status_text,
    ):
        host = self.host
        editor = tk.Toplevel(host.root)
        host.last_unified_hole_editor = editor
        editor.title(f"{title} — 統一開孔編輯器")
        editor.configure(bg=host.COLOR_BG)
        editor.transient(host.root)
        editor.grab_set()
        win_w, win_h, _pos_x, _pos_y, geometry = self.window_geometry(
            editor.winfo_screenwidth(), editor.winfo_screenheight()
        )
        fullscreen_state = [False]
        fullscreen_restore_geometry = [None]
        editor.geometry(geometry)
        editor.minsize(min(760, win_w), min(560, win_h))

        body = tk.Frame(editor, bg=host.COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        left = tk.Frame(
            body, bg=host.COLOR_PANEL, width=min(320, max(270, win_w // 4))
        )
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)
        left_insert_bar = tk.Frame(left, bg=host.COLOR_PANEL)
        left_insert_bar.pack(side=tk.BOTTOM, fill=tk.X)
        center = tk.Frame(body, bg=host.COLOR_BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        editor_tabs = None
        main_page = None
        indicator_page = None
        component_tabs = None
        indicator_door_page = None
        indicator_page_visible = [False]
        if (
            part_key == "door"
            and door_indicator_state is not None
            and indicator_component_context_provider is not None
        ):
            editor_tabs = ttk.Notebook(center, height=32)
            main_page = tk.Frame(editor_tabs, bg=host.COLOR_BG)
            indicator_page = tk.Frame(editor_tabs, bg=host.COLOR_BG)
            editor_tabs.add(main_page, text="  門板  ")
            editor_tabs.pack(fill=tk.X, pady=(0, 4))
            component_tabs = ttk.Notebook(center, height=30)
            indicator_box_page = tk.Frame(component_tabs, bg=host.COLOR_BG)
            indicator_door_page = tk.Frame(component_tabs, bg=host.COLOR_BG)
            component_tabs.add(indicator_box_page, text="  盒體（基準檔＋指示燈）  ")
            component_tabs.add(indicator_door_page, text="  小門（基準檔）  ")

        big_font = ('Microsoft JhengHei', 15, 'bold')
        entry_font = ('Consolas', 12, 'bold')
        normal_font = ('Microsoft JhengHei', 11)
        baseline_status_var = tk.StringVar(value=str(baseline_status_text or ""))
        baseline_status_label = None
        if baseline_status_text or indicator_component_context_provider is not None:
            baseline_status_label = tk.Label(
                left, textvariable=baseline_status_var, bg=host.COLOR_PANEL,
                fg=("#64d2ff" if str(baseline_status_text or "").startswith("基準檔：") else "#ff9f0a"),
                font=('Microsoft JhengHei', 9, 'bold'), anchor=tk.W,
                justify=tk.LEFT, wraplength=285,
            )
            baseline_status_label.pack(fill=tk.X, padx=10, pady=(7, 2))

        return (
            editor, fullscreen_state, fullscreen_restore_geometry,
            left, left_insert_bar, center,
            editor_tabs, main_page, indicator_page, component_tabs,
            indicator_door_page, indicator_page_visible,
            big_font, entry_font, normal_font,
            baseline_status_var, baseline_status_label,
        )


class HoleEditorCanvasViewFactory:
    """Construct the existing canvas view authority; owns no render state."""

    @staticmethod
    def create(canvas, **kwargs):
        return Phase6HoleEditorCanvasView(canvas, **kwargs)


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


class HoleEditorRoundSettingsLauncher:
    """Launch round-hole settings against the current live editor context."""

    def __init__(
        self, *, editor, theme, hole_session, context_provider,
        round_window, position_authority, refresh_created,
        refresh_reference_fields, redraw, sync_all,
        open_round_hole_settings,
    ):
        self.editor = editor
        self.theme = theme
        self.hole_session = hole_session
        self.context_provider = context_provider
        self.round_window = round_window
        self.position_authority = position_authority
        self.refresh_created = refresh_created
        self.refresh_reference_fields = refresh_reference_fields
        self.redraw = redraw
        self.sync_all = sync_all
        self.open_round_hole_settings = open_round_hole_settings

    def open(self):
        context = self.context_provider()
        return self.open_round_hole_settings(
            editor=self.editor,
            theme=self.theme,
            hole_session=self.hole_session,
            feature_list=context["feature_list"],
            surface=context["surface"],
            width=context["width"],
            height=context["height"],
            round_window=self.round_window,
            position_authority=self.position_authority,
            refresh_created=self.refresh_created,
            refresh_reference_fields=self.refresh_reference_fields,
            redraw=self.redraw,
            sync_all=self.sync_all,
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
