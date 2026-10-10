"""Tk presentation with bounded callbacks; no workspace or geometry owner."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk, messagebox
from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS


@dataclass
class ReceivingModeControls:
    frame: object
    mode_var: object
    common_button: object
    versions: object
    quantity_editor: object = None
    mode_row: object = None

    def refresh(self, mode, quantity):
        self.mode_var.set(mode)
        if mode == "quantity":
            self.quantity_editor.frame.pack(fill=tk.X)
            self.common_button.pack(fill=tk.X, pady=4, before=self.quantity_editor.frame)
            self.quantity_editor.refresh()
        else:
            self.common_button.pack_forget()
            self.quantity_editor.frame.pack_forget()


def build_mode_controls(parent, *, on_switch, on_common, quantity_ports):
    frame = ttk.Frame(parent)
    mode_var = tk.StringVar(master=frame)
    row = ttk.Frame(frame)
    row.pack(fill=tk.X)
    for label, value in (("套／連模式", "set_bay"), ("數量模式", "quantity")):
        ttk.Radiobutton(row, text=label, variable=mode_var, value=value,
                        command=lambda value=value: on_switch(value)).pack(side=tk.LEFT)
    common = ttk.Button(frame, text="共用箱體設定", command=on_common)
    from .quantity_version_controls import build_quantity_controls
    editor = build_quantity_controls(frame, quantity_ports)
    return ReceivingModeControls(frame, mode_var, common, editor.versions, editor, row)



def ask_initial_dimensions(parent, target):
    """Closing or cancelling returns None without invoking any commit callback."""
    win = tk.Toplevel(parent)
    win.title("初始化數量模式" if target == "quantity" else "初始化套／連模式")
    win.transient(parent)
    explanation = ("建立獨立單箱體與首筆孔型版本" if target == "quantity"
                   else "建立獨立 1 套 × 1 連、0 Joint")
    ttk.Label(win, text=explanation + "\n請確認 W/H/D（初值來自受電箱 Family 預設）").pack(padx=12, pady=10)
    form = ttk.Frame(win, padding=12)
    form.pack()
    values = {}
    for row, axis in enumerate(("w", "h", "d")):
        ttk.Label(form, text=axis.upper()).grid(row=row, column=0, sticky="w")
        values[axis] = tk.StringVar(master=win, value=str(BOX_BODY_DEFAULTS[axis]))
        ttk.Entry(form, textvariable=values[axis], width=12).grid(row=row, column=1, padx=6, pady=3)
    result = []
    def confirm():
        from ae_engine.receiving_quantity_box import positive_dimension
        try:
            dimensions = {axis: positive_dimension(var.get(), axis) for axis, var in values.items()}
        except ValueError as exc:
            messagebox.showwarning("尺寸未確認", str(exc), parent=win)
            return
        result.append(dimensions)
        win.destroy()
    buttons = ttk.Frame(win, padding=10)
    buttons.pack(fill=tk.X)
    ttk.Button(buttons, text="取消", command=win.destroy).pack(side=tk.RIGHT)
    ttk.Button(buttons, text="確認", command=confirm).pack(side=tk.RIGHT, padx=6)
    win.grab_set()
    parent.wait_window(win)
    return result[0] if result else None
