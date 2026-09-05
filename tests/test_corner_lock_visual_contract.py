from __future__ import annotations

import os
import tkinter as tk

import pytest

import gui


def _require_display():
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")


def _select_head(app, root):
    app.notebook.select(app.tab_head)
    app.refresh_corner_type_panel()
    root.update_idletasks(); root.update()


def test_main_locked_corner_ui_shows_lock_and_collapses_detail_area():
    _require_display()
    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        _select_head(app, root)
        assert app.manual_corner_param_lock_button.winfo_manager() == "pack"
        assert "鎖定" in app.manual_corner_param_lock_button.cget("text")
        # Fine-detail editor must consume zero layout space while locked.
        assert app.manual_corner_param_frame.winfo_manager() == ""
        # Pair-symmetry toggles are part of advanced editing and must also collapse.
        assert all(cb.winfo_manager() == "" for cb in app.manual_corner_pair_same_checkbuttons.values())

        app.toggle_manual_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert "解鎖" in app.manual_corner_param_lock_button.cget("text")
        assert app.manual_corner_param_frame.winfo_manager() == "pack"
        assert all(cb.winfo_manager() == "pack" for cb in app.manual_corner_pair_same_checkbuttons.values())
    finally:
        root.destroy()


def test_3d_locked_corner_ui_shows_lock_collapses_detail_and_has_global_project_toolbar():
    _require_display()
    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()

        assert designer.corner_param_lock_button is None  # per-corner lock was retired
        assert designer.parameter_lock_button is not None
        assert "鎖定" in designer.parameter_lock_button.cget("text")
        # Locked 3D keeps only the fixed summary; advanced corner widgets are built on unlock.
        assert designer.corner_detail_frames == {}
        assert all(var_widget.winfo_manager() == "" for var_widget in designer.corner_pair_checkbuttons.values())

        assert designer.project_toolbar.winfo_manager() == "pack"
        assert designer.project_file_button.cget("text") == "檔案 ▼"
        labels = [designer.project_file_menu.entrycget(i, "label") for i in range(designer.project_file_menu.index("end") + 1)]
        assert labels == ["開啟", "儲存", "另存新檔"]

        designer.toggle_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert "解鎖" in designer.parameter_lock_button.cget("text")
        assert any(frame.winfo_manager() == "grid" for frame in designer.corner_detail_frames.values())
        assert all(var_widget.winfo_manager() == "pack" for var_widget in designer.corner_pair_checkbuttons.values())
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()

def test_3d_global_save_as_then_save_reuses_same_project_path(tmp_path, monkeypatch):
    _require_display()
    import tkinter.filedialog as filedialog
    import phase6_project_file as project

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()

        target = tmp_path / "global-from-3d.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kwargs: str(target))
        saved = designer.save_project_file_as()
        assert saved == str(target)
        assert target.exists()
        assert app._phase6_loaded_project_path == str(target)
        payload = project.read_project(target)
        assert payload["snapshot"]["active_part"] == "head"
        assert "_runtime_project_path" not in payload["snapshot"]

        # Save must reuse current path without prompting again.
        monkeypatch.setattr(
            filedialog,
            "asksaveasfilename",
            lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Save should reuse current path")),
        )
        saved_again = designer.save_project_file()
        assert saved_again == str(target)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
