import importlib

import pytest


ACCEPTED = "db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f"


def _api():
    try:
        module = importlib.import_module("tools.issue312_t8_final_qualification")
    except ModuleNotFoundError:
        pytest.fail("T8 qualification helper is missing", pytrace=False)
    return module.QualificationError, module.validate_final_qualification


def _drift_api():
    try:
        module = importlib.import_module("tools.issue312_t8_drift_audit")
    except ModuleNotFoundError:
        pytest.fail("T8 drift-audit helper is missing", pytrace=False)
    return module.classify_path


def _cleanup_api():
    try:
        module = importlib.import_module("tools.issue312_t8_cleanup_gate")
    except ModuleNotFoundError:
        pytest.fail("T8 cleanup-gate helper is missing", pytrace=False)
    return module.CleanupGateError, module.compute_safe_deletions


def _good_payload():
    return {
        "accepted_t7_sha": ACCEPTED,
        "tested_sha": ACCEPTED,
        "collection": {
            "full": 2270,
            "unique_executed": 2270,
            "missing": [],
            "extra": [],
            "duplicate": [],
        },
        "results": {"unclassified_red": [], "infra_errors": []},
        "timing": {
            "execution_seconds": 314.0,
            "end_to_end_seconds": 316.0,
            "queue_seconds": 2.0,
        },
        "protected_drift": {},
        "production": {
            "mutated": False,
            "drift_audit_complete": True,
            "integration_shape_qualified": True,
        },
        "cleanup": {
            "evidence_secured": True,
            "open_pr_refs_checked": True,
            "deleted_live_pr_refs": [],
        },
        "durable_rules": {"updated": True, "readback_verified": True},
        "final_state": "QUALIFIED_FOR_INTEGRATION",
    }


def test_final_qualification_green():
    _, validate = _api()
    result = validate(_good_payload())
    assert result["decision"] == "GREEN"
    assert result["tested_sha"] == ACCEPTED
    assert result["final_state"] == "QUALIFIED_FOR_INTEGRATION"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda p: p.__setitem__("tested_sha", "wrong"), "T7_SHA_MISMATCH"),
        (lambda p: p["collection"]["missing"].append("node"), "MISSING_NODES"),
        (lambda p: p["collection"]["extra"].append("node"), "EXTRA_NODES"),
        (lambda p: p["collection"]["duplicate"].append("node"), "DUPLICATE_NODES"),
        (
            lambda p: p["collection"].__setitem__("unique_executed", 2269),
            "COLLECTION_EXECUTION_MISMATCH",
        ),
        (
            lambda p: p["results"]["unclassified_red"].append("node"),
            "UNCLASSIFIED_RED",
        ),
        (
            lambda p: p["protected_drift"].update({"config.ini": "changed"}),
            "PROTECTED_DRIFT",
        ),
        (
            lambda p: p["production"].__setitem__("mutated", True),
            "PRODUCTION_MUTATION",
        ),
        (
            lambda p: p["production"].__setitem__("drift_audit_complete", False),
            "DRIFT_AUDIT_INCOMPLETE",
        ),
        (
            lambda p: p["production"].__setitem__("integration_shape_qualified", False),
            "INTEGRATION_SHAPE_UNQUALIFIED",
        ),
        (
            lambda p: p["cleanup"].__setitem__("evidence_secured", False),
            "CLEANUP_BEFORE_EVIDENCE",
        ),
        (
            lambda p: p["cleanup"].__setitem__("open_pr_refs_checked", False),
            "OPEN_PR_REF_GATE_NOT_RUN",
        ),
        (
            lambda p: p["cleanup"]["deleted_live_pr_refs"].append("live-ref"),
            "LIVE_PR_REF_DELETED",
        ),
        (
            lambda p: p["durable_rules"].__setitem__("readback_verified", False),
            "DURABLE_RULE_READBACK_MISSING",
        ),
        (
            lambda p: p.__setitem__("final_state", "MERGED"),
            "INVALID_FINAL_STATE",
        ),
    ],
)
def test_final_qualification_fails_closed(mutation, code):
    QualificationError, validate = _api()
    payload = _good_payload()
    mutation(payload)
    with pytest.raises(QualificationError) as exc:
        validate(payload)
    assert exc.value.code == code


def test_ci_paths_are_not_production_source():
    classify_path = _drift_api()
    assert classify_path(".github/workflows/qa-issue312-t8-final-qualification.yml") == "CI_OR_EVIDENCE"
    assert classify_path("tools/test_shard_manifest.py") == "CI_OR_EVIDENCE"
    assert classify_path("docs/superpowers/checkpoints/issue312-t8.json") == "CI_OR_EVIDENCE"


def test_production_source_fails_out_of_ci_class():
    classify_path = _drift_api()
    assert classify_path("gui.py") == "PRODUCTION_SOURCE"
    assert classify_path("gui_modules/parts/door.py") == "PRODUCTION_SOURCE"


def test_open_pr_head_or_base_is_protected():
    _, compute_safe_deletions = _cleanup_api()
    result = compute_safe_deletions(
        candidates={"qa/temp-a", "qa/temp-b"},
        open_pr_refs={"qa/temp-a", "cleanup/2d-3d-sync"},
        evidence_secured=True,
    )
    assert result == {"safe": ["qa/temp-b"], "protected": ["qa/temp-a"]}


def test_cleanup_before_evidence_fails_closed():
    CleanupGateError, compute_safe_deletions = _cleanup_api()
    with pytest.raises(CleanupGateError) as exc:
        compute_safe_deletions({"qa/temp-a"}, set(), evidence_secured=False)
    assert exc.value.code == "CLEANUP_BEFORE_EVIDENCE"
