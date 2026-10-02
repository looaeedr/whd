from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
CONTROLLER = Path("phase6_workspace_navigation_controller.py")

T1_STATE_MACHINE_FUNCTIONS = {
    "_phase6_sync_authoritative_derived_parts",
    "_phase6_resolve_operator_part_key",
    "_phase6_select_corner_data_part",
    "_phase6_show_assembly",
    "_fix11_select_part",
    "_fix11_activate_selected_part",
    "_fix11_remove_selected_part",
    "_fix11_activate_part",
    "_fix11_add_part",
    "_fix11_remove_part",
    "_fix11_export",
    "_phase6_refresh_linked_part_profiles",
}

FORBIDDEN_WORKSPACE_MUTATORS = {
    "add_part",
    "remove_part",
    "select_part",
    "begin_switch",
    "finish_switch",
    "sync_derived_parts",
    "stash_profiles",
    "stash_features",
    "stash_face_features",
    "mark_dirty",
    "mark_clean",
}

FORBIDDEN_WORKSPACE_ASSIGNS = {
    "active_part",
    "selected_part",
    "dirty",
    "switching",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _is_designer_workspace_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr == "designer_workspace"
        ):
            return True
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_designer_workspace"
        ):
            return True
    if isinstance(node, ast.Name) and node.id in {"workspace", "ws"}:
        return True
    return False


def test_issue365_requires_explicit_workspace_navigation_controller_owner():
    assert CONTROLLER.is_file(), (
        "RED: Phase 3 T1 requires an application-level workspace/navigation "
        "controller; current bridge still owns transition orchestration"
    )

    source = CONTROLLER.read_text(encoding="utf-8")
    forbidden = (
        "tkinter",
        "fold_designer_bridge",
        "phase6_manufacturing_service",
        "phase6_manufacturing_geometry",
    )
    assert not [name for name in forbidden if name in source]


def test_issue365_bridge_has_no_direct_workspace_mutation_in_t1_state_machine_functions():
    tree = _tree(BRIDGE)
    funcs = _functions(tree)
    moved_to_owner = {"_fix11_activate_selected_part"}
    missing = sorted(T1_STATE_MACHINE_FUNCTIONS - set(funcs))
    assert set(missing) <= moved_to_owner

    violations = []
    for name in sorted(T1_STATE_MACHINE_FUNCTIONS & set(funcs)):
        fn = funcs[name]
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if (
                    node.func.attr in FORBIDDEN_WORKSPACE_MUTATORS
                    and _is_designer_workspace_expr(node.func.value)
                ):
                    violations.append((name, node.func.attr, node.lineno))
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, (ast.Store, ast.Del))
                and node.attr in FORBIDDEN_WORKSPACE_ASSIGNS
                and _is_designer_workspace_expr(node.value)
            ):
                violations.append((name, node.attr, node.lineno))

    assert violations == [], (
        "RED: bridge still owns T1 workspace/navigation state transitions: "
        f"{violations}"
    )


def test_issue365_navigation_controller_contract_when_present():
    if not CONTROLLER.is_file():
        return

    import phase6_workspace_navigation_controller as nav
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "door"],
        "active_part": "head",
        "part_profiles": {},
    })
    controller = nav.Phase6WorkspaceNavigationController(
        ws,
        remembered_box_body_child=None,
    )

    plan = controller.plan_activation(
        "door",
        initial=False,
        leaving_non_single_view=False,
    )
    assert plan.accepted is True
    assert plan.previous_active == "head"
    assert plan.resolved_key == "door"
    assert plan.save_outgoing is True
    assert plan.noop is False

    controller.begin_activation(plan)
    assert ws.active_part == "door"
    assert ws.selected_part == "door"
    assert ws.switching is True
    controller.finish_activation()
    assert ws.switching is False

    stale = controller.resolve_operator_part("box_body:left_side")
    assert stale is None

    added = controller.add_part("tail", default_profiles={"X": [], "Y": []})
    assert added.changed is True
    assert "tail" in ws.available_parts

    removed = controller.remove_part("tail")
    assert removed.changed is True
    assert "tail" not in ws.available_parts
