"""Execute a small, prevalidated sequence of WHD Flow v2 control steps in one runner.

Each step still uses the canonical production executor, so every transition gets
its own generation increment, coord ref CAS, exact readback, and runtime
observation. The optimization removes repeated GitHub Actions startup latency;
it does not merge semantic transitions into one record write.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from tools.control_transaction_production_executor import (
    ProductionExecutorError,
    _load_state,
    execute_one,
)

SCHEMA = "WHD_CONTROL_STEP_SEQUENCE_RESULT_V1"
REQUEST_KIND = "STEP_SEQUENCE"

SAFE_PAIRS = frozenset({
    ("ACQUIRE", "ACCEPT_QA"),
    ("ACQUIRE", "FAIL_QA"),
    ("ACQUIRE", "RECONCILE"),
    ("ACQUIRE", "BLOCK"),
    ("ACQUIRE", "HANDOFF"),
    ("ACQUIRE", "FINALIZE"),
    ("MERGE", "FINALIZE"),
})


class ControlStepSequenceError(ValueError):
    """Raised when a requested sequence is not one of the safe pairs."""


def normalize_step_sequence(steps: Iterable[Mapping[str, object]]) -> tuple[dict[str, object], dict[str, object]]:
    materialized = tuple(steps)
    if len(materialized) != 2:
        raise ControlStepSequenceError("step sequence must contain exactly two steps")

    normalized: list[dict[str, object]] = []
    for index, step in enumerate(materialized):
        if not isinstance(step, Mapping):
            raise ControlStepSequenceError(f"step {index} must be an object")
        kind = str(step.get("kind") or "").strip()
        effect = step.get("effect")
        if not kind:
            raise ControlStepSequenceError(f"step {index} kind must be nonblank")
        if not isinstance(effect, Mapping):
            raise ControlStepSequenceError(f"step {index} effect must be an object")
        normalized.append({"kind": kind, "effect": dict(effect)})

    pair = (str(normalized[0]["kind"]), str(normalized[1]["kind"]))
    if pair not in SAFE_PAIRS:
        raise ControlStepSequenceError(f"unsupported safe step pair: {pair[0]} -> {pair[1]}")
    return normalized[0], normalized[1]


def _assert_next_action(*, record, kind: str) -> None:
    if kind == "ACQUIRE":
        return
    action = record.next_action
    if action is None or action.kind != kind:
        observed = action.kind if action is not None else None
        raise ControlStepSequenceError(
            f"step {kind} does not match current next_action {observed!r}"
        )


def execute_step_sequence(
    *,
    repo: str,
    token: str,
    coord_branch: str,
    issue: int,
    lane_id: str,
    invocation_identity: str,
    steps: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    first, second = normalize_step_sequence(steps)
    results: list[dict[str, object]] = []

    for step in (first, second):
        _, _, records = _load_state(repo, token, coord_branch)
        record = records.get(issue)
        if record is None:
            raise ProductionExecutorError(f"native ExecutionRecord missing for issue {issue}")
        kind = str(step["kind"])
        _assert_next_action(record=record, kind=kind)
        result = execute_one(
            repo=repo,
            token=token,
            coord_branch=coord_branch,
            issue=issue,
            kind=kind,
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            supplied_effect=dict(step["effect"]),
        )
        results.append(result)

    return {
        "schema": SCHEMA,
        "result": "APPLIED",
        "issue": issue,
        "applied_steps": results,
        "post_generation": results[-1]["post_generation"],
        "coord_commit_sha": results[-1]["coord_commit_sha"],
        "post_state": results[-1]["post_state"],
        "post_next_action": results[-1]["post_next_action"],
    }
