import pytest

from tools.execution_action_contract import ActionContractError, validate_execution_action
from tools.execution_record import ActionSpec


def test_unknown_and_legacy_text_are_not_executable_actions():
    for kind in ("LEGACY_TEXT", "FOO", "RESUME_EXACT_ACTION"):
        with pytest.raises(ActionContractError):
            validate_execution_action(ActionSpec(kind=kind, args={}, display="x"))


def test_apply_commit_requires_candidate_commit_sha():
    with pytest.raises(ActionContractError, match="candidate_commit_sha"):
        validate_execution_action(ActionSpec(kind="APPLY_COMMIT", args={}, display="apply"))
    assert validate_execution_action(
        ActionSpec(kind="APPLY_COMMIT", args={"candidate_commit_sha": "a" * 40}, display="apply")
    ) is True


def test_start_qa_requires_workflow_identity():
    with pytest.raises(ActionContractError, match="workflow"):
        validate_execution_action(ActionSpec(kind="START_QA", args={}, display="qa"))
    assert validate_execution_action(
        ActionSpec(kind="START_QA", args={"workflow": "broader-acceptance"}, display="qa")
    ) is True


def test_poll_and_accept_qa_require_exact_run_and_head():
    for kind in ("POLL_QA", "ACCEPT_QA"):
        with pytest.raises(ActionContractError):
            validate_execution_action(ActionSpec(kind=kind, args={"run_id": 123}, display=kind))
        assert validate_execution_action(
            ActionSpec(kind=kind, args={"run_id": 123, "head_sha": "b" * 40}, display=kind)
        ) is True


def test_merge_handoff_reconcile_and_wait_external_have_required_identity():
    cases = [
        ("MERGE", {"pr_number": 868}),
        ("HANDOFF", {"to_owner_kind": "SCHEDULER", "to_owner_id": "scheduler.a"}),
        ("RECONCILE", {"reason": "live head advanced"}),
        ("WAIT_EXTERNAL", {"blocker_kind": "EXTERNAL_DEPENDENCY"}),
    ]
    for kind, args in cases:
        assert validate_execution_action(ActionSpec(kind=kind, args=args, display=kind)) is True


def test_zero_arg_control_actions_are_finite_and_executable():
    for kind in ("ACQUIRE", "START_BRANCH", "FINALIZE", "YIELD"):
        assert validate_execution_action(ActionSpec(kind=kind, args={}, display=kind)) is True
