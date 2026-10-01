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


def on_structure_tree_select(
    host,
    *,
    show_assembly: Callable[[], object],
    show_corner_data: Callable[[], object],
    activate_part: Callable[[str], object],
    refresh_tree: Callable[[], object],
):
    """Translate one Treeview selection event into existing authority callbacks."""
    if bool(getattr(host, "_phase6_structure_tree_guard", False)):
        return None
    tree = getattr(host, "structure_tree", None)
    if tree is None:
        return None
    selected = tuple(tree.selection())
    if not selected:
        return None
    iid = str(selected[0])
    projected_iid = str(
        getattr(host, "_phase6_structure_tree_programmatic_iid", "") or ""
    )
    if projected_iid:
        host._phase6_structure_tree_programmatic_iid = ""
        if iid == projected_iid:
            return None
    if iid == "mode:assembly":
        show_assembly()
    elif iid == "mode:corner_data":
        show_corner_data()
    elif iid.startswith("part:"):
        activate_part(iid[5:])
    return refresh_tree()


def set_structure_tree_visibility(
    host,
    key,
    visible,
    *,
    visibility_var: Callable[[str], object | None],
    notify_visibility_changed: Callable[[], object] | None,
    refresh_tree: Callable[[], object],
) -> bool:
    """Project visibility intent through existing assembly-view authority callbacks."""
    part_key = str(key or "")
    var = visibility_var(part_key)
    if var is None:
        return False
    var.set(bool(visible))
    if callable(notify_visibility_changed):
        notify_visibility_changed()
    refresh_tree()
    return True


def on_box_body_piece_tab_changed(
    host,
    *,
    activate_part: Callable[[str], object],
    resolve_operator_part: Callable[[str], object],
):
    """Translate a visible compatibility-tab event without owning navigation state."""
    if bool(getattr(host, "_phase6_box_body_piece_tab_guard", False)):
        return None
    notebook = getattr(host, "box_body_piece_selector", None)
    if notebook is None or not notebook.winfo_manager():
        return None
    key = dict(getattr(host, "_phase6_box_body_piece_tab_map", {}) or {}).get(
        str(notebook.select())
    )
    if not key:
        return None
    workspace = getattr(host, "designer_workspace", None)
    if str(getattr(workspace, "active_part", "") or "") == key:
        return resolve_operator_part(key)
    return activate_part(key)


def refresh_sticky_structure_tree(host) -> None:
    """Hide legacy sticky Structure Tree hosts without owning layout authority."""
    for name in ("structure_tree_host", "structure_tree_spacer"):
        widget = getattr(host, name, None)
        if widget is None:
            continue
        try:
            manager = str(widget.winfo_manager() or "")
            if manager == "place":
                widget.place_forget()
            elif manager == "pack":
                widget.pack_forget()
            elif manager == "grid":
                widget.grid_remove()
        except Exception:
            return


def clear_navigation_residue(host) -> None:
    """Dismiss transient navigation menus before the visible content changes."""
    for name in ("part_choice_menu", "add_part_menu", "project_file_menu"):
        menu = getattr(host, name, None)
        if menu is None:
            continue
        try:
            menu.unpost()
        except Exception:
            pass


def refresh_content_switch(host) -> str:
    """Project the current display mode onto legacy compatibility button handles."""
    mode = str(getattr(host, "_phase6_3d_display_mode", "single") or "single")
    active = "assembly" if mode == "assembly" else "corner_data" if mode == "corner_data" else "input"
    mapping = {
        "input": getattr(host, "input_content_button", None),
        "assembly": getattr(host, "assembly_content_button", None),
        "corner_data": getattr(host, "corner_data_content_button", None),
    }
    for key, button in mapping.items():
        if button is None:
            continue
        try:
            button.state(["pressed"] if key == active else ["!pressed"])
        except Exception:
            pass
    return active


def build_content_switch(host, *, frame_factory: Callable[[object], object]):
    """Create compatibility handles without adding a duplicate visible navigator."""
    host.content_switch_frame = frame_factory(host.left)
    host.input_content_button = None
    host.assembly_content_button = None
    host.corner_data_content_button = None
    refresh_content_switch(host)
    return host.content_switch_frame


def on_structure_tree_click(
    host,
    event,
    *,
    visibility_var: Callable[[str], object | None],
    set_visibility: Callable[[str, bool], object],
):
    """Translate a Structure Tree visibility-column click into existing view authority."""
    tree = getattr(host, "structure_tree", None)
    if tree is None or tree.identify_column(event.x) != "#1":
        return None
    iid = str(tree.identify_row(event.y) or "")
    if not iid.startswith("part:"):
        return "break"
    key = iid[5:]
    var = visibility_var(key)
    if var is None:
        return "break"
    set_visibility(key, not bool(var.get()))
    return "break"


