# -*- coding: utf-8 -*-
"""Tk-only navigation projection for Fold Designer.

This owner renders already-authoritative workspace/navigation state into the
Structure Tree and the hidden BoxBody compatibility Notebook. It never mutates
workspace topology, manufacturing state, geometry, persistence, or selection
authority.
"""
from __future__ import annotations

from typing import Callable, Iterable


def refresh_structure_tree(
    host,
    *,
    project_rows: Callable[[Iterable[object]], tuple[tuple[str, str | None], ...]],
    label_for_key: Callable[..., str],
    visibility_var: Callable[[str], object | None],
):
    """Rebuild the Structure Tree from authoritative identities only."""
    tree = getattr(host, "structure_tree", None)
    if tree is None:
        return ()
    if bool(getattr(host, "_phase6_structure_tree_guard", False)):
        return ()

    host._phase6_structure_tree_guard = True
    try:
        roots = tuple(tree.get_children(""))
        if roots:
            tree.delete(*roots)
        tree.insert("", "end", iid="mode:assembly", text="組合體", values=("",), open=True)
        tree.insert("", "end", iid="mode:corner_data", text="截角資料", values=("",), open=True)

        workspace = getattr(host, "designer_workspace", None)
        available_parts = tuple(getattr(workspace, "available_parts", ()) or ())
        snapshot = dict(getattr(host, "_phase6_input_snapshot", {}) or {})
        rows = tuple(project_rows(available_parts))
        for key, parent_key in rows:
            iid = f"part:{key}"
            parent_iid = f"part:{parent_key}" if parent_key else ""
            var = visibility_var(key)
            visible = True if var is None else bool(var.get())
            tree.insert(
                parent_iid,
                "end",
                iid=iid,
                text=label_for_key(key, snapshot=snapshot),
                values=("顯示" if visible else "隱藏",),
                tags=(() if visible else ("hidden",)),
                open=(key == "box_body"),
            )

        mode = str(getattr(host, "_phase6_3d_display_mode", "assembly") or "assembly")
        active = str(getattr(workspace, "active_part", "") or "")
        selected_iid = (
            "mode:assembly" if mode == "assembly"
            else "mode:corner_data" if mode == "corner_data"
            else f"part:{active}" if active else ""
        )
        if selected_iid and tree.exists(selected_iid):
            host._phase6_structure_tree_programmatic_iid = selected_iid
            tree.selection_set(selected_iid)
            tree.focus(selected_iid)
            tree.see(selected_iid)
        return rows
    finally:
        # Treeview posts <<TreeviewSelect>> asynchronously. Keep the guard alive
        # until Tk drains the programmatic selection event.
        try:
            tree.after_idle(
                lambda: setattr(host, "_phase6_structure_tree_guard", False)
            )
        except Exception:
            host._phase6_structure_tree_guard = False


def refresh_box_body_piece_selector(
    host,
    *,
    piece_keys: Callable[[Iterable[object]], tuple[str, ...]],
    label_for_key: Callable[[str], str],
    frame_factory: Callable[[object], object],
    resolve_remembered: Callable[[Iterable[object], str | None], object],
):
    """Project BoxBody physical children into the hidden compatibility Notebook."""
    notebook = getattr(host, "box_body_piece_selector", None)
    if notebook is None:
        return ()

    workspace = getattr(host, "designer_workspace", None)
    available_parts = tuple(getattr(workspace, "available_parts", ()) or ())
    wanted = tuple(piece_keys(available_parts))
    current = tuple(getattr(host, "_phase6_box_body_piece_tab_keys", ()) or ())
    if current != wanted:
        host._phase6_box_body_piece_tab_guard = True
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
            for key in wanted:
                frame = frame_factory(notebook)
                notebook.add(frame, text=label_for_key(key))
                tab_map[str(frame)] = key
            host._phase6_box_body_piece_tab_map = tab_map
            host._phase6_box_body_piece_tab_keys = wanted
        finally:
            host._phase6_box_body_piece_tab_guard = False

    active = str(getattr(workspace, "active_part", "") or "")
    remembered = str(getattr(host, "_phase6_box_body_active_piece_key", "") or "")
    if active in wanted:
        desired = active
        host._phase6_box_body_active_piece_key = active
    else:
        projection = resolve_remembered(available_parts, remembered or None)
        desired = str(getattr(projection, "resolved_key", "") or "")
        memory = getattr(projection, "memory", None)
        host._phase6_box_body_active_piece_key = getattr(
            memory, "remembered_box_body_child", None
        )

    if desired:
        tab_map = dict(getattr(host, "_phase6_box_body_piece_tab_map", {}) or {})
        target_tab = next(
            (tab_id for tab_id in notebook.tabs() if tab_map.get(str(tab_id)) == desired),
            None,
        )
        if target_tab is not None and str(notebook.select()) != str(target_tab):
            host._phase6_box_body_piece_tab_guard = True
            try:
                notebook.select(target_tab)
            finally:
                host._phase6_box_body_piece_tab_guard = False

    # #124: the Notebook is compatibility state only; Structure Tree is the sole
    # visible physical-child navigator.
    if notebook.winfo_manager():
        notebook.pack_forget()
    return wanted
