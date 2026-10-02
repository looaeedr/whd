from copy import deepcopy

from tools.execution_record import execution_record_from_legacy, execution_record_to_payload
from tools.execution_record_shadow import shadow_compare_legacy_to_v2


def _claim(**overrides):
    payload = {
        "issue": 844,
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "execution_intent": "SCHEDULER_LANE",
        "scheduler_lane": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "work_branch": "governance/issue844-unified-execution-record-20260928",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "production_target": "cleanup/2d-3d-sync",
        "production_sha": "c" * 40,
        "slot_id": "worker.slot.1",
        "next_action": "run focused GREEN",
        "master_issue": 842,
    }
    payload.update(overrides)
    return payload


def _checkpoint(**overrides):
    payload = {
        "issue": 844,
        "branch": "governance/issue844-unified-execution-record-20260928",
        "head_sha": "b" * 40,
        "state": "RUNNING",
        "next_action": "run focused GREEN",
        "run_id": None,
        "operation": None,
        "master_issue": 842,
        "next_issue": None,
        "chain_next_action": None,
        "last_accepted_run_id": None,
        "last_accepted_head_sha": None,
        "recovery_history": [],
        "issue_closed": False,
        "released_at": None,
        "merged_sha": None,
    }
    payload.update(overrides)
    return payload


def _native_from_legacy(claim=None, checkpoint=None):
    claim = claim or _claim()
    checkpoint = checkpoint or _checkpoint()
    return execution_record_to_payload(execution_record_from_legacy(claim, checkpoint))


def test_shadow_read_missing_v2_returns_bootstrap_candidate_without_mutation():
    claim = _claim()
    checkpoint = _checkpoint()

    result = shadow_compare_legacy_to_v2(claim, checkpoint, None)

    assert result.status == "V2_MISSING"
    assert result.differences == ()
    assert result.bootstrap_payload["schema"] == "WHD_EXECUTION_RECORD_V2"
    assert result.bootstrap_payload["issue"] == 844
    assert result.legacy_fingerprint
    assert result.v2_fingerprint is None


def test_shadow_read_exact_bootstrap_candidate_matches():
    native = _native_from_legacy()

    result = shadow_compare_legacy_to_v2(_claim(), _checkpoint(), native)

    assert result.status == "MATCH"
    assert result.differences == ()
    assert result.legacy_fingerprint == result.v2_fingerprint


def test_shadow_read_allows_structured_action_kind_when_display_matches_legacy_text():
    native = _native_from_legacy()
    native["next_action"] = {
        "kind": "START_QA",
        "args": {"suite": "focused"},
        "display": "run focused GREEN",
    }

    result = shadow_compare_legacy_to_v2(_claim(), _checkpoint(), native)

    assert result.status == "MATCH"
    assert result.differences == ()
    assert result.legacy_fingerprint != result.v2_fingerprint


def test_shadow_read_detects_owner_head_and_target_drift():
    native = _native_from_legacy()
    native["owner_id"] = "scheduler.other"
    native["head_sha"] = "d" * 40
    native["target_sha"] = "e" * 40

    result = shadow_compare_legacy_to_v2(_claim(), _checkpoint(), native)

    assert result.status == "MISMATCH"
    fields = {item.field for item in result.differences}
    assert {"owner_id", "head_sha", "target_sha"} <= fields


def test_shadow_read_detects_state_and_next_action_meaning_drift():
    native = _native_from_legacy()
    native["state"] = "VERIFYING"
    native["next_action"] = {
        "kind": "POLL_RUN",
        "args": {"run_id": 1},
        "display": "poll different run",
    }

    result = shadow_compare_legacy_to_v2(_claim(), _checkpoint(), native)

    assert result.status == "MISMATCH"
    by_field = {item.field: item for item in result.differences}
    assert by_field["state"].legacy == "ACTIVE"
    assert by_field["state"].v2 == "VERIFYING"
    assert by_field["next_action.display"].legacy == "run focused GREEN"
    assert by_field["next_action.display"].v2 == "poll different run"


def test_shadow_read_detects_qa_closure_and_chain_drift():
    claim = _claim(next_action=None)
    checkpoint = _checkpoint(
        state="TERMINAL_SUCCESS",
        next_action=None,
        last_accepted_run_id=36370000001,
        last_accepted_head_sha="b" * 40,
        next_issue=845,
        chain_next_action="claim exact successor #845",
        merged_sha="c" * 40,
    )
    native = _native_from_legacy(claim, checkpoint)
    native["qa"] = {"last_accepted_run": 36370000002, "accepted_head_sha": "b" * 40}
    native["closure"]["merged_sha"] = "d" * 40
    native["chain"]["next_issue"] = 846

    result = shadow_compare_legacy_to_v2(claim, checkpoint, native)

    assert result.status == "MISMATCH"
    fields = {item.field for item in result.differences}
    assert {"qa.last_accepted_run", "closure.merged_sha", "chain.next_issue"} <= fields


def test_shadow_read_does_not_mutate_native_payload():
    native = _native_from_legacy()
    before = deepcopy(native)

    shadow_compare_legacy_to_v2(_claim(), _checkpoint(), native)

    assert native == before
