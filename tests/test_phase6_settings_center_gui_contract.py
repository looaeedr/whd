from pathlib import Path

from gui_source_contract_helpers import application_source_bundle, phase6_host_method_source


def method_source(name):
    return phase6_host_method_source(name)


def test_gui_owns_one_shared_settings_state_loaded_from_ae_and_snapshot_carries_it():
    import inspect
    from gui_modules.application import state_sync
    from gui_modules.application import fold_designer_adapter as fold_adapter
    init = inspect.getsource(state_sync.init_variables)
    snap = inspect.getsource(fold_adapter._snapshot_base_state)
    source = application_source_bundle()
    assert "self.settings_service = SettingsService(ae)" in source
    assert "settings = self.settings_service.snapshot()" in init
    assert 'snapshot["settings"]' in snap
    assert 'snapshot["corner_state"]' in snap
    assert 'snapshot["corner_pair_same"]' in snap

def test_open_designer_uses_transactional_settings_and_save_default_callback():
    text = method_source("open_original_fold_designer")
    assert "on_settings_change=None" in text
    assert "on_save_defaults=self._save_fold_designer_defaults" in text
    for name in (
        "_apply_fold_designer_live_settings",
        "_save_fold_designer_defaults",
        "_on_main_setting_var_changed",
    ):
        assert method_source(name)


def test_old_main_gui_no_longer_constructs_fold_advanced_panel_but_keeps_global_dimensions():
    create = method_source("create_widgets")
    left_panel = Path("gui_modules/layout/left_panel.py").read_text(encoding="utf-8")
    assert "_build_main_layout(self)" in create
    for token in ('"寬度 (W) :"', '"高度 (H) :"', '"深度 (D) :"'):
        assert token in left_panel
    assert "create_advanced_inputs" not in create
    assert "create_advanced_inputs" not in left_panel
    assert "self.adv_btn" not in create
    assert "host.adv_btn" not in left_panel
    assert "host.create_corner_type_panel" in left_panel


def test_box_body_tab_keeps_global_fw_t_but_removes_z_comp_input():
    text = Path("gui_modules/parts/panels/box_body.py").read_text(encoding="utf-8")
    assert "def setup_tab_z_ui" in text
    assert "self.fw_z_var" in text
    assert "self.t_var" in text
    assert "self.z_comp_var" not in text


def test_base_plate_tab_has_no_duplicate_shrink_or_bend_entries():
    text = Path("gui_modules/parts/panels/base_plate.py").read_text(encoding="utf-8")
    assert "def setup_tab_base_plate_ui" in text
    assert "self.canvas_base_plate" in text
    for token in (
        "self.base_plate_shrink_same_var",
        "self.base_plate_shrink_top_var",
        "self.base_plate_shrink_bottom_var",
        "self.base_plate_shrink_left_var",
        "self.base_plate_shrink_right_var",
        "self.base_plate_bend_var",
    ):
        assert token not in text


def test_corner_type_and_settings_use_live_canonical_sync_while_defaults_are_explicit_only():
    import inspect
    from gui_modules.application import state_sync
    from gui_modules.application import fold_designer_adapter as fold_adapter

    init = inspect.getsource(state_sync.init_variables)
    corner_init = inspect.getsource(state_sync._init_base_results_and_corner_state)
    snap = inspect.getsource(fold_adapter._snapshot_base_state)
    open_text = method_source("open_original_fold_designer")
    save_text = method_source("_save_fold_designer_defaults")
    live_text = method_source("_apply_fold_designer_live_snapshot")
    assert "load_corner_defaults_from_ini(ae)" in corner_init
    assert "_init_base_results_and_corner_state" in init
    assert 'snapshot["corner_editable"]' in snap
    assert 'snapshot["baseline_models"]' in snap
    assert "on_corner_change=None" in open_text
    assert "on_live_sync=lambda payload:" in open_text
    assert "on_transaction_confirm=" not in open_text
    assert "on_transaction_cancel=" not in open_text
    assert "save_corner_defaults_to_ini" in save_text
    assert "persist_defaults" in save_text
    assert "_apply_manual_corner_snapshot" in live_text
    assert "_phase6_update_scheduler" in live_text
    assert ".mark_dirty(" in live_text
    assert "self.update_calculations()" not in live_text
    assert "self.project_controller.capture_committed(" in live_text

def test_runtime_requires_shared_settings_module_without_reintroducing_global_3d_page():
    source = Path("gui.py").read_text(encoding="utf-8")
    bridge_source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    panel_source = Path("phase6_settings_panel.py").read_text(encoding="utf-8")
    assert "from phase6_settings_center import" in source
    assert "SettingsService" in source
    assert "class Phase6SettingsPanel" in panel_source
    assert "self.global_settings_button =" not in bridge_source
