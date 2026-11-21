"""The 3D parameter lock opens a separate, scrollable Tk window."""

from __future__ import annotations

import os

import pytest


class _DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_parameter_unlock_uses_independent_window_and_reopens_after_close():
    if not os.environ.get("DISPLAY") and os.name != "nt":
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var = _DummyVar("金庫型")
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks()
        root.update()

        window = designer.parameter_settings_window
        center = designer.settings_center
        canvas = designer.renderer.canvas.get_tk_widget()
        assert isinstance(window, tk.Toplevel)
        assert center.master is window
        assert designer.assembly_diagnostics_frame.master is window
        assert not window.winfo_ismapped()
        assert not center.winfo_manager()
        original_parent = canvas.master

        designer.parameter_lock_button.invoke()
        root.update_idletasks()
        root.update()
        assert designer._phase6_parameters_unlocked is True
        assert window.winfo_ismapped()
        assert center.winfo_manager() == "pack"
        assert center.winfo_viewable()
        assert designer.settings_panel.settings_scroll_canvas.winfo_height() > 220
        assert canvas.master is original_parent
        assert canvas.winfo_manager() == "pack"

        # The OS title-bar X must close and re-lock, not destroy the editor.
        close_command = window.protocol("WM_DELETE_WINDOW")
        assert close_command
        window.tk.call(close_command)
        root.update()
        assert not designer._phase6_parameters_unlocked
        assert not window.winfo_ismapped()
        assert center.winfo_manager() == ""

        designer.parameter_lock_button.invoke()
        root.update_idletasks()
        root.update()
        assert window.winfo_ismapped()
        assert center.winfo_manager() == "pack"
        designer.parameter_settings_close_button.invoke()
        root.update()
        assert not designer._phase6_parameters_unlocked
        assert not window.winfo_ismapped()
        assert canvas.winfo_manager() == "pack"
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
