from pathlib import Path
import tkinter as tk

import fold_designer_bridge as bridge
from test_phase6_settings_center_bridge import _snapshot


def _make_app(monkeypatch, **kwargs):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, _snapshot(), **kwargs)
    root.update_idletasks()
    return root, win, app


def test_top_bar_has_reset_but_no_confirm_or_cancel(monkeypatch):
    root, win, app = _make_app(monkeypatch, on_live_sync=lambda payload: None)
    try:
        assert hasattr(app, "reset_initial_button")
        assert not hasattr(app, "confirm_transaction_button")
        assert not hasattr(app, "cancel_transaction_button")
        texts = []
        for child in app.transaction_buttons.winfo_children():
            try:
                texts.append(str(child.cget("text")))
            except tk.TclError:
                pass
        assert "還原初始值" in texts
        assert "確定" not in texts
        assert "取消" not in texts
    finally:
        root.destroy()


def test_setting_edit_publishes_full_live_snapshot(monkeypatch):
    published = []
    root, win, app = _make_app(monkeypatch, on_live_sync=lambda payload: published.append(payload))
    try:
        app.left_global_vars["w"].set("640")
        app.flush_pending_settings()
        root.update_idletasks()
        assert published
        payload = published[-1]
        assert payload["settings"]["w"] == 640.0
        assert payload["workspace"]["existing_parts"]
        assert "corner_state" in payload
    finally:
        root.destroy()


def test_corner_change_notifier_publishes_immediately(monkeypatch):
    published = []
    snap = _snapshot()
    snap.update({
        "model": "未知類型",
        "baseline_models": ["金庫型", "未知類型"],
        "baseline_unknown_value": "未知類型",
        "corner_editable": True,
    })
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, snap, on_live_sync=lambda payload: published.append(payload))
    try:
        published.clear()
        app._phase6_corner_pair_same.setdefault("door", {})["top"] = False
        bridge._phase6_notify_corner_change(app)
        assert published
        assert published[-1]["corner_pair_same"]["door"]["top"] is False
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_main_gui_3d_open_path_has_no_project_draft_confirm_cancel():
    source = Path("gui.py").read_text(encoding="utf-8")
    start = source.index("    def open_original_fold_designer(self):")
    end = source.index("    def _apply_ui_text_size_preference", start)
    block = source[start:end]
    assert "begin_designer(" not in block
    assert "confirm_designer(" not in block
    assert "cancel_designer(" not in block
    assert "on_transaction_confirm=" not in block
    assert "on_transaction_cancel=" not in block
    assert "on_live_sync=" in block


def test_baseline_change_publishes_live(monkeypatch):
    published = []
    snap = _snapshot()
    snap.update({
        "model": "金庫型",
        "baseline_models": ["金庫型", "未知類型"],
        "baseline_unknown_value": "未知類型",
    })
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, snap, on_live_sync=lambda payload: published.append(payload))
    try:
        published.clear()
        app.baseline_model_var.set("未知類型")
        app.on_baseline_model_changed()
        root.update_idletasks()
        assert published
        assert published[-1]["model"] == "未知類型"
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_removing_nonactive_part_publishes_existing_parts(monkeypatch):
    published = []
    snap = _snapshot()
    snap["existing_parts"] = ["box_body", "door", "base_plate"]
    root, win, app = _make_app(monkeypatch, on_live_sync=lambda payload: published.append(payload))
    try:
        app.activate_part("box_body")
        published.clear()
        assert app.remove_part("door") is True
        root.update_idletasks()
        assert published
        assert "door" not in published[-1]["workspace"]["existing_parts"]
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
