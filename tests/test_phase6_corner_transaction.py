import tkinter as tk

import fold_designer_bridge as bridge
from test_phase6_settings_center_bridge import _snapshot


def _transaction_snapshot():
    snap = _snapshot()
    snap.update({
        "model": "金庫型",
        "baseline_models": ["金庫型", "一般型", "未知類型"],
        "baseline_unknown_value": "未知類型",
        "corner_editable": False,
        "corner_state": {
            "door": {
                "top_left": {"type_id": "C03", "rotation_quadrants": 0},
                "top_right": {"type_id": "C03", "rotation_quadrants": 0},
                "bottom_left": {"type_id": "C04", "rotation_quadrants": 0},
                "bottom_right": {"type_id": "C04", "rotation_quadrants": 0},
            }
        },
        "corner_pair_same": {"door": {"top": True, "bottom": True}},
    })
    return snap


def _make_app(monkeypatch, **kwargs):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, _transaction_snapshot(), **kwargs)
    root.update_idletasks()
    return root, win, app


def test_baseline_selector_is_in_3d_and_unknown_uses_existing_corner_state(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        original = app._phase6_corner_state["door"]["top_left"].copy()
        assert app.baseline_model_var.get() == "金庫型"
        assert tuple(app._baseline_models) == ("金庫型", "一般型", "未知類型")
        assert app._corner_editable is False

        app.baseline_model_var.set("未知類型")
        root.update()

        assert app._corner_editable is True
        # Moving from a known baseline to custom starts from the known model's
        # canonical semantic policy, not the legacy C03 alias spelling.
        current = app._phase6_corner_state["door"]["top_left"]
        assert current["type_id"] == "CROSS"
        assert current["cross_mode"] == "retain"
        assert current["direction"] == "width"
    finally:
        root.destroy()


def test_corner_pair_edit_publishes_live_without_confirm(monkeypatch):
    published = []
    root, win, app = _make_app(
        monkeypatch,
        on_live_sync=lambda payload: published.append(payload),
    )
    try:
        app.baseline_model_var.set("未知類型")
        app.on_baseline_model_changed()
        app._phase6_parameters_unlocked = True
        app.activate_part("door")
        root.update_idletasks()
        published.clear()
        app.corner_pair_checkbuttons["top"].invoke()
        root.update_idletasks()

        assert app._phase6_corner_pair_same["door"]["top"] is False
        assert published
        assert published[-1]["corner_pair_same"]["door"]["top"] is False
        assert not hasattr(app, "confirm_transaction_button")
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_cancel_does_not_confirm_corner_transaction(monkeypatch):
    confirmed = []
    cancelled = []
    root, win, app = _make_app(
        monkeypatch,
        on_transaction_confirm=lambda payload: confirmed.append(payload),
        on_transaction_cancel=lambda: cancelled.append(True),
    )
    try:
        app.baseline_model_var.set("未知類型")
        root.update()
        assert app.cancel_corner_transaction() is True
        assert confirmed == []
        assert cancelled == [True]
    finally:
        root.destroy()


def test_unmodified_workspace_close_path_skips_even_lightweight_save(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        calls = []
        app._save_current_part = lambda *a, **k: calls.append(True)
        app._phase6_workspace_dirty = False
        # Viewing another bend tab may queue a preview update, but is not a data edit.
        app.queue_update()
        root.update_idletasks()
        assert app._phase6_workspace_dirty is False
        assert app.export_workspace_state_if_dirty() is None
        assert calls == []
    finally:
        root.destroy()


def test_real_fold_entry_edit_marks_workspace_dirty(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        app._phase6_workspace_dirty = False
        app.bend_ui.controls[0]["len"].set("18")
        root.update_idletasks()
        assert app._phase6_workspace_dirty is True
    finally:
        root.destroy()
