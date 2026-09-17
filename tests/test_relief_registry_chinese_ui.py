import os
import re
import tkinter as tk

import pytest

import gui


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="relief registry UI requires real Tk/Xvfb"
)

_ASCII_LETTER = re.compile(r"[A-Za-z]")


def _open_registry():
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    root.update_idletasks()
    root.update()
    designer.relief_registry_button.invoke()
    root.update_idletasks()
    root.update()
    return root, designer, designer.relief_registry_window


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _visible_presentation_strings(window):
    strings = [("視窗標題", str(window.title()))]
    for widget in _walk(window):
        cls = widget.winfo_class()
        try:
            text = str(widget.cget("text"))
        except tk.TclError:
            text = ""
        if text:
            strings.append((f"{cls}:text", text))

        if isinstance(widget, (tk.Entry,)) or cls in {"TEntry"}:
            try:
                value = str(widget.get())
            except (tk.TclError, AttributeError):
                value = ""
            if value:
                strings.append((f"{cls}:value", value))

        if cls == "TNotebook":
            for tab_id in widget.tabs():
                strings.append(("分頁", str(widget.tab(tab_id, "text"))))

        if cls == "Treeview":
            for column in ("#0",) + tuple(widget["columns"]):
                try:
                    heading = str(widget.heading(column, "text"))
                except tk.TclError:
                    heading = ""
                if heading:
                    strings.append(("表格標題", heading))
            stack = list(widget.get_children(""))
            while stack:
                item = stack.pop()
                item_text = str(widget.item(item, "text"))
                if item_text:
                    strings.append(("表格文字", item_text))
                for value in widget.item(item, "values"):
                    if str(value):
                        strings.append(("表格內容", str(value)))
                stack.extend(widget.get_children(item))

        if cls == "Menu":
            end = widget.index("end")
            if end is not None:
                for index in range(end + 1):
                    try:
                        label = str(widget.entrycget(index, "label"))
                    except tk.TclError:
                        label = ""
                    if label:
                        strings.append(("選單", label))
    return strings


def test_relief_registry_operator_presentation_contains_no_ascii_english():
    root, _designer, window = _open_registry()
    try:
        strings = _visible_presentation_strings(window)
        offenders = [(where, text) for where, text in strings if _ASCII_LETTER.search(text)]
        assert not offenders, "截角資料庫使用者可見文字含英文：\n" + "\n".join(
            f"{where}: {text}" for where, text in offenders
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass
