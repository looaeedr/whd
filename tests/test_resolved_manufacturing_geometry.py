# -*- coding: utf-8 -*-
from types import SimpleNamespace
from shapely.geometry import box

from ae_engine.contracts import (
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
    ResolvedReliefRuleTrace,
)
from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation


def test_resolved_manufacturing_geometry_is_single_canonical_part_lookup():
    render = SimpleNamespace(material=box(0, 0, 20, 10), scene=object())
    part = ResolvedManufacturingPart(
        part_key="head", render_data=render,
        x_profile=({"len": 20.0, "core": True},),
        y_profile=({"len": 10.0, "core": True},), placement="top",
    )
    joint = AssemblyJoint(
        joint_id="j", subject_part="head", target_part="box_body",
        subject_region="top_left", target_region="mating_zone",
        relation=AssemblyJointRelation.INSERT,
    )
    trace = ResolvedReliefRuleTrace(
        part_key="head", corner_name="top_left", rule_id="R", revision=2,
        trust_level="CERTIFIED", signature="INSERT",
    )
    resolved = ResolvedManufacturingGeometry(parts=(part,), joints=(joint,), relief_rules=(trace,))

    assert resolved.part("head") is part
    assert resolved.material("head").equals(render.material)
    assert resolved.relief_rules_for("head")[0].revision == 2
    assert resolved.joints_for("head") == (joint,)


def test_resolved_manufacturing_geometry_rejects_duplicate_part_keys():
    render = SimpleNamespace(material=box(0, 0, 1, 1), scene=object())
    part = ResolvedManufacturingPart(part_key="head", render_data=render)
    import pytest
    with pytest.raises(ValueError, match="duplicate canonical part"):
        ResolvedManufacturingGeometry(parts=(part, part))
