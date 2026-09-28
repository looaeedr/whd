from dataclasses import replace

from tools.execution_claim_guard import GuardTransactionDecision, GuardTransactionState
from tools.execution_cutover_gate import assess_cutover_readiness
from tools.execution_ready_index import build_ready_index
from tools.execution_record import ActionSpec, TransactionState, execution_record_from_legacy, execution_record_to_payload
from tools.execution_record_shadow import shadow_compare_legacy_to_v2


LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"


def _legacy(issue=844, *, slot="worker.slot.1", lane=LANE_A, state="RUNNING", next_action="continue"):
    claim = {
        "issue": issue,
        "worker": lane,
        "executor_source": "scheduler",
        "execution_intent": "SCHEDULER_LANE",
        "scheduler_lane": lane,
        "work_branch": f"work/issue-{issue}",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "production_target": "cleanup/2d-3d-sync",
        "production_sha": "c" * 40,
        "slot_id": slot,
        "next_action": next_action,
        "master_issue": 842,
    }
    checkpoint = {
        "issue": issue,
        "branch": f"work/issue-{issue}",
        "head_sha": "b" * 40,
        "state": state,
        "next_action": next_action,
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
    return claim, checkpoint


def _record(issue=844, **kwargs):
    claim, checkpoint = _legacy(issue, **kwargs)
    legacy = execution_record_from_legacy(claim, checkpoint)
    structured = replace(
        legacy,
        next_action=ActionSpec(
            kind="START_QA",
            args={"workflow": "migration-shadow"},
            display=legacy.next_action.display,
        ),
    )
    return structured, claim, checkpoint


def _match(record, claim, checkpoint):
    return shadow_compare_legacy_to_v2(claim, checkpoint, execution_record_to_payload(record))


def _guard_none():
    return GuardTransactionDecision(GuardTransactionState.NONE)


def _guards(*issues):
    return {issue: _guard_none() for issue in issues}


def test_cutover_ready_requires_exact_shadow_match_and_valid_cache():
    record, claim, checkpoint = _record()
    index = build_ready_index([record])

    result = assess_cutover_readiness(
        [record],
        shadow_by_issue={844: _match(record, claim, checkpoint)},
        legacy_guard_by_issue=_guards(844),
        ready_index=index,
    )

    assert result.status == "READY"
    assert result.reasons == ()
    assert result.active_issues == (844,)
    assert result.shadowed_issues == (844,)
    assert result.ready_source_digest == index.source_digest


def test_active_legacy_text_next_action_blocks_cutover_even_when_shadow_matches():
    claim, checkpoint = _legacy(next_action="legacy prose action")
    record = execution_record_from_legacy(claim, checkpoint)
    shadow = shadow_compare_legacy_to_v2(claim, checkpoint, record)

    result = assess_cutover_readiness(
        [record], shadow_by_issue={record.issue: shadow}, legacy_guard_by_issue=_guards(record.issue), ready_index=build_ready_index([record])
    )

    assert result.status == "NOT_READY"
    assert any("structured next_action" in reason for reason in result.reasons)


def test_unknown_action_kind_blocks_cutover_even_with_matching_shadow_display():
    record, claim, checkpoint = _record()
    invalid = replace(record, next_action=ActionSpec(kind="FOO", args={}, display=record.next_action.display))
    shadow = shadow_compare_legacy_to_v2(claim, checkpoint, invalid)

    result = assess_cutover_readiness([invalid], shadow_by_issue={844: shadow}, legacy_guard_by_issue=_guards(844))

    assert result.status == "NOT_READY"
    assert any("unknown/non-executable action kind" in reason for reason in result.reasons)


def test_v2_missing_shadow_blocks_cutover():
    record, claim, checkpoint = _record()
    missing = shadow_compare_legacy_to_v2(claim, checkpoint, None)

    result = assess_cutover_readiness([record], shadow_by_issue={844: missing}, legacy_guard_by_issue=_guards(844))

    assert result.status == "NOT_READY"
    assert any("V2_MISSING" in reason for reason in result.reasons)


def test_shadow_mismatch_blocks_cutover():
    record, claim, checkpoint = _record()
    native = execution_record_to_payload(record)
    native["head_sha"] = "d" * 40
    mismatch = shadow_compare_legacy_to_v2(claim, checkpoint, native)

    result = assess_cutover_readiness([record], shadow_by_issue={844: mismatch}, legacy_guard_by_issue=_guards(844))

    assert result.status == "NOT_READY"
    assert any("MISMATCH" in reason for reason in result.reasons)


def test_missing_shadow_for_active_record_blocks_cutover():
    record, _, _ = _record()

    result = assess_cutover_readiness([record], shadow_by_issue={}, legacy_guard_by_issue=_guards(844))

    assert result.status == "NOT_READY"
    assert any("missing shadow" in reason for reason in result.reasons)


def test_non_reconciled_transaction_blocks_cutover():
    record, claim, checkpoint = _record()
    pending = replace(
        record,
        transaction=TransactionState(
            id="tx-pending",
            kind="APPLY_COMMIT",
            status="APPLIED",
            expected_fingerprint="d" * 64,
            invocation_identity="scheduled:00:run-a",
        ),
    )

    result = assess_cutover_readiness(
        [pending],
        shadow_by_issue={844: _match(record, claim, checkpoint)},
        legacy_guard_by_issue=_guards(844),
    )

    assert result.status == "NOT_READY"
    assert any("non-reconciled transaction" in reason for reason in result.reasons)


def test_duplicate_slot_or_scheduler_lane_blocks_cutover():
    first, c1, p1 = _record(844, slot="worker.slot.1")
    second, c2, p2 = _record(845, slot="worker.slot.1")

    result = assess_cutover_readiness(
        [first, second],
        shadow_by_issue={
            844: _match(first, c1, p1),
            845: _match(second, c2, p2),
        },
        legacy_guard_by_issue=_guards(844, 845),
    )

    assert result.status == "NOT_READY"
    assert any("duplicate slot occupancy" in reason for reason in result.reasons)
    assert any("multiple active records for scheduler lane" in reason for reason in result.reasons)


def test_stale_ready_index_blocks_cutover():
    record, claim, checkpoint = _record()
    index = build_ready_index([record])
    changed = replace(record, generation=record.generation + 1)

    result = assess_cutover_readiness(
        [changed],
        shadow_by_issue={844: _match(record, claim, checkpoint)},
        legacy_guard_by_issue=_guards(844),
        ready_index=index,
    )

    assert result.status == "NOT_READY"
    assert any("ready-index" in reason for reason in result.reasons)


def test_done_record_does_not_require_legacy_shadow():
    active, claim, checkpoint = _record(844)
    done = replace(
        active,
        issue=900,
        state="DONE",
        semantic_state="TERMINAL_SUCCESS",
        next_action=None,
        lease=None,
        slot_id="worker.slot.2",
        closure=replace(active.closure, issue_closed=True, released_at="2026-09-28T03:00:00Z"),
    )

    result = assess_cutover_readiness(
        [active, done],
        shadow_by_issue={844: _match(active, claim, checkpoint)},
        legacy_guard_by_issue=_guards(844),
    )

    assert result.status == "READY"
    assert result.active_issues == (844,)


def test_pending_or_expired_legacy_guard_blocks_cutover():
    record, claim, checkpoint = _record()
    shadow = _match(record, claim, checkpoint)

    for state in (GuardTransactionState.PENDING, GuardTransactionState.EXPIRED_UNCONSUMED):
        decision = GuardTransactionDecision(state=state, guard_run_ids=(36358916944,))
        result = assess_cutover_readiness(
            [record],
            shadow_by_issue={844: shadow},
            legacy_guard_by_issue={844: decision},
        )
        assert result.status == "NOT_READY"
        assert any(
            f"unresolved legacy Guard transaction state={state.value}" in reason
            for reason in result.reasons
        )


def test_missing_legacy_guard_assessment_blocks_cutover():
    record, claim, checkpoint = _record()
    result = assess_cutover_readiness(
        [record],
        shadow_by_issue={844: _match(record, claim, checkpoint)},
        legacy_guard_by_issue={},
    )
    assert result.status == "NOT_READY"
    assert any("missing legacy Guard transaction assessment" in reason for reason in result.reasons)


def test_consumed_legacy_guard_is_cutover_safe():
    record, claim, checkpoint = _record()
    result = assess_cutover_readiness(
        [record],
        shadow_by_issue={844: _match(record, claim, checkpoint)},
        legacy_guard_by_issue={
            844: GuardTransactionDecision(
                state=GuardTransactionState.CONSUMED, guard_run_ids=(36358514066,)
            )
        },
    )
    assert result.status == "READY"
