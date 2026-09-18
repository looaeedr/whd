"""Part-presence presentation with no authoritative state ownership."""

import tkinter as tk


def refresh_presence_ui(host, supplied_parts=None):
    """Project authoritative physical presence into legacy result/output controls."""
    present = set(supplied_parts) if supplied_parts is not None else host._phase6_current_existing_parts()
    present.add("box_body")

    result_groups = getattr(host, "_phase6_result_part_rows", {}) or {}
    visibility = {
        "box_body": host._phase6_logical_part_present(present, "box_body"),
        "endcap": bool({"head", "tail"} & present),
        "door": host._phase6_logical_part_present(present, "door"),
        "base_plate": host._phase6_logical_part_present(present, "base_plate"),
        "indicator_box": "indicator_box" in present,
        "indicator_door": "indicator_door" in present,
    }
    for group in ("box_body", "endcap", "door", "base_plate", "indicator_box", "indicator_door"):
        for row in result_groups.get(group, ()):
            row.pack_forget()
            if visibility[group]:
                row.pack(fill=tk.X, pady=6, padx=10)

    output_widgets = getattr(host, "_phase6_output_part_widgets", {}) or {}
    output_order = (
        "box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door"
    )
    for widget in output_widgets.values():
        widget.pack_forget()
    visible_keys = [
        key for key in output_order
        if host._phase6_logical_part_present(present, key) and key in output_widgets
    ]
    for index, key in enumerate(visible_keys):
        pady = (6, 1) if index == 0 else (
            (1, 6) if index == len(visible_keys) - 1 else (1, 1)
        )
        output_widgets[key].pack(anchor=tk.W, padx=10, pady=pady)

    if not visibility["endcap"]:
        host.result_y_w_var.set("-"); host.result_y_d_var.set("-")
    if not visibility["door"]:
        host.result_door_w_var.set("-"); host.result_door_h_var.set("-")
    if not visibility["base_plate"]:
        host.result_base_plate_w_var.set("-"); host.result_base_plate_h_var.set("-")
    if not visibility["indicator_box"]:
        host.result_ib_w_var.set("-"); host.result_ib_h_var.set("-")
    if not visibility["indicator_door"]:
        host.result_ib_door_w_var.set("-"); host.result_ib_door_h_var.set("-")
    return present
