# -*- coding: utf-8 -*-
"""Deep Workspace Shell presentation owner for Fold Designer Phase 6.

This module owns Tk shell construction and shell-local presentation effects only.
It deliberately does not import the bridge, manufacturing, geometry, project
persistence, or Settings mutation owners.  Cross-owner behavior enters through
bounded actions supplied by the bridge composition root.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import fold_designer_original as original
from phase6_settings_panel import build_choice_menubutton
from whd_theme import configure_tk_menu


@dataclass(frozen=True)
class WorkspaceShellState:
    root: Any
    left: Any
    right: Any
    left_global_controls: Any
    left_global_cells: dict[str, Any]
    settings_panel: Any
    ui_text_size_var: Any
    ui_text_size_values: tuple[str, ...]
    v_a_bend: Any
    v_a_face: Any
    baseline_models: tuple[str, ...]
    initial_model: str
    structure_label: str
    structure_choices: tuple[str, ...]
    assembly_label: str
    assembly_choices: tuple[str, ...]
    settings_values: Mapping[str, Any]
    external_draw_stock_var: Any = None
    external_export_vars: Mapping[str, Any] | None = None
    left_workspace_width: int = 360
    theme_background: str = "#202020"


@dataclass(frozen=True)
class WorkspaceShellActions:
    status_projection: Callable[[], str]
    load_project_file: Callable[[], Any]
    save_project_file: Callable[[], Any]
    save_project_file_as: Callable[[], Any]
    open_relief_registry: Callable[[], Any]
    reset_initial_values: Callable[[], Any]
    build_settings_global_controls: Callable[[Any], Any]
    sync_settings_panel_compat: Callable[[], Any]
    toggle_parameter_panel: Callable[[], Any]
    select_structure_type: Callable[[Any], Any]
    select_assembly_type: Callable[[], Any]
    refresh_persistent_structure_controls: Callable[[], Any]
    commit_output_draw_stock: Callable[[], Any]
    export_selected_dxf: Callable[[], Any]
    queue_update: Callable[..., Any]
    pack_right_panel: Callable[[Any], Any]
    refresh_sticky_structure_tree: Callable[[], Any]
    install_keyboard_shortcuts: Callable[[], Any]
    toggle_fullscreen: Callable[[], Any]


class WorkspaceShellOwner:
    """Own the persistent Fold Designer Tk shell without owning app/domain state."""

    _BINDING_NAMES = (
        "status_bar",
        "status_projection_var",
        "status_projection_label",
        "top_persistent_bar",
        "top_command_row",
        "project_toolbar",
        "project_file_button",
        "project_file_menu",
        "relief_registry_button",
        "transaction_buttons",
        "reset_initial_button",
        "parameter_lock_button",
        "structure_type_var",
        "structure_choice_button",
        "assembly_type_var",
        "assembly_choice_button",
        "output_controls_frame",
        "output_draw_stock_var",
        "output_draw_stock_check",
        "output_export_vars",
        "output_export_checks",
        "output_export_button",
        "right_controls_host",
        "right_global_host",
        "right_controls_primary",
        "visual_controls",
        "ui_text_size_combo",
        "fullscreen_button",
        "left_scroll_canvas",
        "left_scrollbar",
        "left_scroll_window",
    )

    def __init__(self, state: WorkspaceShellState, actions: WorkspaceShellActions) -> None:
        self.state = state
        self.actions = actions

    def compatibility_bindings(self) -> dict[str, Any]:
        return {
            name: getattr(self, name)
            for name in self._BINDING_NAMES
            if hasattr(self, name)
        }

    def build_project_toolbar(self, parent=None):
        parent = parent or self.state.left
        self.project_toolbar = original.ttk.Frame(parent)
        self.project_toolbar.pack(side=original.tk.LEFT, padx=(0, 8))
        self.project_file_button = original.ttk.Menubutton(
            self.project_toolbar,
            text="檔案 ▼",
            style="Secondary.TMenubutton",
            takefocus=True,
        )
        self.project_file_menu = configure_tk_menu(
            original.tk.Menu(self.project_file_button, tearoff=False)
        )
        self.project_file_menu.add_command(
            label="開啟", command=self.actions.load_project_file
        )
        self.project_file_menu.add_command(
            label="儲存", command=self.actions.save_project_file
        )
        self.project_file_menu.add_command(
            label="另存新檔", command=self.actions.save_project_file_as
        )
        self.project_file_button.configure(menu=self.project_file_menu)
        self.project_file_button.pack(side=original.tk.LEFT)
        self.relief_registry_button = original.ttk.Button(
            self.project_toolbar,
            text="截角資料庫",
            command=self.actions.open_relief_registry,
            style="Secondary.TButton",
            takefocus=True,
        )
        self.relief_registry_button.pack(side=original.tk.LEFT, padx=(6, 0))
        return self.project_toolbar

    def build_transaction_buttons(self, parent=None):
        parent = parent or self.state.left
        self.transaction_buttons = original.ttk.Frame(parent)
        self.transaction_buttons.pack(side=original.tk.RIGHT)
        self.transaction_buttons.columnconfigure(0, weight=1)
        self.reset_initial_button = original.ttk.Button(
            self.transaction_buttons,
            text="還原初始值",
            command=self.actions.reset_initial_values,
            style="Secondary.TButton",
            takefocus=True,
        )
        self.reset_initial_button.grid(row=0, column=0, sticky="ew")
        return self.transaction_buttons

    def build_global_persistent_controls(self):
        host = self.state.left_global_controls
        self.parameter_lock_button = original.ttk.Button(
            host,
            text="參數鎖定",
            command=self.actions.toggle_parameter_panel,
            style="Secondary.TButton",
        )
        self.parameter_lock_button.grid(row=0, column=3, sticky="ew", padx=2, pady=2)

        structure_cell = original.ttk.Frame(host)
        structure_cell.grid(row=1, column=4, sticky="ew", padx=2, pady=2)
        self.state.left_global_cells["structure"] = structure_cell
        original.ttk.Label(structure_cell, text="結構").pack(anchor=original.tk.W)
        self.structure_type_var = original.tk.StringVar(value=self.state.structure_label)
        self.structure_choice_button = build_choice_menubutton(
            structure_cell,
            variable=self.structure_type_var,
            values=self.state.structure_choices,
            width=16,
            command=lambda: self.actions.select_structure_type(
                self.structure_type_var
            ),
        )
        self.structure_choice_button.pack(fill=original.tk.X)

        assembly_cell = original.ttk.Frame(host)
        assembly_cell.grid(row=1, column=5, sticky="ew", padx=2, pady=2)
        self.state.left_global_cells["assembly"] = assembly_cell
        original.ttk.Label(assembly_cell, text="組合方式").pack(anchor=original.tk.W)
        self.assembly_type_var = original.tk.StringVar(value=self.state.assembly_label)
        self.assembly_choice_button = build_choice_menubutton(
            assembly_cell,
            variable=self.assembly_type_var,
            values=self.state.assembly_choices,
            width=12,
            command=self.actions.select_assembly_type,
        )
        self.assembly_choice_button.pack(fill=original.tk.X)
        host.columnconfigure(4, weight=1)
        host.columnconfigure(5, weight=1)
        self.actions.refresh_persistent_structure_controls()
        return host

    def build_output_controls(self, parent=None):
        host = parent or self.top_command_row
        self.output_controls_frame = original.ttk.Frame(host, padding=(4, 0))
        self.output_controls_frame.pack(side=original.tk.RIGHT, fill=original.tk.X)

        draw_stock_var = self.state.external_draw_stock_var
        if draw_stock_var is None:
            draw_stock_var = original.tk.BooleanVar(
                master=self.output_controls_frame,
                value=bool(self.state.settings_values.get("draw_stock", False)),
            )
        self.output_draw_stock_var = draw_stock_var
        self.output_draw_stock_check = original.ttk.Checkbutton(
            self.output_controls_frame,
            text="輸出 STOCK 母材外框",
            variable=self.output_draw_stock_var,
            command=self.actions.commit_output_draw_stock,
        )
        self.output_draw_stock_check.pack(side=original.tk.LEFT, padx=(0, 6))

        parts_host = original.ttk.Frame(self.output_controls_frame)
        parts_host.pack(side=original.tk.LEFT)
        external_vars = dict(self.state.external_export_vars or {})
        labels = (
            ("box_body", "箱身"),
            ("head", "封頭"),
            ("tail", "封尾"),
            ("door", "門"),
            ("base_plate", "底板"),
            ("indicator_box", "指示燈盒子"),
            ("indicator_door", "指示燈小門"),
        )
        default_enabled = {
            "box_body": True,
            "head": True,
            "tail": True,
            "door": True,
            "base_plate": True,
            "indicator_box": False,
            "indicator_door": False,
        }
        self.output_export_vars = {}
        self.output_export_checks = {}
        for index, (key, label) in enumerate(labels):
            var = external_vars.get(key)
            if var is None:
                var = original.tk.BooleanVar(
                    master=parts_host, value=bool(default_enabled[key])
                )
            self.output_export_vars[key] = var
            check = original.ttk.Checkbutton(parts_host, text=label, variable=var)
            check.grid(row=0, column=index, sticky=original.tk.W, padx=(0, 6))
            self.output_export_checks[key] = check

        self.output_export_button = original.ttk.Button(
            self.output_controls_frame,
            text="輸出選取的 DXF 檔案",
            command=self.actions.export_selected_dxf,
            style="Primary.TButton",
            takefocus=True,
        )
        self.output_export_button.pack(side=original.tk.LEFT, padx=(4, 0))
        return self.output_controls_frame

    def build_visual_controls(self, parent):
        self.visual_controls = original.ttk.Frame(parent, padding=(4, 2))
        self.visual_controls.pack(
            side=original.tk.LEFT, fill=original.tk.X, padx=(0, 8)
        )
        original.ttk.Label(self.visual_controls, text="文字大小").grid(
            row=0, column=0, sticky="w"
        )
        self.ui_text_size_combo = build_choice_menubutton(
            self.visual_controls,
            variable=self.state.ui_text_size_var,
            values=self.state.ui_text_size_values,
            width=5,
        )
        self.ui_text_size_combo.grid(row=0, column=1, sticky="w", padx=(4, 10))
        self.state.settings_panel.ui_text_size_combo = self.ui_text_size_combo

        original.ttk.Label(self.visual_controls, text="折彎透視").grid(
            row=0, column=2, sticky="w"
        )
        original.ttk.Scale(
            self.visual_controls,
            from_=0.1,
            to=1.0,
            variable=self.state.v_a_bend,
            command=self.actions.queue_update,
            length=110,
        ).grid(row=0, column=3, sticky="ew", padx=(4, 8))
        original.ttk.Label(self.visual_controls, text="面板透視").grid(
            row=0, column=4, sticky="w"
        )
        original.ttk.Scale(
            self.visual_controls,
            from_=0.0,
            to=1.0,
            variable=self.state.v_a_face,
            command=self.actions.queue_update,
            length=110,
        ).grid(row=0, column=5, sticky="ew", padx=(4, 0))
        return self.visual_controls

    def build_persistent_top_area(self):
        root = self.state.root
        left = self.state.left
        right = self.state.right

        self.status_bar = original.ttk.Frame(root, padding=(8, 2))
        original.ttk.Separator(
            self.status_bar, orient=original.tk.HORIZONTAL
        ).pack(fill=original.tk.X, pady=(0, 2))
        self.status_projection_var = original.tk.StringVar(
            master=self.status_bar, value=self.actions.status_projection()
        )
        self.status_projection_label = original.ttk.Label(
            self.status_bar,
            textvariable=self.status_projection_var,
            anchor=original.tk.W,
        )
        self.status_projection_label.pack(fill=original.tk.X)
        self.status_bar.pack(side=original.tk.BOTTOM, fill=original.tk.X)

        try:
            left.pack_forget()
            right.pack_forget()
        except Exception:
            pass

        self.top_persistent_bar = original.ttk.Frame(
            root, padding=(10, 8, 10, 4)
        )
        self.top_persistent_bar.pack(side=original.tk.TOP, fill=original.tk.X)
        self.top_command_row = original.ttk.Frame(self.top_persistent_bar)
        self.top_command_row.pack(fill=original.tk.X)
        self.build_project_toolbar(self.top_command_row)
        self.build_output_controls(self.top_command_row)

        self.right_controls_host = original.ttk.Frame(
            right, padding=(8, 4, 8, 2)
        )
        self.right_global_host = original.ttk.Frame(self.right_controls_host)
        self.actions.build_settings_global_controls(self.right_global_host)
        self.actions.sync_settings_panel_compat()
        self.build_global_persistent_controls()
        self.actions.sync_settings_panel_compat()

        self.right_controls_primary = original.ttk.Frame(
            self.right_controls_host
        )
        self.right_controls_primary.pack(fill=original.tk.X, pady=(5, 0))
        self.build_transaction_buttons(self.right_controls_primary)
        self.build_visual_controls(self.right_controls_primary)
        self.fullscreen_button = original.ttk.Button(
            self.right_controls_primary,
            text="全螢幕",
            command=self.actions.toggle_fullscreen,
            style="Secondary.TButton",
            takefocus=True,
        )
        self.fullscreen_button.pack(side=original.tk.LEFT, padx=(0, 4))
        self.right_global_host.pack(fill=original.tk.X, pady=(4, 0))
        self.actions.pack_right_panel(self.right_controls_host)

        self.left_scroll_canvas = original.tk.Canvas(
            root,
            width=self.state.left_workspace_width,
            background=self.state.theme_background,
            highlightthickness=0,
            borderwidth=0,
            takefocus=False,
        )

        def left_scroll_command(*args):
            self.left_scroll_canvas.yview(*args)
            self.actions.refresh_sticky_structure_tree()

        def left_yview_changed(first, last):
            self.left_scrollbar.set(first, last)
            self.actions.refresh_sticky_structure_tree()

        self.left_scrollbar = original.ttk.Scrollbar(
            root,
            orient=original.tk.VERTICAL,
            command=left_scroll_command,
        )
        self.left_scroll_canvas.configure(yscrollcommand=left_yview_changed)
        try:
            left.pack_propagate(True)
        except Exception:
            pass
        self.left_scroll_window = self.left_scroll_canvas.create_window(
            (0, 0), window=left, anchor="nw"
        )

        def sync_left_scrollregion(_event=None):
            try:
                bbox = self.left_scroll_canvas.bbox("all")
                if bbox is not None:
                    self.left_scroll_canvas.configure(scrollregion=bbox)
                self.actions.refresh_sticky_structure_tree()
            except Exception:
                pass

        def size_left_window(event):
            try:
                self.left_scroll_canvas.itemconfigure(
                    self.left_scroll_window, width=max(1, int(event.width))
                )
            except Exception:
                pass
            sync_left_scrollregion()

        left.bind("<Configure>", sync_left_scrollregion, add="+")
        self.left_scroll_canvas.bind("<Configure>", size_left_window, add="+")
        self.left_scroll_canvas.pack(
            side=original.tk.LEFT, fill=original.tk.Y
        )
        self.left_scrollbar.pack(side=original.tk.LEFT, fill=original.tk.Y)
        right.pack(side=original.tk.RIGHT, fill=original.tk.BOTH, expand=True)
        left.lift(self.left_scroll_canvas)
        sync_left_scrollregion()
        self.actions.install_keyboard_shortcuts()
        return self.compatibility_bindings()


def mount_shared_content(host, single, assembly, corner_data, mode):
    """Map exactly one direct sibling into the shared content slot."""
    if host is None:
        return None
    selected_mode = (
        "assembly"
        if str(mode or "") == "assembly"
        else "corner_data"
        if str(mode or "") == "corner_data"
        else "single"
    )
    surfaces = {
        "single": single,
        "assembly": assembly,
        "corner_data": corner_data,
    }
    selected = surfaces.get(selected_mode)
    if selected is None:
        return None
    for key, widget in surfaces.items():
        if widget is None:
            continue
        if key == selected_mode:
            if not widget.winfo_manager():
                widget.pack(fill=original.tk.BOTH, expand=False, pady=(0, 8))
        elif widget.winfo_manager():
            widget.pack_forget()
    return selected


def toggle_fullscreen(root, button, *, enabled=False, restore_geometry=None):
    """Own fullscreen Tk effects while returning state to the bridge adapter."""
    enabled = bool(enabled)
    if not enabled:
        try:
            restore_geometry = root.geometry()
        except Exception:
            restore_geometry = None
        applied = False
        try:
            root.state("zoomed")
            applied = True
        except Exception:
            pass
        if not applied:
            try:
                root.attributes("-zoomed", True)
                applied = True
            except Exception:
                pass
        if not applied:
            try:
                root.attributes("-fullscreen", True)
                applied = True
            except Exception:
                pass
        enabled = bool(applied)
    else:
        restored = False
        try:
            root.attributes("-fullscreen", False)
        except Exception:
            pass
        try:
            root.attributes("-zoomed", False)
        except Exception:
            pass
        try:
            root.state("normal")
            restored = True
        except Exception:
            pass
        if restored and restore_geometry:
            try:
                root.geometry(restore_geometry)
            except Exception:
                pass
        enabled = False
    if button is not None:
        button.configure(text=("還原視窗" if enabled else "全螢幕"))
    return enabled, restore_geometry
