# -*- coding: utf-8 -*-
"""Phase6 schema 驅動設定面板。

本模組只擁有 Tk/UI 顯示狀態；3D settings draft、機械語意與 transaction
仍由外部 owner 透過 callback 提供。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from phase6_settings_center import SettingSpec

ADVANCED_SETTING_GROUPS = frozenset({"補償", "門縫", "收縮"})
CORNER_COMPAT_SETTING_GROUPS = frozenset({"Relief", "NOTCH 相容"})
BASELINE_SETTING_GROUPS = frozenset({"固定孔", "封尾固定孔"})
DEFAULT_HIDDEN_KEYS_BY_CONTEXT = {
    "box_body": frozenset({"zl1", "zl2", "zr1", "zr2"}),
    "head": frozenset({"yl1", "yr1", "ytop1", "ybottom1"}),
    "tail": frozenset({"yl1", "yr1", "ytop1", "ybottom1"}),
    "door": frozenset({"door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b"}),
    "base_plate": frozenset({
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right",
    }),
    "indicator_box": frozenset({"indicator_box_fold"}),
    "indicator_door": frozenset({"indicator_door_fold"}),
}


@dataclass(frozen=True)
class SettingSpecGroups:
    normal: tuple[SettingSpec, ...]
    advanced: tuple[SettingSpec, ...]
    baseline: tuple[SettingSpec, ...]
    compatibility_hidden: tuple[SettingSpec, ...]


@dataclass(frozen=True)
class SettingsPanelExtensionResult:
    next_row: int
    state: object = None


def setting_number_text(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    nearest_int = round(number)
    if abs(number - nearest_int) <= 1e-9:
        return str(int(nearest_int))
    return str(number)


def partition_setting_specs(
    context: str,
    specs: Sequence[SettingSpec] | Iterable[SettingSpec],
    *,
    hidden_keys: set[str] | frozenset[str] = frozenset(),
) -> SettingSpecGroups:
    visible = tuple(spec for spec in specs if spec.key not in hidden_keys)
    compatibility = tuple(spec for spec in visible if spec.group in CORNER_COMPAT_SETTING_GROUPS)
    baseline = tuple(spec for spec in visible if spec.group in BASELINE_SETTING_GROUPS)
    advanced = tuple(spec for spec in visible if spec.group in ADVANCED_SETTING_GROUPS)
    normal = tuple(
        spec for spec in visible
        if spec not in compatibility and spec not in baseline and spec not in advanced
    )
    return SettingSpecGroups(
        normal=normal,
        advanced=advanced,
        baseline=baseline,
        compatibility_hidden=compatibility,
    )


def inspector_setting_groups(
    specs: Sequence[SettingSpec] | Iterable[SettingSpec],
) -> tuple[tuple[str, tuple[SettingSpec, ...]], ...]:
    """Project existing SettingSpec groups in first-seen engineering order."""
    grouped: dict[str, list[SettingSpec]] = {}
    order: list[str] = []
    for spec in tuple(specs):
        name = str(spec.group or "一般")
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].append(spec)
    return tuple((name, tuple(grouped[name])) for name in order)


def baseline_row_text(row) -> str:
    kind = str(row.get("kind") or "特徵")
    layer = str(row.get("layer") or "")
    x = setting_number_text(row.get("x", 0))
    y = setting_number_text(row.get("y", 0))
    d1 = setting_number_text(row.get("d1", 0))
    d2 = setting_number_text(row.get("d2", 0))
    if kind == "圓孔":
        size = f"Ø{d1}"
    elif kind == "方孔":
        size = f"{d1}×{d2}"
    else:
        size = d1 if float(row.get("d1", 0) or 0) else ""
    suffix = f" [{layer}]" if layer else ""
    return f"{kind}  X={x}  Y={y}  {size}{suffix}".strip()

import tkinter as tk
from tkinter import ttk
from typing import Callable, Mapping
from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS, configure_tk_menu

from phase6_settings_center import (
    GLOBAL_CONTEXT,
    UI_TEXT_SIZE_LABELS,
    normalize_ui_text_size,
    settings_for_context,
    ui_text_size_label,
)


def build_choice_menubutton(
    parent,
    *,
    variable,
    values,
    command=None,
    width=None,
    state="normal",
):
    """固定選項選擇器。

    Phase6 不再用 ``ttk.Combobox(readonly)`` 顯示固定選項，避免 Windows/Tk
    在焦點切換時把其他 readonly Combobox 的文字畫成空白。每一次選單操作都
    直接走 command；數值 Source of Truth 仍是呼叫端傳入的 Tk variable。
    """
    kwargs = {"textvariable": variable, "state": state, "takefocus": True, "style": "Selector.TMenubutton"}
    if width is not None:
        kwargs["width"] = width
    button = ttk.Menubutton(parent, **kwargs)
    menu = tk.Menu(
        button, tearoff=False, relief=tk.RAISED, borderwidth=1, activeborderwidth=1
    )
    configure_tk_menu(menu)
    for value in tuple(values or ()):
        menu.add_radiobutton(
            label=str(value),
            variable=variable,
            value=str(value),
            command=command,
        )
    button.configure(menu=menu)
    button._phase6_menu = menu
    button._phase6_foreground_role = "dropdown"
    menu._phase6_foreground_role = "floating_menu"
    return button


class Phase6SettingsPanel:
    """Schema-driven Tk settings UI with callback-only state mutation."""

    def __init__(
        self,
        *,
        values_snapshot: Callable[[], Mapping[str, object]],
        stage_setting_update: Callable[[str, object], object],
        flush_settings: Callable[[], object],
        save_defaults: Callable[[str], object],
        query_baseline_rows: Callable[[str, str, Mapping[str, object]], Iterable[Mapping[str, object]]] | None = None,
        baseline_model_getter: Callable[[], str] | None = None,
        is_unknown_baseline: Callable[[str], bool] | None = None,
        should_show_baseline_data: Callable[[str, Sequence[SettingSpec]], bool] | None = None,
        specs_provider: Callable[[str], Sequence[SettingSpec]] = settings_for_context,
        part_labels: Mapping[str, str] | None = None,
        hidden_keys_by_context: Mapping[str, set[str] | frozenset[str]] | None = None,
        render_context_extensions: Callable[[object, str, int], SettingsPanelExtensionResult] | None = None,
        sync_context_extension: Callable[[object, str], object] | None = None,
        context_extension_projection: Callable[[str], Mapping[str, object]] | None = None,
        endcap_fw_value_selected: Callable[[str, object], object] | None = None,
        box_structure_numeric_changed: Callable[[object, str, object], object] | None = None,
        box_back_panel_mode_changed: Callable[[object], object] | None = None,
        box_structure_toggle_advanced: Callable[[object], object] | None = None,
        bottom_wrap_commit: Callable[[str, object, object], object] | None = None,
        corner_pair_changed: Callable[[str, str, object], object] | None = None,
        corner_type_selected: Callable[[str, str], object] | None = None,
        corner_mode_selected: Callable[[str, str], object] | None = None,
        corner_target_changed: Callable[[str, str], object] | None = None,
        baseline_model_changed: Callable[[], object] | None = None,
        ui_text_size_changed: Callable[[str], object] | None = None,
    ):
        self._values_snapshot = values_snapshot
        self._stage_setting_update = stage_setting_update
        self._flush_settings = flush_settings
        self._save_defaults = save_defaults
        self._query_baseline_rows = query_baseline_rows
        self._baseline_model_getter = baseline_model_getter or (lambda: "")
        self._is_unknown_baseline = is_unknown_baseline or (lambda _model: False)
        self._should_show_baseline_data = should_show_baseline_data or (lambda _context, specs: bool(specs))
        self._specs_provider = specs_provider
        self._part_labels = dict(part_labels or {})
        self._hidden_keys_by_context = {
            str(key): frozenset(values)
            for key, values in (hidden_keys_by_context or DEFAULT_HIDDEN_KEYS_BY_CONTEXT).items()
        }
        self._render_context_extensions = render_context_extensions
        self._sync_context_extension = sync_context_extension
        self._context_extension_projection = context_extension_projection
        self._endcap_fw_value_selected = endcap_fw_value_selected
        self._box_structure_numeric_changed = box_structure_numeric_changed
        self._box_back_panel_mode_changed = box_back_panel_mode_changed
        self._box_structure_toggle_advanced = box_structure_toggle_advanced
        self._bottom_wrap_commit = bottom_wrap_commit
        self._corner_pair_changed = corner_pair_changed
        self._corner_type_selected = corner_type_selected
        self._corner_mode_selected = corner_mode_selected
        self._corner_target_changed = corner_target_changed
        self._baseline_model_changed = baseline_model_changed
        self._ui_text_size_changed = ui_text_size_changed

        # 3D 右側由單一「參數鎖定」控制整塊參數面板；解鎖後進階參數
        # 直接跟著顯示，不再需要第二層「顯示進階設定」操作。
        self.advanced_settings_visible = True
        self.page_cache: dict[str, dict[str, object]] = {}
        self.current_page: str | None = None
        self.settings_context = GLOBAL_CONTEXT
        self.setting_vars: dict[str, tk.Variable] = {}
        self._guard = False
        self._rendering = False

        self.settings_center = None
        self.settings_fields = None
        self.settings_scroll_host = None
        self.settings_scroll_canvas = None
        self.settings_scrollbar = None
        self._settings_scroll_window = None
        self.settings_title_var = None
        self.settings_status_var = None
        self.unfolded_size_var = None
        self.save_settings_button = None
        self.advanced_settings_frame = None
        self.advanced_toggle_button = None
        self.baseline_data_frame = None
        self.baseline_data_toggle_button = None
        self.baseline_setting_cells = {}
        self.left_global_controls = None
        self.left_global_vars: dict[str, tk.Variable] = {}
        self.left_global_cells: dict[str, object] = {}
        self.baseline_model_var = None
        self.baseline_model_combo = None
        self.ui_text_size_var = None
        self.ui_text_size_combo = None
        self.save_global_settings_button = None

    def build_left_global_controls(self, parent, *, baseline_models=(), initial_model=""):
        self.left_global_controls = ttk.LabelFrame(parent, text="全域設定", padding=5)
        self.left_global_controls.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(self.left_global_controls, text="基準型號：").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.baseline_model_var = tk.StringVar(master=self.left_global_controls, value=str(initial_model or ""))
        self.baseline_model_combo = build_choice_menubutton(
            self.left_global_controls,
            variable=self.baseline_model_var,
            values=tuple(baseline_models or ()),
            width=18,
        )
        self.baseline_model_combo.grid(row=0, column=1, columnspan=2, sticky="ew", padx=2, pady=2)
        self.baseline_model_var.trace_add("write", lambda *_a: self._emit_baseline_model_changed())

        values = dict(self._values_snapshot())
        self.left_global_vars = {
            key: tk.StringVar(master=self.left_global_controls, value=setting_number_text(values.get(key, default)))
            for key, default in (("w", 500), ("h", 600), ("d", 200), ("t", 2))
        }
        self.left_global_cells = {}
        labels = (("W", "w"), ("H", "h"), ("D", "d"), ("T", "t"))
        for col, (label, key) in enumerate(labels):
            cell = ttk.Frame(self.left_global_controls)
            self.left_global_cells[key] = cell
            cell.grid(row=1, column=col, sticky="ew", padx=2, pady=2)
            cell.columnconfigure(1, weight=1)
            ttk.Label(cell, text=label).grid(row=0, column=0, sticky="w", padx=(0, 4))
            entry = ttk.Entry(cell, textvariable=self.left_global_vars[key], width=6, justify=tk.CENTER, style="Editable.TEntry")
            entry.grid(row=0, column=1, sticky="ew")
            ttk.Label(cell, text="mm").grid(row=0, column=2, sticky="w", padx=(4, 0))
            entry.bind("<Return>", lambda _e: self._flush_settings())
            entry.bind("<FocusOut>", lambda _e: self._flush_settings())
            self.left_global_vars[key].trace_add(
                "write", lambda *_a, k=key, v=self.left_global_vars[key]: self._on_left_numeric_changed(k, v)
            )
            self.left_global_controls.columnconfigure(col, weight=1)

        # 文字大小屬於最上列「3D 顯示」，變數仍由 settings panel 擁有，
        # 可視 widget 由 Phase6 top bar 建立，避免全域設定出現第三行。
        self.ui_text_size_var = tk.StringVar(
            master=self.left_global_controls,
            value=ui_text_size_label(values.get("ui_text_size", "small")),
        )
        self.left_global_vars["ui_text_size"] = self.ui_text_size_var
        self.ui_text_size_combo = None
        self.ui_text_size_var.trace_add("write", lambda *_a: self._emit_ui_text_size_changed())

        self.save_global_settings_button = ttk.Button(
            self.left_global_controls,
            text="儲存預設值",
            style="Primary.TButton",
            command=lambda: self._save_defaults(GLOBAL_CONTEXT),
        )
        self.save_global_settings_button.grid(row=0, column=4, sticky="ew", padx=2, pady=2)
        self.left_global_controls.columnconfigure(4, weight=0)
        return self.left_global_controls

    def _on_left_numeric_changed(self, key: str, var):
        if self._guard or self._rendering:
            return
        try:
            value = float(var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        current = self._values_snapshot().get(key)
        try:
            if current is not None and abs(float(current) - value) <= 1e-9:
                return
        except (TypeError, ValueError):
            pass
        self._stage_setting_update(key, value)

    def _emit_baseline_model_changed(self):
        if self._guard or self._rendering:
            return
        if self._baseline_model_changed is not None:
            self._baseline_model_changed()

    def _emit_ui_text_size_changed(self):
        if self._guard or self._rendering or self.ui_text_size_var is None:
            return
        if self._ui_text_size_changed is not None:
            self._ui_text_size_changed(normalize_ui_text_size(self.ui_text_size_var.get()))

    def _refresh_settings_scrollregion(self, _event=None):
        canvas = self.settings_scroll_canvas
        if canvas is None:
            return
        try:
            bbox = canvas.bbox("all")
            canvas.configure(scrollregion=bbox or (0, 0, 1, 1))
            if bbox is not None and canvas.winfo_height() >= max(0, int(bbox[3] - bbox[1])):
                canvas.yview_moveto(0.0)
        except tk.TclError:
            pass

    def _resize_settings_scroll_window(self, event):
        canvas = self.settings_scroll_canvas
        if canvas is None or self._settings_scroll_window is None:
            return
        try:
            canvas.itemconfigure(self._settings_scroll_window, width=max(1, int(event.width)))
        except tk.TclError:
            return
        self._refresh_settings_scrollregion()

    def _scroll_settings_fields(self, event):
        canvas = self.settings_scroll_canvas
        if canvas is None:
            return "break"
        delta = int(getattr(event, "delta", 0) or 0)
        number = int(getattr(event, "num", 0) or 0)
        if number == 4:
            steps = -1
        elif number == 5:
            steps = 1
        elif delta:
            steps = -1 if delta > 0 else 1
        else:
            return "break"
        try:
            canvas.yview_scroll(steps, "units")
        except tk.TclError:
            pass
        return "break"

    def _scroll_settings_keyboard(self, event):
        """Keyboard reachability for the existing settings scroll owner."""
        canvas = self.settings_scroll_canvas
        if canvas is None:
            return "break"
        key = str(getattr(event, "keysym", "") or "")
        try:
            if key == "Home":
                canvas.yview_moveto(0.0)
            elif key == "End":
                canvas.yview_moveto(1.0)
            elif key in {"Prior", "Page_Up"}:
                canvas.yview_scroll(-1, "pages")
            elif key in {"Next", "Page_Down"}:
                canvas.yview_scroll(1, "pages")
            else:
                return None
        except tk.TclError:
            pass
        return "break"

    def _bind_settings_scroll_tree(self, widget):
        try:
            widget.bind("<MouseWheel>", self._scroll_settings_fields, add="+")
            widget.bind("<Button-4>", self._scroll_settings_fields, add="+")
            widget.bind("<Button-5>", self._scroll_settings_fields, add="+")
            widget.bind("<Home>", self._scroll_settings_keyboard, add="+")
            widget.bind("<End>", self._scroll_settings_keyboard, add="+")
            widget.bind("<Prior>", self._scroll_settings_keyboard, add="+")
            widget.bind("<Next>", self._scroll_settings_keyboard, add="+")
        except tk.TclError:
            pass
        for child in tuple(widget.winfo_children()):
            self._bind_settings_scroll_tree(child)

    def build_settings_center(self, parent):
        self.settings_center = ttk.LabelFrame(parent, text="板件設定", padding=6)
        self.settings_center.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        header = ttk.Frame(self.settings_center)
        header.pack(fill=tk.X, pady=(0, 4))
        self.settings_title_var = tk.StringVar(master=self.settings_center, value="板件設定")
        ttk.Label(
            header,
            textvariable=self.settings_title_var,
            font=("Microsoft JhengHei", 10, "bold"),
        ).pack(side=tk.LEFT)
        self.unfolded_size_var = tk.StringVar(master=self.settings_center, value="展開料：-")
        ttk.Label(
            header,
            textvariable=self.unfolded_size_var,
            font=("Microsoft JhengHei", 10, "bold"),
        ).pack(side=tk.RIGHT)

        # Header/Footer stay fixed. Only the variable settings body owns scroll,
        # so Medium text + unlocked parameters cannot consume the 3D viewport.
        self.settings_scroll_host = ttk.Frame(self.settings_center)
        self.settings_scroll_host.pack(fill=tk.X)
        self.settings_scroll_canvas = tk.Canvas(
            self.settings_scroll_host,
            height=220,
            highlightthickness=0,
            borderwidth=0,
        )
        self.settings_scrollbar = ttk.Scrollbar(
            self.settings_scroll_host,
            orient=tk.VERTICAL,
            command=self.settings_scroll_canvas.yview,
        )
        self.settings_scroll_canvas.configure(yscrollcommand=self.settings_scrollbar.set)
        self.settings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.settings_scroll_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.settings_fields = ttk.Frame(self.settings_scroll_canvas)
        self._settings_scroll_window = self.settings_scroll_canvas.create_window(
            (0, 0),
            window=self.settings_fields,
            anchor="nw",
        )
        self.settings_fields.bind("<Configure>", self._refresh_settings_scrollregion, add="+")
        self.settings_scroll_canvas.bind("<Configure>", self._resize_settings_scroll_window, add="+")
        self._bind_settings_scroll_tree(self.settings_scroll_canvas)
        self._bind_settings_scroll_tree(self.settings_fields)

        footer = ttk.Frame(self.settings_center)
        footer.pack(fill=tk.X, pady=(4, 0))
        self.settings_status_var = tk.StringVar(
            master=self.settings_center,
            value="3D 內暫存；按左側確定才帶回主畫面",
        )
        ttk.Label(footer, textvariable=self.settings_status_var).pack(side=tk.LEFT)
        self.save_settings_button = ttk.Button(
            footer,
            text="儲存此板件為預設值",
            style="Primary.TButton",
            command=self.save_current_settings_as_defaults,
        )
        self.save_settings_button.pack(side=tk.RIGHT)
        return self.settings_center

    def _add_setting_widget(self, parent, spec: SettingSpec, row: int, col: int):
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=col, sticky="ew", padx=3, pady=2)
        ttk.Label(cell, text=spec.label).pack(anchor=tk.W)
        value = self._values_snapshot().get(spec.key, spec.default)
        if spec.kind == "bool":
            var = tk.BooleanVar(master=cell, value=bool(value))
            widget = ttk.Checkbutton(cell, text="啟用", variable=var)
        elif spec.kind == "choice" and spec.key == "ui_text_size":
            var = tk.StringVar(master=cell, value=ui_text_size_label(value))
            widget = build_choice_menubutton(
                cell,
                variable=var,
                values=tuple(UI_TEXT_SIZE_LABELS.values()),
                command=lambda k=spec.key, v=var, sp=spec: self._on_setting_var_changed(k, v, sp),
                width=6,
            )
        else:
            var = tk.StringVar(master=cell, value=setting_number_text(value))
            widget = ttk.Entry(cell, textvariable=var, width=9, justify=tk.CENTER, style="Editable.TEntry")
            widget.bind("<Return>", lambda _e: self._flush_settings())
            widget.bind("<FocusOut>", lambda _e: self._flush_settings())
        widget.pack(fill=tk.X)
        self.setting_vars[spec.key] = var
        if not (spec.kind == "choice" and spec.key == "ui_text_size"):
            var.trace_add("write", lambda *_args, k=spec.key, v=var, sp=spec: self._on_setting_var_changed(k, v, sp))
        return cell

    def _add_inspector_property_row(self, parent, spec: SettingSpec, row: int):
        """Build one aligned label/value/unit row without changing edit ownership."""
        row_frame = ttk.Frame(parent)
        row_frame.grid(row=row, column=0, sticky="ew", padx=2, pady=1)
        row_frame.columnconfigure(1, weight=1)
        ttk.Label(row_frame, text=spec.label, anchor="w", width=16).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        value = self._values_snapshot().get(spec.key, spec.default)
        if spec.kind == "bool":
            var = tk.BooleanVar(master=row_frame, value=bool(value))
            widget = ttk.Checkbutton(row_frame, text="啟用", variable=var)
            unit_text = ""
        elif spec.kind == "choice" and spec.key == "ui_text_size":
            var = tk.StringVar(master=row_frame, value=ui_text_size_label(value))
            widget = build_choice_menubutton(
                row_frame,
                variable=var,
                values=tuple(UI_TEXT_SIZE_LABELS.values()),
                command=lambda k=spec.key, v=var, sp=spec: self._on_setting_var_changed(k, v, sp),
                width=6,
            )
            unit_text = ""
        else:
            var = tk.StringVar(master=row_frame, value=setting_number_text(value))
            widget = ttk.Entry(row_frame, textvariable=var, width=9, justify=tk.CENTER, style="Editable.TEntry")
            widget.bind("<Return>", lambda _e: self._flush_settings())
            widget.bind("<FocusOut>", lambda _e: self._flush_settings())
            unit_text = "mm"
        widget.grid(row=0, column=1, sticky="ew")
        ttk.Label(row_frame, text=unit_text, width=4, anchor="w").grid(
            row=0, column=2, sticky="w", padx=(6, 0)
        )
        self.setting_vars[spec.key] = var
        if not (spec.kind == "choice" and spec.key == "ui_text_size"):
            var.trace_add(
                "write",
                lambda *_args, k=spec.key, v=var, sp=spec: self._on_setting_var_changed(k, v, sp),
            )
        return row_frame

    def _on_setting_var_changed(self, key: str, var, spec: SettingSpec):
        if self._guard or self._rendering:
            return
        raw = var.get()
        if spec.kind == "bool":
            value = bool(raw)
        elif spec.kind == "choice":
            value = normalize_ui_text_size(raw) if spec.key == "ui_text_size" else str(raw)
        else:
            try:
                value = float(raw)
            except (TypeError, ValueError, tk.TclError):
                return
        self._stage_setting_update(key, value)

    def _build_page(self, context: str):
        if self.settings_fields is None:
            raise RuntimeError("settings center 尚未建立")
        page_frame = ttk.Frame(self.settings_fields)
        old_vars = self.setting_vars
        self.setting_vars = {}
        try:
            groups = partition_setting_specs(
                context,
                self._specs_provider(context),
                hidden_keys=self._hidden_keys_by_context.get(context, frozenset()),
            )
            normal_groups = inspector_setting_groups(groups.normal)
            next_row = 0
            for group_name, group_specs in normal_groups:
                section = ttk.Frame(page_frame)
                section.grid(
                    row=next_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(4, 2)
                )
                section.columnconfigure(0, weight=1)
                ttk.Label(
                    section, text=group_name, font=("Microsoft JhengHei", 9, "bold")
                ).grid(row=0, column=0, sticky="w")
                ttk.Separator(section, orient=tk.HORIZONTAL).grid(
                    row=1, column=0, sticky="ew", pady=(2, 3)
                )
                body = ttk.Frame(section)
                body.grid(row=2, column=0, sticky="ew")
                body.columnconfigure(0, weight=1)
                for index, spec in enumerate(group_specs):
                    self._add_inspector_property_row(body, spec, index)
                next_row += 1
            for col in range(5):
                page_frame.columnconfigure(col, weight=1)
            extension_state = None
            result = self.render_context_extensions(page_frame, context, next_row)
            if result is not None:
                if not isinstance(result, SettingsPanelExtensionResult):
                    raise TypeError("settings context extension 必須回傳 SettingsPanelExtensionResult")
                next_row = int(result.next_row)
                extension_state = result.state

            baseline_data_toggle = None
            baseline_data_frame = None
            baseline_rows_host = None
            baseline_setting_cells = {}
            if self._should_show_baseline_data(context, groups.baseline):
                baseline_data_toggle = ttk.Button(
                    page_frame,
                    text="▶ 基準檔開孔資料",
                    style="Secondary.TButton",
                    command=self.toggle_baseline_data,
                )
                baseline_data_toggle.grid(row=next_row, column=0, columnspan=5, sticky="w", padx=3, pady=(7, 2))
                baseline_data_frame = ttk.LabelFrame(page_frame, text="基準檔開孔資料（數值）", padding=4)
                baseline_data_frame.grid(row=next_row + 1, column=0, columnspan=5, sticky="ew", padx=3, pady=(0, 2))
                for index, spec in enumerate(groups.baseline):
                    cell = self._add_setting_widget(baseline_data_frame, spec, index // 4, index % 4)
                    baseline_setting_cells[spec.key] = cell
                for col in range(4):
                    baseline_data_frame.columnconfigure(col, weight=1)
                baseline_rows_host = ttk.Frame(baseline_data_frame)
                baseline_rows_host.grid(
                    row=((len(groups.baseline) + 3) // 4) + 1,
                    column=0,
                    columnspan=4,
                    sticky="ew",
                    padx=3,
                    pady=(3, 0),
                )
                baseline_data_frame.grid_remove()
                next_row += 2

            advanced_frame = ttk.LabelFrame(page_frame, text="進階參數", padding=4)
            advanced_toggle = None
            if groups.advanced:
                advanced_frame.grid(row=next_row + 1, column=0, columnspan=5, sticky="ew", padx=3, pady=(8, 2))
                ttk.Label(
                    advanced_frame,
                    text="實際值依欄位定義套用；RELIEF 係數為 × 板厚 T。",
                ).grid(row=0, column=0, columnspan=4, sticky="w", padx=3, pady=(0, 3))
                for index, spec in enumerate(groups.advanced):
                    self._add_setting_widget(advanced_frame, spec, 1 + index // 4, index % 4)
                for col in range(4):
                    advanced_frame.columnconfigure(col, weight=1)
            return {
                "frame": page_frame,
                "setting_vars": dict(self.setting_vars),
                "advanced_frame": advanced_frame,
                "advanced_toggle": advanced_toggle,
                "baseline_data_frame": baseline_data_frame,
                "baseline_data_toggle": baseline_data_toggle,
                "baseline_rows_host": baseline_rows_host,
                "baseline_data_visible": False,
                "baseline_setting_cells": baseline_setting_cells,
                "extension_state": extension_state,
            }
        finally:
            self.setting_vars = old_vars


    def _owned_structure_entry(self, parent, row, label, value, active_type, field, *, suffix="mm"):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        var = tk.StringVar(master=parent, value=setting_number_text(value))
        entry = ttk.Entry(parent, textvariable=var, width=10, justify=tk.CENTER)
        entry.grid(row=row, column=1, sticky="w", pady=2)
        ttk.Label(parent, text=suffix).grid(row=row, column=2, sticky="w", padx=(5, 12), pady=2)
        if self._box_structure_numeric_changed is not None:
            entry.bind(
                "<Return>",
                lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
            )
            entry.bind(
                "<FocusOut>",
                lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
            )
        return var, entry

    def _render_owned_box_structure(self, parent, start_row, projection, state):
        frame = ttk.LabelFrame(parent, text="結構參數", padding=5)
        frame.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
        piece_host = ttk.Frame(frame)
        piece_host.grid(row=0, column=0, columnspan=4, sticky="ew")
        piece_sections = {}
        piece_vars = {}
        piece_entries = {}
        active_type = projection.get("active_type")
        mode = str(projection.get("mode") or "integral")

        error = projection.get("projection_error")
        if error:
            ttk.Label(
                piece_host,
                text=f"逐片尺寸：無法解析（{error}）",
                foreground=WHD_SEMANTIC_COLORS["warning"],
            ).pack(fill=tk.X, pady=2)

        for item in tuple(projection.get("pieces") or ()):
            item = dict(item or {})
            part_key = str(item.get("part_key") or "")
            sub = ttk.LabelFrame(piece_host, text=str(item.get("label") or part_key), padding=4)
            sub._phase6_part_key = part_key
            sub.pack(fill=tk.X, pady=(2, 4))
            piece_sections[part_key] = sub
            piece_vars[part_key] = {}
            piece_entries[part_key] = {}

            input_spec = item.get("input")
            if input_spec:
                input_spec = dict(input_spec)
                field_key = str(input_spec.get("field_key") or "")
                ttk.Label(sub, text=str(input_spec.get("label") or "")).grid(
                    row=0, column=0, sticky="w", padx=(0, 6), pady=2
                )
                var = tk.StringVar(master=sub, value=setting_number_text(input_spec.get("value")))
                entry = ttk.Entry(sub, textvariable=var, width=10, justify=tk.CENTER)
                entry.grid(row=0, column=1, sticky="w", pady=2)
                ttk.Label(sub, text=str(input_spec.get("suffix") or "")).grid(
                    row=0, column=2, sticky="w", padx=(5, 12), pady=2
                )
                if self._box_structure_numeric_changed is not None:
                    field = str(input_spec.get("state_field") or "")
                    entry.bind(
                        "<Return>",
                        lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
                    )
                    entry.bind(
                        "<FocusOut>",
                        lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
                    )
                piece_vars[part_key][field_key] = var
                piece_entries[part_key][field_key] = entry

            next_row = 1 if input_spec else 0
            selector = item.get("back_panel_selector")
            if selector:
                selector = dict(selector)
                ttk.Label(sub, text=str(selector.get("label") or "後面板形式")).grid(
                    row=next_row, column=0, sticky="w", padx=(0, 6), pady=2
                )
                selector_var = tk.StringVar(
                    master=sub, value=str(selector.get("value") or "")
                )
                selector_widget = ttk.Combobox(
                    sub,
                    textvariable=selector_var,
                    values=tuple(selector.get("options") or ()),
                    state="readonly",
                    width=10,
                )
                selector_widget.grid(row=next_row, column=1, columnspan=2, sticky="w", pady=2)
                if self._box_back_panel_mode_changed is not None:
                    selector_widget.bind(
                        "<<ComboboxSelected>>",
                        lambda _e, v=selector_var: self._box_back_panel_mode_changed(v),
                    )
                piece_vars[part_key]["back_panel_mode"] = selector_var
                piece_entries[part_key]["back_panel_mode"] = selector_widget
                next_row += 1

            ttk.Label(
                sub,
                text=(
                    f"包外尺寸：{setting_number_text(item.get('formed_width'))} × "
                    f"{setting_number_text(item.get('formed_height'))} mm"
                ),
            ).grid(row=next_row, column=0, columnspan=4, sticky="w", pady=(2, 0))
            next_row += 1
            ttk.Label(
                sub,
                text=(
                    f"料尺寸：{setting_number_text(item.get('blank_width'))} × "
                    f"{setting_number_text(item.get('blank_height'))} mm"
                ),
            ).grid(row=next_row, column=0, columnspan=4, sticky="w", pady=(0, 2))
            next_row += 1
            detail = item.get("detail")
            if detail:
                ttk.Label(sub, text=str(detail)).grid(
                    row=next_row, column=0, columnspan=4, sticky="w", pady=(0, 2)
                )

        state["box_body_piece_input_host"] = piece_host
        state["box_body_piece_input_sections"] = piece_sections
        state["box_body_piece_input_vars"] = piece_vars
        state["box_body_piece_input_entries"] = piece_entries

        row = 1
        if mode in {"two_w", "three_w"}:
            self._owned_structure_entry(
                frame,
                row,
                "中央接合折邊",
                projection.get("seam_bend", 12),
                active_type,
                "seam_bend",
            )
            row += 1
            seam = float(projection.get("seam_bend", 12) or 0)
            if seam >= 50:
                ttk.Label(
                    frame,
                    text=f"⚠ 中央接合折邊 {seam:g} mm 已達 50 mm 以上，請確認尺寸是否合理。",
                    foreground=WHD_SEMANTIC_COLORS["warning"],
                ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(2, 4))
                row += 1
            advanced_open = bool(projection.get("advanced_open", False))
            button = ttk.Button(
                frame,
                text=("▼ 截角／避讓" if advanced_open else "▶ 截角／避讓"),
                command=(
                    (lambda t=active_type: self._box_structure_toggle_advanced(t))
                    if self._box_structure_toggle_advanced is not None else None
                ),
            )
            button.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 0))
            row += 1
            advanced = ttk.LabelFrame(frame, text="截角／避讓", padding=4)
            if advanced_open:
                advanced.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(3, 0))
            for index, field in enumerate(tuple(projection.get("advanced_fields") or ())):
                field = dict(field or {})
                self._owned_structure_entry(
                    advanced,
                    index,
                    str(field.get("label") or ""),
                    field.get("value"),
                    active_type,
                    str(field.get("field") or ""),
                    suffix=str(field.get("suffix") or "mm"),
                )
        return start_row + 1

    def _render_owned_endcap_fw(self, parent, context, start_row, projection, state):
        box = ttk.Frame(parent, padding=4)
        box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
        ttk.Label(box, text="邊框寬度 FW", font=("Microsoft JhengHei", 9, "bold")).pack(anchor=tk.W)
        ttk.Separator(box, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(2, 4))
        follow_var = tk.BooleanVar(master=box, value=bool(projection.get("follow", True)))
        value_var = tk.StringVar(master=box, value=setting_number_text(projection.get("effective")))
        check = ttk.Checkbutton(box, text="跟隨箱身 FW", variable=follow_var)
        check.pack(side=tk.LEFT, padx=(0, 8))
        entry = ttk.Entry(box, textvariable=value_var, width=9, justify=tk.CENTER)
        entry.pack(side=tk.LEFT, padx=(0, 6))
        entry.configure(state="normal")
        check.configure(state="disabled")
        if self._endcap_fw_value_selected is not None:
            entry.bind(
                "<Return>",
                lambda _e, p=context, v=value_var: self._endcap_fw_value_selected(p, v),
            )
            entry.bind(
                "<FocusOut>",
                lambda _e, p=context, v=value_var: self._endcap_fw_value_selected(p, v),
            )
        ttk.Label(box, text="直接修改：先改一端會帶另一端；再改另一端後各自獨立").pack(side=tk.LEFT)
        state["endcap_fw_follow_var"] = follow_var
        state["endcap_fw_value_var"] = value_var
        state["endcap_fw_widget"] = entry
        return start_row + 1

    def _render_owned_bottom_wrap(self, parent, context, start_row, projection, state):
        if not projection:
            return start_row
        box = ttk.LabelFrame(parent, text="下方包覆貼外預留", padding=4)
        box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
        reserve_u_var = tk.StringVar(master=box, value=setting_number_text(projection.get("reserve_u")))
        reserve_v_var = tk.StringVar(master=box, value=setting_number_text(projection.get("reserve_v")))
        ttk.Label(box, text="X 預留 (mm)").grid(row=0, column=0, sticky="e")
        u_entry = ttk.Entry(box, textvariable=reserve_u_var, width=8, justify=tk.CENTER)
        u_entry.grid(row=0, column=1, padx=(3, 10))
        ttk.Label(box, text="Y 預留 (mm)").grid(row=0, column=2, sticky="e")
        v_entry = ttk.Entry(box, textvariable=reserve_v_var, width=8, justify=tk.CENTER)
        v_entry.grid(row=0, column=3, padx=3)
        if self._bottom_wrap_commit is not None:
            for entry in (u_entry, v_entry):
                entry.bind(
                    "<Return>",
                    lambda _e, p=context, u=reserve_u_var, v=reserve_v_var: self._bottom_wrap_commit(p, u, v),
                )
                entry.bind(
                    "<FocusOut>",
                    lambda _e, p=context, u=reserve_u_var, v=reserve_v_var: self._bottom_wrap_commit(p, u, v),
                )
        ttk.Label(
            box,
            text="WRAP 關係由組合方式／Joint Graph 決定；此處只調整預留。封頭/封尾先連動，修改另一端後才獨立。",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 0))
        state["bottom_wrap_enabled_var"] = None
        state["bottom_wrap_reserve_u_var"] = reserve_u_var
        state["bottom_wrap_reserve_v_var"] = reserve_v_var
        state["bottom_wrap_widget"] = box
        return start_row + 1

    def _render_owned_corner(self, parent, context, start_row, projection, state):
        fixed_summary_var = state["fixed_corner_summary_var"]
        mode = str(projection.get("mode") or "none")
        if mode == "none":
            return start_row
        if mode == "fixed":
            summary = str(projection.get("summary") or "")
            if not summary:
                return start_row
            box = ttk.LabelFrame(parent, text="截角類型（固定 / 唯讀）", padding=4)
            box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
            fixed_summary_var.set(summary)
            ttk.Label(box, textvariable=fixed_summary_var, wraplength=900).pack(anchor=tk.W)
            return start_row + 1

        type_editable = bool(projection.get("type_editable", False))
        params_unlocked = bool(projection.get("params_unlocked", False))
        params_editable = bool(projection.get("params_editable", False))
        box = ttk.LabelFrame(
            parent,
            text="截角類型" if type_editable else "截角類型（基準預設）",
            padding=4,
        )
        box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))

        for pair in tuple(projection.get("pairs") or ()):
            pair = dict(pair or {})
            pair_key = str(pair.get("pair_key") or "")
            row = ttk.Frame(box)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=str(pair.get("label") or ""), width=6).pack(side=tk.LEFT)
            same_var = tk.BooleanVar(master=row, value=bool(pair.get("same", False)))
            state["corner_pair_vars"][pair_key] = same_var
            same_cb = ttk.Checkbutton(
                row,
                text="左右相同",
                variable=same_var,
                command=(
                    (lambda p=context, pair=pair_key, v=same_var: self._corner_pair_changed(p, pair, v))
                    if self._corner_pair_changed is not None else None
                ),
            )
            same_cb.configure(state=("normal" if params_editable else "disabled"))
            state["corner_pair_checkbuttons"][pair_key] = same_cb
            if params_unlocked:
                same_cb.pack(side=tk.LEFT, padx=(0, 6))

            targets = tuple(pair.get("targets") or ())
            for target_item in targets:
                target_item = dict(target_item or {})
                target_key = str(target_item.get("target_key") or "")
                target = ttk.Frame(row)
                target.pack(side=tk.LEFT, padx=(3, 8))
                side_label = str(target_item.get("side_label") or "")
                if side_label:
                    ttk.Label(target, text=side_label).grid(row=0, column=0, sticky="w")

                type_var = tk.StringVar(master=target, value=str(target_item.get("type_label") or ""))
                state["corner_type_vars"][target_key] = type_var
                type_cb = build_choice_menubutton(
                    target,
                    variable=type_var,
                    values=tuple(target_item.get("type_options") or ()),
                    state=("normal" if type_editable and not bool(target_item.get("top_assembly_owned")) else "disabled"),
                    width=12,
                    command=(
                        (lambda p=context, t=target_key: self._corner_type_selected(p, t))
                        if self._corner_type_selected is not None else None
                    ),
                )
                type_cb.grid(row=0, column=1, padx=2, sticky="w")

                subrow = ttk.Frame(target)
                state["corner_detail_frames"][target_key] = subrow
                amount_var = tk.StringVar(
                    master=subrow,
                    value=setting_number_text(target_item.get("amount_t", 1.0)),
                )
                state["corner_amount_vars"][target_key] = amount_var

                if params_unlocked:
                    subrow.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
                else:
                    ttk.Label(
                        target,
                        text=str(target_item.get("parameter_summary") or ""),
                    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

                kind = str(target_item.get("type_kind") or "")
                if kind == "CROSS":
                    mode_var = tk.StringVar(master=subrow, value=str(target_item.get("mode_label") or ""))
                    state["corner_mode_vars"][target_key] = mode_var
                    mode_cb = build_choice_menubutton(
                        subrow,
                        variable=mode_var,
                        values=("標準", "單邊留肉", "多切"),
                        state=("normal" if params_editable else "disabled"),
                        width=9,
                        command=(
                            (lambda p=context, t=target_key: self._corner_mode_selected(p, t))
                            if self._corner_mode_selected is not None else None
                        ),
                    )
                    mode_cb.pack(side=tk.LEFT, padx=(0, 3))
                    if str(target_item.get("mode_kind") or "") != "STANDARD":
                        direction_var = tk.StringVar(
                            master=subrow,
                            value=str(target_item.get("direction_label") or ""),
                        )
                        state["corner_direction_vars"][target_key] = direction_var
                        direction_cb = build_choice_menubutton(
                            subrow,
                            variable=direction_var,
                            values=tuple(target_item.get("direction_options") or ()),
                            state=("normal" if params_editable else "disabled"),
                            width=7,
                            command=(
                                (lambda p=context, t=target_key: self._corner_target_changed(p, t))
                                if self._corner_target_changed is not None else None
                            ),
                        )
                        direction_cb.pack(side=tk.LEFT, padx=3)
                        entry = ttk.Entry(subrow, textvariable=amount_var, width=6, justify=tk.CENTER)
                        entry.configure(state=("normal" if params_editable else "disabled"))
                        entry.pack(side=tk.LEFT, padx=(3, 1))
                        ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                        if self._corner_target_changed is not None:
                            entry.bind("<Return>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                            entry.bind("<FocusOut>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                elif kind in {"OVERLAY", "INSERT"}:
                    action = "留肉（高）" if kind == "OVERLAY" else "多切（高）"
                    ttk.Label(subrow, text=action).pack(side=tk.LEFT, padx=(0, 3))
                    entry = ttk.Entry(subrow, textvariable=amount_var, width=6, justify=tk.CENTER)
                    entry.configure(state=("normal" if params_editable else "disabled"))
                    entry.pack(side=tk.LEFT, padx=(3, 1))
                    ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                    if self._corner_target_changed is not None:
                        entry.bind("<Return>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                        entry.bind("<FocusOut>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                else:
                    ttk.Label(subrow, text="貼外留肉（高）").pack(side=tk.LEFT, padx=(0, 2))
                    primary = ttk.Entry(subrow, textvariable=amount_var, width=5, justify=tk.CENTER)
                    primary.configure(state=("normal" if params_editable else "disabled"))
                    primary.pack(side=tk.LEFT, padx=(1, 1))
                    ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                    retain_var = tk.StringVar(
                        master=subrow,
                        value=setting_number_text(target_item.get("secondary_retain_t", 0)),
                    )
                    depth_var = tk.StringVar(
                        master=subrow,
                        value=setting_number_text(target_item.get("secondary_depth_t", 0)),
                    )
                    state["corner_secondary_retain_vars"][target_key] = retain_var
                    state["corner_secondary_depth_vars"][target_key] = depth_var
                    ttk.Label(subrow, text="  嵌入留肉").pack(side=tk.LEFT)
                    retain = ttk.Entry(subrow, textvariable=retain_var, width=5, justify=tk.CENTER)
                    retain.configure(state=("normal" if params_editable else "disabled"))
                    retain.pack(side=tk.LEFT, padx=(1, 1))
                    ttk.Label(subrow, text="T  深度").pack(side=tk.LEFT)
                    depth = ttk.Entry(subrow, textvariable=depth_var, width=5, justify=tk.CENTER)
                    depth.configure(state=("normal" if params_editable else "disabled"))
                    depth.pack(side=tk.LEFT, padx=(1, 1))
                    ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                    if self._corner_target_changed is not None:
                        for entry in (primary, retain, depth):
                            entry.bind("<Return>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                            entry.bind("<FocusOut>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
        return start_row + 1

    def render_context_extensions(self, parent, context, start_row):
        """Dispatch Settings context extensions through the canonical panel owner."""
        if self._context_extension_projection is not None:
            return self.render_owned_context_extensions(parent, context, start_row)
        if self._render_context_extensions is not None:
            # Compatibility fallback for callers not yet migrated to the owned projection seam.
            return self._render_context_extensions(parent, context, start_row)
        return SettingsPanelExtensionResult(next_row=int(start_row), state=None)

    def render_owned_context_extensions(self, parent, context, start_row):
        """Render the live Settings extension cluster inside the canonical panel owner."""
        if self._context_extension_projection is None:
            return SettingsPanelExtensionResult(next_row=int(start_row), state={})
        projection = dict(self._context_extension_projection(str(context)) or {})
        state = {
            "corner_pair_vars": {},
            "corner_pair_checkbuttons": {},
            "corner_type_vars": {},
            "corner_mode_vars": {},
            "corner_direction_vars": {},
            "corner_amount_vars": {},
            "corner_secondary_retain_vars": {},
            "corner_secondary_depth_vars": {},
            "corner_detail_frames": {},
            "fixed_corner_summary_var": tk.StringVar(master=parent, value=""),
            "corner_param_lock_button": None,
            "endcap_fw_follow_var": None,
            "endcap_fw_value_var": None,
            "endcap_fw_widget": None,
            "bottom_wrap_enabled_var": None,
            "bottom_wrap_reserve_u_var": None,
            "bottom_wrap_reserve_v_var": None,
            "bottom_wrap_widget": None,
        }
        next_row = int(start_row)
        box_projection = projection.get("box_structure")
        if box_projection:
            next_row = self._render_owned_box_structure(
                parent, next_row, dict(box_projection), state
            )
        endcap_projection = projection.get("endcap_fw")
        if endcap_projection:
            next_row = self._render_owned_endcap_fw(
                parent, str(context), next_row, dict(endcap_projection), state
            )
        bottom_projection = projection.get("bottom_wrap")
        if bottom_projection:
            next_row = self._render_owned_bottom_wrap(
                parent, str(context), next_row, dict(bottom_projection), state
            )
        corner_projection = dict(projection.get("corner") or {"mode": "none"})
        next_row = self._render_owned_corner(
            parent, str(context), next_row, corner_projection, state
        )
        return SettingsPanelExtensionResult(next_row=next_row, state=state)

    def invalidate_context(self, context: str):
        page = self.page_cache.pop(str(context), None)
        if page is not None:
            try:
                page["frame"].destroy()
            except Exception:
                pass
        if self.current_page == str(context):
            self.current_page = None

    def render_context(self, context: str):
        context = str(context or GLOBAL_CONTEXT)
        self.settings_context = context
        title = "全域設定" if context == GLOBAL_CONTEXT else f"{self._part_labels.get(context, context)}設定"
        if self.settings_title_var is not None:
            self.settings_title_var.set(title)
        self._rendering = True
        try:
            current = self.current_page
            if current is not None and current in self.page_cache:
                self.page_cache[current]["frame"].pack_forget()
            page = self.page_cache.get(context)
            if page is None:
                page = self._build_page(context)
                self.page_cache[context] = page
            page["frame"].pack(fill=tk.X)
            self._bind_settings_scroll_tree(page["frame"])
            self._refresh_settings_scrollregion()
            if self.settings_scroll_canvas is not None:
                try:
                    self.settings_scroll_canvas.yview_moveto(0.0)
                except tk.TclError:
                    pass
            self.current_page = context
            self.setting_vars = page["setting_vars"]
            self.advanced_settings_frame = page["advanced_frame"]
            self.advanced_toggle_button = page["advanced_toggle"]
            self.baseline_data_frame = page.get("baseline_data_frame")
            self.baseline_data_toggle_button = page.get("baseline_data_toggle")
            self.baseline_setting_cells = page.get("baseline_setting_cells", {})
            if self._sync_context_extension is not None:
                self._sync_context_extension(page.get("extension_state"), context)
            self.sync_values()
            if self.save_settings_button is not None:
                self.save_settings_button.configure(
                    text="儲存全域預設值" if context == GLOBAL_CONTEXT else "儲存此板件為預設值"
                )
            return page
        finally:
            self._rendering = False

    def sync_values(self, values: Mapping[str, object] | None = None):
        snapshot = dict(values if values is not None else self._values_snapshot())
        self._guard = True
        try:
            for page in self.page_cache.values():
                for key, var in page.get("setting_vars", {}).items():
                    if key not in snapshot:
                        continue
                    value = snapshot[key]
                    if key == "ui_text_size":
                        text = ui_text_size_label(value)
                        if var.get() != text:
                            var.set(text)
                    elif isinstance(var, tk.BooleanVar):
                        if bool(var.get()) != bool(value):
                            var.set(bool(value))
                    else:
                        text = setting_number_text(value)
                        if var.get() != text:
                            var.set(text)
            for key, var in self.left_global_vars.items():
                if key not in snapshot:
                    continue
                value = snapshot[key]
                if key == "ui_text_size":
                    text = ui_text_size_label(value)
                    if var.get() != text:
                        var.set(text)
                elif isinstance(var, tk.BooleanVar):
                    if bool(var.get()) != bool(value):
                        var.set(bool(value))
                else:
                    text = setting_number_text(value)
                    if var.get() != text:
                        var.set(text)
        finally:
            self._guard = False

    def toggle_advanced(self):
        # 相容舊 caller；新版 UI 由外層參數鎖統一控制，進階區固定隨面板顯示。
        self.advanced_settings_visible = True
        return self.page_cache.get(self.settings_context)

    def _fill_baseline_data_rows(self, page, context: str):
        host = page.get("baseline_rows_host")
        if host is None:
            return
        for child in host.winfo_children():
            child.destroy()
        if self.baseline_model_var is not None:
            model = str(self.baseline_model_var.get() or "").strip()
        else:
            model = str(self._baseline_model_getter() or "").strip()
        rows = []
        if self._query_baseline_rows is not None and not self._is_unknown_baseline(model):
            try:
                rows = list(self._query_baseline_rows(context, model, dict(self._values_snapshot())) or ())
            except Exception as exc:
                ttk.Label(host, text=f"讀取基準檔資料失敗：{exc}").pack(anchor=tk.W)
                return
        if not rows:
            ttk.Label(host, text="此板件沒有額外基準檔開孔資料").pack(anchor=tk.W)
            return
        for row in rows:
            ttk.Label(host, text=baseline_row_text(row)).pack(anchor=tk.W, pady=1)

    def refresh_baseline_data(self):
        page = self.page_cache.get(self.settings_context)
        if page and page.get("baseline_data_visible", False):
            self._fill_baseline_data_rows(page, self.settings_context)

    def toggle_baseline_data(self):
        page = self.page_cache.get(self.settings_context)
        if not page:
            return
        frame = page.get("baseline_data_frame")
        button = page.get("baseline_data_toggle")
        if frame is None or button is None:
            return
        if page.get("baseline_data_visible", False):
            frame.grid_remove()
            page["baseline_data_visible"] = False
            button.configure(text="▶ 基準檔開孔資料")
        else:
            self._fill_baseline_data_rows(page, self.settings_context)
            frame.grid()
            page["baseline_data_visible"] = True
            button.configure(text="▼ 基準檔開孔資料")
        self.baseline_data_frame = frame
        self.baseline_data_toggle_button = button
        self._refresh_settings_scrollregion()

    def save_current_settings_as_defaults(self):
        self._flush_settings()
        try:
            result = self._save_defaults(self.settings_context)
        except Exception as exc:
            if self.settings_status_var is not None:
                self.settings_status_var.set(f"儲存失敗：{exc}")
            return False
        if self.settings_status_var is not None:
            self.settings_status_var.set("已儲存到 config.ini" if result is not False else "儲存失敗")
        return result is not False
