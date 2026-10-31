"""#2517: Engine owns Certified Joint diagnostic status, not Phase6 GUI."""
from __future__ import annotations
from copy import deepcopy
import inspect
from types import SimpleNamespace

from ae_engine import manufacturing_api as api
from ae_engine import assembly_joint as owner
from phase6_manufacturing_geometry import _phase6_joint_registry_diagnostic_info as gui_diag


def _joint(edge, relation="WRAP"):
    return SimpleNamespace(edge=edge, relation=relation, subject_part="head", target_part="box_body")


def test_own_engine_contract_and_gui_forwarder():
    assert api.joint_registry_diagnostic_info is owner.joint_registry_diagnostic_info
    assert "manufacturing_api.joint_registry_diagnostic_info(" in inspect.getsource(gui_diag)
    assert "from phase6_" not in inspect.getsource(owner)


def test_bottom_wrap_certified_provenance_and_empty_rule_fail_closed():
    joint = _joint("BOTTOM")
    evidence = {"certified": ["head", "bottom"]}
    render = SimpleNamespace(metadata={"receiving_bottom_relief_rule": {
        "rule_id": "current-certified", "revision": 2,
        "trust_level": "CERTIFIED", "geometry_evidence": evidence,
    }})
    before = deepcopy(render.metadata)
    result = api.joint_registry_diagnostic_info(joint, {"head": render}, {})
    assert result == gui_diag(joint, {"head": render}, {})
    assert result["registry_status"] == "HIT"
    assert result["rule_id"] == "current-certified"
    assert result["verified"] is True
    assert result["evidence"] == evidence
    assert render.metadata == before
    absent = api.joint_registry_diagnostic_info(joint, {}, {})
    assert absent["registry_status"] == "MISS"
    assert absent["candidate_status"] == "UNSUPPORTED"
    assert absent["verified"] is False


def test_bottom_no_semantic_delta_stays_standard_not_certified():
    result = api.joint_registry_diagnostic_info(_joint("BOTTOM", "OVERLAY"), {}, {})
    assert result["registry_status"] == "MISS"
    assert result["candidate_status"] == "STANDARD"
    assert result["trust_level"] == "STANDARD"
    assert result["evidence"]["owner"] == "STANDARD"
    assert result == gui_diag(_joint("BOTTOM", "OVERLAY"), {}, {})


def test_other_edge_rule_proof_and_unknown_stay_separate():
    joint = _joint("LEFT", "INSERT")
    assert api.joint_registry_diagnostic_info(joint, {}, {})["candidate_status"] == "UNKNOWN"
    valid = SimpleNamespace(
        rule_id="certified-left", rule_revision="v2", trust_level="CERTIFIED",
        verified=True, projections=(SimpleNamespace(pair_count=2),),
        residual_projection=SimpleNamespace(pair_count=0),
        shadow_validation={"verified_world": True},
    )
    result = api.joint_registry_diagnostic_info(joint, {}, {"head": valid})
    assert result["registry_status"] == "HIT"
    assert result["revision"] == "v2"
    assert result["pre_pair_count"] == 2
    assert result["post_pair_count"] == 0
    assert result["evidence"]["verified_world"] is True
    assert result == gui_diag(joint, {}, {"head": valid})
