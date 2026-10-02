# -*- coding: utf-8 -*-
import pytest

from ae_engine.assembly_joint import (
    AssemblyJoint,
    AssemblyJointRelation,
    AssemblyJointSource,
    ResolvedAssemblyGraph,
)


def test_graph_queries_nearby_joints_for_corner_region():
    graph = ResolvedAssemblyGraph(
        parts=("head", "left_side", "rear_panel"),
        joints=(
            AssemblyJoint(
                joint_id="head-left",
                subject_part="head",
                target_part="left_side",
                subject_region="top_left",
                relation=AssemblyJointRelation.INSERT_OVERLAY,
            ),
            AssemblyJoint(
                joint_id="head-rear",
                subject_part="head",
                target_part="rear_panel",
                subject_region="top_left",
                relation=AssemblyJointRelation.WRAP,
                source=AssemblyJointSource.USER_ADDED,
            ),
        ),
    )
    nearby = graph.nearby_joints("head", "top_left")
    assert {j.relation for j in nearby} == {
        AssemblyJointRelation.INSERT_OVERLAY,
        AssemblyJointRelation.WRAP,
    }


def test_graph_rejects_joint_targeting_missing_part():
    with pytest.raises(ValueError, match="missing part"):
        ResolvedAssemblyGraph(
            parts=("head",),
            joints=(
                AssemblyJoint(
                    joint_id="bad",
                    subject_part="head",
                    target_part="rear_panel",
                    relation=AssemblyJointRelation.WRAP,
                ),
            ),
        )


def test_graph_rejects_conflicting_relations_for_same_pair_and_regions():
    with pytest.raises(ValueError, match="conflicting joint"):
        ResolvedAssemblyGraph(
            parts=("head", "rear_panel"),
            joints=(
                AssemblyJoint(
                    joint_id="j1",
                    subject_part="head",
                    target_part="rear_panel",
                    subject_region="rear_edge",
                    target_region="top",
                    relation=AssemblyJointRelation.WRAP,
                ),
                AssemblyJoint(
                    joint_id="j2",
                    subject_part="head",
                    target_part="rear_panel",
                    subject_region="rear_edge",
                    target_region="top",
                    relation=AssemblyJointRelation.OVERLAY,
                ),
            ),
        )
