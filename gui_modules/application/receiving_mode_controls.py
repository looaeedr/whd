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
    """Legacy compatibility only: return Family defaults, never open a dialog.

    Fresh Receiving Set/Bay or Quantity sessions must use one deterministic
    800 x 1600 x 350 default. No UI initialization/confirmation is allowed.
    """
    if target not in {"quantity", "set_bay"}:
        raise ValueError("不合法的受電箱操作模式")
    return {key: int(BOX_BODY_DEFAULTS[key]) for key in ("w", "h", "d")}
