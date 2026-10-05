from types import SimpleNamespace

import pytest

from tools.control_transaction import (
    MERGE_ANCHOR_CORRECTION_PROOF_SCHEMA,
    MERGE_ANCHOR_PROOF_SCHEMA,
    ControlTransactionError,
    execute_transaction,
    prepare_transaction,
)
from tools.execution_record import (
    ActionSpec,
    ClosureState,
    ExecutionRecord,
    LeaseState,
    QAState,
)


HEAD = "b" * 40
OLD_TARGET = "c" * 40
DELIVERY_MERGE = "d" * 40
CURRENT_TARGET = "e" * 40
INVOCATION = "interactive:work0:anchor-fix"


def _merge_record() -> ExecutionRecord:
    return ExecutionRecord(
        issue=1197,
        execution_intent="EXECUTE_TICKET",
        owner_kind="SCHEDULER",
        owner_id="chatgpt.flowv2.work0",
        lane_id="chatgpt.flowv2.work0",
        slot_id="worker.slot.0",
        source_branch="refactor/issue1197",
        source_sha=HEAD,
        work_branch="refactor/issue1197",
        head_sha=HEAD,
        target_branch="cleanup/2d-3d-sync",
        target_sha=OLD_TARGET,
        state="INTEGRATING",
        semantic_state="QA_ACCEPTED",
        next_action=ActionSpec(
            kind="MERGE",
            args={"pr_number": 1205},
            display="reconcile merged delivery",
        ),
        lease=LeaseState(
            token="lease-1197",
            invocation_identity=INVOCATION,
            expires_at="2099-01-01T00:00:00Z",
        ),
        qa=QAState(last_accepted_run=37253515728, accepted_head_sha=HEAD),
        generation=4,
        updated_at="2026-10-05T04:25:00Z",
    )


def _merge_effect(*, with_proof: bool = True) -> dict[str, object]:
    effect: dict[str, object] = {
        "merge_precheck_status": "ALREADY_MERGED",
        "merged_sha": DELIVERY_MERGE,
        "target_sha": CURRENT_TARGET,
        "semantic_state": "MERGED",
        "next_action": {
            "kind": "FINALIZE",
            "args": {},
            "display": "Finalize exact merged Issue",
        },
        "updated_at": "2026-10-05T04:29:00Z",
    }
    if with_proof:
        effect["merge_anchor_proof"] = {
            "schema": MERGE_ANCHOR_PROOF_SCHEMA,
            "pr_number": 1205,
            "target_branch": "cleanup/2d-3d-sync",
            "merged_sha": DELIVERY_MERGE,
            "observed_target_sha": CURRENT_TARGET,
            "merged_anchor_is_ancestor": True,
            "fresh_readback": True,
            "trusted_source": "control_transaction_production_executor",
        }
    return effect


def test_already_merged_keeps_delivery_merge_anchor_separate_from_live_target():
    record = _merge_record()
    plan = prepare_transaction(
        record,
        kind="MERGE",
        transaction_id="tx-already-merged",
        invocation_identity=INVOCATION,
    )
    post = execute_transaction(record, plan, effect=_merge_effect())

    assert post.state == "INTEGRATING"
    assert post.semantic_state == "MERGED"
    assert post.closure.merged_sha == DELIVERY_MERGE
    assert post.target_sha == CURRENT_TARGET
    assert post.next_action.kind == "FINALIZE"


def test_already_merged_descendant_target_fails_without_trusted_anchor_proof():
    record = _merge_record()
    plan = prepare_transaction(
        record,
        kind="MERGE",
        transaction_id="tx-already-merged-no-proof",
        invocation_identity=INVOCATION,
    )
    with pytest.raises(ControlTransactionError, match="trusted merge-anchor proof"):
        execute_transaction(record, plan, effect=_merge_effect(with_proof=False))


