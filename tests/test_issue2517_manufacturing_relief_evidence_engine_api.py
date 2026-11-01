"""#2517: manufacturing relief evidence DTOs must be Engine-owned, not Phase6."""
import inspect
from types import SimpleNamespace

from ae_engine import manufacturing_api, resolve_manufacturing_relief_evidence
from ae_engine.contracts import ResolvedJointDiagnostic, ResolvedReliefRuleTrace
import ae_engine.manufacturing_relief_evidence as owner
import phase6_manufacturing_service as phase6


def _part(key, metadata=None):
    return SimpleNamespace(
        part_key=key, render_data=SimpleNamespace(metadata=metadata or {})
    )


def test_engine_preserves_corner_then_receiving_bottom_wrap_traces_without_mutation():
    solver_evidence = {"geometry_inputs": ["W", "T"], "geometry_evidence": {"src": [1]}}
    receiving_evidence = {
        "geometry_inputs": ["zl1"],
        "projection_by_corner": {"bottom_left": [1], "bottom_right": [2]},
    }
    metadata = {"receiving_bottom_relief_rule": {
        "rule_id": "CERTIFIED-BOTTOM", "revision": 3, "trust_level": "CERTIFIED",
        "geometry_evidence": receiving_evidence,
    }}
    result = SimpleNamespace(
        rule_id="ENDCAP-CERT", rule_revision=2, trust_level="CERTIFIED",
        corner_reliefs=(SimpleNamespace(corner_name="top_left", signature="TOP:INSERT"),),
        shadow_validation=solver_evidence,
    )
    traces, diag = resolve_manufacturing_relief_evidence(
        (_part("head", metadata),), {"head": result}, (),
    )
    assert manufacturing_api.resolve_manufacturing_relief_evidence is resolve_manufacturing_relief_evidence
    assert diag == ()
    assert len(traces) == 3
    assert all(isinstance(row, ResolvedReliefRuleTrace) for row in traces)
    assert [(row.part_key, row.corner_name, row.rule_id) for row in traces] == [
        ("head", "top_left", "ENDCAP-CERT"),
        ("head", "bottom_left", "CERTIFIED-BOTTOM"),
        ("head", "bottom_right", "CERTIFIED-BOTTOM"),
    ]
    assert traces[0].geometry_inputs == ("W", "T")
    assert traces[1].geometry_inputs == ("zl1",)
    assert traces[0].geometry_evidence == {"src": [1]}
    assert traces[0].geometry_evidence is not solver_evidence["geometry_evidence"]
    assert traces[1].geometry_evidence is not receiving_evidence
    assert traces[1].signature == "BOTTOM:WRAP"
    assert solver_evidence["geometry_evidence"] == {"src": [1]}
    assert receiving_evidence["projection_by_corner"]["bottom_left"] == [1]


def test_joint_registry_diagnostic_preserves_status_and_excludes_explicit(monkeypatch):
    evidence = {"signal": [4, 5]}
    monkeypatch.setattr(
        owner, "joint_relief_ownership",
        lambda joint: SimpleNamespace(preserve_part="box_body", relief_part="head"),
    )
    monkeypatch.setattr(
        owner, "joint_registry_diagnostic_info",
        lambda joint, by_part, by_solution: {
            "registry_status": "HIT", "rule_id": "SAME-REGISTRY",
            "revision": 2, "trust_level": "CERTIFIED",
            "candidate_status": "CERTIFIED",
            "verified": True, "pre_pair_count": 2, "post_pair_count": 1,
            "evidence": evidence,
        },
    )
    joint = SimpleNamespace(
        joint_id="j", subject_part="head", target_part="box_body",
        relation="INSERT", source="INTENT_DERIVED",
    )
    explicit = SimpleNamespace(
        joint_id="custom", subject_part="head", target_part="box_body",
        relation="INSERT", source="USER_ADDED",
    )
    traces, rows = resolve_manufacturing_relief_evidence(
        (_part("box_body"), _part("head")), {}, (joint, explicit),
    )
    assert traces == ()
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, ResolvedJointDiagnostic)
    assert row.joint_id == "j"
    assert row.registry_status == "HIT"
    assert row.preserve_part == "box_body" and row.relief_part == "head"
    assert row.legal_contact is True and row.illegal_penetration is False
    assert (row.pre_pair_count, row.post_pair_count) == (2, 1)
    assert row.evidence == evidence and row.evidence is not evidence


def test_phase6_only_consumes_engine_evidence_without_private_geometry():
    source = inspect.getsource(phase6.resolve)
    assert "resolve_manufacturing_relief_evidence(" in source
    assert "ResolvedReliefRuleTrace(" not in source
    assert "ResolvedJointDiagnostic(" not in source
    assert "joint_relief_ownership(" not in source
    assert "_phase6_joint_registry_diagnostic_info(" not in source
    assert "diagnostics.extend(tuple(divider_joint_diagnostics or ()))" in source
    assert "diagnostics.extend(tuple(explicit_joint_diagnostics or ()))" in source
