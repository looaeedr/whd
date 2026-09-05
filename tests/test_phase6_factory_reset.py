from types import SimpleNamespace
import tkinter as tk

import fold_designer_bridge as bridge
from phase6_settings_center import load_factory_defaults_from_ae
from test_phase6_corner_transaction import _transaction_snapshot


def _fake_ae():
    # Mirrors the authoritative default_config contract in ae_engine.ae.
    return SimpleNamespace(
        default_config={
            'DEFAULT_SIZES': {'W': '400.0', 'H': '600.0', 'D': '250.0', 'T': '2.0', 'FW': '25.0'},
            'BOX_BODY_Z': {'zl1': '15.0', 'zl2': '20.0', 'zr1': '15.0', 'zr2': '20.0', 'z_comp': '2.0'},
            'END_CAP_Y': {'yl1': '15.0', 'yr1': '15.0', 'ytop1': '16.0', 'ybottom1': '15.0'},
            'OUTPUT': {'draw_stock': 'false'},
            'HOLES': {
                'hang_hole_radius': '3.2', 'hang_hole_x_offset': '35.5',
                'hang_hole_y_from_top_bend': '6.0', 'square_hole_x_from_left': '3.0',
                'square_hole_width': '4.0', 'square_hole_y_from_bottom': '18.0',
                'square_hole_height': '4.0', 'bottom_hole_radius': '2.5',
                'bottom_hole_y_from_bottom': '5.0',
            },
            'NOTCH': {'bottom_gap': '0.5', 'sub_x_half_t': '0.5', 'sub_y_factor': '2.0'},
            'RELIEF': {
                'top_secondary_x_factor': '0.5', 'top_secondary_depth_factor': '2.0',
                'bottom_x_factor': '0.5', 'bottom_y_factor': '0.5',
            },
            'DOOR': {
                'door_gap_w': '3.5', 'door_gap_h': '3.5', 'door_fold_left': '19.0',
                'door_fold_right': '15.0', 'door_fold_top': '15.0', 'door_fold_bottom': '15.0',
            },
            'INDICATOR_BOX': {'fold': '49.0'},
            'BASE_PLATE': {'shrink': '55.0', 'bend': '15.0'},
        },
        # Deliberately poisoned runtime values: factory reset must ignore these.
        W=999.0, H=999.0, D=999.0, T=9.0, FW=99.0,
        z_comp_def=999.0, base_plate_shrink_def=999.0,
    )


def test_factory_defaults_come_from_default_config_not_runtime_or_schema_fallbacks():
    values = load_factory_defaults_from_ae(_fake_ae())
    assert values['w'] == 400.0
    assert values['h'] == 600.0
    assert values['d'] == 250.0
    assert values['t'] == 2.0
    assert values['fw'] == 25.0
    # Important: ae.default_config says 2.0 even though an older schema fallback was 3.0.
    assert values['z_comp'] == 2.0
    assert values['door_fold_l'] == 19.0
    assert values['indicator_box_fold'] == 49.0
    # Per-edge keys intentionally inherit the legacy factory shrink key.
    assert values['base_plate_shrink_top'] == 55.0
    assert values['base_plate_shrink_bottom'] == 55.0
    assert values['base_plate_shrink_left'] == 55.0
    assert values['base_plate_shrink_right'] == 55.0
    # ae(4).py has no INDICATOR_SMALL_DOOR section; schema factory fallback remains authoritative.
    assert values['indicator_door_fold'] == 19.0


def _make_app(monkeypatch, confirmed):
    snap = _transaction_snapshot()
    snap['existing_parts'] = ['box_body', 'head', 'tail', 'door', 'base_plate', 'indicator_box', 'indicator_door']
    snap['factory_defaults'] = load_factory_defaults_from_ae(_fake_ae())
    monkeypatch.setattr(bridge, 'project_features_to_original_holes', lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(
        win, snap,
        on_transaction_confirm=lambda payload: confirmed.append(payload),
    )
    root.update_idletasks()
    return root, app


def test_reset_initial_values_is_local_and_restores_factory_profiles(monkeypatch):
    confirmed = []
    root, app = _make_app(monkeypatch, confirmed)
    try:
        # Live canonical mode keeps only the local reset button in the top command row;
        # Confirm/Cancel buttons were removed when every edit became immediately published.
        assert app.reset_initial_button.master is app.transaction_buttons
        assert not hasattr(app, 'cancel_transaction_button')
        assert not hasattr(app, 'confirm_transaction_button')

        app.activate_part('box_body')
        root.update_idletasks()
        app.left_global_vars['w'].set('777')
        app.flush_pending_settings()
        # Edit a fold value too. Outside first segment at T=2 is material+1T.
        app.bend_ui.controls[0]['len'].set('29')
        app.activate_part('door')  # persists the box-body editor into staged settings
        root.update_idletasks()
        assert app._settings_values['w'] == 777.0
        assert app._settings_values['zl1'] == 27.0
        assert confirmed == []

        assert app.reset_initial_values() is True
        root.update_idletasks()

        # Reset remains inside 3D; main-GUI confirm callback is still untouched.
        assert confirmed == []
        assert app._settings_values['w'] == 400.0
        assert app._settings_values['h'] == 600.0
        assert app._settings_values['d'] == 250.0
        assert app._settings_values['t'] == 2.0
        assert app._settings_values['fw'] == 25.0
        assert app._settings_values['z_comp'] == 2.0
        assert app._settings_values['zl1'] == 15.0
        assert app._settings_values['door_fold_l'] == 19.0
        assert app._settings_values['base_plate_bend'] == 15.0

        # Linked profiles are regenerated from factory values, not left at edited dimensions.
        assert app._phase6_input_snapshot['part_dimensions']['door']['width'] == 335.0
        assert app._phase6_input_snapshot['part_dimensions']['base_plate']['width'] == 290.0
        assert app._phase6_part_profiles['door']['X'][1]['len'] == 331.0
        assert app._phase6_part_profiles['base_plate']['X'][1]['len'] == 290.0

        # Baseline selection is not part of ae.default_config and must not be invented/reset.
        assert app.baseline_model_var.get() == '金庫型'

        assert app.confirm_corner_transaction() is True
        assert len(confirmed) == 1
        assert confirmed[0]['settings']['w'] == 400.0
        assert confirmed[0]['settings']['z_comp'] == 2.0
        assert confirmed[0]['settings']['base_plate_bend'] == 15.0
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_main_gui_passes_ae_factory_defaults_into_3d_snapshot():
    source = open('gui.py', encoding='utf-8').read()
    assert 'load_factory_defaults_from_ae' in source
    assert 'snapshot["factory_defaults"] = load_factory_defaults_from_ae(ae)' in source


def test_factory_reset_does_not_poison_next_main_gui_baseline_model(monkeypatch):
    import gui

    confirmed = []
    root, app = _make_app(monkeypatch, confirmed)
    try:
        assert app.reset_initial_values() is True
        root.update_idletasks()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

    next_root = tk.Tk(); next_root.withdraw()
    next_app = gui.BoxCalculatorGUI(next_root)
    try:
        assert next_app.baseline_var._root is next_root
        assert next_app.baseline_var.get() == "金庫型"
        spec = next_app._end_cap_part_spec(next_app.get_float_values(), is_tail=False)
        assert spec.model_name == "金庫型"
    finally:
        next_root.destroy()
