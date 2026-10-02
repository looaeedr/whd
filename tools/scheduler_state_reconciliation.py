"""Canonical durable readback classifier for WHD scheduler state mutations.

This module is intentionally pure: it does not call the automation host and it
does not own scheduler cadence, lane selection, or mutation transport. It only
classifies one exact pre-intent against one fresh live observation so a
crash/re-entry can decide whether the mutation is absent, already observed, or
ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SchedulerStateReconciliationState(str, Enum):
    NOT_APPLIED = "NOT_APPLIED"
    EFFECT_OBSERVED = "EFFECT_OBSERVED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class SchedulerStateMutationIntent:
    lane_owner: str
    entrypoint: str
    automation_id: str
    schedule: str
    timing_mode: str
    enabled_before: bool
    enabled_after: bool


@dataclass(frozen=True)
class SchedulerStateObservation:
    lane_owner: str
    entrypoint: str
    automation_id: str
    schedule: str
    timing_mode: str
    enabled: bool | None


@dataclass(frozen=True)
class SchedulerStateReconciliationDecision:
    state: SchedulerStateReconciliationState
    reason: str


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _decision(
    state: SchedulerStateReconciliationState,
    reason: str,
) -> SchedulerStateReconciliationDecision:
    return SchedulerStateReconciliationDecision(state=state, reason=reason)


def classify_scheduler_state_reconciliation(
    intent: SchedulerStateMutationIntent,
    observation: SchedulerStateObservation,
) -> SchedulerStateReconciliationDecision:
    """Classify one exact scheduler mutation readback.

    NOT_APPLIED means the exact pre-state is still live, so the caller may make
    at most the one mutation described by the durable intent.
    EFFECT_OBSERVED means the exact requested post-state is already live and
    must not be replayed.
    AMBIGUOUS means identity, cadence, timing mode, or state does not match the
    durable intent closely enough to act safely.
    """

    intent_identity = (
        intent.lane_owner,
        intent.entrypoint,
        intent.automation_id,
        intent.schedule,
        intent.timing_mode,
    )
    if not all(_nonblank(value) for value in intent_identity):
        return _decision(
            SchedulerStateReconciliationState.AMBIGUOUS,
            "scheduler mutation intent identity is incomplete",
        )
    if not isinstance(intent.enabled_before, bool) or not isinstance(
        intent.enabled_after, bool
    ):
        return _decision(
            SchedulerStateReconciliationState.AMBIGUOUS,
            "scheduler mutation intent enabled state is malformed",
        )
    if intent.enabled_before == intent.enabled_after:
        return _decision(
            SchedulerStateReconciliationState.AMBIGUOUS,
            "scheduler mutation intent does not describe a state transition",
        )

    observed_identity = (
        observation.lane_owner,
        observation.entrypoint,
        observation.automation_id,
        observation.schedule,
        observation.timing_mode,
    )
    if not all(_nonblank(value) for value in observed_identity):
        return _decision(
            SchedulerStateReconciliationState.AMBIGUOUS,
            "scheduler readback identity is incomplete",
        )
    if observed_identity != intent_identity:
        return _decision(
            SchedulerStateReconciliationState.AMBIGUOUS,
            "scheduler readback identity/cadence differs from durable intent",
        )
    if not isinstance(observation.enabled, bool):
        return _decision(
            SchedulerStateReconciliationState.AMBIGUOUS,
            "scheduler readback enabled state is unknown",
        )

    if observation.enabled == intent.enabled_before:
        return _decision(
            SchedulerStateReconciliationState.NOT_APPLIED,
            "exact durable pre-state is still observed",
        )
    if observation.enabled == intent.enabled_after:
        return _decision(
            SchedulerStateReconciliationState.EFFECT_OBSERVED,
            "exact durable requested post-state is already observed",
        )

    return _decision(
        SchedulerStateReconciliationState.AMBIGUOUS,
        "scheduler readback state is outside durable pre/post identity",
    )
