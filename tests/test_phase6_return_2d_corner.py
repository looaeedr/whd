from pathlib import Path

import pytest


def test_loaded_project_opens_head_2d_in_fold_designer_corner_data(tmp_path):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from phase6_project_file import PROJECT_SCHEMA, write_project

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        snapshot = app._make_original_fold_designer_snapshot()
        snapshot.update({"model": "自訂", "active_part": "head", "w": 400.0, "h": 600.0, "d": 250.0})
        snapshot["settings"] = dict(snapshot.get("settings") or {})
        snapshot["settings"].update({"w": 400.0, "h": 600.0, "d": 250.0})
        snapshot["workspace"] = {
            "box_body_profile": snapshot.get("box_body_profile") or [],
            "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
            "active_part": "head",
            "part_profiles": snapshot.get("part_profiles", {}),
            "endcap_fw": snapshot.get("endcap_fw", {}),
        }
        snapshot["existing_parts"] = list(snapshot["workspace"]["existing_parts"])
        path = write_project(
            tmp_path / "corner-data-2d.p6fold",
            {"schema": PROJECT_SCHEMA, "saved_at": "now", "snapshot": snapshot, "final_geometry": {}},
        )

        designer = app.load_phase6_project(path, open_designer=True)
        for _ in range(4):
            root.update_idletasks(); root.update()

        bridge._phase6_show_corner_data(designer)
        selected = bridge._phase6_select_corner_data_part(designer, "head")
        for _ in range(2):
            root.update_idletasks(); root.update()

        assert selected == "head"
        assert designer._phase6_3d_display_mode == "corner_data"
        assert designer.part_var.get() == "截角資料"
        assert designer._phase6_corner_data_selected_part_key == "head"
        assert designer.corner_data_canvas is not None
        assert app.fold_designer_window is not None
        assert app.fold_designer_app is designer

        # T7 retired the standalone Notebook and the return-to-legacy-2D path.
        # The same 2D capability must remain inside Fold Designer instead.
        assert not hasattr(app, "notebook")
        assert not hasattr(bridge, "_phase6_return_to_2d_corner")
        assert not hasattr(designer, "return_2d_button")
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
