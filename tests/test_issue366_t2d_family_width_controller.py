from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
CONTROLLER = Path("phase6_settings_transaction_controller.py")
COORDINATOR = Path("gui_modules/application/fold_designer_settings_coordinator.py")


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _controller_methods():
    tree = _tree(CONTROLLER)
    return {
        node.name
        for cls in tree.body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6SettingsTransactionController"
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_t2d_requires_width_and_family_transaction_controller_methods():
    required = {
        "commit_reconciled_width_structure",
        "commit_family_model_transition",
    }
    missing = sorted(required - _controller_methods())
    assert missing == [], f"RED: missing T2D controller methods: {missing}"


def test_t2d_bridge_no_longer_owns_width_or_family_semantic_commits():
    funcs = _functions(_tree(BRIDGE))
    apply_settings = ast.unparse(funcs["_phase6_apply_setting_updates"])
    baseline = ast.unparse(funcs["_phase6_on_baseline_model_changed"])

    coordinator_tree = _tree(COORDINATOR)
    coordinator_cls = next(
        node
        for node in coordinator_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerSettingsCoordinator"
    )
    coordinator_methods = {
        node.name: ast.unparse(node)
        for node in coordinator_cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    apply_updates = coordinator_methods["apply_updates"]
    apply_baseline = coordinator_methods["apply_baseline_transition"]

    violations = []
    if "_phase6_settings_coordinator" not in apply_settings:
        violations.append("MISSING_WIDTH_COORDINATOR_DELEGATE")
    if "commit_reconciled_width_structure" not in apply_updates:
        violations.append("MISSING_WIDTH_TRANSACTION_DELEGATE")
    if "reconcile_box_body_structure_for_total_w_change" in apply_settings:
        violations.append("WIDTH_RECONCILE_IN_BRIDGE")

    if "_phase6_settings_coordinator" not in baseline:
        violations.append("MISSING_FAMILY_COORDINATOR_DELEGATE")
    if "commit_family_model_transition" not in apply_baseline:
        violations.append("MISSING_FAMILY_TRANSACTION_DELEGATE")

    forbidden_tokens = (
        "cabinet_family_policy.apply_fresh_family_defaults",
        "cabinet_family_policy.fresh_assembly_intent",
        "cabinet_family_policy.resolve_box_body_structure_state",
        "normalize_endcap_bottom_wrap_state",
        "_phase6_sync_joint_state_for_intent",
        "_phase6_selection_to_raw",
        "designer_workspace.set_box_body_structure_state",
    )
    family_owner_surface = baseline + "\n" + apply_baseline
    violations.extend(
        f"FAMILY_SEMANTIC:{token}"
        for token in forbidden_tokens
        if token in family_owner_surface
    )

    forbidden_attrs = {
        "_phase6_assembly_type",
        "_phase6_corner_state",
        "_phase6_corner_pair_same",
        "_phase6_endcap_bottom_wrap_state",
    }
    for node in ast.walk(funcs["_phase6_on_baseline_model_changed"]):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr in forbidden_attrs
        ):
            violations.append(f"DIRECT_ATTR_WRITE:{node.attr}@{node.lineno}")

    assert violations == [], (
        "RED: bridge/coordinator chain still owns T2D width/family semantics: "
        f"{violations}"
    )
def test_t2d_controller_behavior_when_methods_exist():
    methods = _controller_methods()
    if not {
        "commit_reconciled_width_structure",
        "commit_family_model_transition",
    } <= methods:
        return

    from phase6_box_body_structure import (
        BoxBodyStructureType,
        default_box_body_structure_state,
    )
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "part_profiles": {},
        "box_body_structure": default_box_body_structure_state(),
    })
    workspace.set_box_body_structure_state(
        {
            **default_box_body_structure_state(),
            "active_type": BoxBodyStructureType.TWO_PIECE_W_SPLIT.value,
            "locked": False,
            "configs": {
                **default_box_body_structure_state()["configs"],
                BoxBodyStructureType.TWO_PIECE_W_SPLIT.value: {
                    **default_box_body_structure_state()["configs"][
                        BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
                    ],
                    "left_w": 300.0,
                    "right_w": 500.0,
                    "last_driver": "left",
                },
            },
        }
    )
    settings = {"w": 800.0, "h": 1600.0, "d": 300.0, "fw": 25.0}
    snapshot = {
        "model": "金庫型",
        "w": 800.0,
        "h": 1600.0,
        "d": 300.0,
        "fw": 25.0,
        "existing_parts": ["box_body", "head", "tail"],
        "factory_defaults": dict(settings),
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
    )

    reconciled = owner.commit_reconciled_width_structure(900.0)
    cfg = reconciled["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    assert cfg["left_w"] == 300.0
    assert cfg["right_w"] == 600.0

    fixed = {
        "head": {
            "top_left": {"type_id": "OVERLAY", "rotation_quadrants": 0},
            "top_right": {"type_id": "OVERLAY", "rotation_quadrants": 0},
            "bottom_left": {"type_id": "INSERT", "rotation_quadrants": 0},
            "bottom_right": {"type_id": "INSERT", "rotation_quadrants": 0},
        }
    }
    plan = owner.commit_family_model_transition(
        "受電箱",
        "金庫型",
        new_editable=False,
        old_editable=False,
        fixed_corner_state=fixed,
        available_parts=("box_body", "head", "tail"),
        previous_non_receiving_structure=workspace.box_body_structure_state(),
    )
    assert plan.new_model == "受電箱"
    assert plan.editable is False
    assert snapshot["model"] == "受電箱"
    assert snapshot["assembly_type"]
    assert snapshot["box_body_structure"]
    assert corner_state["head"]["top_left"]["type_id"] == "OVERLAY"
