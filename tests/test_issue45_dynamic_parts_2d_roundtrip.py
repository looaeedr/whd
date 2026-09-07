from __future__ import annotations

import os
import pytest

import fold_designer_bridge as bridge


DYNAMIC_PARTS = (
    "box_body",
    "box_body:left_side",
    "box_body:back",
    "box_body:right_side",
    "head",
    "tail",
    "door_c1_r1",
    "door_c1_r2",
    "base_plate_c1_r1",
    "base_plate_c1_r2",
    "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1",
    "inner_door:upper:panel",
    "inner_door:upper:top_frame",
    "inner_door:upper:left_frame",
    "inner_door:upper:right_frame",
)


def test_r3_normalize_part_selection_preserves_authoritative_dynamic_ids():
    parts, active = bridge.normalize_part_selection(
        DYNAMIC_PARTS,
        active_part="door_c1_r2",
    )
    assert tuple(parts) == DYNAMIC_PARTS
    assert active == "door_c1_r2"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_r3_main_2d_keeps_dynamic_receiving_door_base_and_physical_ids_visible():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1200x900")
    app = gui.BoxCalculatorGUI(root)
    try:
        existing = app._apply_existing_parts_from_fold_workspace(DYNAMIC_PARTS)
        root.update_idletasks(); root.update()

        assert str(app.notebook.tab(app.tab_door, "state")) != "hidden"
        assert str(app.notebook.tab(app.tab_base_plate, "state")) != "hidden"

        current = app._phase6_current_existing_parts()
        for key in DYNAMIC_PARTS:
            assert key in current, (key, sorted(current))

        app.update_calculations()
        root.update_idletasks(); root.update()
        assert app.result_door_w_var.get() != "-"
        assert app.result_door_h_var.get() != "-"
        assert app.result_base_plate_w_var.get() != "-"
        assert app.result_base_plate_h_var.get() != "-"
        assert bool(app.export_door_var.get()) is True
        assert bool(app.export_base_plate_var.get()) is True
    finally:
        root.destroy()
