# -*- coding: utf-8 -*-
import pytest

from ae_engine.assembly_joint import AssemblyJointRelation, joint_semantics
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, resolve_endcap_assembly_semantics


@pytest.mark.parametrize(
    "relation, outer, inner, preserve",
    [
        (AssemblyJointRelation.INSERT, False, True, "TARGET"),
        (AssemblyJointRelation.OVERLAY, True, False, "SUBJECT"),
        (AssemblyJointRelation.INSERT_OVERLAY, True, True, "SUBJECT_OUTER_CONTACT"),
        (AssemblyJointRelation.WRAP, True, False, "SUBJECT"),
    ],
)
def test_joint_semantics_are_global_and_explicit(relation, outer, inner, preserve):
    got = joint_semantics(relation)
    assert got.has_outer_contact is outer
    assert got.has_inner_insertion is inner
    assert got.preserve_side == preserve
    assert got.family_override_allowed is False


def test_endcap_semantics_exposes_mechanical_relation_fields():
    got = resolve_endcap_assembly_semantics(CornerTypeSelection(CornerTypeId.INSERT_OVERLAY))
    assert got.has_outer_contact is True
    assert got.has_inner_insertion is True
    assert got.mating_relation == "OUTER_OVERLAY_AND_INNER_INSERT"
