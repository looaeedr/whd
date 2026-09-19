# -*- coding: utf-8 -*-
import os
import tkinter as tk

import pytest

import gui


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#398 requires real Tk/Xvfb"
)


def _pump(root, cycles=3):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def test_fresh_application_defaults_baseline_model_to_vault_everywhere():
    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        _pump(root)

        assert app.baseline_var.get() == "金庫型"

        snapshot = app._make_original_fold_designer_snapshot()
        assert snapshot["model"] == "金庫型"
        assert "金庫型" in tuple(snapshot["baseline_models"])

        designer = app.open_original_fold_designer()
        _pump(root)

        assert designer.baseline_model_var.get() == "金庫型"
        assert designer._phase6_input_snapshot["model"] == "金庫型"
    finally:
        try:
            if getattr(app, "fold_designer_window", None) is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_primary_python_gui_launch_defaults_baseline_model_to_vault():
    root = tk.Tk()
    root.geometry("1200x800+0+0")
    app = gui.Phase6PrimaryApplication(root)
    try:
        _pump(root)

        assert app.baseline_var.get() == "金庫型"
        assert app._active_cabinet_type == "金庫型"

        snapshot = app._make_original_fold_designer_snapshot()
        assert snapshot["model"] == "金庫型"

        designer = app.fold_designer_app
        assert designer.baseline_model_var.get() == "金庫型"
        assert designer._phase6_input_snapshot["model"] == "金庫型"
    finally:
        root.destroy()
