# -*- coding: utf-8 -*-
from shapely.geometry import box

from ae_engine.assembly_collision import (
    FlatInterferenceProjection,
    classify_joint_interference,
    joint_relief_ownership,
)
from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation


def _joint(relation):
    return AssemblyJoint(
        joint_id=f"j-{relation.value}", subject_part="head", target_part="box_body",
        subject_region="top_left", target_region="left_mating_zone", relation=relation,
    )


def test_boundary_only_crossing_is_legal_contact_not_illegal_penetration():
    material = box(0, 0, 20, 20)
    projection = FlatInterferenceProjection(segments_2d=(((0, 2), (0, 18)),), points_2d=(), pair_count=1)
    result = classify_joint_interference(_joint(AssemblyJointRelation.OVERLAY), projection=projection, flat_material=material)
    assert result.has_contact is True
    assert result.illegal_penetration is False


def test_interior_crossing_is_illegal_penetration():
    material = box(0, 0, 20, 20)
    projection = FlatInterferenceProjection(segments_2d=(((5, 2), (5, 18)),), points_2d=(), pair_count=1)
    result = classify_joint_interference(_joint(AssemblyJointRelation.INSERT), projection=projection, flat_material=material)
    assert result.illegal_penetration is True


def test_wrap_preserves_wrapper_and_reliefs_wrapped_target():
    owner = joint_relief_ownership(_joint(AssemblyJointRelation.WRAP))
    assert owner.preserve_part == "head"
    assert owner.relief_part == "box_body"
    assert owner.reason == "WRAP_WRAPPER_PRESERVED"


def test_insert_reliefs_inserting_subject():
    owner = joint_relief_ownership(_joint(AssemblyJointRelation.INSERT))
    assert owner.relief_part == "head"
    assert owner.preserve_part == "box_body"
