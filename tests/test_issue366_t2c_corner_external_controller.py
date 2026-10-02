from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


BRIDGE = Path("fold_designer_bridge.py")
CONTROLLER = Path("phase6_settings_transaction_controller.py")

REQUIRED_CONTROLLER_METHODS = {
    "ensure_corner_part",
    "commit_corner_pair",
    "commit_corner_type",
    "commit_corner_mode",
    "commit_corner_parameters",
    "commit_assembly_intent",
    "replace_corner_state",
    "plan_external_sync",
    "push_active_transaction",
    "restore_active_transaction",
    "commit_symmetry",
    "settings_defaults_payload",
    "plan_external_model_change",
}

EXPECTED_BRIDGE_DELEGATES = {
    "_phase6_ensure_corner_part": "ensure_corner_part",
    "_phase6_corner_pair_var_changed": "commit_corner_pair",
    "_phase6_corner_type_selected": "commit_corner_type",
    "_phase6_corner_mode_selected": "commit_corner_mode",
    "_phase6_corner_target_var_changed": "commit_corner_parameters",
    "_phase6_on_assembly_type_selected": "commit_assembly_intent",
    "_phase6_apply_external_assembly_type": "commit_assembly_intent",
    "_phase6_apply_external_corner_state": "replace_corner_state",
    "_phase6_apply_external_sync": "plan_external_sync",
    "_phase6_apply_settings_delta": "apply_fold_designer_settings_delta",
    "_phase6_on_box_symmetry_changed": "commit_symmetry",
    "_phase6_save_settings_context_as_defaults": "settings_defaults_payload",
    "_phase6_apply_external_model": "plan_external_model_change",
}

FORBIDDEN_DIRECT_ATTR_WRITES = {
    "_phase6_corner_state",
    "_phase6_corner_pair_same",
    "_phase6_assembly_type",
    "_phase6_last_external_revision",
    "_phase6_last_external_transaction_id",
    "_phase6_active_transaction_id",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue366_t2c_requires_corner_external_transaction_controller_api():
    tree = _tree(CONTROLLER)
    methods = {
        node.name
        for cls in tree.body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6SettingsTransactionController"
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(REQUIRED_CONTROLLER_METHODS - methods)
    assert missing == [], f"RED: missing T2C controller methods: {missing}"


def test_issue366_t2c_bridge_delegates_transaction_semantics_and_keeps_only_effects():
    funcs = _functions(_tree(BRIDGE))
    moved_to_controller = {"_phase6_apply_settings_delta"}
    missing_funcs = sorted(set(EXPECTED_BRIDGE_DELEGATES) - set(funcs))
    assert set(missing_funcs) <= moved_to_controller

    violations = []
    for name, delegate in EXPECTED_BRIDGE_DELEGATES.items():
        if name not in funcs:
            continue
        node = funcs[name]
        source = ast.unparse(node)
        if delegate not in source:
            violations.append((name, "MISSING_DELEGATE", delegate))
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Attribute)
                and isinstance(child.ctx, (ast.Store, ast.Del))
                and isinstance(child.value, ast.Name)
                and child.value.id == "self"
                and child.attr in FORBIDDEN_DIRECT_ATTR_WRITES
            ):
                violations.append((name, "DIRECT_ATTR_WRITE", child.attr, child.lineno))
            if (
                isinstance(child, ast.Subscript)
                and isinstance(child.ctx, (ast.Store, ast.Del))
                and isinstance(child.value, ast.Attribute)
                and isinstance(child.value.value, ast.Name)
                and child.value.value.id == "self"
                and child.value.attr in FORBIDDEN_DIRECT_ATTR_WRITES
            ):
                violations.append((name, "DIRECT_ITEM_WRITE", child.value.attr, child.lineno))

    semantic_forbidden = {
        "_phase6_corner_pair_var_changed": ("state[", "pairs["),
        "_phase6_corner_type_selected": ("state[", "_phase6_selection_to_raw"),
        "_phase6_corner_mode_selected": ("state[", "_phase6_selection_to_raw"),
        "_phase6_corner_target_var_changed": ("state[", "_phase6_selection_to_raw"),
        "_phase6_apply_external_assembly_type": ("apply_box_assembly_type_to_raw_state",),
    }
    for name, tokens in semantic_forbidden.items():
        source = ast.unparse(funcs[name])
        for token in tokens:
            if token in source:
                violations.append((name, "SEMANTIC_MUTATION_IN_BRIDGE", token))

    assert violations == [], (
        "RED: bridge still owns T2C corner/assembly/external transaction semantics: "
        f"{violations}"
    )


