"""Presentation-only canvas interaction routing for Door views.

The host remains the state owner.  This module only performs hit-testing,
event normalization, transient drag routing, and callback dispatch.
"""

import time
import tkinter as tk

from ae_engine.sheetmetal_geometry import Vec2


def door_layout_cell_at_canvas_point(bounds_by_key, x, y):
    """Return (column_index, row_index) for a point inside one visible cell."""
    for key, bounds in dict(bounds_by_key or {}).items():
        x1, y1, x2, y2 = bounds
        if x1 <= x <= x2 and y1 <= y <= y2:
            column_index, row_index = (int(part) for part in str(key).split(":", 1))
            return column_index, row_index
    return None


def on_door_canvas_press(host, event):
    if host.multi_door_enabled_var.get():
        hit = door_layout_cell_at_canvas_point(
            host.door_layout_cell_bounds, event.x, event.y
        )
        if hit is None:
            host._door_layout_last_click = None
            return "break"

        event_time = int(getattr(event, "time", 0) or 0)
        if not event_time:
            event_time = int(time.monotonic() * 1000)
        last = host._door_layout_last_click
        is_manual_double = False
        if last is not None:
            last_hit, last_time = last
            delta = event_time - last_time if event_time and last_time else 999999
            is_manual_double = last_hit == hit and 0 <= delta <= 650

        if is_manual_double:
            host._door_layout_last_click = None
            host.open_door_layout_cell_editor(*hit)
        else:
            host._door_layout_last_click = (hit, event_time)
            host.select_door_layout_cell(*hit)
        return "break"

    if (
        not host.is_door_indicator_var.get()
        or not hasattr(host, "last_door_draw_params")
    ):
        return None

    params = host.last_door_draw_params
    transform = params.get("transform")
    layout = params.get("indicator_layout")
    if transform is None or layout is None:
        return None

    world = transform.canvas_to_world(event.x, event.y)
    if layout.hit_test(world, padding=15.0):
        host.drag_active = True
        host.drag_start_world = world
        host.drag_start_offset_x = host.door_indicator_offset_x
        host.drag_start_offset_y = host.door_indicator_offset_y
    return None


def on_door_canvas_drag(host, event):
    if not host.drag_active:
        return None

    params = host.last_door_draw_params
    transform = params.get("transform")
    layout = params.get("indicator_layout")
    if transform is None or layout is None:
        return None

    world = transform.canvas_to_world(event.x, event.y)
    delta = world - host.drag_start_world
    desired = Vec2(
        host.drag_start_offset_x + delta.x,
        host.drag_start_offset_y + delta.y,
    )
    clamped = layout.clamp_offset(desired)
    host.door_indicator_offset_x = clamped.x
    host.door_indicator_offset_y = clamped.y
    host.draw_preview()
    return None


def on_door_canvas_release(host, event):
    host.drag_active = False
    return None


def on_door_canvas_double_click(host, event):
    if host.multi_door_enabled_var.get():
        hit = (
            door_layout_cell_at_canvas_point(
                host.door_layout_cell_bounds, event.x, event.y
            )
            if event is not None
            else None
        )
        if hit is not None:
            host.open_door_layout_cell_editor(*hit)
        return "break"

    host.open_part_hole_editor("door")
    return "break"



def box_body_face_at_canvas_point(bounds_by_face, x, y):
    for face_key, bounds in dict(bounds_by_face or {}).items():
        x1, y1, x2, y2 = bounds
        if x1 <= x <= x2 and y1 <= y <= y2:
            return face_key
    return None


def select_box_body_face(host, face_key):
    if face_key not in {"left", "back", "right"}:
        return None

    host.box_body_face_selected_var.set(face_key)
    for key in ("left", "back", "right"):
        try:
            host.canvas_z.itemconfigure(
                f"box_body_face_{key}",
                outline=(host.COLOR_ACCENT if key == face_key else "#30d158"),
                width=(3 if key == face_key else 2),
            )
        except tk.TclError:
            pass
    return None


def on_box_body_canvas_press(host, event):
    piece_var = getattr(host, "box_body_piece_2d_selected_var", None)
    piece_key = str(piece_var.get() if piece_var is not None else "")
    face_key = host._box_body_piece_face_key(piece_key)
    if face_key is not None:
        host.box_body_face_selected_var.set(face_key)
        return "break"

    hit = host._box_body_face_at_canvas_point(event.x, event.y)
    if hit is None:
        host._box_body_face_last_click = None
        return "break"

    event_time = int(getattr(event, "time", 0) or 0)
    if not event_time:
        event_time = int(time.monotonic() * 1000)

    last = host._box_body_face_last_click
    is_manual_double = False
    if last is not None:
        last_face, last_time = last
        delta = event_time - last_time if event_time and last_time else 999999
        is_manual_double = last_face == hit and 0 <= delta <= 650

    if is_manual_double:
        host._box_body_face_last_click = None
        host.open_box_body_face_editor(hit)
    else:
        host._box_body_face_last_click = (hit, event_time)
        host.select_box_body_face(hit)
    return "break"



def draw_preview(host):
    """Refresh only the visible authoritative Fold Designer corner-data view."""
    designer = getattr(host, "fold_designer_app", None)
    if designer is None:
        return None
    if str(getattr(designer, "_phase6_3d_display_mode", "") or "") != "corner_data":
        return None
    if getattr(designer, "corner_data_canvas", None) is None:
        return None
    refresh = getattr(designer, "_phase6_refresh_corner_data_unfold_view", None)
    return refresh() if callable(refresh) else None


def _refresh_box_body_after_hole_editor(host):
    """Refresh the owning view without reviving legacy canvas ownership."""
    if bool(getattr(host, "_phase6_primary_workspace", False)):
        return host.draw_preview()
    return host.draw_box_body(host.get_float_values())


def open_box_body_face_editor(
    host,
    face_key,
    *,
    messagebox_module,
    face_dimensions_fn,
    vertical_offsets_fn,
    surface_builder,
    guide_type,
    vec2_type,
    baseline_label_fn,
):
    if face_key not in {"left", "back", "right"}:
        messagebox_module.showerror("開孔失敗", f"未知箱身面: {face_key}")
        return None

    try:
        val = host.get_float_values()
    except ValueError as exc:
        messagebox_module.showerror("輸入錯誤", str(exc))
        return None

    dims = face_dimensions_fn(w=val["w"], h=val["h"], d=val["d"])
    width, height = dims[face_key]
    head_policy, tail_policy = host._box_body_corner_policies(val["fw"])
    bottom_outer, top_outer = vertical_offsets_fn(
        val["t"],
        head_corner_policy=head_policy,
        tail_corner_policy=tail_policy,
    )
    surface = surface_builder(
        f"box_body_{face_key}",
        vec2_type(val["t"], bottom_outer),
        vec2_type(width - val["t"], height - top_outer),
    )
    reference_guide = guide_type(
        vec2_type(0.0, 0.0),
        vec2_type(width, height),
        "enclosure_boundary",
    )
    title = {
        "left": "箱身左側",
        "back": "箱身背面",
        "right": "箱身右側",
    }[face_key]
    host.box_body_face_selected_var.set(face_key)
    return host._open_unified_hole_editor(
        f"box_body_{face_key}",
        title,
        surface,
        width,
        height,
        reference_guide=reference_guide,
        feature_list_override=host.box_body_face_features[face_key],
        baseline_scene=host._box_body_face_baseline_scene(face_key, val),
        baseline_status_text=baseline_label_fn(host.baseline_var.get()),
        on_close=lambda: _refresh_box_body_after_hole_editor(host),
    )
