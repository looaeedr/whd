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

from .hole_editor_controls import (
    HoleEditorCatalogControls,
    HoleEditorReferencePresentation,
    HoleEditorIndicatorStateCollector,
    HoleEditorIndicatorGroupControls,
    HoleEditorSyncCoordinator,
    HoleEditorIndicatorContextRefresh,
    HoleEditorPageNavigation,
    HoleEditorFormRowBuilders,
    HoleEditorFullscreenActions,
    HoleEditorCreatedListPresentation,
    HoleEditorIndicatorUiActions,
    draw_hole_editor_hint,
)
from .hole_editor_round_settings import (
    HoleEditorRoundSettingsLauncher,
    open_round_hole_settings,
    _RoundHoleSettingsDialog,
)

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