def test_issue366_t2c_controller_semantics_when_api_present():
    tree = _tree(CONTROLLER)
    methods = {
        node.name
        for cls in tree.body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6SettingsTransactionController"
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if not REQUIRED_CONTROLLER_METHODS <= methods:
        return

    from ae_engine.sheetmetal_geometry import (
        CornerTypeId,
        CrossCornerMode,
        CornerDirection,
    )
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    dirty = []
    workspace = SimpleNamespace(mark_dirty=lambda: dirty.append(True))
    settings = {"w": 800.0, "h": 1600.0, "d": 300.0, "fw": 25.0}
    snapshot = {
        "model": "金庫型",
        "w": 800.0,
        "h": 1600.0,
        "d": 300.0,
        "fw": 25.0,
        "existing_parts": ["box_body", "head", "tail"],
    }
    corner_state = {}
    corner_pairs = {}
    owner = Phase6SettingsTransactionController(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd={"w": 800.0, "h": 1600.0, "d": 300.0},
        workspace=workspace,
        corner_state=corner_state,
        corner_pair_same=corner_pairs,
        assembly_type=CornerTypeId.INSERT_OVERLAY,
    )

    state, pairs = owner.ensure_corner_part("head")
    assert set(state) == {"top_left", "top_right", "bottom_left", "bottom_right"}
    assert pairs == {"top": True, "bottom": True}

    owner.commit_corner_type("head", "top", CornerTypeId.OVERLAY)
    assert corner_state["head"]["top_left"]["type_id"] == "OVERLAY"
    assert corner_state["head"]["top_right"]["type_id"] == "OVERLAY"

    owner.commit_corner_pair("head", "top", False)
    assert corner_pairs["head"]["top"] is False

    owner.commit_corner_type("head", "top_left", CornerTypeId.CROSS)
    owner.commit_corner_mode("head", "top_left", CrossCornerMode.RETAIN)
    owner.commit_corner_parameters(
        "head",
        "top_left",
        amount_t=1.5,
        direction=CornerDirection.WIDTH,
    )
    assert corner_state["head"]["top_left"]["cross_mode"] == "retain"
    assert corner_state["head"]["top_left"]["amount_t"] == 1.5

    stable = owner.commit_assembly_intent(
        CornerTypeId.OVERLAY,
        available_parts=("box_body", "head", "tail"),
        project_legacy_corner=False,
    )
    assert getattr(stable, "value", stable) == "OVERLAY"
    assert snapshot["assembly_type"] == "OVERLAY"
    assert snapshot["assembly_joints"]

    replacement = {"door": {"top_left": {"type_id": "CROSS", "rotation_quadrants": 0}}}
    owner.replace_corner_state(replacement, {"door": {"top": False, "bottom": True}})
    assert corner_state == replacement
    assert corner_pairs["door"]["top"] is False

    plan = owner.plan_external_sync({
        "origin": "main_gui",
        "revision": 2,
        "transaction_id": "main:2",
        "delta": {"settings": {"w": 810.0}},
    })
    assert plan.accepted is True
    assert plan.settings == {"w": 810.0}
    stale = owner.plan_external_sync({
        "origin": "main_gui",
        "revision": 1,
        "transaction_id": "main:1",
        "delta": {"settings": {"w": 820.0}},
    })
    assert stale.accepted is False

    previous = owner.push_active_transaction("tx:1")
    assert owner.active_transaction_id == "tx:1"
    owner.restore_active_transaction(previous)
    assert owner.active_transaction_id == ""

    state_obj = SimpleNamespace(symmetric=True)
    owner.commit_symmetry(state_obj, False)
    assert state_obj.symmetric is False

    payload = owner.settings_defaults_payload("head")
    assert payload[0] == "head"
    assert payload[1] == settings
    assert payload[2] == corner_state
    assert payload[3] == corner_pairs

    model_plan = owner.plan_external_model_change("受電箱")
    assert model_plan.changed is True
    assert model_plan.target_model == "受電箱"


def test_issue366_t2c_application_router_preserves_transaction_push_restore():
    from gui_modules.application import command_router

    source = Path(command_router.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(command_router.__file__))
    funcs = _functions(tree)
    node = funcs["apply_fold_designer_settings_delta"]
    rendered = ast.unparse(node)
    assert "push_active_transaction" in rendered
    assert "restore_active_transaction" in rendered
