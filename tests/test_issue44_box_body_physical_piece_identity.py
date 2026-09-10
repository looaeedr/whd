from __future__ import annotations

import os
import pytest


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_r4_receiving_corner_data_exposes_all_three_physical_box_body_pieces():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk()
    root.geometry("1200x900")
    app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("受電箱")
        app.on_baseline_changed()
        root.update_idletasks(); root.update()

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_corner_data(designer)
        root.update_idletasks(); root.update()

        keys = tuple(bridge._phase6_corner_data_part_keys(designer))
        physical = (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
        for key in physical:
            assert key in keys, (key, keys)
            assert bridge._phase6_select_corner_data_part(designer, key) == key
            projection = bridge._phase6_corner_data_unfold_projection(designer)
            assert projection is not None
            assert projection.part_key == key
            assert projection.render_data is not None

        assert not hasattr(app, "notebook")
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()
