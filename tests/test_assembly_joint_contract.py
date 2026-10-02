# -*- coding: utf-8 -*-
import pytest

from ae_engine.assembly_joint import (
    AssemblyJoint,
    AssemblyJointRelation,
    AssemblyJointSource,
)


def test_wrap_direction_is_encoded_by_subject_and_target_only():
    joint = AssemblyJoint(
        joint_id="head-wrap-rear",
        subject_part="head",
        target_part="rear_panel",
        subject_region="rear_edge",
        target_region="top_mating_zone",
        relation=AssemblyJointRelation.WRAP,
        source=AssemblyJointSource.USER_ADDED,
    )
    assert joint.relation is AssemblyJointRelation.WRAP
    assert joint.subject_part == "head"
    assert joint.target_part == "rear_panel"
    assert not hasattr(joint, "wrapper")
    assert not hasattr(joint, "wrapped")


def test_one_part_can_own_different_joint_relations_to_different_targets():
    side = AssemblyJoint(
        joint_id="head-left",
        subject_part="head",
        target_part="left_side",
        relation=AssemblyJointRelation.INSERT_OVERLAY,
        source=AssemblyJointSource.INTENT_DERIVED,
    )
    rear = AssemblyJoint(
        joint_id="head-rear",
        subject_part="head",
        target_part="rear_panel",
        relation=AssemblyJointRelation.WRAP,
        source=AssemblyJointSource.USER_ADDED,
    )
    assert side.subject_part == rear.subject_part == "head"
    assert side.relation is not rear.relation


def test_joint_rejects_self_target():
    with pytest.raises(ValueError, match="subject_part.*target_part"):
        AssemblyJoint(
            joint_id="bad",
            subject_part="head",
            target_part="head",
            relation=AssemblyJointRelation.WRAP,
        )
