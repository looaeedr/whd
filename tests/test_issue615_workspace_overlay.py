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

        # Initial Phase6 presentation is Assembly. Enter a real part first so
        # unlocking exercises Settings, then switch back to Assembly to exercise
        # Diagnostics through the same overlay host.
        app.activate_part("head")
        root.update_idletasks()
        root.update()

        if bool(getattr(app, "_phase6_parameters_unlocked", False)):
            bridge._phase6_toggle_parameter_panel(app)
            root.update_idletasks()
            root.update()

        canvas = app.renderer.canvas.get_tk_widget()
        baseline_size = (canvas.winfo_width(), canvas.winfo_height())

        bridge._phase6_toggle_parameter_panel(app)
        root.update_idletasks()
        root.update()
        assert settings.winfo_manager()
        assert not diagnostics.winfo_manager()
        assert overlay.winfo_manager() == "place"
        assert (canvas.winfo_width(), canvas.winfo_height()) == baseline_size, (
            "UI-R2 RED: opening Settings reduced the allocated renderer viewport"
        )

        scroll_canvas = app.settings_panel.settings_scroll_canvas
        bbox = scroll_canvas.bbox("all")
        assert bbox is not None
        assert int(bbox[3] - bbox[1]) > int(scroll_canvas.winfo_height()) > 0
        before_scroll = tuple(float(v) for v in scroll_canvas.yview())
        scroll_canvas.yview_moveto(1.0)
        root.update_idletasks()
        root.update()
        after_scroll = tuple(float(v) for v in scroll_canvas.yview())
        assert after_scroll != before_scroll, (
            "UI-R2: Settings overlay must preserve real scroll interaction"
        )

        def descendants(widget):
            result = []
            for child in widget.winfo_children():
                result.append(child)
                result.extend(descendants(child))
            return result

        settings_focus = app.save_settings_button
        settings_focus.focus_force()
        root.update_idletasks()
        root.update()
        assert root.focus_get() is settings_focus
        sx = settings_focus.winfo_rootx() + max(1, settings_focus.winfo_width() // 2)
        sy = settings_focus.winfo_rooty() + max(1, settings_focus.winfo_height() // 2)
        assert root.winfo_containing(sx, sy) is settings_focus, (
            "UI-R2: Settings overlay must receive hit-tests above the renderer"
        )

        bridge._phase6_show_assembly(app)
        root.update_idletasks()
        root.update()
        assert not settings.winfo_manager()
        assert diagnostics.winfo_manager()
        assert overlay.winfo_manager() == "place"
        assert (canvas.winfo_width(), canvas.winfo_height()) == baseline_size, (
            "UI-R2 RED: switching to Diagnostics reduced the allocated renderer viewport"
        )

        diagnostic_entry = app.assembly_relief_clearance_entry
        diagnostic_entry.focus_force()
        root.update_idletasks()
        root.update()
        assert root.focus_get() is diagnostic_entry
        dx = diagnostic_entry.winfo_rootx() + max(1, diagnostic_entry.winfo_width() // 2)
        dy = diagnostic_entry.winfo_rooty() + max(1, diagnostic_entry.winfo_height() // 2)
        assert root.winfo_containing(dx, dy) is diagnostic_entry, (
            "UI-R2: Diagnostics overlay must receive hit-tests above the renderer"
        )
    finally:
        root.destroy()
