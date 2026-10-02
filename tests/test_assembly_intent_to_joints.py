# -*- coding: utf-8 -*-
from ae_engine.assembly_joint import (
    AssemblyJoint,
    AssemblyJointRelation,
    AssemblyJointSource,
    resolve_endcap_intent_joints,
)
from ae_engine.sheetmetal_geometry import CornerTypeId


def test_insert_overlay_resolves_to_side_joints():
    joints = resolve_endcap_intent_joints(
        CornerTypeId.INSERT_OVERLAY,
        endcap_part="head",
        target_parts=("left_side", "right_side"),
    )
    assert [j.target_part for j in joints] == ["left_side", "right_side"]
    assert all(j.relation is AssemblyJointRelation.INSERT_OVERLAY for j in joints)
    assert all(j.source is AssemblyJointSource.INTENT_DERIVED for j in joints)


def test_switching_intent_replaces_only_intent_derived_and_preserves_user_wrap():
    existing = (
        AssemblyJoint(
            joint_id="head-left-old",
            subject_part="head",
            target_part="left_side",
            relation=AssemblyJointRelation.INSERT_OVERLAY,
            source=AssemblyJointSource.INTENT_DERIVED,
        ),
        AssemblyJoint(
            joint_id="head-wrap-rear",
            subject_part="head",
            target_part="rear_panel",
            relation=AssemblyJointRelation.WRAP,
            source=AssemblyJointSource.USER_ADDED,
        ),
    )
    joints = resolve_endcap_intent_joints(
        CornerTypeId.OVERLAY,
        endcap_part="head",
        target_parts=("left_side", "right_side"),
        existing_joints=existing,
    )
    assert any(j.joint_id == "head-wrap-rear" and j.relation is AssemblyJointRelation.WRAP for j in joints)
    side = [j for j in joints if j.source is AssemblyJointSource.INTENT_DERIVED]
    assert len(side) == 2
    assert all(j.relation is AssemblyJointRelation.OVERLAY for j in side)


def test_sync_snapshot_intent_joints_preserves_user_wrap_for_both_endcaps():
    from ae_engine.assembly_joint import sync_snapshot_intent_joints
    raw = {
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
            ).to_dict(),
        ],
        "existing_parts": ["box_body", "head", "tail"],
    }
    out = sync_snapshot_intent_joints(raw, CornerTypeId.OVERLAY)
    assert any(j["relation"] == "WRAP" and j["source"] == "USER_ADDED" for j in out["assembly_joints"])
    derived = [j for j in out["assembly_joints"] if j["source"] == "INTENT_DERIVED"]
    assert len(derived) == 8
    expected = {
        "TOP": "OVERLAY",
        "BOTTOM": "INSERT",
        "LEFT": "OVERLAY",
        "RIGHT": "OVERLAY",
    }
    assert {(j["subject_part"], j["edge"], j["relation"]) for j in derived} == {
        (part, edge, relation)
        for part in ("head", "tail")
        for edge, relation in expected.items()
    }
    assert out["assembly_type"] == "OVERLAY"
