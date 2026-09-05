# -*- coding: utf-8 -*-
import pytest

from ae_engine.assembly_joint import (
    AssemblyJoint, AssemblyJointRelation, AssemblyJointSource, joint_semantics,
)
from ae_engine.assembly_collision import joint_relief_ownership
from ae_engine.certified_relief_registry import (
    load_external_relief_rule_records, evaluate_relief_formula_record,
)


@pytest.mark.parametrize("relation", tuple(AssemblyJointRelation), ids=lambda r: r.value)
def test_every_registered_joint_relation_has_semantics_ownership_and_roundtrip(relation):
    joint = AssemblyJoint(
        joint_id=f"matrix-{relation.value}", subject_part="subject", target_part="target",
        subject_region="top_left", target_region="bottom_left", relation=relation,
        source=AssemblyJointSource.USER_ADDED,
    )
    semantics = joint_semantics(relation)
    ownership = joint_relief_ownership(joint)
    assert semantics.relation is relation
    assert semantics.family_override_allowed is False
    assert ownership.preserve_part in {"subject", "target"}
    assert ownership.relief_part in {"subject", "target"}
    assert ownership.preserve_part != ownership.relief_part
    assert AssemblyJoint.from_dict(joint.to_dict()) == joint
    if relation is AssemblyJointRelation.WRAP:
        assert ownership.preserve_part == "subject"
        assert ownership.relief_part == "target"


@pytest.mark.parametrize(
    "record",
    tuple(r for r in load_external_relief_rule_records() if bool(r.get("active", True))),
    ids=lambda r: f"{r['rule_id']}@{r['revision']}",
)
def test_every_active_certified_rule_has_valid_joint_relations_and_formula(record):
    for entry in record["joint_signature"]:
        AssemblyJointRelation(str(entry["relation"]))
        assert str(entry.get("subject_role") or "").strip()
        assert str(entry.get("target_role") or "").strip()
    variables = {
        "T": 2.0, "FW": 25.0, "side_fold": 15.0, "ytop1": 16.0,
        "ybottom1": 15.0, "rear_bend": 15.0,
        "reserve_u": 2.0, "reserve_v": 1.0,
        "mating_width": 50.0, "effective_mating_width": 50.0,
        "fold_u": 15.0, "fold_v": 16.0, "clearance": 0.0,
    }
    values = evaluate_relief_formula_record(record, variables)
    assert values["primary_u"] >= 0
    assert values["primary_v"] >= 0
    if int(record["topology_levels"]) == 1:
        assert values["secondary_u"] is None and values["secondary_depth"] is None
    else:
        assert values["secondary_u"] is not None and values["secondary_depth"] is not None
