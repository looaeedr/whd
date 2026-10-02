from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
ROUTER = Path("gui_modules/application/command_router.py")
SERVICE = Path("phase6_settings_service.py")

MIRROR_ATTRS = {
    "_phase6_assembly_type",
    "_phase6_last_external_revision",
    "_phase6_last_external_transaction_id",
    "_phase6_active_transaction_id",
}


def _tree(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue392_requires_settings_orchestration_service_without_ui_dependencies():
    assert SERVICE.is_file(), "RED: T3 requires phase6_settings_service.py"
    source = SERVICE.read_text(encoding="utf-8")
    tree = _tree(SERVICE)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = sorted(
        name for name in imports
        if name == "tkinter"
        or name.startswith("tkinter.")
        or name == "fold_designer_bridge"
        or name.startswith("gui")
    )
    assert forbidden == []
    assert "Phase6SettingsTransactionService" in source


def test_issue392_bridge_has_no_rebinding_or_scalar_mirror_writes():
    source = BRIDGE.read_text(encoding="utf-8")
    tree = _tree(BRIDGE)
    funcs = _top_functions(tree)

    assert "controller.bind_state(" not in source
    assert "_phase6_sync_settings_transaction_compatibility_mirrors" not in source
    assert "Phase6SettingsTransactionService" in source

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.ctx, (ast.Store, ast.Del)):
            continue
        if not isinstance(node.value, ast.Name) or node.value.id != "self":
            continue
        if node.attr in MIRROR_ATTRS:
            violations.append((node.attr, node.lineno))
    assert violations == [], f"RED: scalar mirror writes remain: {violations}"

    factory = ast.unparse(funcs["_phase6_settings_transactions"])
    assert "bind_state" not in factory
    assert (
        "_phase6_settings_service" in factory
        or "_phase6_composition" in factory
    )


def test_issue392_command_router_no_longer_requires_sync_mirrors_callback():
    tree = _tree(ROUTER)
    funcs = _top_functions(tree)
    source = ast.unparse(funcs["apply_fold_designer_settings_delta"])
    assert "sync_mirrors" not in source
    assert "push_active_transaction" in source
    assert "restore_active_transaction" in source


def test_issue392_service_preserves_stage_drain_and_transaction_ordering():
    from phase6_settings_service import Phase6SettingsTransactionService

    settings = {"w": 800.0}
    snapshot = {"w": 800.0}
    pending = {}
    box = {"w": 800.0, "h": 1600.0, "d": 300.0}
    service = Phase6SettingsTransactionService(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd=box,
        pending_settings=pending,
    )

    stage = service.stage_setting_update("w", 810.0)
    assert stage.changed is True
    assert stage.schedule_after_ms == 150
    assert settings["w"] == 810.0
    assert snapshot["w"] == 810.0
    assert pending == {"w": 810.0}

    service.install_debounce_job("after#1")
    flush = service.drain_pending()
    assert flush.cancel_job == "after#1"
    assert flush.pending == {"w": 810.0}
    assert pending == {}

    previous = service.push_active_transaction("tx:1")
    assert previous == ""
    assert service.active_transaction_id == "tx:1"
    service.restore_active_transaction(previous)
    assert service.active_transaction_id == ""


def test_issue392_bridge_runtime_maps_keep_stable_identity_after_controller_creation():
    source = BRIDGE.read_text(encoding="utf-8")
    # After T3, runtime refreshes update existing mappings instead of replacing
    # objects already held by the long-lived Settings controller/service.
    forbidden_runtime_replacements = (
        'self._phase6_box_whd = {',
        'self._phase6_pending_settings = {}\n    self._settings_values.update',
    )
    for token in forbidden_runtime_replacements:
        assert token not in source


def test_issue392_t7_composition_preserves_single_settings_service_injection():
    composition = Path("gui_modules/application/fold_designer_adapter.py")
    assert composition.is_file()
    source = composition.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(composition))
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    methods = {
        node.name: ast.unparse(node)
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "Phase6SettingsTransactionService(" in methods["settings_service"]
    assert "Phase6SettingsTransactionController(" in methods["settings_transactions"]
    assert "orchestration=self.settings_service()" in methods["settings_transactions"]
