from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
CONTROLLER = Path("phase6_registry_diagnostics_controller.py")
PANEL = Path("phase6_registry_diagnostics_panel.py")

TARGETS = {
    "_phase6_registry_validate_formula_form",
    "_phase6_registry_candidate_form_is_current",
    "_phase6_registry_save_candidate_form",
    "_phase6_registry_run_formula_matrix",
    "_phase6_registry_preview_assembly_3d",
    "_phase6_registry_promote_form",
    "_phase6_joint_form_add",
    "_phase6_joint_form_delete",
    "_phase6_create_relief_promotion_candidates",
    "_phase6_update_assembly_diagnostic_status",
}

ZERO_CONSUMER_REMOVED = {
    "_phase6_registry_require_current_candidate",
    "_phase6_selected_joint_diagnostic",
}

REQUIRED_METHODS = {
    "validate_formula",
    "candidate_is_current",
    "require_current_candidate",
    "save_candidate",
    "run_formula_matrix",
    "merge_3d_evidence",
    "promote_candidate",
    "load_rule_records",
    "rule_record",
    "route_joint_add",
    "route_joint_delete",
    "build_promotion_candidates",
    "diagnostic_ids",
    "selected_diagnostic",
    "diagnostic_status",
}

STATE_ATTRS = {
    "_phase6_registry_candidate_id",
    "_phase6_registry_candidate_record",
    "_phase6_registry_regression_evidence",
    "_phase6_registry_rule_records",
    "_phase6_last_relief_promotion_candidates",
}

DIRECT_BACKEND = {
    "save_relief_rule_candidate",
    "promote_relief_rule_candidate",
    "load_external_relief_rule_records",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue368_requires_registry_diagnostics_controller_without_solver_ownership():
    assert CONTROLLER.is_file(), "RED: missing T4 registry diagnostics controller"
    tree = _tree(CONTROLLER)
    methods = {
        node.name
        for cls in tree.body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6RegistryDiagnosticsController"
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(REQUIRED_METHODS - methods)
    assert missing == [], f"RED: missing T4 controller methods: {missing}"

    source = CONTROLLER.read_text(encoding="utf-8")
    forbidden = (
        "fold_designer_bridge",
        "phase6_manufacturing_service",
        "phase6_manufacturing_geometry",
        "solve_world_backprojected_endcap_relief",
    )
    assert not [token for token in forbidden if token in source]


def test_issue368_bridge_has_no_registry_state_machine_or_backend_ownership():
    funcs = _functions(_tree(BRIDGE))
    missing = sorted(TARGETS - set(funcs))
    assert missing == []
    assert ZERO_CONSUMER_REMOVED.isdisjoint(funcs)

    violations = []
    for name in sorted(TARGETS):
        node = funcs[name]
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Attribute)
                and isinstance(child.ctx, (ast.Store, ast.Del))
                and isinstance(child.value, ast.Name)
                and child.value.id == "self"
                and child.attr in STATE_ATTRS
            ):
                violations.append((name, "STATE_WRITE", child.attr, child.lineno))
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id in DIRECT_BACKEND:
                    violations.append((name, "DIRECT_BACKEND", child.func.id, child.lineno))
    assert violations == [], (
        "RED: bridge still owns T4 registry/diagnostic state machine: "
        f"{violations}"
    )


def test_issue368_bridge_commands_delegate_to_registry_controller():
    funcs = _functions(_tree(BRIDGE))
    assert ZERO_CONSUMER_REMOVED.isdisjoint(funcs)
    expected = {
        "_phase6_registry_validate_formula_form": "validate_formula",
        "_phase6_registry_candidate_form_is_current": "candidate_is_current",
        "_phase6_registry_save_candidate_form": "save_candidate",
        "_phase6_registry_run_formula_matrix": "run_formula_matrix",
        "_phase6_registry_preview_assembly_3d": "merge_3d_evidence",
        "_phase6_registry_promote_form": "promote_candidate",
        "_phase6_joint_form_add": "route_joint_add",
        "_phase6_joint_form_delete": "route_joint_delete",
        "_phase6_create_relief_promotion_candidates": "build_promotion_candidates",
        "_phase6_update_assembly_diagnostic_status": "diagnostic_status",
    }
    missing=[]
    for name,method in expected.items():
        if method not in ast.unparse(funcs[name]):
            missing.append((name,method))
    assert missing == [], f"RED: bridge T4 delegates missing: {missing}"

def test_issue446_registry_diagnostics_presentation_moves_to_panel_without_semantic_ownership():
    assert PANEL.is_file(), "T4 v3: missing Registry diagnostics presentation owner"
    tree = _tree(PANEL)
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    panel = classes.get("Phase6RegistryDiagnosticsPanel")
    assert panel is not None
    methods = {
        node.name
        for node in panel.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required = {
        "open_registry_editor",
        "build_assembly_diagnostics",
        "refresh_rule_rows",
        "populate_rule_form",
        "refresh_joint_rows",
        "refresh_joint_diagnostic_menu",
        "draw_registry_preview",
    }
    assert required <= methods

    source = PANEL.read_text(encoding="utf-8")
    forbidden = (
        "fold_designer_bridge",
        "ae_engine.certified_relief_registry",
        "save_relief_rule_candidate",
        "promote_relief_rule_candidate",
        "evaluate_editable_endcap_rule_record",
        "build_relief_promotion_candidate",
        "_phase6_add_user_joint",
        "_phase6_delete_user_joint",
        "resolve_manufacturing_geometry",
    )
    assert not [token for token in forbidden if token in source]


def test_issue446_bridge_keeps_semantic_registry_callbacks_but_not_selected_tk_constructors():
    funcs = _functions(_tree(BRIDGE))
    selected_presentation = {
        "_phase6_form_choice",
        "_phase6_registry_preview_2d",
        "_phase6_registry_refresh_rule_tree",
        "_phase6_registry_rule_selected",
        "_phase6_joint_form_refresh",
        "_phase6_open_relief_registry_form",
        "_phase6_refresh_joint_diagnostic_menu",
        "_phase6_build_assembly_diagnostics",
    }
    assert not (selected_presentation & set(funcs))
    semantic_callbacks = {
        "_phase6_registry_validate_formula_form",
        "_phase6_registry_candidate_form_is_current",
        "_phase6_registry_save_candidate_form",
        "_phase6_registry_run_formula_matrix",
        "_phase6_registry_preview_assembly_3d",
        "_phase6_registry_promote_form",
        "_phase6_joint_form_add",
        "_phase6_joint_form_delete",
        "_phase6_create_relief_promotion_candidates",
        "_phase6_update_assembly_diagnostic_status",
    }
    assert semantic_callbacks <= set(funcs)
    assert ZERO_CONSUMER_REMOVED.isdisjoint(funcs)

