from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
COMPOSITION = Path("gui_modules/application/fold_designer_adapter.py")
SECOND_ROOT = Path("gui_modules/application/fold_designer_composition.py")

DIRECT_CONSTRUCTION_TOKENS = (
    "Phase6SettingsTransactionService(",
    "Phase6SettingsTransactionController(",
    "Phase6FinalSceneRenderer(",
    "Phase6FinalSceneViewAdapter(",
    "FinalSceneDependencies(",
)

APPLICATION_CONTROLLER_TOKENS = (
    "Phase6WorkspaceNavigationController(",
    "Phase6RegistryDiagnosticsController(",
)

DEEP_MODULES = (
    Path("phase6_settings_contracts.py"),
    Path("phase6_settings_transitions.py"),
    Path("phase6_settings_service.py"),
    Path("phase6_settings_transaction_controller.py"),
    Path("phase6_final_scene_contracts.py"),
    Path("phase6_final_scene_projection.py"),
    Path("phase6_final_scene_renderer.py"),
    Path("phase6_final_scene_view.py"),
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def _facade_binding_count() -> int:
    tree = _tree(BRIDGE)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name)
             and node.func.id == "install_fold_designer_bridge_facade")
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "install_fold_designer_bridge_facade"
            )
        )
    ]
    assert len(calls) == 1, f"expected one facade install call, got {len(calls)}"
    call = calls[0]
    dict_args = [arg for arg in call.args if isinstance(arg, ast.Dict)]
    assert len(dict_args) == 1, "facade binding dict not found"
    return len(dict_args[0].keys)


def test_issue396_uses_existing_adapter_as_single_composition_root():
    source = COMPOSITION.read_text(encoding="utf-8")
    assert not SECOND_ROOT.exists(), (
        "RED: competing fold_designer_composition.py root must not exist"
    )
    assert "class Phase6FoldDesignerComposition" in source
    assert "class FinalSceneCompositionPorts" in source


def test_issue396_bridge_no_longer_constructs_deep_settings_or_scene_owners():
    bridge = BRIDGE.read_text(encoding="utf-8")
    violations = [
        token for token in DIRECT_CONSTRUCTION_TOKENS if token in bridge
    ]
    assert violations == [], (
        "RED: bridge still constructs deep Settings/Final Scene owners: "
        f"{violations}"
    )
    assert "Phase6FoldDesignerComposition" in bridge


def test_issue396_composition_root_owns_all_deep_construction():
    source = COMPOSITION.read_text(encoding="utf-8")
    missing = [
        token for token in DIRECT_CONSTRUCTION_TOKENS if token not in source
    ]
    assert missing == [], (
        "RED: composition root does not own required construction: "
        f"{missing}"
    )


def test_c0_bridge_no_longer_constructs_application_controllers():
    bridge = BRIDGE.read_text(encoding="utf-8")
    violations = [
        token for token in APPLICATION_CONTROLLER_TOKENS if token in bridge
    ]
    assert violations == [], (
        "C0 RED: bridge still constructs application controllers outside the "
        f"single Phase6FoldDesignerComposition root: {violations}"
    )


def test_c0_single_composition_root_constructs_application_controllers():
    source = COMPOSITION.read_text(encoding="utf-8")
    missing = [
        token for token in APPLICATION_CONTROLLER_TOKENS if token not in source
    ]
    assert missing == [], (
        "C0 RED: existing Phase6FoldDesignerComposition has not absorbed "
        f"application controller construction: {missing}"
    )


def test_issue396_no_direct_phase6_app_class_wiring_and_facade_does_not_grow():
    source = BRIDGE.read_text(encoding="utf-8")
    tree = _tree(BRIDGE)
    direct = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        else:
            targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "Phase6FoldDesignerApp"
            ):
                direct.append((target.attr, getattr(node, "lineno", 0)))
    assert direct == [], f"DIRECT_CLASS_WIRING remains: {direct}"
    assert _facade_binding_count() <= 70


def test_issue396_deep_modules_do_not_reverse_import_bridge_or_gui():
    violations = {}
    for path in DEEP_MODULES:
        imports = _imports(path)
        bad = sorted(
            name for name in imports
            if name == "fold_designer_bridge"
            or name.startswith("fold_designer_bridge.")
            or name.startswith("gui_modules")
        )
        if bad:
            violations[str(path)] = bad
    assert violations == {}


def test_issue396_settings_t3_gates_remain_zero():
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert "controller.bind_state(" not in bridge
    assert "_phase6_sync_settings_transaction_compatibility_mirrors" not in bridge

    settings_core = (
        Path("phase6_settings_contracts.py"),
        Path("phase6_settings_transitions.py"),
        Path("phase6_settings_service.py"),
    )
    for path in settings_core:
        source = path.read_text(encoding="utf-8")
        imports = _imports(path)
        assert "tkinter" not in imports
        assert not any(name.startswith("tkinter.") for name in imports)
        assert "fold_designer_bridge" not in imports
        assert "phase6_settings_panel" not in imports


def test_issue396_final_scene_t6_gates_remain_zero():
    bridge = BRIDGE.read_text(encoding="utf-8")
    renderer = Path("phase6_final_scene_renderer.py").read_text(encoding="utf-8")
    view = Path("phase6_final_scene_view.py").read_text(encoding="utf-8")
    contracts = Path("phase6_final_scene_contracts.py").read_text(encoding="utf-8")

    assert "_phase6_sync_final_scene_view_compatibility_mirrors" not in bridge
    assert "mirror_view_state" not in contracts
    assert "self.owner" not in renderer
    assert "self.owner" not in view
    assert "def _service(" not in view
    assert "self.services" not in view
