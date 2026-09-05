import time
import tkinter as tk

import fold_designer_bridge as bridge
from test_phase6_part_switch_performance import _snapshot


def _make_app(monkeypatch, callback):
    monkeypatch.setattr(bridge, 'project_features_to_original_holes', lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, _snapshot(), on_settings_change=callback)
    end = time.perf_counter() + 0.25
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.003)
    return root, app


def _drain(root, seconds=0.25):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.003)


def test_switch_without_edits_does_not_notify_main_gui(monkeypatch):
    calls = []
    root, app = _make_app(monkeypatch, lambda payload: calls.append(dict(payload)))
    try:
        calls.clear()
        app.set_3d_preview_enabled(False)
        app.activate_part('door')
        _drain(root)
        assert calls == []
    finally:
        root.destroy()


def test_switch_after_left_edit_notifies_only_changed_setting_keys(monkeypatch):
    calls = []
    root, app = _make_app(monkeypatch, lambda payload: calls.append(dict(payload)))
    try:
        calls.clear()
        app.set_3d_preview_enabled(False)
        app.activate_part('box_body')
        _drain(root, 0.05)
        calls.clear()
        # Box-body first row is outside dimension 17 for material 15 at T=2.
        app.bend_ui.controls[0]['len'].set('19')
        app.activate_part('door')
        _drain(root)
        assert len(calls) == 1
        assert calls[0] == {'zl1': 17.0, 'zr1': 17.0}
    finally:
        root.destroy()


def test_equivalent_part_switch_submits_display_intent_not_geometry(monkeypatch):
    calls = []
    root, app = _make_app(monkeypatch, lambda payload: None)
    try:
        app.set_3d_preview_enabled(False)
        _drain(root, 0.05)
        assert hasattr(app, "submit_update_intent")
        original_submit = app.submit_update_intent

        def counted_submit(reason, *, commit=False):
            calls.append((str(reason), bool(commit)))
            return original_submit(reason, commit=commit)

        app.submit_update_intent = counted_submit
        app.activate_part("door")
        _drain(root, 0.2)

        assert calls
        assert ("display", True) in calls
        assert not any(reason in {"geometry", "assembly"} for reason, _ in calls)
    finally:
        root.destroy()


def test_head_tail_ten_switches_do_not_drift_global_d_or_manufacturing_signature(monkeypatch):
    root, app = _make_app(monkeypatch, lambda payload: None)
    try:
        app.set_3d_preview_enabled(False)
        # Visit both EndCaps once so lazy UI-only corner controls are materialized
        # before the drift fingerprint is captured. The repeated switch phase
        # below must then be semantically idempotent.
        app.activate_part("head")
        app.activate_part("tail")
        app.activate_part("head")
        _drain(root, 0.05)
        initial_d = float(app._phase6_box_whd["d"])
        initial_snapshot_d = float(app._phase6_input_snapshot["d"])
        initial_signature = bridge._phase6_manufacturing_state_signature(app)

        for index in range(10):
            app.activate_part("tail" if index % 2 == 0 else "head")
            _drain(root, 0.02)

        assert float(app._phase6_box_whd["d"]) == initial_d
        assert float(app._phase6_input_snapshot["d"]) == initial_snapshot_d
        assert bridge._phase6_manufacturing_state_signature(app) == initial_signature
    finally:
        root.destroy()
