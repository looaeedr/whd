"""Small modal dialog presentation helpers for the Phase6 GUI.

This module owns only transient Tk presentation/input normalization.  It does
not own committed project state, geometry, or manufacturing calculations.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


def parse_xy_values(x_text: str, y_text: str) -> tuple[float, float]:
    """Parse the two numeric fields using the legacy float contract."""
    return float(x_text), float(y_text)


def ask_xy_dialog(
    root,
    current_x,
    current_y,
    *,
    color_bg,
    color_text,
    color_panel,
    color_accent,
):
    """Show the legacy XY modal and return ``(x, y)`` or ``(None, None)``."""
    dialog = tk.Toplevel(root)
    dialog.title("輸入指示燈定位距離")
    dialog.transient(root)
    dialog.grab_set()
    dialog.resizable(False, False)
    dialog.geometry("+%d+%d" % (root.winfo_rootx() + 200, root.winfo_rooty() + 150))
    dialog.configure(bg=color_bg)

    tk.Label(
        dialog,
        text="請輸入新的定位距離 (mm)",
        bg=color_bg,
        fg=color_text,
        font=("Microsoft JhengHei", 10, "bold"),
    ).pack(pady=10)

    input_frame = tk.Frame(dialog, bg=color_bg)
    input_frame.pack(padx=20, pady=5)

    tk.Label(
        input_frame,
        text="水平距離 X (mm):",
        bg=color_bg,
        fg=color_text,
        font=("Microsoft JhengHei", 9),
    ).grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
    entry_x = ttk.Entry(input_frame, width=12)
    entry_x.insert(0, f"{current_x:.1f}")
    entry_x.grid(row=0, column=1, padx=5, pady=5)
    entry_x.focus_set()

    tk.Label(
        input_frame,
        text="垂直距離 Y (mm):",
        bg=color_bg,
        fg=color_text,
        font=("Microsoft JhengHei", 9),
    ).grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
    entry_y = ttk.Entry(input_frame, width=12)
    entry_y.insert(0, f"{current_y:.1f}")
    entry_y.grid(row=1, column=1, padx=5, pady=5)

    result = [None, None]

    def on_ok(event=None):
        try:
            result[0], result[1] = parse_xy_values(entry_x.get(), entry_y.get())
            dialog.destroy()
        except ValueError:
            messagebox.showerror("錯誤", "請輸入正確的數字格式", parent=dialog)

    def on_cancel():
        dialog.destroy()

    btn_frame = tk.Frame(dialog, bg=color_bg)
    btn_frame.pack(pady=15)

    tk.Button(
        btn_frame,
        text="確認",
        font=("Microsoft JhengHei", 9, "bold"),
        bg=color_panel,
        fg=color_accent,
        bd=1,
        relief=tk.SOLID,
        padx=15,
        command=on_ok,
    ).pack(side=tk.LEFT, padx=10)
    tk.Button(
        btn_frame,
        text="取消",
        font=("Microsoft JhengHei", 9),
        bg=color_panel,
        fg=color_text,
        bd=1,
        relief=tk.SOLID,
        padx=15,
        command=on_cancel,
    ).pack(side=tk.LEFT, padx=10)

    dialog.bind("<Return>", on_ok)
    dialog.bind("<Escape>", lambda _event: on_cancel())
    root.wait_window(dialog)
    return result[0], result[1]
