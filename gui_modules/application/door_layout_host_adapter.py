# -*- coding: utf-8 -*-
"""Door-layout grid/state adapter for Phase6ApplicationHost.

Receiving inner-door controls intentionally remain outside this module.
"""
from __future__ import annotations

import tkinter as tk

import ae_engine.ae as ae
from gui_modules.application.door_layout_controller import (
    DoorLayoutColumnState as _DoorLayoutColumnState,
    door_layout_cells as _door_layout_cells_impl,
    recompute_door_layout as _recompute_door_layout_impl,
    remap_owned_data as _remap_door_layout_owned_data_impl,
    validate_height_commit as _validate_door_layout_height_commit_impl,
    validate_width_commit as _validate_door_layout_width_commit_impl,
)
from gui_modules.parts.panels.door import (
    _parse_layout_value as _parse_layout_value_impl,
    _reject_door_layout_dimension as _reject_door_layout_dimension_impl,
)

def _door_layout_number_text(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)

def _new_door_layout_column(self, width, heights, *, width_auto=False, height_auto=None):
    height_values = list(heights)
    if height_auto is None:
        height_auto = [False] * len(height_values)
    return {
        "width_var": tk.StringVar(value=self._door_layout_number_text(width)),
        "width_auto": bool(width_auto),
        "width_committed": float(width),
        "height_vars": [tk.StringVar(value=self._door_layout_number_text(v)) for v in height_values],
        "height_auto": [bool(v) for v in height_auto],
        "height_committed": [float(v) for v in height_values],
        "height_completion": None,
    }

def set_door_layout_columns(self, columns):
    """Replace Door layout with explicit user values, then append any W/H remainders."""
    model = []
    for width, heights in columns:
        height_values = list(heights)
        if not height_values:
            raise ValueError("每一欄至少需要一層高度")
        model.append(self._new_door_layout_column(width, height_values))
    if not model:
        raise ValueError("門配置至少需要一欄")
    self.door_layout_columns = model
    self.door_layout_selected_var.set("0:0")
    self._recompute_door_layout_remainders(rebuild=False)
    if hasattr(self, "door_layout_columns_frame"):
        self.rebuild_door_layout_ui()

def _ensure_door_layout_default(self):
    if self.door_layout_columns:
        return
    try:
        width = float(self.w_var.get())
        height = float(self.h_var.get())
    except ValueError:
        width, height = ae.W, ae.H
    self.door_layout_columns = [self._new_door_layout_column(width, [height])]
    self._recompute_door_layout_remainders(rebuild=False)

def _parse_layout_value(var, label):
    return _parse_layout_value_impl(var, label)

def _door_layout_controller_columns(self):
    columns = []
    for index, column in enumerate(self.door_layout_columns, start=1):
        columns.append(_DoorLayoutColumnState(
            width=self._parse_layout_value(column["width_var"], f"欄 {index} 寬度"),
            width_auto=bool(column.get("width_auto", False)),
            heights=tuple(
                self._parse_layout_value(var, f"欄 {index} 第 {row} 層高度")
                for row, var in enumerate(column["height_vars"], start=1)
            ),
            height_auto=tuple(bool(value) for value in column["height_auto"]),
        ))
    return tuple(columns)

def _recompute_door_layout_remainders(self, *, rebuild=True):
    """Apply the bounded application Door Layout transition to Tk presentation state."""
    if not self.door_layout_columns:
        return
    try:
        total_width = float(self.w_var.get())
        total_height = float(self.h_var.get())
    except ValueError as exc:
        raise ValueError("W / H 必須先填入有效數字") from exc
    result = _recompute_door_layout_impl(
        self._door_layout_controller_columns(),
        total_width=total_width,
        total_height=total_height,
        selected_key=self.door_layout_selected_var.get(),
    )
    model = []
    for column in result.columns:
        item = self._new_door_layout_column(
            column.width,
            column.heights,
            width_auto=column.width_auto,
            height_auto=column.height_auto,
        )
        item["height_completion"] = column.height_completion
        model.append(item)
    self.door_layout_columns = model
    self._door_layout_width_completion = result.width_completion
    self.door_layout_selected_var.set(result.selected_key)
    if rebuild and hasattr(self, "door_layout_columns_frame"):
        self.rebuild_door_layout_ui()

