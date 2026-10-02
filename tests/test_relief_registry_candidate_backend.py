# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest

from ae_engine.certified_relief_registry import (
    CertifiedReliefRegistryError,
    save_relief_rule_candidate,
    load_relief_rule_candidates,
    promote_relief_rule_candidate,
    load_external_relief_rule_records,
)


def _candidate():
    return {
        "rule_id": "USER_WRAP_TEST",
        "cabinet_family": "ANY",
        "part_role": "HEAD_OR_TAIL",
        "joint_face": "TOP_LEFT",
        "assembly_intent": "INSERT_OVERLAY",
        "joint_signature": [
            {"relation":"INSERT_OVERLAY","subject_role":"HEAD_OR_TAIL","target_role":"BOX_SIDE","subject_region":"TOP_LEFT","target_region":"MATING_ZONE"},
            {"relation":"WRAP","subject_role":"HEAD_OR_TAIL","target_role":"REAR_PANEL","subject_region":"TOP_LEFT","target_region":"WRAP_ZONE"},
        ],
        "topology_levels": 2,
        "preconditions": ["ytop1_present", "x_folded"],
        "formula": {"primary_u":"side_fold + FW", "primary_v":"ytop1 + FW - T", "secondary_u":"side_fold + 0.5*T", "secondary_depth":"2*T"},
        "source": "operator verified drawing",
    }


def test_candidate_is_saved_separately_and_does_not_mutate_certified_registry(tmp_path):
    candidates = tmp_path / "candidates.json"
    certified = tmp_path / "certified.json"
    certified.write_text(json.dumps({"schema_version":2,"rules":[]}), encoding="utf-8")
    item = save_relief_rule_candidate(_candidate(), path=candidates)
    assert item["status"] == "CANDIDATE"
    assert load_relief_rule_candidates(candidates)[0]["rule_id"] == "USER_WRAP_TEST"
    assert load_external_relief_rule_records(certified) == ()


def test_promotion_requires_regression_evidence_and_creates_new_revision(tmp_path):
    candidates = tmp_path / "candidates.json"
    certified = tmp_path / "certified.json"
    certified.write_text(json.dumps({"schema_version":2,"rules":[]}, ensure_ascii=False), encoding="utf-8")
    saved = save_relief_rule_candidate(_candidate(), path=candidates)
    with pytest.raises(CertifiedReliefRegistryError, match="regression"):
        promote_relief_rule_candidate(saved["candidate_id"], candidates_path=candidates, certified_path=certified, regression_evidence={})
    promoted = promote_relief_rule_candidate(
        saved["candidate_id"],
        candidates_path=candidates,
        certified_path=certified,
        regression_evidence={"matrix_passed": True, "cases": 12, "zero_penetration": True, "candidate_specific": True, "candidate_id": saved["candidate_id"]},
    )
    assert promoted["trust_level"] == "CERTIFIED"
    assert promoted["revision"] == 1
    assert load_external_relief_rule_records(certified)[0]["rule_id"] == "USER_WRAP_TEST"
    assert load_relief_rule_candidates(candidates)[0]["status"] == "PROMOTED"


def test_promotion_rejects_zero_penetration_evidence_not_bound_to_candidate(tmp_path):
    candidates = tmp_path / "candidates.json"
    certified = tmp_path / "certified.json"
    certified.write_text(json.dumps({"schema_version":2,"rules":[]}, ensure_ascii=False), encoding="utf-8")
    saved = save_relief_rule_candidate(_candidate(), path=candidates)
    with pytest.raises(CertifiedReliefRegistryError, match="candidate-specific"):
        promote_relief_rule_candidate(
            saved["candidate_id"],
            candidates_path=candidates,
            certified_path=certified,
            regression_evidence={"matrix_passed": True, "cases": 12, "zero_penetration": True},
        )
    with pytest.raises(CertifiedReliefRegistryError, match="candidate_id"):
        promote_relief_rule_candidate(
            saved["candidate_id"],
            candidates_path=candidates,
            certified_path=certified,
            regression_evidence={"matrix_passed": True, "cases": 12, "zero_penetration": True, "candidate_specific": True, "candidate_id": "other"},
        )


def test_wrap_candidate_can_be_independent_from_high_level_assembly_intent(tmp_path):
    candidate = _candidate()
    candidate["rule_id"] = "USER_BOTTOM_WRAP_ANY"
    candidate["assembly_intent"] = "ANY"
    candidate["joint_face"] = "BOTTOM"
    candidate["joint_signature"] = [
        {"relation":"WRAP","subject_role":"HEAD_OR_TAIL","target_role":"REAR_PANEL","subject_region":"BOTTOM","target_region":"OUTER_SURFACE"},
    ]
    candidate["topology_levels"] = 2
    item = save_relief_rule_candidate(candidate, path=tmp_path / "candidates.json")
    assert item["assembly_intent"] == "ANY"
