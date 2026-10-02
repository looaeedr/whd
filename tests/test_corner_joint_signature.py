# -*- coding: utf-8 -*-
from ae_engine.assembly_joint import (
    AssemblyJoint,
    AssemblyJointRelation,
    AssemblyJointSource,
    CornerJointSignature,
    ResolvedAssemblyGraph,
    corner_joint_signature,
)


def _graph(order=False):
    joints = [
        AssemblyJoint(
            joint_id="side",
            subject_part="head",
            target_part="left_side",
            subject_region="top_left",
            target_region="mating",
            relation=AssemblyJointRelation.INSERT_OVERLAY,
        ),
        AssemblyJoint(
            joint_id="wrap",
            subject_part="head",
            target_part="rear_panel",
            subject_region="top_left",
            target_region="top",
            relation=AssemblyJointRelation.WRAP,
            source=AssemblyJointSource.USER_ADDED,
        ),
    ]
    if order:
        joints.reverse()
    return ResolvedAssemblyGraph(parts=("head", "left_side", "rear_panel"), joints=tuple(joints))


def test_corner_joint_signature_is_order_independent_and_stable():
    a = corner_joint_signature(_graph(False), "head", "top_left")
    b = corner_joint_signature(_graph(True), "head", "top_left")
    assert a == b
    assert isinstance(a, CornerJointSignature)
    assert a.key == b.key
    assert "INSERT_OVERLAY" in a.key and "WRAP" in a.key


def test_corner_joint_signature_preserves_direction():
    graph = ResolvedAssemblyGraph(
        parts=("head", "rear_panel"),
        joints=(AssemblyJoint(
            joint_id="wrap",
            subject_part="head",
            target_part="rear_panel",
            subject_region="top_left",
            target_region="top",
            relation=AssemblyJointRelation.WRAP,
        ),),
    )
    sig = corner_joint_signature(graph, "head", "top_left")
    assert "head>rear_panel" in sig.key
    assert "rear_panel>head" not in sig.key


def test_intent_side_joint_is_near_both_corners_on_that_side():
    from ae_engine.assembly_joint import resolve_endcap_intent_joints

    joints = resolve_endcap_intent_joints(
        AssemblyJointRelation.INSERT_OVERLAY,
        endcap_part="head",
        target_parts=("left_side", "right_side"),
    )
    graph = ResolvedAssemblyGraph(parts=("head", "left_side", "right_side"), joints=joints)

    left_top = corner_joint_signature(graph, "head", "top_left")
    left_bottom = corner_joint_signature(graph, "head", "bottom_left")
    right_top = corner_joint_signature(graph, "head", "top_right")
    assert any("head>left_side" in e for e in left_top.entries)
    assert any("head>left_side" in e for e in left_bottom.entries)
    assert any("head>right_side" in e for e in right_top.entries)


def test_legacy_side_joint_is_near_corner_after_migration():
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints

    migrated = migrate_legacy_snapshot_joints({
        "assembly_type": "INSERT",
        "existing_parts": ["box_body", "head", "tail"],
    })
    joints = tuple(AssemblyJoint.from_dict(raw) for raw in migrated["assembly_joints"])
    graph = ResolvedAssemblyGraph(parts=("box_body", "head", "tail"), joints=joints)
    assert corner_joint_signature(graph, "head", "top_left").entries
    assert corner_joint_signature(graph, "head", "bottom_right").entries
