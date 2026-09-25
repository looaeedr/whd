# -*- coding: utf-8 -*-
"""Issue #615 / B2 UI-R2 requirement RED for the viewport overlay seam."""
from __future__ import annotations

import os
import tkinter as tk

import pytest


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="#615 UI-R2 requires a real Tk/Xvfb display",
)
def test_ui_r2_settings_and_diagnostics_share_overlay_without_shrinking_viewport():
    import fold_designer_bridge as bridge

    snapshot = {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    }
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, snapshot)
    try:
        for _ in range(3):
            root.update_idletasks()
            root.update()

        overlay = getattr(app, "viewport_overlay_host", None)
        assert overlay is not None, (
            "UI-R2 RED: WorkspaceShell has no single viewport overlay host "
            "for Settings/Diagnostics"
        )

        settings = getattr(app, "settings_center", None)
        diagnostics = getattr(app, "assembly_diagnostics_frame", None)
        assert settings is not None
        assert diagnostics is not None
        assert settings.master is overlay, (
            "UI-R2 RED: Settings is not mounted in the WorkspaceShell overlay host"
        )
        assert diagnostics.master is overlay, (
            "UI-R2 RED: Diagnostics is not mounted in the same WorkspaceShell overlay host"
        )

        canvas = app.renderer.canvas.get_tk_widget()
        root.update_idletasks()
        root.update()
        baseline_size = (canvas.winfo_width(), canvas.winfo_height())

        if bool(getattr(app, "_phase6_parameters_unlocked", False)):
            bridge._phase6_toggle_parameter_panel(app)
            root.update_idletasks()
            root.update()

        bridge._phase6_toggle_parameter_panel(app)
        root.update_idletasks()
        root.update()
        assert settings.winfo_manager()
        assert not diagnostics.winfo_manager()
        assert (canvas.winfo_width(), canvas.winfo_height()) == baseline_size, (
            "UI-R2 RED: opening Settings reduced the allocated renderer viewport"
        )

        bridge._phase6_show_assembly(app)
        root.update_idletasks()
        root.update()
        assert not settings.winfo_manager()
        assert diagnostics.winfo_manager()
        assert (canvas.winfo_width(), canvas.winfo_height()) == baseline_size, (
            "UI-R2 RED: switching to Diagnostics reduced the allocated renderer viewport"
        )
    finally:
        root.destroy()
