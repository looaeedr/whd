# -*- coding: utf-8 -*-
"""Reusable presentation primitives for the Phase6 settings panel."""
from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from whd_theme import configure_tk_menu


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
