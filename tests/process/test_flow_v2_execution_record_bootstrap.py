from tools.execution_record import ActionSpec, execution_record_fingerprint
from tools.execution_record_bootstrap import plan_legacy_bootstrap
from tools.execution_record_shadow import shadow_compare_legacy_to_v2


def _legacy(*, next_action="run broader acceptance", state="RUNNING", slot_id="UNBOUND"):
    claim = {
        "issue": 844,
        "worker": "scheduler.a",
        "executor_source": "scheduler",
        "execution_intent": "SCHEDULER_LANE",
        "work_branch": "work/844",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "production_target": "cleanup/2d-3d-sync",
        "production_sha": "c" * 40,
        "slot_id": slot_id,
        "next_action": next_action,
        "master_issue": 842,
    }
    checkpoint = {
        "issue": 844,
        "branch": "work/844",
        "head_sha": "b" * 40,
        "state": state,
        "next_action": next_action,
        "run_id": None,
        "operation": None,
        "master_issue": None,
        "chain_state": "NONE",
        "next_issue": None,
        "chain_next_action": None,
        "issue_closed": False,
        "released_at": None,
    }
    return claim, checkpoint


def test_active_bootstrap_requires_explicit_structured_action_mapping():
    claim, checkpoint = _legacy()

    result = plan_legacy_bootstrap(claim, checkpoint)

    assert result.status == "REQUIRES_ACTION_MAPPING"
    assert result.candidate is None
    assert any("structured next_action" in reason for reason in result.reasons)


def test_bootstrap_never_accepts_legacy_text_as_structured_mapping():
    claim, checkpoint = _legacy()
    result = plan_legacy_bootstrap(
        claim,
        checkpoint,
        structured_next_action=ActionSpec(
            kind="LEGACY_TEXT", args={}, display="run broader acceptance"
        ),
    )
    assert result.status == "REQUIRES_ACTION_MAPPING"
    assert result.candidate is None


def test_explicit_mapping_must_preserve_legacy_display_during_shadow_migration():
    claim, checkpoint = _legacy(next_action="old visible meaning")
    result = plan_legacy_bootstrap(
        claim,
        checkpoint,
        structured_next_action=ActionSpec(
            kind="START_QA",
            args={"workflow": "broader-acceptance"},
            display="new visible meaning",
        ),
    )
    assert result.status == "REQUIRES_LEGACY_RECONCILIATION"
    assert result.candidate is None
    assert any("display" in reason for reason in result.reasons)


def test_explicit_mapping_produces_native_candidate_without_guessing_args():
    claim, checkpoint = _legacy(slot_id="UNBOUND")
    action = ActionSpec(
        kind="START_QA",
        args={"workflow": "broader-acceptance"},
        display="run broader acceptance",
    )

    result = plan_legacy_bootstrap(
        claim,
        checkpoint,
        structured_next_action=action,
    )

    assert result.status == "CANDIDATE_READY"
    assert result.candidate is not None
    assert result.candidate.next_action == action
    assert result.candidate.slot_id is None
    assert result.candidate.next_action.args == {"workflow": "broader-acceptance"}
    assert result.legacy_fingerprint != execution_record_fingerprint(result.candidate)
    shadow = shadow_compare_legacy_to_v2(claim, checkpoint, result.candidate)
    assert shadow.status == "MATCH"


def test_bootstrap_does_not_infer_machine_args_from_sha_mentioned_in_prose():
    prose = "run acceptance against current head " + "d" * 40
    claim, checkpoint = _legacy(next_action=prose)
    action = ActionSpec(kind="START_QA", args={"workflow": "broader-acceptance"}, display=prose)

    result = plan_legacy_bootstrap(
        claim,
        checkpoint,
        structured_next_action=action,
    )

    assert result.status == "CANDIDATE_READY"
    assert result.candidate.next_action.args == {"workflow": "broader-acceptance"}


def test_terminal_done_record_can_bootstrap_without_next_action_mapping():
    claim, checkpoint = _legacy(next_action=None, state="TERMINAL_SUCCESS")
    checkpoint["issue_closed"] = True
    checkpoint["released_at"] = "2026-09-28T03:00:00Z"

    result = plan_legacy_bootstrap(claim, checkpoint)

    assert result.status == "CANDIDATE_READY"
    assert result.candidate.state == "DONE"
    assert result.candidate.next_action is None