def refresh_part_selector(
    host,
    *,
    tk_end,
    operator_selector_keys: Callable[[Iterable[object]], tuple[str, ...]],
    label_for_key: Callable[..., str],
    is_box_piece: Callable[[object], bool],
    show_assembly: Callable[[], object],
    show_corner_data: Callable[[], object],
    activate_part: Callable[[str], object],
    refresh_button_states: Callable[[], object],
    refresh_piece_selector: Callable[[], object],
    refresh_back_panel: Callable[[], object],
    refresh_assembly_panel: Callable[[], object] | None,
    refresh_structure_tree: Callable[[], object],
    refresh_content_switch: Callable[[], object],
    refresh_status_bar: Callable[[], object],
):
    """Project current operator navigation identities into the compact part menu."""
    host.part_buttons = {}
    snapshot = dict(getattr(host, "_phase6_input_snapshot", {}) or {})
    menu = getattr(host, "part_choice_menu", None)
    if menu is not None:
        menu.delete(0, tk_end)
        menu.add_radiobutton(
            label="組合體", variable=host.part_var, value="組合體", command=show_assembly
        )
        for key in operator_selector_keys(getattr(host, "available_parts", ())):
            label = label_for_key(key, snapshot=snapshot)
            menu.add_radiobutton(
                label=label, variable=host.part_var, value=label,
                command=lambda k=key: activate_part(k),
            )
        menu.add_radiobutton(
            label="截角資料", variable=host.part_var, value="截角資料", command=show_corner_data
        )

    active = getattr(host, "active_part_key", None)
    if hasattr(host, "part_var"):
        mode = str(getattr(host, "_phase6_3d_display_mode", "single") or "single")
        if mode == "assembly":
            host.part_var.set("組合體")
        elif mode == "corner_data":
            host.part_var.set("截角資料")
        elif is_box_piece(active):
            host.part_var.set(label_for_key("box_body", snapshot=snapshot))
        elif active in getattr(host, "available_parts", ()):
            host.part_var.set(label_for_key(active, snapshot=snapshot))

    refresh_button_states()
    refresh_piece_selector()
    refresh_back_panel()
    if callable(refresh_assembly_panel):
        refresh_assembly_panel()
    refresh_structure_tree()
    refresh_content_switch()
    refresh_status_bar()


def refresh_part_button_states(
    host,
    *,
    is_derived_part: Callable[[object], bool],
) -> None:
    """Project selection eligibility into legacy remove-button state."""
    selected = getattr(host, "selected_part_key", None)
    for button in getattr(host, "part_buttons", {}).values():
        button.state(["!disabled"])
    delete = getattr(host, "remove_part_button", None)
    if delete is not None:
        available = tuple(getattr(host, "available_parts", ()) or ())
        enabled = selected in available and selected != "box_body" and not is_derived_part(selected)
        delete.configure(state=("normal" if enabled else "disabled"))


def refresh_add_part_menu(
    host,
    *,
    tk_end,
    known_parts: Iterable[str],
    label_for_key: Callable[[str], str],
    add_part: Callable[[str], object],
) -> None:
    """Project missing legacy top-level parts into the add-part menu."""
    menu = host.add_part_menu
    menu.delete(0, tk_end)
    available = tuple(getattr(host, "available_parts", ()) or ())
    missing = [key for key in known_parts if key not in available]
    if not missing:
        menu.add_command(label="沒有可新增板件", state="disabled")
        return
    for key in missing:
        menu.add_command(label=label_for_key(key), command=lambda k=key: add_part(k))

def hide_corner_data_canvas(host, *, visibility_plan, tk_both):
    """Project Corner Data/Matplotlib visibility without owning geometry state."""
    plan = dict(visibility_plan or {})
    info_label = getattr(host, "corner_data_info_label", None)
    if info_label is not None and not bool(plan.get("info_label", False)):
        try:
            if info_label.winfo_manager():
                info_label.pack_forget()
        except Exception:
            pass
    canvas = getattr(host, "corner_data_canvas", None)
    if canvas is not None and not bool(plan.get("corner_canvas", False)):
        try:
            if canvas.winfo_manager():
                canvas.pack_forget()
        except Exception:
            pass
    renderer = getattr(host, "renderer", None)
    mpl_canvas = getattr(renderer, "canvas", None)
    get_widget = getattr(mpl_canvas, "get_tk_widget", None)
    if not callable(get_widget):
        return None
    mpl_widget = get_widget()
    if bool(plan.get("mpl_canvas", False)) and not mpl_widget.winfo_manager():
        mpl_widget.pack(fill=tk_both, expand=True)
    return mpl_widget


