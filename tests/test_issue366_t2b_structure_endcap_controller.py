from __future__ import annotations

import ast
from pathlib import Path


def _owner(*, snapshot=None, fw_state=None, wrap_state=None):
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    snapshot = dict(snapshot or {"fw": 25.0, "model": "受電箱", "assembly_type": "WRAP_OVERLAY"})
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "part_profiles": {},
    })
    workspace.mark_clean()
    settings = {"w": 800.0, "h": 1600.0, "d": 300.0, "fw": 25.0}
    box = {"w": 800.0, "h": 1600.0, "d": 300.0}
    owner = Phase6SettingsTransactionController(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd=box,
        workspace=workspace,
        endcap_fw_state=fw_state if fw_state is not None else {},
        endcap_bottom_wrap_state=wrap_state if wrap_state is not None else {},
    )
    return owner, workspace, snapshot


def test_t2b_structure_commit_updates_workspace_snapshot_and_dirty():
    from phase6_box_body_structure import (
        BoxBodyStructureType,
        default_box_body_structure_state,
    )

    owner, workspace, snapshot = _owner()
    state = default_box_body_structure_state()
    committed = owner.activate_box_structure(
        state,
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        800.0,
    )

    assert committed["active_type"] == BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    assert workspace.box_body_structure_state() == committed
    assert snapshot["box_body_structure"] == committed
    assert workspace.dirty is True


def test_t2b_structure_numeric_semantics_remain_in_structure_owner():
    from phase6_box_body_structure import (
        BoxBodyStructureType,
        default_box_body_structure_state,
    )

    owner, workspace, _snapshot = _owner()
    state = owner.activate_box_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        800.0,
    )
    workspace.mark_clean()

    committed = owner.apply_box_structure_numeric(
        state,
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        "left",
        300.0,
        total_w=800.0,
    )

    config = committed["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    assert config["left_w"] == 300.0
    assert config["right_w"] == 500.0
    assert workspace.dirty is True


def test_t2b_endcap_fw_pair_then_split_state_and_snapshot_are_canonical():
    from phase6_endcap_semantics import normalize_endcap_fw_state

    initial_snapshot = {"fw": 25.0, "model": "受電箱"}
    fw_state = normalize_endcap_fw_state(initial_snapshot)
    owner, workspace, snapshot = _owner(snapshot=initial_snapshot, fw_state=fw_state)

    owner.commit_endcap_fw_override("head", 29.0)
    assert fw_state["head"]["value"] == 29.0
    assert fw_state["tail"]["value"] == 29.0
    assert snapshot["endcap_fw"]["head"]["value"] == 29.0

    owner.commit_endcap_fw_override("tail", 31.0)
    assert fw_state["head"]["value"] == 29.0
    assert fw_state["tail"]["value"] == 31.0
    assert snapshot["endcap_fw"]["tail"]["value"] == 31.0
    assert workspace.dirty is True


def test_t2b_receiving_bottom_wrap_commit_preserves_pair_semantics():
    from phase6_endcap_semantics import normalize_endcap_bottom_wrap_state

    snap = {"model": "受電箱", "t": 2.0, "assembly_type": "WRAP_OVERLAY"}
    state = normalize_endcap_bottom_wrap_state(snap)
    owner, workspace, snapshot = _owner(snapshot=snap, wrap_state=state)

    committed = owner.commit_bottom_wrap("head", reserve_u=3.5, reserve_v=2.25)

    assert committed["enabled"] is True
    assert committed["reserve_u"] == 3.5
    assert committed["reserve_v"] == 2.25
    assert snapshot["endcap_bottom_wrap"]["mode"] == "FOLLOW_HEAD"
    assert workspace.dirty is True


def test_t2b_endcap_edge_relation_updates_joint_snapshot_and_dirty():
    from ae_engine.assembly_joint import AssemblyJointRelation

    snap = {
        "model": "受電箱",
        "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    }
    owner, workspace, snapshot = _owner(snapshot=snap)

    updated = owner.commit_endcap_edge_relation(
        "head", "BOTTOM", AssemblyJointRelation.WRAP
    )

    assert updated["assembly_joints"]
    assert snapshot["assembly_joints"] == updated["assembly_joints"]
    assert snapshot["assembly_joint_schema_version"] == updated["assembly_joint_schema_version"]
    assert workspace.dirty is True


def test_t2b_controller_and_bridge_keep_semantics_and_effects_separate():
    controller = Path("phase6_settings_transaction_controller.py").read_text(encoding="utf-8")
    assert "tkinter" not in controller
    assert "fold_designer_bridge" not in controller
    assert "phase6_manufacturing_service" not in controller
    assert "phase6_manufacturing_geometry" not in controller

    tree = ast.parse(Path("fold_designer_bridge.py").read_text(encoding="utf-8"))
    funcs = {
        node.name: ast.unparse(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    controller_methods = {
        node.name
        for cls in ast.parse(controller).body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6SettingsTransactionController"
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "commit_endcap_fw_follow" in controller_methods
    if "_phase6_set_endcap_fw_follow" in funcs:
        assert "commit_endcap_fw_follow" in funcs["_phase6_set_endcap_fw_follow"]
    assert "commit_endcap_fw_override" in funcs["_phase6_set_endcap_fw_override"]
    assert "commit_box_structure_state" in funcs["_phase6_commit_box_structure_state"]
    assert "set_box_body_structure_state" not in funcs["_phase6_commit_box_structure_state"]
    assert "apply_box_structure_numeric" in funcs["_phase6_apply_box_structure_numeric"]
    assert "set_two_piece_width(" not in funcs["_phase6_apply_box_structure_numeric"]
    assert "commit_bottom_wrap" in funcs["_phase6_commit_receiving_bottom_wrap_controls"]
    assert "commit_endcap_bottom_wrap(" not in funcs["_phase6_commit_receiving_bottom_wrap_controls"]
    assert "commit_endcap_edge_relation" in funcs["_phase6_on_endcap_edge_relation_selected"]
