from __future__ import annotations

import ast
from pathlib import Path

BRIDGE = Path("fold_designer_bridge.py")
ROUTER = Path("gui_modules/application/command_router.py")
ADAPTER = Path("gui_modules/application/fold_designer_adapter.py")
LIFECYCLE = Path("gui_modules/application/lifecycle.py")
GUI = Path("gui.py")

REQUIRED_ROUTER_FUNCTIONS = {
    "execute_fold_designer_update_reasons",
    "submit_fold_designer_update_intent",
    "flush_fold_designer_update_intents",
    "queue_fold_designer_update",
    "install_fold_designer_keyboard_shortcuts",
}

EXPECTED_BRIDGE_DELEGATES = {
    "_phase6_execute_update_intents": "execute_fold_designer_update_reasons",
    "_phase6_flush_update_intents": "flush_fold_designer_update_intents",
    "_phase6_submit_update_intent": "submit_fold_designer_update_intent",
    "_phase6_queue_update": "queue_fold_designer_update",
    "_phase6_install_keyboard_shortcuts": "install_fold_designer_keyboard_shortcuts",
}

FACADE_FUNCTIONS = {
    "_phase6_execute_update_intents",
    "_phase6_flush_update_intents",
    "_phase6_submit_update_intent",
    "_phase6_apply_settings_delta",
    "_phase6_switch_active_part",
    "_phase6_publish_if_changed",
    "_phase6_preview_aware_do_update",
    "_phase6_set_3d_preview_enabled",
    "_phase6_refresh_3d_preview",
    "_phase6_queue_update",
    "_phase6_install_keyboard_shortcuts",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue371_reuses_application_update_scheduler_for_fold_designer():
    tree = _tree(ROUTER)
    funcs = _functions(tree)
    missing = sorted(REQUIRED_ROUTER_FUNCTIONS - set(funcs))
    assert missing == [], (
        "RED: command_router lacks Fold Designer update/lifecycle routing: "
        f"{missing}"
    )

    scheduler = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_Phase6UpdateScheduler"
    )
    init = next(
        node for node in scheduler.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    args = {arg.arg for arg in init.args.args + init.args.kwonlyargs}
    assert "executor" in args, (
        "RED: canonical _Phase6UpdateScheduler cannot accept a Fold Designer executor"
    )


def test_issue371_bridge_update_and_keyboard_facades_are_thin_delegates():
    funcs = _functions(_tree(BRIDGE))
    violations = []
    for name, delegate in EXPECTED_BRIDGE_DELEGATES.items():
        node = funcs.get(name)
        if node is None:
            if name == "_phase6_flush_update_intents":
                continue
            violations.append((name, "MISSING"))
            continue
        source = ast.unparse(node)
        if delegate not in source:
            violations.append((name, "MISSING_DELEGATE", delegate))
        if any(isinstance(child, (ast.For, ast.While)) for child in ast.walk(node)):
            violations.append((name, "FACADE_LOOP"))
        if any(isinstance(child, ast.If) for child in ast.walk(node)):
            violations.append((name, "FACADE_BRANCH"))
    assert violations == [], (
        "RED: bridge still owns T7 update/keyboard orchestration: "
        f"{violations}"
    )


def test_issue371_all_residual_facades_have_no_loops_or_domain_branches():
    funcs = _functions(_tree(BRIDGE))
    violations = []
    for name in sorted(FACADE_FUNCTIONS):
        node = funcs.get(name)
        if node is None:
            continue
        loops = sum(
            isinstance(child, (ast.For, ast.While))
            for child in ast.walk(node)
        )
        branches = sum(isinstance(child, ast.If) for child in ast.walk(node))
        if loops:
            violations.append((name, "LOOPS", loops))
        if branches:
            violations.append((name, "BRANCHES", branches))
    assert violations == [], (
        "RED: bridge compatibility facade still owns control flow: "
        f"{violations}"
    )


def test_issue371_class_wiring_is_installed_by_application_adapter():
    adapter_funcs = _functions(_tree(ADAPTER))
    assert "install_fold_designer_bridge_facade" in adapter_funcs, (
        "RED: missing application-owned Fold Designer facade installer"
    )

    bridge_tree = _tree(BRIDGE)
    direct = []
    for node in bridge_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "Phase6FoldDesignerApp"
            ):
                direct.append((target.attr, node.lineno))
    assert direct == [], (
        "RED: bridge still performs direct Phase6FoldDesignerApp class wiring: "
        f"{direct}"
    )


def test_issue371_lifecycle_has_no_reverse_bridge_import_and_gui_injects_factory():
    lifecycle_tree = _tree(LIFECYCLE)
    reverse = [
        (node.module, [alias.name for alias in node.names], node.lineno)
        for node in ast.walk(lifecycle_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "fold_designer_bridge"
    ]
    assert reverse == [], (
        "RED: application lifecycle still reverse-imports fold_designer_bridge: "
        f"{reverse}"
    )

    gui_source = GUI.read_text(encoding="utf-8")
    assert "_fold_designer_factory = Phase6FoldDesignerApp" in gui_source, (
        "RED: composition root does not inject the Fold Designer factory"
    )
