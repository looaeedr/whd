#!/usr/bin/env python3
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from collections.abc import Mapping


def safe(value):
    if isinstance(value, Enum):
        return safe(value.value)
    if isinstance(value, Mapping):
        return {str(k): safe(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, set):
        return sorted(safe(v) for v in value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def owner(*, snapshot=None, fw_state=None, wrap_state=None, workspace=None,
          corner_state=None, corner_pairs=None, settings=None):
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    snapshot = dict(snapshot or {
        "fw": 25.0, "model": "受電箱", "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    })
    if workspace is None:
        workspace = Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"],
            "active_part": "box_body",
            "part_profiles": {},
        })
    workspace.mark_clean()
    settings = settings if settings is not None else {
        "w": 800.0, "h": 1600.0, "d": 300.0, "fw": 25.0,
        "ui_text_size": "small", "flag": False,
    }
    box = {"w": 800.0, "h": 1600.0, "d": 300.0}
    controller = Phase6SettingsTransactionController(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd=box,
        workspace=workspace,
        endcap_fw_state=fw_state if fw_state is not None else {},
        endcap_bottom_wrap_state=wrap_state if wrap_state is not None else {},
        corner_state=corner_state if corner_state is not None else {},
        corner_pair_same=corner_pairs if corner_pairs is not None else {},
    )
    return controller, workspace, snapshot, settings, box


def main():
    from ae_engine.assembly_joint import AssemblyJointRelation
    from ae_engine.sheetmetal_geometry import (
        CornerDirection, CornerTypeId, CrossCornerMode,
    )
    from phase6_box_body_structure import (
        BoxBodyStructureType, default_box_body_structure_state,
    )
    from phase6_endcap_semantics import (
        normalize_endcap_bottom_wrap_state, normalize_endcap_fw_state,
    )
    from phase6_designer_workspace import Phase6DesignerWorkspace

    out = {}

    c, _, snap, settings, box = owner()
    clean = c.normalize_updates({
        "w": "640", "flag": 1, "ui_text_size": "大", "unknown": 99,
    })
    committed = c.commit_settings(clean)
    out["local_settings"] = {
        "clean": clean, "committed": committed,
        "settings": settings, "snapshot": snap, "box": box,
    }

    c, ws, snap, _, _ = owner()
    st = c.activate_box_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.TWO_PIECE_W_SPLIT, 800.0,
    )
    st = c.apply_box_structure_numeric(
        st, BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        "left", 300.0, total_w=800.0,
    )
    out["structure"] = {
        "state": st,
        "snapshot": snap.get("box_body_structure"),
        "dirty": ws.dirty,
    }

    fw_snapshot = {"fw": 25.0, "model": "受電箱"}
    fw = normalize_endcap_fw_state(fw_snapshot)
    c, ws, snap, _, _ = owner(snapshot=fw_snapshot, fw_state=fw)
    c.commit_endcap_fw_override("head", 29.0)
    c.commit_endcap_fw_override("tail", 31.0)
    out["endcap_fw"] = {
        "state": fw, "snapshot": snap.get("endcap_fw"), "dirty": ws.dirty,
    }

    wrap_snapshot = {
        "model": "受電箱", "t": 2.0, "assembly_type": "WRAP_OVERLAY",
    }
    wrap = normalize_endcap_bottom_wrap_state(wrap_snapshot)
    c, ws, snap, _, _ = owner(snapshot=wrap_snapshot, wrap_state=wrap)
    resolved = c.commit_bottom_wrap("head", reserve_u=3.5, reserve_v=2.25)
    out["bottom_wrap"] = {
        "resolved": resolved,
        "state": wrap,
        "snapshot": snap.get("endcap_bottom_wrap"),
        "dirty": ws.dirty,
    }

    joint_snapshot = {
        "model": "受電箱",
        "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    }
    c, ws, snap, _, _ = owner(snapshot=joint_snapshot)
    joint = c.commit_endcap_edge_relation(
        "head", "BOTTOM", AssemblyJointRelation.WRAP
    )
    out["edge_relation"] = {
        "snapshot": {
            "assembly_joint_schema_version": snap.get("assembly_joint_schema_version"),
            "assembly_joints": snap.get("assembly_joints"),
            "assembly_type": snap.get("assembly_type"),
        },
        "returned": joint,
        "dirty": ws.dirty,
    }

    corner_state = {}
    corner_pairs = {}
    c, ws, snap, _, _ = owner(
        snapshot={
            "model": "金庫型", "w": 800.0, "h": 1600.0,
            "d": 300.0, "fw": 25.0,
            "existing_parts": ["box_body", "head", "tail"],
        },
        corner_state=corner_state,
        corner_pairs=corner_pairs,
    )
    c.ensure_corner_part("head")
    c.commit_corner_type("head", "top", CornerTypeId.OVERLAY)
    c.commit_corner_pair("head", "top", False)
    c.commit_corner_type("head", "top_left", CornerTypeId.CROSS)
    c.commit_corner_mode("head", "top_left", CrossCornerMode.RETAIN)
    c.commit_corner_parameters(
        "head", "top_left", amount_t=1.5, direction=CornerDirection.WIDTH,
    )
    assembly = c.commit_assembly_intent(
        CornerTypeId.OVERLAY,
        available_parts=("box_body", "head", "tail"),
        project_legacy_corner=False,
    )
    out["corner_assembly"] = {
        "corner_state": corner_state,
        "corner_pairs": corner_pairs,
        "assembly": assembly,
        "snapshot": {
            "assembly_type": snap.get("assembly_type"),
            "assembly_joint_schema_version": snap.get("assembly_joint_schema_version"),
            "assembly_joints": snap.get("assembly_joints"),
        },
        "dirty": ws.dirty,
    }

    accepted = c.plan_external_sync({
        "origin": "main_gui", "revision": 2, "transaction_id": "main:2",
        "delta": {"settings": {"w": 810.0}},
    })
    stale = c.plan_external_sync({
        "origin": "main_gui", "revision": 1, "transaction_id": "main:1",
        "delta": {"settings": {"w": 820.0}},
    })
    out["external_sync"] = {
        "accepted": accepted.__dict__,
        "stale": stale.__dict__,
        "last_revision": c.last_external_revision,
        "last_transaction": c.last_external_transaction_id,
        "model_plan": c.plan_external_model_change("受電箱").__dict__,
    }

    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "part_profiles": {},
        "box_body_structure": default_box_body_structure_state(),
    })
    workspace.set_box_body_structure_state({
        **default_box_body_structure_state(),
        "active_type": BoxBodyStructureType.TWO_PIECE_W_SPLIT.value,
        "locked": False,
        "configs": {
            **default_box_body_structure_state()["configs"],
            BoxBodyStructureType.TWO_PIECE_W_SPLIT.value: {
                **default_box_body_structure_state()["configs"][
                    BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
                ],
                "left_w": 300.0, "right_w": 500.0, "last_driver": "left",
            },
        },
    })
    family_settings = {"w": 800.0, "h": 1600.0, "d": 300.0, "fw": 25.0}
    family_snapshot = {
        "model": "金庫型", "w": 800.0, "h": 1600.0,
        "d": 300.0, "fw": 25.0,
        "existing_parts": ["box_body", "head", "tail"],
        "factory_defaults": dict(family_settings),
    }
    corners = {}
    pairs = {}
    c, ws, snap, _, _ = owner(
        snapshot=family_snapshot,
        workspace=workspace,
        corner_state=corners,
        corner_pairs=pairs,
        settings=family_settings,
    )
    reconciled = c.commit_reconciled_width_structure(900.0)
    fixed = {
        "head": {
            "top_left": {"type_id": "OVERLAY", "rotation_quadrants": 0},
            "top_right": {"type_id": "OVERLAY", "rotation_quadrants": 0},
            "bottom_left": {"type_id": "INSERT", "rotation_quadrants": 0},
            "bottom_right": {"type_id": "INSERT", "rotation_quadrants": 0},
        }
    }
    family = c.commit_family_model_transition(
        "受電箱", "金庫型",
        new_editable=False, old_editable=False,
        fixed_corner_state=fixed,
        available_parts=("box_body", "head", "tail"),
        previous_non_receiving_structure=workspace.box_body_structure_state(),
    )
    out["family_model"] = {
        "reconciled": reconciled,
        "transition": family.__dict__,
        "snapshot": snap,
        "corner_state": corners,
        "corner_pairs": pairs,
        "workspace_structure": ws.box_body_structure_state(),
        "dirty": ws.dirty,
    }

    print(json.dumps(safe(out), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
