"""Box-body physical-subtab presentation and event routing."""

import tkinter as tk
from tkinter import ttk


def build_box_body_piece_selector(host, parent):
    """Build the transient physical-piece selector; host remains routing owner."""
    notebook = ttk.Notebook(parent, height=1)
    notebook.bind("<<NotebookTabChanged>>", host._on_box_body_piece_2d_tab_changed)
    return notebook


def box_body_piece_label(part_key):
    return {
        "box_body:left_side": "左側板",
        "box_body:back": "後面板",
        "box_body:right_side": "右側板",
        "box_body:left": "左箱身",
        "box_body:middle": "中箱身",
        "box_body:right": "右箱身",
    }.get(str(part_key or ""), str(part_key or ""))


def box_body_piece_face_key(part_key):
    return {
        "box_body:left_side": "left",
        "box_body:back": "back",
        "box_body:right_side": "right",
    }.get(str(part_key or ""))


def refresh_box_body_piece_tabs_2d(host, render_data):
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    keys = tuple(
        f"box_body:{str(getattr(piece, 'role', '') or '').strip()}"
        for piece in pieces
        if str(getattr(piece, "role", "") or "").strip()
    )
    notebook = getattr(host, "box_body_piece_tabs", None)
    if notebook is None:
        return ""
    if len(keys) <= 1:
        if notebook.winfo_manager():
            notebook.pack_forget()
        host._box_body_piece_2d_tab_keys = keys
        return ""

    current = tuple(getattr(host, "_box_body_piece_2d_tab_keys", ()) or ())
    if current != keys:
        host._box_body_piece_2d_tab_guard = True
        try:
            for tab_id in tuple(notebook.tabs()):
                try:
                    widget = host.root.nametowidget(tab_id)
                except Exception:
                    widget = None
                notebook.forget(tab_id)
                if widget is not None:
                    try:
                        widget.destroy()
                    except Exception:
                        pass
            tab_map = {}
            for key in keys:
                frame = ttk.Frame(notebook)
                notebook.add(frame, text=box_body_piece_label(key))
                tab_map[str(frame)] = key
            host._box_body_piece_2d_tab_map = tab_map
            host._box_body_piece_2d_tab_keys = keys
        finally:
            host._box_body_piece_2d_tab_guard = False

    selected = str(host.box_body_piece_2d_selected_var.get() or "")
    desired = selected if selected in keys else (
        "box_body:back" if "box_body:back" in keys else keys[0]
    )
    if selected != desired:
        host.box_body_piece_2d_selected_var.set(desired)
    tab_map = dict(getattr(host, "_box_body_piece_2d_tab_map", {}) or {})
    target = next(
        (tab_id for tab_id in notebook.tabs() if tab_map.get(str(tab_id)) == desired),
        None,
    )
    if target is not None and str(notebook.select()) != str(target):
        host._box_body_piece_2d_tab_guard = True
        try:
            notebook.select(target)
        finally:
            host._box_body_piece_2d_tab_guard = False
    if not notebook.winfo_manager():
        notebook.pack(
            fill=tk.X, padx=10, pady=(0, 2),
            before=host.box_body_canvas_frame,
        )
    face_key = box_body_piece_face_key(desired)
    if face_key is not None:
        host.box_body_face_selected_var.set(face_key)
    return desired


def on_box_body_piece_2d_tab_changed(host, _event=None):
    if bool(getattr(host, "_box_body_piece_2d_tab_guard", False)):
        return None
    notebook = getattr(host, "box_body_piece_tabs", None)
    if notebook is None:
        return None
    key = dict(getattr(host, "_box_body_piece_2d_tab_map", {}) or {}).get(
        str(notebook.select())
    )
    if not key:
        return None
    host.box_body_piece_2d_selected_var.set(key)
    face_key = box_body_piece_face_key(key)
    if face_key is not None:
        host.box_body_face_selected_var.set(face_key)
    host.draw_preview()
    return None


def on_box_body_piece_double_click(host, _event=None):
    piece_var = getattr(host, "box_body_piece_2d_selected_var", None)
    key = str(piece_var.get() if piece_var is not None else "")
    face_key = box_body_piece_face_key(key)
    if face_key is None:
        return None
    host.open_box_body_face_editor(face_key)
    return "break"
