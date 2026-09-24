# -*- coding: utf-8 -*-
from types import SimpleNamespace

from ae_engine.assembly_joint import (
    AssemblyJoint, AssemblyJointRelation, AssemblyJointSource,
    migrate_legacy_snapshot_joints, sync_snapshot_intent_joints,
)
from ae_engine.sheetmetal_geometry import CornerTypeId


def test_bridge_sync_joint_state_updates_intent_and_preserves_user_wrap():
    app = SimpleNamespace(
        _phase6_input_snapshot={
            "existing_parts": ["box_body", "head", "tail"],
            "assembly_joint_schema_version": 1,
            "assembly_joints": [
                AssemblyJoint(
                    joint_id="head-wrap-rear",
                    subject_part="head",
                    target_part="box_body",
                    subject_region="rear_edge",
                    target_region="rear_mating",
                    relation=AssemblyJointRelation.WRAP,
                    source=AssemblyJointSource.USER_ADDED,
                ).to_dict()
            ],
        },
        designer_workspace=SimpleNamespace(available_parts=("box_body", "head", "tail")),
    )
    snapshot = migrate_legacy_snapshot_joints(app._phase6_input_snapshot)
    snapshot["existing_parts"] = list(app.designer_workspace.available_parts)
    snapshot = sync_snapshot_intent_joints(snapshot, CornerTypeId.OVERLAY)
    rows = snapshot["assembly_joints"]
    assert any(row["relation"] == "WRAP" and row["source"] == "USER_ADDED" for row in rows)
    derived = [row for row in rows if row["source"] == "INTENT_DERIVED"]
    assert len(derived) == 8
    assert {row["edge"] for row in derived if row["subject_part"] == "head"} == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
    assert {row["edge"] for row in derived if row["subject_part"] == "tail"} == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
    for part in ("head", "tail"):
        by_edge = {row["edge"]: row["relation"] for row in derived if row["subject_part"] == part}
        assert by_edge == {"TOP": "OVERLAY", "BOTTOM": "INSERT", "LEFT": "OVERLAY", "RIGHT": "OVERLAY"}