def get_door_layout_columns(self):
    """Read current fixed + generated remainder cells as numeric layout values."""
    if not self.door_layout_columns:
        self._ensure_door_layout_default()
    columns = []
    for column_index, column in enumerate(self.door_layout_columns, start=1):
        if isinstance(column, (list, tuple)):
            columns.append((float(column[0]), [float(h) for h in list(column[1])]))
            continue
        width = self._parse_layout_value(column["width_var"], f"欄 {column_index} 寬度")
        heights = [
            self._parse_layout_value(var, f"欄 {column_index} 第 {row_index} 層高度")
            for row_index, var in enumerate(column["height_vars"], start=1)
        ]
        columns.append((width, heights))
    return columns

def get_door_layout_cells(self):
    columns = self.get_door_layout_columns()
    try:
        total_width = float(self.w_var.get())
        total_height = float(self.h_var.get())
    except ValueError as exc:
        raise ValueError("W / H 必須先填入有效數字") from exc
    return _door_layout_cells_impl(
        columns, total_width=total_width, total_height=total_height
    )

def _door_layout_cell_key(cell):
    return f"{cell.column_index}:{cell.row_index}"

def get_selected_door_layout_cell(self):
    cells = self.get_door_layout_cells()
    selected_key = self.door_layout_selected_var.get()
    for cell in cells:
        if self._door_layout_cell_key(cell) == selected_key:
            return cell
    first = cells[0]
    self.door_layout_selected_var.set(self._door_layout_cell_key(first))
    return first

def select_door_layout_cell(self, column_index, row_index):
    """Select one multi-door cell without rebuilding geometry or Canvas widgets."""
    selected_key = f"{int(column_index)}:{int(row_index)}"
    self.door_layout_selected_var.set(selected_key)

    canvas = getattr(self, "canvas_door", None)
    designer = getattr(self, "fold_designer_app", None)
    if (
        designer is not None
        and str(getattr(designer, "_phase6_3d_display_mode", "") or "") == "corner_data"
    ):
        corner_canvas = getattr(designer, "corner_data_canvas", None)
        if corner_canvas is not None:
            canvas = corner_canvas
        import fold_designer_bridge as phase6_bridge
        stable_key = f"door_c{int(column_index) + 1}_r{int(row_index) + 1}"
        phase6_bridge._phase6_select_corner_data_part(
            designer, stable_key, refresh_view=False
        )
    if canvas is not None:
        for key, item_id in getattr(self, "door_layout_cell_items", {}).items():
            try:
                canvas.itemconfigure(
                    item_id,
                    outline=self.COLOR_ACCENT if key == selected_key else "#30d158",
                    width=3 if key == selected_key else 2,
                )
            except tk.TclError:
                pass

    if hasattr(self, "last_door_layout_overview"):
        self.last_door_layout_overview["selected"] = selected_key

def _sync_door_canvas_double_click_binding(self):
    """Multi-door counts two Button-1 presses itself; single Door keeps Tk double-click."""
    if not hasattr(self, "canvas_door"):
        return
    self.canvas_door.unbind("<Double-Button-1>")
    if not self.multi_door_enabled_var.get():
        self.canvas_door.bind("<Double-Button-1>", self.on_door_canvas_double_click)

def toggle_multi_door_layout(self):
    self._door_layout_last_click = None
    if self.multi_door_enabled_var.get():
        self._ensure_door_layout_default()
        self._recompute_door_layout_remainders(rebuild=False)
    self._sync_door_canvas_double_click_binding()
    # 舊的欄/層表單永久不佔 Door 分頁空間；尺寸直接在 Canvas 上編輯。
    if hasattr(self, "door_layout_body"):
        self.door_layout_body.pack_forget()
    self._on_door_layout_value_changed()

def _reject_door_layout_dimension(self, var, previous_value, message):
    return _reject_door_layout_dimension_impl(self, var, previous_value, message)

def commit_door_layout_width(self, column_index):
    column = self.door_layout_columns[column_index]
    previous = float(column.get("width_committed", self._parse_layout_value(column["width_var"], "欄寬")))
    try:
        current = self._parse_layout_value(column["width_var"], f"欄 {column_index+1} 寬度")
        total_width = self._parse_layout_value(self.w_var, "W")
        validation = _validate_door_layout_width_commit_impl(
            self._door_layout_controller_columns(), column_index, total_width, current
        )
    except ValueError as exc:
        return self._reject_door_layout_dimension(column["width_var"], previous, str(exc))
    if not validation.valid:
        return self._reject_door_layout_dimension(
            column["width_var"], previous,
            f"欄 {column_index+1} 寬度不可超過盤體 W。\n"
            f"W = {total_width:g} mm，其餘固定欄合計 {validation.other_fixed:g} mm，"
            f"此欄最大只能輸入 {max(0.0, validation.maximum):g} mm。"
        )
    column["width_auto"] = validation.keep_auto
    column["width_committed"] = current
    self._recompute_door_layout_remainders(rebuild=True)
    self._on_door_layout_value_changed(recompute=False)
    return True

