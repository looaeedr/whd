from __future__ import annotations

import inspect

from tools.local_durability_gate import LocalDurabilityState
import tools.stale_claim_takeover as takeover


def _evaluate(**overrides):
    fn = getattr(takeover, "evaluate_outage_recovery", None)
    assert callable(fn), (
        "R9_OUTAGE_RECOVERY_POLICY_MISSING: "
        "tools.stale_claim_takeover.evaluate_outage_recovery"
    )
    payload = {
        "local_state": LocalDurabilityState.LOCAL_MACHINE_UNAVAILABLE,
        "planned_handoff_verified": False,
        "exact_remote_run_active": False,
        "durable_checkpoint_present": True,
        "durable_next_action": "resume exact durable next action",
        "mutation_outcome": "NONE",
        "mutation_idempotent": True,
        "abnormal_outage": True,
    }
    payload.update(overrides)
    result = fn(**payload)
    assert isinstance(result, dict)
    assert result["schema"] == "WHD_OUTAGE_RECOVERY_V1"
    return result


def test_R9_reuses_wi1_local_state_vocabulary_without_second_enum():
    out = _evaluate(local_state=LocalDurabilityState.LOCAL_UNPUSHED)
    assert out["local_state"] == LocalDurabilityState.LOCAL_UNPUSHED.value
    assert not hasattr(takeover, "OutageLocalState")
    source = inspect.getsource(takeover)
    assert "from tools.local_durability_gate import LocalDurabilityState" in source


def test_R9_machine_unavailable_never_claims_local_only_truth_recovered():
    out = _evaluate(local_state=LocalDurabilityState.LOCAL_MACHINE_UNAVAILABLE)
    assert out["reason"] == "LOCAL_UNPERSISTED_STATE_UNKNOWN"
    assert out["resume_source"] == "DURABLE_GITHUB_ONLY"
    assert out["local_truth_recovered"] is False
    assert out["replay_allowed"] is False


def test_R9_unpushed_state_is_not_claimed_recovered_after_outage():
    out = _evaluate(local_state=LocalDurabilityState.LOCAL_UNPUSHED)
    assert out["reason"] == "LOCAL_UNPERSISTED_STATE_UNKNOWN"
    assert out["local_state"] == "LOCAL_UNPUSHED"
    assert out["local_truth_recovered"] is False


def test_R9_exact_active_remote_run_is_absolute_lock():
    out = _evaluate(
        local_state=LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        exact_remote_run_active=True,
        mutation_outcome="NOT_APPLIED",
    )
    assert out["decision"] == "REMOTE_RUN_LOCKED"
    assert out["reason"] == "EXACT_ACTIVE_REMOTE_RUN"
    assert out["stale_takeover_allowed"] is False
    assert out["replay_allowed"] is False


def test_R9_planned_handoff_prevents_fallback_to_stale_takeover():
    out = _evaluate(
        local_state=LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        planned_handoff_verified=True,
        abnormal_outage=True,
        mutation_outcome="NOT_APPLIED",
    )
    assert out["decision"] == "PLANNED_HANDOFF"
    assert out["reason"] == "PLANNED_HANDOFF_VERIFIED"
    assert out["stale_takeover_allowed"] is False
    assert out["resume_source"] == "DURABLE_GITHUB_ONLY"


def test_R9_unknown_non_idempotent_mutation_requires_reconcile_before_replay():
    out = _evaluate(
        local_state=LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        mutation_outcome="UNKNOWN",
        mutation_idempotent=False,
    )
    assert out["decision"] == "RECONCILE_BEFORE_REPLAY"
    assert out["reason"] == "UNKNOWN_MUTATION_OUTCOME"
    assert out["replay_allowed"] is False
    assert out["reconcile_before_replay"] is True


def test_R9_reconciled_not_applied_mutation_can_resume_from_durable_checkpoint():
    out = _evaluate(
        local_state=LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        mutation_outcome="NOT_APPLIED",
        mutation_idempotent=False,
    )
    assert out["decision"] == "DURABLE_RESUME"
    assert out["reason"] == "DURABLE_CHECKPOINT_RESUME"
    assert out["replay_allowed"] is True
    assert out["resume_source"] == "DURABLE_GITHUB_ONLY"


def test_R9_missing_durable_checkpoint_fails_closed():
    out = _evaluate(
        local_state=LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        durable_checkpoint_present=False,
        durable_next_action=None,
        mutation_outcome="NOT_APPLIED",
    )
    assert out["decision"] == "DURABLE_EVIDENCE_MISSING"
    assert out["reason"] == "DURABLE_CHECKPOINT_REQUIRED"
    assert out["stale_takeover_allowed"] is False
    assert out["replay_allowed"] is False


def test_R9_stale_takeover_is_only_eligible_for_abnormal_recovery():
    normal = _evaluate(
        local_state=LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        abnormal_outage=False,
        mutation_outcome="NOT_APPLIED",
    )
    abnormal = _evaluate(
        local_state=LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        abnormal_outage=True,
        mutation_outcome="NOT_APPLIED",
    )
    assert normal["stale_takeover_allowed"] is False
    assert abnormal["stale_takeover_allowed"] is True


def test_R9_approved_requirement_tokens_are_owned_by_recovery_policy():
    source = inspect.getsource(takeover)
    assert "LOCAL_UNPERSISTED_STATE_UNKNOWN" in source
    assert "UNKNOWN_MUTATION_OUTCOME" in source