def show_corner_data_mode(
    host,
    *,
    frame_factory: Callable[[object], object],
    mount_shared_content: Callable[[str], object],
    prepare_canvas: Callable[[], object],
    refresh_parts_panel: Callable[[], object],
    refresh_unfold: Callable[[], object],
    refresh_part_button_states: Callable[[], object] | None,
    refresh_content_switch: Callable[[], object],
):
    """Project the view-only Corner Data mode; no workspace mutation is owned here."""
    clear_navigation_residue(host)
    host._phase6_3d_display_mode = "corner_data"
    part_var = getattr(host, "part_var", None)
    if part_var is not None:
        part_var.set("截角資料")
    piece_selector = getattr(host, "box_body_piece_selector", None)
    if piece_selector is not None and hasattr(piece_selector, "pack_forget"):
        try:
            piece_selector.pack_forget()
        except Exception:
            pass
    panel = getattr(host, "corner_data_panel", None)
    if panel is None:
        shared_host = getattr(host, "left", None)
        if shared_host is None:
            return None
        panel = frame_factory(shared_host)
        host.corner_data_panel = panel
    mount_shared_content("corner_data")
    corner_canvas = prepare_canvas()
    refresh_parts_panel()
    if corner_canvas is not None:
        refresh_unfold()
    if callable(refresh_part_button_states):
        refresh_part_button_states()
    refresh_content_switch()
    return None


def project_assembly_mode(
    host,
    *,
    mount_shared_content: Callable[[str], object],
    pack_right_panel: Callable[[object], object],
    clear_drawing_edge_controls: Callable[[], object],
    tk_both,
) -> None:
    """Project assembly-mode widgets after Bridge completes authoritative state work."""
    part_var = getattr(host, "part_var", None)
    if part_var is not None:
        part_var.set("組合體")
    piece_selector = getattr(host, "box_body_piece_selector", None)
    if piece_selector is not None and piece_selector.winfo_manager():
        piece_selector.pack_forget()
    mount_shared_content("assembly")
    center = getattr(host, "settings_center", None)
    if center is not None and center.winfo_manager():
        center.pack_forget()
    diagnostics = getattr(host, "assembly_diagnostics_frame", None)
    if diagnostics is not None:
        if bool(getattr(host, "_phase6_parameters_unlocked", False)):
            if not diagnostics.winfo_manager():
                pack_right_panel(diagnostics)
        elif diagnostics.winfo_manager():
            diagnostics.pack_forget()
    delete = getattr(host, "remove_part_button", None)
    if delete is not None:
        delete.configure(state="disabled")
    renderer = getattr(host, "renderer", None)
    mpl_canvas = getattr(renderer, "canvas", None)
    get_widget = getattr(mpl_canvas, "get_tk_widget", None)
    if callable(get_widget):
        canvas_widget = get_widget()
        if not canvas_widget.winfo_manager():
            canvas_widget.pack(fill=tk_both, expand=True)
    clear_drawing_edge_controls()
    host.endcap_joint_vars = {}
    host.endcap_joint_widgets = {}
    host.endcap_joint_allowed = {}
    host.base_plate_edge_shrink_vars = {}
    host.base_plate_edge_shrink_widgets = {}

def project_active_part_selector(
    host,
    *,
    key: str,
    label: str,
    removable: bool,
    refresh_part_button_states: Callable[[], object] | None,
) -> None:
    """Project active-part label/remove affordance without owning navigation state."""
    part_var = getattr(host, "part_var", None)
    if part_var is not None:
        part_var.set(label)
    if callable(refresh_part_button_states):
        refresh_part_button_states()
    remove = getattr(host, "remove_part_button", None)
    if remove is not None:
        remove.configure(state=("normal" if removable else "disabled"))


def finalize_single_part_layout(
    host,
    *,
    settings_context: str,
    render_settings_context: Callable[[str], object],
    pack_right_panel: Callable[[object], object],
    render_active_drawing_edge_controls: Callable[[], object],
    tk_both,
) -> None:
    """Settle settings/canvas widgets after authoritative part activation completes."""
    center = getattr(host, "settings_center", None)
    if center is not None:
        render_settings_context(settings_context)
        if bool(getattr(host, "_phase6_parameters_unlocked", False)):
            if not center.winfo_manager():
                pack_right_panel(center)
        elif center.winfo_manager():
            center.pack_forget()

    renderer = getattr(host, "renderer", None)
    canvas = getattr(renderer, "canvas", None)
    if canvas is None:
        return
    pending_draw = getattr(canvas, "_idle_draw_id", None)
    if pending_draw is not None:
        try:
            host.root.after_cancel(pending_draw)
        except Exception:
            pass
        try:
            canvas._idle_draw_id = None
        except Exception:
            pass
    try:
        host.root.update_idletasks()
    except Exception:
        pass

    get_widget = getattr(canvas, "get_tk_widget", None)
    if callable(get_widget):
        canvas_widget = get_widget()
        if not canvas_widget.winfo_manager():
            canvas_widget.pack(fill=tk_both, expand=True)
    render_active_drawing_edge_controls()

    resize_draw_idle = getattr(canvas, "draw_idle", None)
    if callable(resize_draw_idle):
        canvas.draw_idle = lambda *args, **kwargs: None
    try:
        host.root.update_idletasks()
    except Exception:
        pass
    finally:
        if callable(resize_draw_idle):
            canvas.draw_idle = resize_draw_idle

