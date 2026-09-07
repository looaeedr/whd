from __future__ import annotations

import os
import pytest


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_r4_receiving_main_2d_exposes_all_three_physical_box_body_pieces():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1200x900")
    app = gui.BoxCalculatorGUI(root)
    try:
        app.notebook.select(app.tab_z)
        root.update_idletasks(); root.update()
        app.baseline_var.set("受電箱")
        app.on_baseline_changed()
        root.update_idletasks(); root.update()

        app.notebook.select(app.tab_z)
        app.canvas_z.configure(width=900, height=650)
        root.update_idletasks(); root.update()
        assert app.canvas_z.winfo_width() > 1
        assert app.canvas_z.winfo_height() > 1
        app.draw_box_body(app.get_float_values())

        assert tuple(app.last_box_body_face_overview["piece_keys"]) == (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
    finally:
        root.destroy()
