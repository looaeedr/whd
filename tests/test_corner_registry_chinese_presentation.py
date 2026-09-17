import os
import re
import tkinter as tk
from tkinter import ttk

import pytest

import gui


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="Corner registry presentation requires real Tk/Xvfb"
)

_ASCII_ALPHA = re.compile(r"[A-Za-z]")


def _open_designer():
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    root.update_idletasks()
    root.update()
    return root, app, designer


def _pump(root, cycles=4):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _safe_cget(widget, option):
    try:
        return str(widget.cget(option) or "")
    except (tk.TclError, AttributeError):
        return ""


def _visible_strings(widget):
    rows = []

    text = _safe_cget(widget, "text").strip()
    if text:
        rows.append((str(widget), "text", text))

    textvariable = _safe_cget(widget, "textvariable").strip()
    if textvariable:
        try:
            value = str(widget.getvar(textvariable) or "").strip()
        except (tk.TclError, AttributeError):
            value = ""
        if value:
            rows.append((str(widget), "textvariable", value))

    if isinstance(widget, ttk.Notebook):
        for tab_id in widget.tabs():
            value = str(widget.tab(tab_id, "text") or "").strip()
            if value:
                rows.append((str(widget), "tab", value))

    if isinstance(widget, ttk.Treeview):
        columns = ("#0",) + tuple(widget["columns"])
        for column in columns:
            try:
                value = str(widget.heading(column, "text") or "").strip()
            except tk.TclError:
                value = ""
            if value:
                rows.append((str(widget), f"heading:{column}", value))

        def walk(parent=""):
            for item_id in widget.get_children(parent):
                item = widget.item(item_id)
                value = str(item.get("text") or "").strip()
                if value:
                    rows.append((str(widget), f"item:{item_id}:text", value))
                for index, cell in enumerate(item.get("values") or ()):
                    value = str(cell or "").strip()
                    if value:
                        rows.append((str(widget), f"item:{item_id}:value:{index}", value))
                walk(item_id)
        walk()

    if isinstance(widget, tk.Canvas):
        for item_id in widget.find_all():
            try:
                if widget.type(item_id) == "text":
                    value = str(widget.itemcget(item_id, "text") or "").strip()
                    if value:
                        rows.append((str(widget), f"canvas:{item_id}", value))
            except tk.TclError:
                pass

    for child in widget.winfo_children():
        rows.extend(_visible_strings(child))
    return rows


def test_corner_registry_user_visible_text_is_chinese_only():
    """Registry presentation may localize internal IDs, but must never expose ASCII words."""
    root, _app, designer = _open_designer()
    try:
        designer.relief_registry_button.invoke()
        _pump(root)
        win = designer.relief_registry_window
        assert win.winfo_exists()
        assert win.winfo_ismapped()

        visible = [(str(win), "title", str(win.title() or "").strip())]
        visible.extend(_visible_strings(win))
        leaks = [row for row in visible if row[2] and _ASCII_ALPHA.search(row[2])]

        print("CORNER_REGISTRY_VISIBLE_TEXT", visible)
        print("CORNER_REGISTRY_ASCII_LEAKS", leaks)
        assert not leaks, (
            "截角資料庫使用者可見文字不得顯示英文字母；內部 enum/key/schema 可保留英文，"
            f"但 presentation boundary 必須中文化。leaks={leaks!r}"
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass
