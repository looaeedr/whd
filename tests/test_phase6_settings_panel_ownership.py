# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from phase6_settings_center import SettingSpec


def test_settings_panel_module_has_no_domain_or_project_imports():
    source = Path('phase6_settings_panel.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        'fold_designer_bridge',
        'phase6_project_session',
        'phase6_project_controller',
        'phase6_workspace_controller',
        'phase6_final_scene_view',
        'ae_engine',
    }
    assert not any(name == bad or name.startswith(bad + '.') for name in imported for bad in forbidden)


def test_partition_setting_specs_separates_ui_groups_without_losing_values():
    from phase6_settings_panel import partition_setting_specs

    specs = (
        SettingSpec('normal', '一般', ('box_body',), 'X', 'normal', 1.0, group='一般'),
        SettingSpec('advanced', '進階', ('box_body',), 'X', 'advanced', 2.0, group='補償'),
        SettingSpec('baseline', '基準', ('box_body',), 'X', 'baseline', 3.0, group='固定孔'),
        SettingSpec('compat', '相容', ('box_body',), 'X', 'compat', 4.0, group='Relief'),
        SettingSpec('left', '左側已有', ('box_body',), 'X', 'left', 5.0, group='一般'),
    )
    groups = partition_setting_specs('box_body', specs, hidden_keys={'left'})
    assert [spec.key for spec in groups.normal] == ['normal']
    assert [spec.key for spec in groups.advanced] == ['advanced']
    assert [spec.key for spec in groups.baseline] == ['baseline']
    assert [spec.key for spec in groups.compatibility_hidden] == ['compat']


def test_baseline_row_text_formats_supported_feature_rows():
    from phase6_settings_panel import baseline_row_text

    assert baseline_row_text({'kind': '圓孔', 'x': 10, 'y': 20, 'd1': 8, 'layer': 'CUT'}) == '圓孔  X=10  Y=20  Ø8 [CUT]'
    assert baseline_row_text({'kind': '方孔', 'x': 1.5, 'y': 2, 'd1': 20, 'd2': 30}) == '方孔  X=1.5  Y=2  20×30'


def _panel_specs_for_context(context):
    if context != 'box_body':
        return ()
    return (
        SettingSpec('normal', '一般', ('box_body',), 'X', 'normal', 10.0, group='一般'),
        SettingSpec('advanced', '進階', ('box_body',), 'X', 'advanced', 20.0, group='補償'),
        SettingSpec('baseline', '基準孔', ('box_body',), 'X', 'baseline', 30.0, group='固定孔'),
    )


def test_settings_panel_widget_stages_draft_without_owning_values():
    import tkinter as tk
    from tkinter import ttk
    from phase6_settings_panel import Phase6SettingsPanel

    root = tk.Tk(); root.withdraw()
    try:
        values = {'normal': 10.0, 'advanced': 20.0, 'baseline': 30.0}
        staged = []
        panel = Phase6SettingsPanel(
            values_snapshot=lambda: dict(values),
            stage_setting_update=lambda key, value: staged.append((key, value)),
            flush_settings=lambda: None,
            save_defaults=lambda _context: True,
            specs_provider=_panel_specs_for_context,
            part_labels={'box_body': '箱身'},
        )
        panel.build_settings_center(ttk.Frame(root))
        panel.render_context('box_body')
        panel.setting_vars['normal'].set('12.5')
        root.update_idletasks()
        assert staged[-1] == ('normal', 12.5)
        assert values['normal'] == 10.0
    finally:
        root.destroy()


def test_advanced_toggle_changes_only_ui_state_not_draft_values():
    import tkinter as tk
    from tkinter import ttk
    from phase6_settings_panel import Phase6SettingsPanel

    root = tk.Tk(); root.withdraw()
    try:
        values = {'normal': 10.0, 'advanced': 20.0, 'baseline': 30.0}
        panel = Phase6SettingsPanel(
            values_snapshot=lambda: dict(values),
            stage_setting_update=lambda *_a: None,
            flush_settings=lambda: None,
            save_defaults=lambda _context: True,
            specs_provider=_panel_specs_for_context,
            part_labels={'box_body': '箱身'},
        )
        panel.build_settings_center(ttk.Frame(root))
        page1 = panel.render_context('box_body')
        # The outer parameter lock owns visibility now; the legacy advanced
        # toggle is a compatibility no-op and must not rebuild or mutate state.
        assert panel.advanced_settings_visible is True
        assert panel.advanced_toggle_button is None
        page2 = panel.toggle_advanced()
        assert panel.advanced_settings_visible is True
        assert page2 is page1
        assert values == {'normal': 10.0, 'advanced': 20.0, 'baseline': 30.0}
    finally:
        root.destroy()


def test_baseline_query_runs_lazily_only_when_section_is_opened():
    import tkinter as tk
    from tkinter import ttk
    from phase6_settings_panel import Phase6SettingsPanel

    root = tk.Tk(); root.withdraw()
    try:
        queries = []
        panel = Phase6SettingsPanel(
            values_snapshot=lambda: {'normal': 10.0, 'advanced': 20.0, 'baseline': 30.0},
            stage_setting_update=lambda *_a: None,
            flush_settings=lambda: None,
            save_defaults=lambda _context: True,
            query_baseline_rows=lambda c, m, v: queries.append((c, m, v)) or ({'kind': '圓孔', 'x': 1, 'y': 2, 'd1': 8},),
            baseline_model_getter=lambda: 'MODEL-A',
            is_unknown_baseline=lambda _m: False,
            should_show_baseline_data=lambda _c, _s: True,
            specs_provider=_panel_specs_for_context,
            part_labels={'box_body': '箱身'},
        )
        panel.build_settings_center(ttk.Frame(root))
        panel.render_context('box_body')
        assert queries == []
        panel.toggle_baseline_data()
        assert len(queries) == 1
        panel.toggle_baseline_data()
        assert len(queries) == 1
    finally:
        root.destroy()


def test_settings_panel_domain_extension_is_callback_driven_and_resynced():
    import tkinter as tk
    from tkinter import ttk
    from phase6_settings_panel import Phase6SettingsPanel, SettingsPanelExtensionResult

    root = tk.Tk(); root.withdraw()
    try:
        built = []
        synced = []
        token = object()

        def render_extension(parent, context, start_row):
            built.append((context, start_row, parent.winfo_class()))
            return SettingsPanelExtensionResult(next_row=start_row + 2, state=token)

        panel = Phase6SettingsPanel(
            values_snapshot=lambda: {'normal': 10.0, 'advanced': 20.0, 'baseline': 30.0},
            stage_setting_update=lambda *_a: None,
            flush_settings=lambda: None,
            save_defaults=lambda _context: True,
            specs_provider=_panel_specs_for_context,
            part_labels={'box_body': '箱身'},
            render_context_extensions=render_extension,
            sync_context_extension=lambda state, context: synced.append((state, context)),
        )
        panel.build_settings_center(ttk.Frame(root))
        page = panel.render_context('box_body')
        assert page['extension_state'] is token
        assert built and built[0][0] == 'box_body'
        assert synced[-1] == (token, 'box_body')

        panel.render_context('box_body')
        assert len(built) == 1  # cached page 不重建
        assert synced[-1] == (token, 'box_body')
        assert len(synced) == 2
    finally:
        root.destroy()


def test_bridge_no_longer_owns_generic_settings_panel_implementation():
    source = Path('fold_designer_bridge.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    top_level_defs = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    forbidden = {
        '_phase6_add_setting_widget',
        '_phase6_build_settings_page',
        '_phase6_fill_baseline_data_rows',
        '_phase6_toggle_baseline_data',
        '_phase6_toggle_advanced_settings',
        '_baseline_row_text',
    }
    assert not (top_level_defs & forbidden), sorted(top_level_defs & forbidden)
    assert 'from phase6_settings_panel import' in source


def test_left_global_controls_stage_values_and_emit_ui_callbacks_without_owning_draft():
    import tkinter as tk
    from tkinter import ttk
    from phase6_settings_panel import Phase6SettingsPanel

    root = tk.Tk(); root.withdraw()
    try:
        values = {'w': 400.0, 'h': 600.0, 'd': 250.0, 't': 2.0, 'draw_stock': False, 'ui_text_size': 'small'}
        staged = []
        baseline_changes = []
        text_changes = []
        panel = Phase6SettingsPanel(
            values_snapshot=lambda: dict(values),
            stage_setting_update=lambda key, value: staged.append((key, value)),
            flush_settings=lambda: None,
            save_defaults=lambda _context: True,
            baseline_model_changed=lambda: baseline_changes.append(panel.baseline_model_var.get()),
            ui_text_size_changed=lambda key: text_changes.append(key),
        )
        panel.build_left_global_controls(
            ttk.Frame(root),
            baseline_models=('MODEL-A', '自訂'),
            initial_model='MODEL-A',
        )
        panel.left_global_vars['w'].set('450')
        assert 'draw_stock' not in panel.left_global_vars  # STOCK 已移出左側全域列
        panel.ui_text_size_var.set('大')
        panel.baseline_model_var.set('自訂')
        root.update_idletasks()

        assert ('w', 450.0) in staged
        assert not [item for item in staged if item[0] == 'draw_stock']
        assert text_changes[-1] == 'large'
        assert baseline_changes[-1] == '自訂'
        assert values['w'] == 400.0
        assert values['draw_stock'] is False
    finally:
        root.destroy()


def test_bridge_no_longer_owns_left_global_widget_wiring():
    source = Path('fold_designer_bridge.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    top_level_defs = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert '_phase6_build_left_global_controls' not in top_level_defs
    assert '_phase6_on_left_global_var_changed' not in top_level_defs


def test_external_settings_sync_does_not_restage_through_panel_traces():
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('需要 Tk 顯示環境')
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part('box_body')
        root.update_idletasks(); root.update()
        staged = []
        designer.settings_panel._stage_setting_update = lambda key, value: staged.append((key, value))
        current = float(designer._settings_values['w'])
        designer.apply_external_settings({'w': current + 10.0})
        root.update_idletasks(); root.update()
        assert staged == []
        assert float(designer._settings_values['w']) == pytest.approx(current + 10.0)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
