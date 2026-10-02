# -*- coding: utf-8 -*-
from types import SimpleNamespace
from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource


def _joint(edge, relation):
    return AssemblyJoint(
        f"head:{edge}", "head", "box_body", f"{edge.lower()}_edge", f"{edge.lower()}_mating_zone",
        relation, source=AssemblyJointSource.INTENT_DERIVED, edge=edge,
    )


def test_bottom_wrap_diagnostic_uses_bottom_registry_trace_not_top_solution():
    import fold_designer_bridge as bridge
    render = SimpleNamespace(metadata={
        "receiving_bottom_relief_rule": {
            "rule_id": "RECEIVING_ENDCAP_BOTTOM_WRAP_V1", "revision": 1,
            "trust_level": "CERTIFIED_FROM_3D",
            "geometry_evidence": {"source": "SIDE_BACK_SPLIT_3D_FACE_PROJECTION"},
        }
    })
    top_solution = SimpleNamespace(
        rule_id="ENDCAP_TOP_INSERT_OVERLAY_EXTRA_V1", rule_revision=3,
        trust_level="CERTIFIED", verified=True,
        projections=(SimpleNamespace(pair_count=4),),
        residual_projection=SimpleNamespace(pair_count=0),
        shadow_validation={"geometry_evidence": {"source": "TOP"}},
    )
    info = bridge._phase6_joint_registry_diagnostic_info(
        _joint("BOTTOM", AssemblyJointRelation.WRAP),
        {"head": render}, {"head": top_solution},
    )
    assert info["registry_status"] == "HIT"
    assert info["rule_id"] == "RECEIVING_ENDCAP_BOTTOM_WRAP_V1"
    assert info["revision"] == 1
    assert info["evidence"]["source"] == "SIDE_BACK_SPLIT_3D_FACE_PROJECTION"


def test_bottom_insert_is_standard_not_top_rule_borrowing():
    import fold_designer_bridge as bridge
    render = SimpleNamespace(metadata={})
    top_solution = SimpleNamespace(
        rule_id="ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", rule_revision=1,
        trust_level="CERTIFIED", verified=True,
        projections=(SimpleNamespace(pair_count=2),),
        residual_projection=SimpleNamespace(pair_count=0),
        shadow_validation={},
    )
    info = bridge._phase6_joint_registry_diagnostic_info(
        _joint("BOTTOM", AssemblyJointRelation.INSERT),
        {"head": render}, {"head": top_solution},
    )
    assert info["registry_status"] == "MISS"
    assert info["rule_id"] is None
    assert info["candidate_status"] == "STANDARD"
