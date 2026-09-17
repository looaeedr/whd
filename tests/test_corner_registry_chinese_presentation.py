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
_TEXT_WIDGETS = (tk.Label, tk.Button, tk.Checkbutton, tk.Menubutton, tk.LabelFrame,
                 ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Menubutton, ttk.LabelFrame)


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


def _menu_visible_strings(widget):
    rows = []
    menu_name = _safe_cget(widget, "menu").strip()
    if not menu_name:
        return rows
    try:
        menu = widget.nametowidget(menu_name)
        end = menu.index("end")
    except (tk.TclError, KeyError):
        return rows
    if end is None:
        return rows
    for index in range(end + 1):
        try:
            label = str(menu.entrycget(index, "label") or "").strip()
        except tk.TclError:
            continue
        if label:
            rows.append((str(widget), f"menu:{index}", label))
    return rows


def _visible_strings(widget):
    rows = []
    if isinstance(widget, _TEXT_WIDGETS):
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

    if isinstance(widget, (tk.Menubutton, ttk.Menubutton)):
        rows.extend(_menu_visible_strings(widget))

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


def _english_leaks(win, *, context=""):
    visible = [(str(win), "title", str(win.title() or "").strip())]
    visible.extend(_visible_strings(win))
    leaks = [row for row in visible if row[2] and _ASCII_ALPHA.search(row[2])]
    print("CORNER_REGISTRY_CONTEXT", context)
    print("CORNER_REGISTRY_ASCII_LEAKS", leaks)
    return leaks


def test_corner_registry_user_visible_text_is_chinese_only():
    """Every rule projection must localize internal IDs without changing raw authority."""
    root, _app, designer = _open_designer()
    try:
        designer.relief_registry_button.invoke()
        _pump(root)
        win = designer.relief_registry_window
        assert win.winfo_exists()
        assert win.winfo_ismapped()

        all_leaks = []
        initial = _english_leaks(win, context="initial")
        if initial:
            all_leaks.append(("initial", initial))

        tree = designer.relief_registry_rule_tree
        children = tuple(tree.get_children())
        assert children, "截角資料庫應至少有一筆規則可驗證"
        for item_id in children:
            tree.selection_set(item_id)
            tree.event_generate("<<TreeviewSelect>>")
            _pump(root, 2)
            leaks = _english_leaks(win, context=f"rule:{item_id}")
            if leaks:
                all_leaks.append((f"rule:{item_id}", leaks))

        assert not all_leaks, (
            "截角資料庫使用者可見文字不得顯示英文字母；內部 enum/key/schema 可保留英文，"
            f"但 presentation boundary 必須中文化。all_leaks={all_leaks!r}"
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass
