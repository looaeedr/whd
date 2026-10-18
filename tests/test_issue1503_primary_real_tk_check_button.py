# -*- coding: utf-8 -*-
"""#1503: primary uses ordinary DXF export; EAR debug tool is opt-in only."""
import tkinter as tk
from tkinter import ttk

import pytest
import gui
from gui_modules.application.receiving_ear_check_primary_entry import (
    mount_primary_receiving_ear_side_check,
)


def test_real_primary_3d_has_no_redundant_check_or_manufacturing_buttons():
    root = tk.Tk()
    try:
        root.geometry("1400x900+15+15")
        root.update()
        app = gui.Phase6PrimaryApplication(root)
        root.update()
        assert app._phase6_primary_workspace
        assert app._legacy_2d_compat_host is None
        assert app.fold_designer_app is not None
        assert not hasattr(app, "btn_ear_side_check_dxf")
        assert not hasattr(app, "btn_ear_side_mfg_dxf")
        assert not hasattr(app, "_receiving_ear_check_primary_group")
        assert callable(app.export_selected_dxf)
        assert callable(app.export_receiving_ear_side_check_dxf)
        assert callable(app.export_receiving_ear_side_manufacturing_dxf)
    finally:
        root.destroy()


def test_diagnostic_check_widget_requires_explicit_mount_only(monkeypatch):
    clicks = []
    monkeypatch.setattr(
        gui.Phase6PrimaryApplication,
        "export_receiving_ear_side_check_dxf",
        lambda host: clicks.append(host),
    )
    root = tk.Tk()
    try:
        app = gui.Phase6PrimaryApplication(root)
        root.update()
        assert not hasattr(app, "btn_ear_side_check_dxf")
        widget = mount_primary_receiving_ear_side_check(app)
        root.update()
        assert isinstance(widget, ttk.Button)
        assert widget.winfo_exists()
        assert widget.winfo_viewable()
        assert widget.master.master is app.fold_designer_app.left
        assert mount_primary_receiving_ear_side_check(app) is widget
        widget.invoke()
        assert clicks == [app]
    finally:
        root.destroy()


def test_explicit_debug_mount_requires_real_workspace():
    class Host:
        fold_designer_app = None
    with pytest.raises(ValueError, match="EAR_CHECK_PRIMARY_3D_WORKSPACE_MISSING"):
        mount_primary_receiving_ear_side_check(Host())
