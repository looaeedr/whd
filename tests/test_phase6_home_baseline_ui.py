import tkinter as tk

import fold_designer_bridge as bridge
from test_phase6_corner_transaction import _transaction_snapshot


def _make_app(monkeypatch, *, baseline_query=None, model='金庫型'):
    snap = _transaction_snapshot()
    snap['model'] = model
    snap['existing_parts'] = ['box_body', 'head', 'tail', 'door', 'base_plate', 'indicator_box', 'indicator_door']
    monkeypatch.setattr(bridge, 'project_features_to_original_holes', lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(
        win, snap,
        on_transaction_confirm=lambda payload: None,
        on_baseline_data_query=baseline_query,
    )
    root.update_idletasks()
    return root, app


def test_initial_view_is_assembly_and_global_controls_remain_visible(monkeypatch):
    root, app = _make_app(monkeypatch)
    try:
        assert app.active_part_key == 'box_body'
        assert app.part_var.get() == '組合體'
        assert app._phase6_3d_display_mode == 'assembly'
        assert app.left_global_controls.winfo_manager() == 'pack'
        assert 'fw' not in app.left_global_vars
        assert app.fold_editor_host.winfo_manager() == ''
        assert app.settings_center.winfo_manager() == ''
        assert app.renderer.canvas.get_tk_widget().winfo_manager() == 'pack'
    finally:
        root.destroy()


def test_selecting_part_keeps_global_visible_and_shows_fold_editor(monkeypatch):
    root, app = _make_app(monkeypatch)
    try:
        app.activate_part('door')
        root.update_idletasks()
        assert app.left_global_controls.winfo_manager() == 'pack'
        assert app.fold_editor_host.winfo_manager() == 'pack'
        assert app.settings_center.winfo_manager() == ''
        assert app.renderer.canvas.get_tk_widget().winfo_manager() == 'pack'
        assert app.transaction_buttons.master is app.top_command_row
        assert app.reset_initial_button.master is app.transaction_buttons
        assert not hasattr(app, 'cancel_transaction_button')
        assert not hasattr(app, 'confirm_transaction_button')
    finally:
        root.destroy()


def test_baseline_numeric_data_section_is_collapsed_by_default(monkeypatch):
    root, app = _make_app(monkeypatch)
    try:
        app.activate_part('head')
        root.update_idletasks()
        assert app.baseline_data_toggle_button is not None
        assert app.baseline_data_frame.winfo_manager() == ''
        # Existing EndCap fixed-hole settings live inside the collapsed baseline data section.
        assert {'hang_hole_r', 'hang_hole_y_up', 'sq_x_left', 'sq_width'} <= set(app.setting_vars)
        for key in ('hang_hole_r', 'hang_hole_y_up', 'sq_x_left', 'sq_width'):
            widget = app.baseline_setting_cells[key]
            assert widget.master is app.baseline_data_frame
    finally:
        root.destroy()


def test_door_baseline_numeric_rows_are_lazy_loaded_when_section_expands(monkeypatch):
    calls = []
    def query(part_key, model, values):
        calls.append((part_key, model, dict(values)))
        return [
            {'kind': '圓孔', 'layer': 'CUTTING', 'x': 100.0, 'y': 80.0, 'd1': 12.0, 'd2': 0.0},
            {'kind': '方孔', 'layer': 'CUTTING', 'x': 220.0, 'y': 90.0, 'd1': 20.0, 'd2': 10.0},
        ]
    root, app = _make_app(monkeypatch, baseline_query=query)
    try:
        app.activate_part('door')
        root.update_idletasks()
        assert calls == []
        assert app.baseline_data_frame.winfo_manager() == ''
        app.toggle_baseline_data()
        root.update_idletasks()
        assert len(calls) == 1
        assert calls[0][0:2] == ('door', '金庫型')
        assert app.baseline_data_frame.winfo_manager() == 'grid'
        def collect_texts(widget):
            out = []
            for child in widget.winfo_children():
                if child.winfo_class() == 'TLabel':
                    out.append(str(child.cget('text')))
                out.extend(collect_texts(child))
            return out
        joined = ' '.join(collect_texts(app.baseline_data_frame))
        assert '圓孔' in joined and 'Ø12' in joined
        assert '方孔' in joined and '20×10' in joined
    finally:
        root.destroy()


def test_known_parts_show_readonly_factory_corner_types(monkeypatch):
    root, app = _make_app(monkeypatch, model='金庫型')
    try:
        app.activate_part('head'); root.update_idletasks()
        assert app.fixed_corner_summary_var.get() == bridge._FIXED_CORNER_SUMMARIES['head']
        assert app.corner_type_vars == {}
        app.activate_part('door'); root.update_idletasks()
        assert app.fixed_corner_summary_var.get() == bridge._FIXED_CORNER_SUMMARIES['door']
        app.activate_part('base_plate'); root.update_idletasks()
        assert app.fixed_corner_summary_var.get() == bridge._FIXED_CORNER_SUMMARIES['base_plate']
    finally:
        root.destroy()


def test_main_gui_wires_lazy_baseline_numeric_query_into_3d():
    source = open('gui.py', encoding='utf-8').read()
    assert 'def _query_fold_designer_baseline_data' in source
    assert 'on_baseline_data_query=self._query_fold_designer_baseline_data' in source
    assert 'ae.get_stretched_door_data' in source
    assert 'self._fold_designer_secondary_scene_rows(data.scene)' in source