def _wrong_anchor_record() -> ExecutionRecord:
    record = _merge_record()
    return ExecutionRecord(
        issue=record.issue,
        execution_intent=record.execution_intent,
        owner_kind=record.owner_kind,
        owner_id=record.owner_id,
        lane_id=record.lane_id,
        slot_id=record.slot_id,
        source_branch=record.source_branch,
        source_sha=record.source_sha,
        work_branch=record.work_branch,
        head_sha=record.head_sha,
        target_branch=record.target_branch,
        target_sha=CURRENT_TARGET,
        state="INTEGRATING",
        semantic_state="MERGED",
        next_action=ActionSpec(kind="FINALIZE", args={}, display="finalize"),
        lease=record.lease,
        qa=record.qa,
        closure=ClosureState(
            merged_sha=CURRENT_TARGET,
            issue_closed=False,
            released_at=None,
        ),
        generation=5,
        updated_at="2026-10-05T04:29:12Z",
    )


def test_reconcile_can_correct_legacy_wrong_merge_anchor_without_reqa():
    record = _wrong_anchor_record()
    plan = prepare_transaction(
        record,
        kind="RECONCILE",
        transaction_id="tx-anchor-correction",
        invocation_identity=INVOCATION,
    )
    post = execute_transaction(
        record,
        plan,
        effect={
            "observed_work_branch": record.work_branch,
            "observed_head_sha": record.head_sha,
            "observed_target_sha": CURRENT_TARGET,
            "state": "INTEGRATING",
            "semantic_state": "MERGE_ANCHOR_CORRECTED",
            "next_action": {
                "kind": "FINALIZE",
                "args": {},
                "display": "finalize",
            },
            "corrected_merged_sha": DELIVERY_MERGE,
            "merge_anchor_correction_proof": {
                "schema": MERGE_ANCHOR_CORRECTION_PROOF_SCHEMA,
                "pr_number": 1205,
                "target_branch": "cleanup/2d-3d-sync",
                "previous_merged_sha": CURRENT_TARGET,
                "corrected_merged_sha": DELIVERY_MERGE,
                "observed_target_sha": CURRENT_TARGET,
                "corrected_anchor_is_ancestor": True,
                "fresh_readback": True,
                "trusted_source": "control_transaction_production_executor",
            },
            "updated_at": "2026-10-05T04:31:00Z",
        },
    )

    assert post.closure.merged_sha == DELIVERY_MERGE
    assert post.target_sha == CURRENT_TARGET
    assert post.qa == record.qa
    assert post.next_action.kind == "FINALIZE"


def test_trusted_already_merged_effect_reads_pr_merge_commit_as_anchor(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _merge_record()
    monkeypatch.setattr(
        executor,
        "_merge_precheck_readback",
        lambda repo, token, record, pr_number: (
            {
                "merged": True,
                "merge_commit_sha": DELIVERY_MERGE,
                "head": {"sha": HEAD},
                "base": {"ref": "cleanup/2d-3d-sync"},
            },
            SimpleNamespace(
                classification="ALREADY_MERGED",
                observed_target_sha=CURRENT_TARGET,
                missing_required_checks=(),
                reason="already merged",
            ),
        ),
    )
    monkeypatch.setattr(
        executor,
        "_read_branch_head",
        lambda repo, token, branch: CURRENT_TARGET,
    )
    monkeypatch.setattr(
        executor,
        "_is_ancestor",
        lambda repo, token, ancestor, descendant: (
            ancestor == DELIVERY_MERGE and descendant == CURRENT_TARGET
        ),
    )

    effect = executor._trusted_merge_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=INVOCATION,
        supplied={},
    )

    assert effect["merged_sha"] == DELIVERY_MERGE
    assert effect["target_sha"] == CURRENT_TARGET
    assert effect["merge_anchor_proof"]["merged_anchor_is_ancestor"] is True
    assert effect["next_action"]["kind"] == "FINALIZE"
