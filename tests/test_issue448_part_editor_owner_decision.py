# -*- coding: utf-8 -*-
"""Issue #448 / T6 Part Editor owner-decision contracts."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
WORKSPACE = ROOT / "phase6_designer_workspace.py"
NAV = ROOT / "phase6_workspace_navigation_controller.py"
ROUTER = ROOT / "gui_modules" / "application" / "command_router.py"
CENSUS = ROOT / "docs" / "superpowers" / "checkpoints" / "issue448-t6-part-editor-census.md"
PROSPECTIVE_SESSION = ROOT / "phase6_part_editor_session.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in _tree(path).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _call_lines(fn: ast.FunctionDef, *, name: str | None = None, attr: str | None = None) -> list[int]:
    result = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if name is not None and isinstance(node.func, ast.Name) and node.func.id == name:
            result.append(node.lineno)
        if attr is not None and isinstance(node.func, ast.Attribute) and node.func.attr == attr:
            result.append(node.lineno)
    return sorted(result)


def _imports(path: Path) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_t6_decision_keeps_composition_adapter_and_rejects_shallow_session():
    text = CENSUS.read_text(encoding="utf-8")
    assert "DECISION=C_KEEP_BRIDGE_COMPATIBILITY" in text
    assert not PROSPECTIVE_SESSION.exists(), (
        "T6 C decision forbids a move-only phase6_part_editor_session.py"
    )


def test_t6_existing_workspace_and_navigation_owners_stay_pure():
    workspace_imports = _imports(WORKSPACE)
    nav_imports = _imports(NAV)
    for token in ("tkinter", "fold_designer_bridge"):
        assert token not in workspace_imports
        assert token not in nav_imports
    assert "phase6_manufacturing_geometry" not in nav_imports
    assert "phase6_manufacturing_service" not in nav_imports


def test_t6_activation_orders_outgoing_save_before_identity_switch():
    fn = _function(BRIDGE, "_fix11_activate_part")
    plan = _call_lines(fn, attr="plan_activation")
    save = _call_lines(fn, attr="_save_current_part")
    begin = _call_lines(fn, attr="begin_activation")
    finish = _call_lines(fn, attr="finish_activation")
    assert len(plan) == len(save) == len(begin) == len(finish) == 1
    assert plan[0] < save[0] < begin[0] < finish[0]


def test_t6_activation_routes_contracts_to_existing_seams():
    fn = _function(BRIDGE, "_fix11_activate_part")
    required_calls = {
        "_phase6_mount_shared_content",
        "_phase6_render_settings_context",
        "_phase6_render_active_drawing_edge_controls",
        "_phase6_refresh_persistent_structure_controls",
        "_phase6_refresh_box_body_piece_selector",
        "_phase6_refresh_content_switch",
    }
    names = {
        node.func.id
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert required_calls <= names

    attrs = {
        node.func.attr
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "plan_activation" in attrs
    assert "begin_activation" in attrs
    assert "finish_activation" in attrs

    body = ast.get_source_segment(BRIDGE.read_text(encoding="utf-8"), fn) or ""
    # Compatibility adapter resolves the installed facade method dynamically, then
    # calls the local `submit` exactly once. Do not require a direct Attribute call.
    assert 'getattr(self, "submit_update_intent", None)' in body
    local_submit_calls = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "submit"
    ]
    assert len(local_submit_calls) == 1
    # Profile stashing through the navigation controller is the accepted owner route.
    # The separate direct-mutation contract below rejects bridge writes to
    # DesignerWorkspace backing state.
    assert "stash_profiles" in attrs


def test_t6_activation_does_not_directly_mutate_designer_workspace_state():
    fn = _function(BRIDGE, "_fix11_activate_part")
    forbidden_attrs = {
        "active_part",
        "selected_part",
        "dirty",
        "switching",
    }
    violations = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.ctx, (ast.Store, ast.Del)):
            continue
        if not (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "self"
            and node.value.attr == "designer_workspace"
        ):
            continue
        if node.attr in forbidden_attrs:
            violations.append((node.attr, node.lineno))
    assert violations == []


def test_t6_update_scheduler_remains_command_router_owner():
    bridge = BRIDGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    fn = _function(BRIDGE, "_phase6_submit_update_intent")
    body = ast.get_source_segment(bridge, fn) or ""
    assert "submit_fold_designer_update_intent" in body
    assert "class _Phase6UpdateScheduler" in router
    assert "def submit_fold_designer_update_intent" in router


def test_t6_workspace_export_uses_owner_snapshot_not_legacy_profile_mirror():
    fn = _function(BRIDGE, "_phase6_collect_workspace_state")
    body = ast.get_source_segment(BRIDGE.read_text(encoding="utf-8"), fn) or ""
    assert "self.designer_workspace.export_shared_snapshot" in body
    assert "self.designer_workspace.snapshot" not in body
    assert "live_active_profiles=" in body
