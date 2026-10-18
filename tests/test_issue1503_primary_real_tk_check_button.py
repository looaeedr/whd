# -*- coding: utf-8 -*-
"""#1503: real Phase6PrimaryApplication must expose EAR CHECK in the live 3D UI."""
import tkinter as tk
from tkinter import ttk

import pytest

import gui
from gui_modules.application.receiving_ear_check_primary_entry import (
    mount_primary_receiving_ear_side_check,
)


def test_real_primary_3d_shows_check_only_action_and_click_routes_to_host(monkeypatch):
    clicks = []
    monkeypatch.setattr(
        gui.Phase6PrimaryApplication,
        "export_receiving_ear_side_check_dxf",
        lambda host: clicks.append(host),
    )
    root = tk.Tk()
    try:
        root.geometry("1400x900+15+15")
        root.update()
        app = gui.Phase6PrimaryApplication(root)
        root.update()
        assert app._phase6_primary_workspace
        assert app._legacy_2d_compat_host is None
        assert app.fold_designer_app is not None
        widget = app.btn_ear_side_check_dxf
        assert isinstance(widget, ttk.Button)
        assert widget.winfo_exists()
        assert widget.winfo_viewable()
        assert "CHECK DXF" in widget.cget("text")
        assert "非製造" in widget.cget("text")
        assert widget.master.master is app.fold_designer_app.left
        # The primary UI deliberately unpacks original.main_nb; CHECK must
        # be mounted among the ACTUAL packed controls, not that dead widget.
        assert app.fold_designer_app.main_nb.winfo_manager() != "pack"
        assert widget.master.winfo_manager() == "pack"
        packed = app.fold_designer_app.left.pack_slaves()
        assert widget.master in packed
        assert widget.master.winfo_viewable()
        assert mount_primary_receiving_ear_side_check(app) is widget
        widget.invoke()
        assert clicks == [app]
        assert not hasattr(app, "btn_export")
    finally:
        root.destroy()


def test_primary_mount_rejects_incomplete_designer_without_legacy_fallback():
    class Host:
        fold_designer_app = None
    with pytest.raises(ValueError, match="EAR_CHECK_PRIMARY_3D_WORKSPACE_MISSING"):
        mount_primary_receiving_ear_side_check(Host())
