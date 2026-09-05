import ast
from pathlib import Path

SOURCE = Path("gui.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
GUI = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "BoxCalculatorGUI")


def method_source(name):
    node = next(node for node in GUI.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(SOURCE, node)


def test_gui_owns_one_shared_settings_state_loaded_from_ae_and_snapshot_carries_it():
    init = method_source("init_variables")
    snap = method_source("_make_original_fold_designer_snapshot")
    source = Path("gui.py").read_text(encoding="utf-8")
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
        assert any(isinstance(node, ast.FunctionDef) and node.name == name for node in GUI.body)


def test_old_main_gui_no_longer_constructs_fold_advanced_panel_but_keeps_global_dimensions():
    create = method_source("create_widgets")
    assert '"寬度 (W) :"' in create
    assert '"高度 (H) :"' in create
    assert '"深度 (D) :"' in create
    assert "create_advanced_inputs" not in create
    assert "self.adv_btn" not in create
    assert "create_corner_type_panel" in create


def test_box_body_tab_keeps_global_fw_t_but_removes_z_comp_input():
    text = method_source("setup_tab_z_ui")
    assert "self.fw_z_var" in text
    assert "self.t_var" in text
    assert "self.z_comp_var" not in text


def test_base_plate_tab_has_no_duplicate_shrink_or_bend_entries():
    text = method_source("setup_tab_base_plate_ui")
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
    init = method_source("init_variables")
    snap = method_source("_make_original_fold_designer_snapshot")
    open_text = method_source("open_original_fold_designer")
    save_text = method_source("_save_fold_designer_defaults")
    live_text = method_source("_apply_fold_designer_live_snapshot")
    assert "load_corner_defaults_from_ini(ae)" in init
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
    assert "from phase6_settings_center import" in source
    assert "SettingsService" in source
    assert "Phase6SettingsPanel" in bridge_source
    assert "self.global_settings_button =" not in bridge_source

