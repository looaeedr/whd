from __future__ import annotations

import ast
import json
from pathlib import Path

BRIDGE = Path("fold_designer_bridge.py")
CONTROLLER = Path("phase6_workspace_navigation_controller.py")
DECISION = Path("docs/superpowers/checkpoints/issue481-t3-linked-endcap-decision.json")

MUTATION_TOKENS = (
    "navigation.remove_part(",
    "navigation.sync_derived_parts(",
    "navigation.stash_features(",
    "navigation.add_part(",
    "navigation.stash_profiles(",
    "navigation.set_active_part(",
    "navigation.set_selected_part(",
)

ALLOWED_DECISIONS = {
    "DEEPEN_FOLD_PROFILES",
    "JOIN_DERIVED_PART_PLAN",
    "KEEP_COMPATIBILITY",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function(path: Path, name: str):
    return next(
        node for node in _tree(path).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _class(path: Path, name: str):
    return next(
        node for node in _tree(path).body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _method(cls: ast.ClassDef, name: str):
    return next(
        (
            node for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ),
        None,
    )


def test_t3_bridge_derived_sync_has_no_direct_plan_apply_mutations():
    fn = _function(BRIDGE, "_phase6_sync_authoritative_derived_parts")
    source = ast.get_source_segment(BRIDGE.read_text(encoding="utf-8"), fn) or ""
    assert "build_derived_part_sync_plan(request)" in source
    assert "navigation.apply_derived_sync_plan(plan)" in source, (
        "T3 RED: bridge does not delegate immutable plan application to navigation owner"
    )
    assert not [token for token in MUTATION_TOKENS if token in source], (
        "T3 RED: bridge still applies derived sync mutations directly"
    )


def test_t3_navigation_controller_owns_narrow_derived_plan_apply_seam():
    cls = _class(CONTROLLER, "Phase6WorkspaceNavigationController")
    method = _method(cls, "apply_derived_sync_plan")
    assert method is not None, "T3 RED: missing navigation apply_derived_sync_plan owner"
    source = ast.get_source_segment(CONTROLLER.read_text(encoding="utf-8"), method) or ""
    assert "DerivedPartSyncPlan" in CONTROLLER.read_text(encoding="utf-8")
    for forbidden in (
        "fold_designer_bridge",
        "phase6_manufacturing_geometry",
        "manufacturing_api",
        "cabinet_family_policy",
        "derive_box_body_dividers",
        "derive_inner_door",
    ):
        assert forbidden not in source


def test_t3_linked_endcap_owner_decision_is_machine_readable_and_single_choice():
    assert DECISION.is_file(), "T3 RED: linked-endcap ownership decision evidence is missing"
    payload = json.loads(DECISION.read_text(encoding="utf-8"))
    assert payload["issue"] == 481
    assert payload["decision"] in ALLOWED_DECISIONS
    assert payload["decision"] == "KEEP_COMPATIBILITY"
    assert payload["derivation_owner"] == "phase6_fold_profiles.build_linked_endcap_xy_profiles"
    assert payload["bridge_role"] == "workspace/live-editor compatibility effects"
    assert payload["join_derived_part_plan"] is False
    assert payload["deepen_fold_profiles"] is False


def test_t3_keep_compatibility_does_not_move_linked_endcap_derivation_into_planner():
    planner = Path("phase6_derived_part_projection.py").read_text(encoding="utf-8")
    assert "build_linked_endcap_xy_profiles" not in planner
    fn = _function(BRIDGE, "_phase6_rebuild_linked_endcaps")
    source = ast.get_source_segment(BRIDGE.read_text(encoding="utf-8"), fn) or ""
    assert "build_linked_endcap_xy_profiles" in source
    assert "designer_workspace.stash_profiles" in source
