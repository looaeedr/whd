from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
COORDINATOR = Path("gui_modules/application/fold_designer_settings_coordinator.py")


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def _coordinator_method_source(name: str) -> str:
    source = COORDINATOR.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(COORDINATOR))
    cls = next(
        item
        for item in tree.body
        if isinstance(item, ast.ClassDef)
        and item.name == "Phase6FoldDesignerSettingsCoordinator"
    )
    node = next(
        item
        for item in cls.body
        if isinstance(item, ast.FunctionDef)
        and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_issue501_coordinator_owns_baseline_transition_effect_order():
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "def apply_baseline_transition(" in source, (
        "RED R3: Settings coordinator does not own baseline transition effect order"
    )
    method = _coordinator_method_source("apply_baseline_transition")
    assert "commit_family_model_transition(" in method
    assert "project_ui_values(" in method
    assert "apply_profile_plan(" in method
    assert "sync_derived_parts(" in method
    assert "refresh_topology(" in method
    assert "refresh_persistent_controls(" in method
    assert "submit_update_intent(" in method


def test_issue501_bridge_baseline_handler_is_narrow_coordinator_delegate():
    source = _function_source(BRIDGE, "_phase6_on_baseline_model_changed")
    assert "_phase6_settings_coordinator(self).apply_baseline_transition" in source
    forbidden = (
        "commit_family_model_transition(",
        "_phase6_store_editor_values(",
        "_phase6_refresh_profiles_from_settings(",
        "_phase6_sync_authoritative_derived_parts(",
        "_phase6_refresh_persistent_structure_controls(",
        "_phase6_render_settings_context(",
        "_phase6_publish_live_state(",
    )
    assert [token for token in forbidden if token in source] == []


def test_issue501_coordinator_owns_factory_reset_sequence():
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "def reset_factory_settings(" in source, (
        "RED R4: Settings coordinator does not own factory reset sequencing"
    )
    method = _coordinator_method_source("reset_factory_settings")
    assert "commit_settings(" in method
    assert "apply_profile_plan(" in method
    assert "project_ui_values(" in method
    assert "render_bending(" in method
    assert "refresh_settings_panel(" in method
    assert "submit_update_intent(" in method
    assert "project_status(" in method


def test_issue501_bridge_factory_reset_is_narrow_coordinator_delegate():
    source = _function_source(BRIDGE, "_phase6_reset_initial_values")
    assert "_phase6_settings_coordinator(self).reset_factory_settings" in source
    forbidden = (
        "self._settings_values.update(",
        "self._phase6_input_snapshot.update(",
        "build_box_body_profile(",
        "build_endcap_xy_profiles(",
        "build_standard_part_profiles(",
        "designer_workspace.stash_profiles(",
        "bend_ui.render(",
        "settings_panel.refresh_baseline_data(",
        "self.do_update(",
    )
    assert [token for token in forbidden if token in source] == []


def test_issue501_semantic_owner_stays_transaction_controller():
    baseline = _function_source(BRIDGE, "_phase6_on_baseline_model_changed")
    coordinator = _coordinator_method_source("apply_baseline_transition")
    assert "commit_family_model_transition(" not in baseline
    assert "self._transactions.commit_family_model_transition(" in coordinator
