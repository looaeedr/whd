from __future__ import annotations

import ast
from pathlib import Path


TRANSITIONS = Path("phase6_settings_transitions.py")
CONTROLLER = Path("phase6_settings_transaction_controller.py")

REQUIRED_FUNCTIONS = {
    "normalize_updates",
    "commit_settings",
    "toggle_box_structure_lock",
    "activate_box_structure",
    "apply_box_structure_numeric",
    "reconcile_width_structure",
    "endcap_fw_follow",
    "endcap_fw_override",
    "bottom_wrap",
    "endcap_edge_relation",
    "ensure_corner_part",
    "corner_selection",
    "commit_corner_pair",
    "commit_corner_type",
    "commit_corner_mode",
    "commit_corner_parameters",
    "assembly_intent",
    "replace_corner_state",
    "plan_external_sync",
    "normalize_symmetry",
    "settings_defaults_payload",
    "plan_external_model_change",
    "family_model_transition",
}


def _functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }, tree


def test_issue391_requires_pure_settings_transition_module():
    assert TRANSITIONS.is_file(), (
        "RED: Phase 4 T2 requires phase6_settings_transitions.py"
    )
    funcs, tree = _functions(TRANSITIONS)
    missing = sorted(REQUIRED_FUNCTIONS - set(funcs))
    assert not missing, f"RED: missing pure Settings transitions: {missing}"

    source = TRANSITIONS.read_text(encoding="utf-8")
    assert "self." not in source
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


def test_issue391_controller_delegates_semantics_to_transition_kernel():
    source = CONTROLLER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CONTROLLER))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "phase6_settings_transitions" in imports

    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6SettingsTransactionController"
    )
    methods = {
        node.name: ast.unparse(node)
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required_delegates = {
        "normalize_updates": "settings_transitions.normalize_updates",
        "commit_settings": "settings_transitions.commit_settings",
        "apply_box_structure_numeric": "settings_transitions.apply_box_structure_numeric",
        "commit_endcap_fw_follow": "settings_transitions.endcap_fw_follow",
        "commit_endcap_fw_override": "settings_transitions.endcap_fw_override",
        "commit_bottom_wrap": "settings_transitions.bottom_wrap",
        "commit_endcap_edge_relation": "settings_transitions.endcap_edge_relation",
        "commit_corner_pair": "settings_transitions.commit_corner_pair",
        "commit_corner_type": "settings_transitions.commit_corner_type",
        "commit_corner_mode": "settings_transitions.commit_corner_mode",
        "commit_corner_parameters": "settings_transitions.commit_corner_parameters",
        "commit_assembly_intent": "settings_transitions.assembly_intent",
        "plan_external_sync": "_orchestration.plan_external_sync",
        "commit_symmetry": "settings_transitions.normalize_symmetry",
        "commit_reconciled_width_structure": "settings_transitions.reconcile_width_structure",
        "commit_family_model_transition": "settings_transitions.family_model_transition",
        "plan_external_model_change": "settings_transitions.plan_external_model_change",
    }
    missing = [
        (method, token)
        for method, token in required_delegates.items()
        if token not in methods.get(method, "")
    ]
    assert missing == [], f"RED: controller still owns T2 transition formulas: {missing}"


def test_issue391_pure_transition_smoke_contracts():
    from ae_engine.sheetmetal_geometry import CornerTypeId
    from phase6_box_body_structure import (
        BoxBodyStructureType,
        default_box_body_structure_state,
    )
    from phase6_settings_transitions import (
        activate_box_structure,
        apply_box_structure_numeric,
        normalize_updates,
        plan_external_sync,
    )

    clean = normalize_updates(
        {"w": 500.0, "flag": False, "ui_text_size": "small"},
        {"w": "640", "flag": 1, "ui_text_size": "大", "unknown": 99},
    )
    assert clean == {"w": 640.0, "flag": True, "ui_text_size": "large"}

    state = activate_box_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        800.0,
    )
    state = apply_box_structure_numeric(
        state,
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        "left",
        300.0,
        total_w=800.0,
    )
    cfg = state["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    assert cfg["left_w"] == 300.0
    assert cfg["right_w"] == 500.0

    plan = plan_external_sync(
        {
            "origin": "main_gui",
            "revision": 2,
            "transaction_id": "main:2",
            "delta": {"settings": {"w": 810}},
        },
        last_external_revision=1,
    )
    assert plan.accepted is True
    assert plan.settings == {"w": 810}
    assert CornerTypeId.INSERT_OVERLAY.value == "INSERT_OVERLAY"


def test_issue391_t3_service_keeps_external_sync_semantics_in_pure_kernel():
    service = Path("phase6_settings_service.py")
    assert service.is_file()
    source = service.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(service))
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6SettingsTransactionService"
    )
    methods = {
        node.name: ast.unparse(node)
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "settings_transitions.plan_external_sync" in methods["plan_external_sync"]
