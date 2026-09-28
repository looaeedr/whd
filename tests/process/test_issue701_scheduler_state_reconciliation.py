from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEDULER_SKILL = ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
WRITER_SKILL = ROOT / ".agents" / "skills" / "engineering" / "寫排程" / "SKILL.md"

LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
ENTRY_A = "00"
AUTOMATION_A = "6ab13f881c34819180cee63f5dd9446b"
SCHEDULE_A = "BEGIN:VEVENT\nRRULE:FREQ=HOURLY;BYMINUTE=0\nEND:VEVENT"


def _contract():
    try:
        module = importlib.import_module("tools.scheduler_state_reconciliation")
    except ModuleNotFoundError:
        pytest.fail(
            "RED-STOP-24: canonical scheduler state reconciliation owner is missing"
        )
    state = getattr(module, "SchedulerStateReconciliationState", None)
    classify = getattr(module, "classify_scheduler_state_reconciliation", None)
    intent = getattr(module, "SchedulerStateMutationIntent", None)
    observed = getattr(module, "SchedulerStateObservation", None)
    assert isinstance(state, type), "RED-STOP-24: state enum missing"
    assert isinstance(intent, type), "RED-STOP-24: mutation intent identity missing"
    assert isinstance(observed, type), "RED-STOP-24: readback observation identity missing"
    assert callable(classify), "RED-STOP-24: classifier missing"
    return state, intent, observed, classify


def _intent(*, enabled_before: bool = False, enabled_after: bool = True):
    _, intent, _, _ = _contract()
    return intent(
        lane_owner=LANE_A,
        entrypoint=ENTRY_A,
        automation_id=AUTOMATION_A,
        schedule=SCHEDULE_A,
        timing_mode="exact_schedule",
        enabled_before=enabled_before,
        enabled_after=enabled_after,
    )


def _observation(
    *,
    lane_owner: str = LANE_A,
    entrypoint: str = ENTRY_A,
    automation_id: str = AUTOMATION_A,
    schedule: str = SCHEDULE_A,
    timing_mode: str = "exact_schedule",
    enabled: bool = True,
):
    _, _, observed, _ = _contract()
    return observed(
        lane_owner=lane_owner,
        entrypoint=entrypoint,
        automation_id=automation_id,
        schedule=schedule,
        timing_mode=timing_mode,
        enabled=enabled,
    )


def test_red_stop_24_pre_state_readback_allows_one_mutation_attempt():
    state, _, _, classify = _contract()
    decision = classify(_intent(), _observation(enabled=False))
    assert decision.state is state.NOT_APPLIED
    assert decision.reason


def test_red_stop_24_exact_post_state_is_effect_observed_after_crash():
    state, _, _, classify = _contract()
    decision = classify(_intent(), _observation(enabled=True))
    assert decision.state is state.EFFECT_OBSERVED
    assert decision.reason


@pytest.mark.parametrize(
    "observation",
    [
        _observation.__name__,
    ],
)
def test_red_stop_24_placeholder_for_collection_stability(observation):
    # Keeps pytest collection explicit while the real fail-closed cases below
    # instantiate only after the canonical owner exists.
    assert observation == "_observation"


def test_red_stop_24_wrong_or_missing_automation_identity_fails_closed():
    state, _, _, classify = _contract()
    wrong = classify(
        _intent(),
        _observation(automation_id="wrong-automation"),
    )
    missing = classify(
        _intent(),
        _observation(automation_id=""),
    )
    assert wrong.state is state.AMBIGUOUS
    assert missing.state is state.AMBIGUOUS


def test_red_stop_24_wrong_lane_or_entrypoint_fails_closed():
    state, _, _, classify = _contract()
    wrong_lane = classify(
        _intent(),
        _observation(lane_owner="scheduler.foreign"),
    )
    wrong_entry = classify(
        _intent(),
        _observation(entrypoint="20"),
    )
    assert wrong_lane.state is state.AMBIGUOUS
    assert wrong_entry.state is state.AMBIGUOUS


def test_red_stop_24_cadence_or_timing_mode_drift_fails_closed():
    state, _, _, classify = _contract()
    cadence_drift = classify(
        _intent(),
        _observation(
            schedule="BEGIN:VEVENT\nRRULE:FREQ=DAILY\nEND:VEVENT",
        ),
    )
    timing_drift = classify(
        _intent(),
        _observation(timing_mode="flexible_schedule"),
    )
    assert cadence_drift.state is state.AMBIGUOUS
    assert timing_drift.state is state.AMBIGUOUS


def test_red_stop_24_unknown_enabled_state_fails_closed():
    state, intent, observed, classify = _contract()
    current = observed(
        lane_owner=LANE_A,
        entrypoint=ENTRY_A,
        automation_id=AUTOMATION_A,
        schedule=SCHEDULE_A,
        timing_mode="exact_schedule",
        enabled=None,
    )
    decision = classify(
        intent(
            lane_owner=LANE_A,
            entrypoint=ENTRY_A,
            automation_id=AUTOMATION_A,
            schedule=SCHEDULE_A,
            timing_mode="exact_schedule",
            enabled_before=False,
            enabled_after=True,
        ),
        current,
    )
    assert decision.state is state.AMBIGUOUS


def test_red_stop_24_scheduler_entrypoints_bridge_canonical_reconciliation_owner():
    scheduler_text = SCHEDULER_SKILL.read_text(encoding="utf-8")
    writer_text = WRITER_SKILL.read_text(encoding="utf-8")
    marker = "SCHEDULER_STATE_RECONCILIATION_IDENTITY_V1"
    owner = "tools/scheduler_state_reconciliation.py"
    assert marker in scheduler_text
    assert owner in scheduler_text
    assert marker in writer_text
    assert owner in writer_text
