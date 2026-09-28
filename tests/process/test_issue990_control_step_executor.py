import pytest

import tools.control_transaction_step_executor as step_executor


def test_step_sequence_accepts_only_declared_pairs():
    first, second = step_executor.normalize_step_sequence([
        {"kind": "MERGE", "effect": {"merged_sha": "a" * 40}},
        {"kind": "FINALIZE", "effect": {}},
    ])
    assert (first["kind"], second["kind"]) == ("MERGE", "FINALIZE")

    with pytest.raises(step_executor.ControlStepSequenceError):
        step_executor.normalize_step_sequence([
            {"kind": "ACQUIRE", "effect": {}},
            {"kind": "START_BRANCH", "effect": {}},
        ])


def test_step_sequence_runs_two_reads_and_two_transitions(monkeypatch):
    class Action:
        def __init__(self, kind):
            self.kind = kind

    class Record:
        def __init__(self, kind):
            self.next_action = Action(kind)

    states = [
        (None, None, {990: Record("MERGE")}),
        (None, None, {990: Record("FINALIZE")}),
    ]
    monkeypatch.setattr(step_executor, "_load_state", lambda *args, **kwargs: states.pop(0))

    calls = []

    def fake_execute_one(**kwargs):
        calls.append(kwargs["kind"])
        return {
            "result": "APPLIED",
            "post_generation": 10 + len(calls),
            "coord_commit_sha": str(len(calls)) * 40,
            "post_state": "INTEGRATING" if len(calls) == 1 else "DONE",
            "post_next_action": "FINALIZE" if len(calls) == 1 else None,
        }

    monkeypatch.setattr(step_executor, "execute_one", fake_execute_one)

    result = step_executor.execute_step_sequence(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=990,
        lane_id="scheduler.6ab13fa557fc8191935c671214b865e2",
        invocation_identity="scheduler-a:00:issue990",
        steps=[
            {"kind": "MERGE", "effect": {"merged_sha": "a" * 40}},
            {"kind": "FINALIZE", "effect": {}},
        ],
    )

    assert calls == ["MERGE", "FINALIZE"]
    assert result["result"] == "APPLIED"
    assert result["post_generation"] == 12
    assert result["post_state"] == "DONE"
