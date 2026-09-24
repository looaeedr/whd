from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
CONTROLLER = Path("phase6_settings_transaction_controller.py")

T2_FUNCTIONS = {
    "_phase6_apply_setting_updates",
    "_phase6_flush_pending_settings",
    "_phase6_stage_setting_update",
    "_phase6_ensure_corner_part",
    "_phase6_corner_pair_var_changed",
    "_phase6_corner_type_selected",
    "_phase6_corner_mode_selected",
    "_phase6_corner_target_var_changed",
    "_phase6_confirm_corner_transaction",
    "_phase6_cancel_corner_transaction",
    "_phase6_commit_endcap_fw_state",
    "_phase6_set_endcap_fw_follow",
    "_phase6_set_endcap_fw_override",
    "_phase6_commit_box_structure_state",
    "_phase6_toggle_box_structure_lock",
    "_phase6_select_box_structure_type",
    "_phase6_apply_box_structure_numeric",
    "_phase6_on_assembly_type_selected",
    "_phase6_on_endcap_edge_relation_selected",
    "_phase6_commit_base_plate_edge_shrink",
    "_phase6_on_box_symmetry_changed",
    "_phase6_commit_receiving_bottom_wrap_controls",
    "_phase6_apply_external_assembly_type",
    "_phase6_apply_external_corner_state",
    "_phase6_apply_external_settings",
    "_phase6_apply_external_model",
    "_phase6_apply_external_sync",
    "_phase6_save_settings_context_as_defaults",
    "_phase6_apply_settings_delta",
}

CANONICAL_ATTRS = {
    "_settings_values",
    "_phase6_input_snapshot",
    "_phase6_box_whd",
    "_phase6_pending_settings",
    "_phase6_settings_debounce_job",
    "_phase6_corner_state",
    "_phase6_corner_pair_same",
    "_phase6_endcap_fw_state",
    "_phase6_endcap_bottom_wrap_state",
    "_phase6_assembly_type",
    "_phase6_active_transaction_id",
    "_phase6_last_external_revision",
    "_phase6_last_external_transaction_id",
}

MUTATING_METHODS = {
    "update", "setdefault", "pop", "clear", "append", "extend", "remove",
}

DIRECT_SEMANTIC_MUTATORS = {
    "set_endcap_fw_follow",
    "set_endcap_fw_override",
    "commit_endcap_fw",
    "commit_endcap_bottom_wrap",
    "apply_box_assembly_type_to_raw_state",
    "set_active_structure",
    "activate_structure_with_defaults",
    "set_structure_locked",
    "set_two_piece_width",
    "set_three_piece_width",
    "update_structure_config",
    "set_join_seam_bend",
    "set_side_back_geometry",
}

WORKSPACE_MUTATORS = {
    "set_box_body_structure_state",
    "mark_dirty",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _self_attr(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return node.attr
    return None


def _root_self_attr(node: ast.AST) -> str | None:
    cur = node
    while isinstance(cur, (ast.Attribute, ast.Subscript)):
        if isinstance(cur, ast.Attribute):
            if isinstance(cur.value, ast.Name) and cur.value.id == "self":
                return cur.attr
            cur = cur.value
        else:
            cur = cur.value
    return None


def _bridge_violations(tree: ast.Module):
    funcs = _functions(tree)
    moved_to_controller = {
        "_phase6_apply_settings_delta",
        "_phase6_cancel_corner_transaction",
        "_phase6_confirm_corner_transaction",
        "_phase6_set_endcap_fw_follow",
        "_phase6_toggle_box_structure_lock",
    }
    missing = sorted(T2_FUNCTIONS - set(funcs))
    assert set(missing) <= moved_to_controller, f"unexpected missing T2 functions: {missing}"

    controller_methods = {
        node.name
        for cls in _tree(CONTROLLER).body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6SettingsTransactionController"
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for method in ("toggle_box_structure_lock", "commit_endcap_fw_follow"):
        assert method in controller_methods

    violations: list[tuple] = []
    for name in sorted(T2_FUNCTIONS & set(funcs)):
        fn = funcs[name]
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
                attr = _self_attr(node)
                if attr in CANONICAL_ATTRS:
                    violations.append((name, "ATTR_WRITE", attr, node.lineno))

            if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
                root = _root_self_attr(node)
                if root in CANONICAL_ATTRS:
                    violations.append((name, "ITEM_WRITE", root, node.lineno))

            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    root = _root_self_attr(node.func.value)
                    if root in CANONICAL_ATTRS and node.func.attr in MUTATING_METHODS:
                        violations.append((name, "MUTATING_CALL", f"{root}.{node.func.attr}", node.lineno))
                    if (
                        isinstance(node.func.value, ast.Attribute)
                        and isinstance(node.func.value.value, ast.Name)
                        and node.func.value.value.id == "self"
                        and node.func.value.attr == "designer_workspace"
                        and node.func.attr in WORKSPACE_MUTATORS
                    ):
                        violations.append((name, "WORKSPACE_MUTATION", node.func.attr, node.lineno))
                elif isinstance(node.func, ast.Name) and node.func.id in DIRECT_SEMANTIC_MUTATORS:
                    violations.append((name, "SEMANTIC_MUTATOR", node.func.id, node.lineno))
    return sorted(set(violations))


def test_issue366_requires_explicit_settings_transaction_controller():
    assert CONTROLLER.is_file(), (
        "RED: Phase 3 T2 requires an application-level settings transaction "
        "controller; bridge still owns transaction state and semantic commit ordering"
    )
    source = CONTROLLER.read_text(encoding="utf-8")
    forbidden = (
        "tkinter",
        "fold_designer_bridge",
        "phase6_manufacturing_service",
        "phase6_manufacturing_geometry",
    )
    assert not [name for name in forbidden if name in source]


def test_issue366_bridge_has_no_canonical_t2_transaction_ownership():
    violations = _bridge_violations(_tree(BRIDGE))
    assert violations == [], (
        "RED: bridge still owns T2 settings/corner/structure transaction state: "
        f"{violations}"
    )


def test_issue366_baseline_debounce_and_event_order_is_characterized():
    tree = _tree(BRIDGE)
    funcs = _functions(tree)

    stage = funcs["_phase6_stage_setting_update"]
    after_calls = []
    for node in ast.walk(stage):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "after"
        ):
            after_calls.append(node)
    assert len(after_calls) == 1
    call = after_calls[0]
    assert len(call.args) >= 2
    assert isinstance(call.args[0], ast.Attribute)
    assert call.args[0].attr == "schedule_after_ms"

    controller_tree = _tree(CONTROLLER)
    controller_classes = [
        node for node in controller_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6SettingsTransactionController"
    ]
    assert len(controller_classes) == 1
    debounce_assigns = [
        node for node in controller_classes[0].body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "DEBOUNCE_MS"
            for target in node.targets
        )
    ]
    assert len(debounce_assigns) == 1
    assert isinstance(debounce_assigns[0].value, ast.Constant)
    assert debounce_assigns[0].value.value == 150

    flush = funcs["_phase6_flush_pending_settings"]
    cancel_lines = []
    apply_lines = []
    for node in ast.walk(flush):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "after_cancel":
            cancel_lines.append(node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_phase6_apply_setting_updates":
            apply_lines.append(node.lineno)
    assert cancel_lines and apply_lines
    assert min(cancel_lines) < min(apply_lines), (cancel_lines, apply_lines)
