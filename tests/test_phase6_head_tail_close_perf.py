import time
import tkinter as tk

import fold_designer_bridge as bridge
from test_phase6_part_switch_performance import _snapshot


def _make_app(monkeypatch, callback=None):
    monkeypatch.setattr(bridge, 'project_features_to_original_holes', lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, _snapshot(), on_settings_change=callback)
    end = time.perf_counter() + 0.25
    while time.perf_counter() < end:
        root.update(); time.sleep(0.002)
    app.set_3d_preview_enabled(False)
    return root, app


def test_head_to_tail_switch_does_not_rebuild_same_standard_xy_notebook(monkeypatch):
    root, app = _make_app(monkeypatch)
    try:
        app.activate_part('head')
        root.update()
        calls = []
        original = app.bend_ui.rebuild_tabs
        app.bend_ui.rebuild_tabs = lambda *a, **k: (calls.append(1), original(*a, **k))[1]
        app.activate_part('tail')
        root.update()
        assert calls == []
        assert app.bend_ui.tabs == ['X', 'Y']
    finally:
        root.destroy()


def test_head_tail_save_does_not_set_unchanged_global_whd(monkeypatch):
    root, app = _make_app(monkeypatch)
    try:
        app.activate_part('head')
        root.update()
        counts = {'w': 0, 'd': 0}
        w_set = app.v_w.set
        d_set = app.v_d.set
        app.v_w.set = lambda value: (counts.__setitem__('w', counts['w'] + 1), w_set(value))[1]
        app.v_d.set = lambda value: (counts.__setitem__('d', counts['d'] + 1), d_set(value))[1]
        app._save_current_part()
        assert counts == {'w': 0, 'd': 0}
    finally:
        root.destroy()


def test_export_collects_active_edit_without_notifying_main_gui(monkeypatch):
    calls = []
    root, app = _make_app(monkeypatch, lambda payload: calls.append(dict(payload)))
    try:
        app.activate_part('head')
        root.update()
        calls.clear()
        # Edit the first outside length. Export must collect it, but close path
        # owns the single full snapshot apply and must not trigger a live callback.
        app.bend_ui.controls[0]['len'].set('19')
        calls.clear()
        snapshot = app.export_phase6_snapshot()
        assert snapshot['yl1'] == 17.0
        assert calls == []
    finally:
        root.destroy()


def test_settings_context_pages_are_reused_after_first_build(monkeypatch):
    root, app = _make_app(monkeypatch)
    try:
        app.activate_part('head')
        root.update_idletasks()
        head_page = app._settings_page_cache['head']['frame']
        child_ids = tuple(str(w) for w in head_page.winfo_children())
        app.activate_part('tail')
        root.update_idletasks()
        app.activate_part('head')
        root.update_idletasks()
        assert app._settings_page_cache['head']['frame'] is head_page
        assert tuple(str(w) for w in head_page.winfo_children()) == child_ids
    finally:
        root.destroy()
