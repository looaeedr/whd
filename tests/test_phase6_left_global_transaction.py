import tkinter as tk

import fold_designer_bridge as bridge
from test_phase6_corner_transaction import _transaction_snapshot


def _make_app(monkeypatch, **kwargs):
    monkeypatch.setattr(bridge, 'project_features_to_original_holes', lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, _transaction_snapshot(), **kwargs)
    root.update_idletasks()
    return root, win, app


def _is_descendant(widget, ancestor):
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        current = getattr(current, 'master', None)
    return False


def test_global_controls_and_reset_only_live_in_persistent_top_area(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        assert app.left_global_controls.master is app.top_global_host
        assert app.baseline_model_combo.master.winfo_toplevel() is win
        assert _is_descendant(app.baseline_model_combo, app.left_global_controls)
        assert {'w', 'h', 'd', 't'} <= set(app.left_global_vars)
        assert 'fw' not in app.left_global_vars
        assert _is_descendant(app.reset_initial_button, app.top_command_row)
        assert not hasattr(app, 'cancel_transaction_button')
        assert not hasattr(app, 'confirm_transaction_button')
    finally:
        root.destroy()


def test_right_settings_center_has_no_global_page(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        assert not hasattr(app, 'global_settings_button')
        # Assembly startup may initialize the settings controller context;
        # selecting a physical part must still render only that part context.
        app.activate_part('box_body')
        root.update_idletasks()
        assert app.settings_context == 'box_body'
        assert app.settings_title_var.get() == '箱身設定'
        assert 'w' not in app.setting_vars
        app.activate_part('door')
        root.update_idletasks()
        assert app.settings_context == 'door'
        assert {'door_gap_w', 'door_gap_h'} <= set(app.setting_vars)
    finally:
        root.destroy()


def test_global_w_change_updates_profiles_and_publishes_immediately(monkeypatch):
    published = []
    root, win, app = _make_app(
        monkeypatch,
        on_live_sync=lambda payload: published.append(payload),
    )
    try:
        app.left_global_vars['w'].set('600')
        app.flush_pending_settings()
        root.update_idletasks()

        assert app._settings_values['w'] == 600.0
        assert app._phase6_input_snapshot['part_dimensions']['door']['width'] == 535.0
        assert app._phase6_input_snapshot['part_dimensions']['base_plate']['width'] == 490.0
        assert app._phase6_part_profiles['door']['X'][1]['len'] == 531.0
        assert app._phase6_part_profiles['base_plate']['X'][1]['len'] == 490.0
        assert published
        assert published[-1]['settings']['w'] == 600.0
        assert published[-1]['model'] == '金庫型'
    finally:
        root.destroy()


def test_left_fold_edit_publishes_live_without_confirm(monkeypatch):
    published = []
    root, win, app = _make_app(
        monkeypatch,
        on_live_sync=lambda payload: published.append(payload),
    )
    try:
        app.activate_part('box_body')
        root.update_idletasks()
        app.bend_ui.controls[0]['len'].set('19')
        app.activate_part('door')
        root.update_idletasks()
        assert app._settings_values['zl1'] == 17.0
        assert published
        assert published[-1]['settings']['zl1'] == 17.0
    finally:
        root.destroy()

def test_head_outside_width_relinks_door_and_base_profiles(monkeypatch):
    snap = _transaction_snapshot()
    snap['existing_parts'] = ['box_body', 'head', 'tail', 'door', 'base_plate']
    monkeypatch.setattr(bridge, 'project_features_to_original_holes', lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, snap, on_live_sync=lambda payload: None)
    root.update_idletasks()
    try:
        app.activate_part('head')
        root.update_idletasks()
        # EndCap X outside core = W-2T. At T=2, 596 means global W=600.
        app.bend_ui.controls[1]['len'].set('596')
        app.activate_part('door')
        root.update_idletasks()
        assert app._settings_values['w'] == 600.0
        assert app._phase6_input_snapshot['part_dimensions']['door']['width'] == 535.0
        assert app._phase6_input_snapshot['part_dimensions']['base_plate']['width'] == 490.0
        assert app._phase6_part_profiles['door']['X'][1]['len'] == 531.0
        assert app._phase6_part_profiles['base_plate']['X'][1]['len'] == 490.0
    finally:
        root.destroy()
