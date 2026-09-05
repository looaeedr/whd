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
    kwargs = {"textvariable": variable, "state": state}
    if width is not None:
        kwargs["width"] = width
    button = ttk.Menubutton(parent, **kwargs)
    menu = tk.Menu(button, tearoff=False)
    for value in tuple(values or ()):
        menu.add_radiobutton(
            label=str(value),
            variable=variable,
            value=str(value),
            command=command,
        )
    button.configure(menu=menu)
    button._phase6_menu = menu
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
            ttk.Label(cell, text=label).pack(anchor=tk.W)
            entry = ttk.Entry(cell, textvariable=self.left_global_vars[key], width=6, justify=tk.CENTER)
            entry.pack(fill=tk.X)
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
        self.settings_fields = ttk.Frame(self.settings_center)
        self.settings_fields.pack(fill=tk.X)
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
            widget = ttk.Entry(cell, textvariable=var, width=9, justify=tk.CENTER)
            widget.bind("<Return>", lambda _e: self._flush_settings())
            widget.bind("<FocusOut>", lambda _e: self._flush_settings())
        widget.pack(fill=tk.X)
        self.setting_vars[spec.key] = var
        if not (spec.kind == "choice" and spec.key == "ui_text_size"):
            var.trace_add("write", lambda *_args, k=spec.key, v=var, sp=spec: self._on_setting_var_changed(k, v, sp))
        return cell

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
            for index, spec in enumerate(groups.normal):
                self._add_setting_widget(page_frame, spec, index // 5, index % 5)
            for col in range(5):
                page_frame.columnconfigure(col, weight=1)
            next_row = (len(groups.normal) + 4) // 5
            extension_state = None
            if self._render_context_extensions is not None:
                result = self._render_context_extensions(page_frame, context, next_row)
                if result is not None:
                    if not isinstance(result, SettingsPanelExtensionResult):
                        raise TypeError("render_context_extensions 必須回傳 SettingsPanelExtensionResult")
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