def commit_door_layout_height(self, column_index, row_index):
    column = self.door_layout_columns[column_index]
    committed = column.get("height_committed") or []
    previous = float(committed[row_index]) if row_index < len(committed) else self._parse_layout_value(
        column["height_vars"][row_index], "高度"
    )
    try:
        current = self._parse_layout_value(
            column["height_vars"][row_index], f"欄 {column_index+1} 第 {row_index+1} 層高度"
        )
        total_height = self._parse_layout_value(self.h_var, "H")
        validation = _validate_door_layout_height_commit_impl(
            self._door_layout_controller_columns(), column_index, row_index, total_height, current
        )
    except ValueError as exc:
        return self._reject_door_layout_dimension(column["height_vars"][row_index], previous, str(exc))
    if not validation.valid:
        return self._reject_door_layout_dimension(
            column["height_vars"][row_index], previous,
            f"欄 {column_index+1} 第 {row_index+1} 層高度不可超過盤體 H。\n"
            f"H = {total_height:g} mm，同欄其他固定高度合計 {validation.other_fixed:g} mm，"
            f"此層最大只能輸入 {max(0.0, validation.maximum):g} mm。"
        )
    column["height_auto"][row_index] = validation.keep_auto
    if row_index >= len(committed):
        column["height_committed"] = [
            self._parse_layout_value(var, "高度") for var in column["height_vars"]
        ]
    else:
        column["height_committed"][row_index] = current
    self._recompute_door_layout_remainders(rebuild=True)
    self._on_door_layout_value_changed(recompute=False)
    return True

def add_door_layout_column(self):
    """Compatibility action: promote current auto width; remainder creates the next column."""
    self._ensure_door_layout_default()
    auto_index = next((i for i, c in enumerate(self.door_layout_columns) if c.get("width_auto")), None)
    if auto_index is not None:
        self.commit_door_layout_width(auto_index)

def _remap_door_layout_owned_data(self, mapper):
    for attr in (
        "door_layout_features", "door_layout_indicator_states",
        "door_layout_indicator_box_features", "door_layout_indicator_door_features",
    ):
        setattr(
            self,
            attr,
            _remap_door_layout_owned_data_impl(getattr(self, attr, {}), mapper),
        )

def remove_door_layout_column(self, column_index):
    if not self.door_layout_columns:
        return
    if self.door_layout_columns[column_index].get("width_auto"):
        return
    self._remap_door_layout_owned_data(
        lambda c, r: None if c == column_index else ((c - 1, r) if c > column_index else (c, r))
    )
    del self.door_layout_columns[column_index]
    self.door_layout_selected_var.set("0:0")
    if not self.door_layout_columns:
        try:
            total_h = float(self.h_var.get())
        except ValueError:
            total_h = ae.H
        self.door_layout_columns = [self._new_door_layout_column(0.0, [total_h], width_auto=True, height_auto=[True])]
    self._recompute_door_layout_remainders(rebuild=True)
    self._on_door_layout_value_changed(recompute=False)

def add_door_layout_height(self, column_index):
    """Compatibility action: promote current auto height; remainder creates the next segment."""
    column = self.door_layout_columns[column_index]
    auto_index = next((i for i, value in enumerate(column["height_auto"]) if value), None)
    if auto_index is not None:
        self.commit_door_layout_height(column_index, auto_index)

def remove_door_layout_height(self, column_index, row_index):
    column = self.door_layout_columns[column_index]
    if column["height_auto"][row_index]:
        return
    self._remap_door_layout_owned_data(
        lambda c, r: (
            None if c == column_index and r == row_index
            else ((c, r - 1) if c == column_index and r > row_index else (c, r))
        )
    )
    del column["height_vars"][row_index]
    del column["height_auto"][row_index]
    self.door_layout_selected_var.set(f"{column_index}:0")
    self._recompute_door_layout_remainders(rebuild=True)
    self._on_door_layout_value_changed(recompute=False)

def _on_door_layout_value_changed(self, *, recompute=True):
    if recompute and self.multi_door_enabled_var.get():
        try:
            self._recompute_door_layout_remainders(rebuild=False)
        except Exception:
            pass
    self.refresh_door_layout_status()
    self._request_phase6_update("geometry")

def _on_total_door_dimension_changed(self):
    if self.multi_door_enabled_var.get() and self.door_layout_columns:
        try:
            self._recompute_door_layout_remainders(rebuild=True)
        except Exception:
            self.refresh_door_layout_status()
