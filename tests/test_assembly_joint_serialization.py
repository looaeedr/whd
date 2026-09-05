# -*- coding: utf-8 -*-
from ae_engine.assembly_joint import (
    AssemblyJoint,
    AssemblyJointRelation,
    AssemblyJointSource,
    deserialize_joint_graph,
    migrate_legacy_snapshot_joints,
    serialize_joint_graph,
)


def test_joint_graph_round_trip_preserves_user_added_wrap_and_source():
    joints = (
        AssemblyJoint(
            joint_id="head-wrap-rear",
            subject_part="head",
            target_part="box_body",
            subject_region="rear_edge",
            target_region="rear_mating",
            relation=AssemblyJointRelation.WRAP,
            source=AssemblyJointSource.USER_ADDED,
        ),
    )
    payload = serialize_joint_graph(("box_body", "head"), joints)
    restored = deserialize_joint_graph(payload)
    assert restored.parts == ("box_body", "head")
    assert restored.joints == joints


def test_legacy_migration_creates_intent_joints_but_never_guesses_wrap_and_is_idempotent():
    snapshot = {"assembly_type": "INSERT_OVERLAY", "existing_parts": ["box_body", "head", "tail"]}
    migrated = migrate_legacy_snapshot_joints(snapshot)
    assert migrated["assembly_joint_schema_version"] == 2
    assert migrated["assembly_joints"]
    assert {j["edge"] for j in migrated["assembly_joints"]} == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
    assert {j["relation"] for j in migrated["assembly_joints"]} == {"INSERT", "OVERLAY"}
    assert all(j["source"] == "LEGACY_MIGRATED" for j in migrated["assembly_joints"])
    assert not any(j["relation"] == "WRAP" for j in migrated["assembly_joints"])
    again = migrate_legacy_snapshot_joints(migrated)
    assert again["assembly_joints"] == migrated["assembly_joints"]
