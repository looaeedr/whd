from __future__ import annotations

import inspect
import os

import pytest


def test_main_gui_box_body_dimension_path_has_no_legacy_calculate_z_length():
    import gui

    source = inspect.getsource(gui.BoxCalculatorGUI.update_calculations)
    assert "calculate_z_length(" not in source, (
        "Main GUI Box Body dimension projection still owns the fixed-segment "
        "calculate_z_length fallback"
    )


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_main_result_uses_authoritative_1596_material_width():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        app.update_calculations()
        assert app.result_z_var.get() == "1596.00 mm"
        assert app.workspace_controller.box_body_profile()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
