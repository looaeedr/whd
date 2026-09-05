from pathlib import Path

import pytest


def test_return_2d_after_loaded_project_closes_designer_cleanly(tmp_path):
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
            tmp_path / "return-2d.p6fold",
            {"schema": PROJECT_SCHEMA, "saved_at": "now", "snapshot": snapshot, "final_geometry": {}},
        )

        designer = app.load_phase6_project(path, open_designer=True)
        for _ in range(4):
            root.update_idletasks(); root.update()
        for key in designer.available_parts:
            designer.activate_part(key)
            root.update_idletasks(); root.update()
        bridge._phase6_show_assembly(designer)
        root.update_idletasks(); root.update()
        designer.activate_part("head")
        root.update_idletasks(); root.update()

        assert bridge._phase6_return_to_2d_corner(designer) is True
        root.update_idletasks(); root.update()
        assert app.fold_designer_window is None
        assert app.fold_designer_app is None
        assert "封頭" in app.notebook.tab(app.notebook.select(), "text")
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
