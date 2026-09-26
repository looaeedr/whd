from pathlib import Path
import subprocess
import sys

import pytest

import tools.continuity_controller as continuity


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ISSUE = "#321"
EXPECTED_BRANCH = "fix/issue321-owning-checkpoint-guard-proof-20260916"
EXPECTED_HEAD_SHA = "abc123"


def _save_checkpoint(path: Path, state: continuity.ContinuityState) -> None:
    continuity.save_checkpoint(
        path,
        continuity.Checkpoint(
            issue=EXPECTED_ISSUE,
            branch=EXPECTED_BRANCH,
            head_sha=EXPECTED_HEAD_SHA,
            state=state,
            next_action=(
                None
                if state in continuity.TERMINAL_STATES
                else "execute exact next action"
            ),
        ),
    )


def _guard_kwargs(receipt_path: Path) -> dict[str, object]:
    return {
        "expected_issue": EXPECTED_ISSUE,
        "expected_branch": EXPECTED_BRANCH,
        "expected_head_sha": EXPECTED_HEAD_SHA,
        "receipt_path": receipt_path,
    }


def _blocked_exit_proof() -> continuity.BlockedExitProof:
    return continuity.BlockedExitProof(
        exhaustive=True,
        executable_leaf_count=0,
        evidence=("fresh durable blocker census: no executable alternative",),
        stop_reason=continuity.StopReason.EXTERNAL_AUTHORITY_REQUIRED,
    )


def test_path_boundary_exists_and_missing_checkpoint_fails_closed(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    with pytest.raises(continuity.CheckpointError, match="checkpoint file not found"):
        guard(tmp_path / "missing.json", **_guard_kwargs(tmp_path / "receipt.json"))


def test_path_boundary_rejects_malformed_checkpoint(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(continuity.CheckpointError, match="invalid checkpoint JSON"):
        guard(path, **_guard_kwargs(tmp_path / "receipt.json"))


def test_path_boundary_rejects_valid_but_nonowning_checkpoint(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    path = tmp_path / "foreign.json"
    continuity.save_checkpoint(
        path,
        continuity.Checkpoint(
            issue="#foreign",
            branch="foreign/branch",
            head_sha="deadbeef",
            state=continuity.ContinuityState.BLOCKED,
            next_action="wait for external authority",
        ),
    )
    with pytest.raises(continuity.CheckpointError, match="checkpoint owner mismatch"):
        guard(path, **_guard_kwargs(tmp_path / "receipt.json"))


def test_path_boundary_blocks_autonomous_nonterminal_checkpoint(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    path = tmp_path / "continuity.json"
    receipt = tmp_path / "receipt.json"
    _save_checkpoint(path, continuity.ContinuityState.RUNNING)
    with pytest.raises(continuity.TurnExitBlocked, match="execute exact next action"):
        guard(path, **_guard_kwargs(receipt))
    assert not receipt.exists(), "blocked guard must not mint turn-exit proof"


def test_path_boundary_must_really_invoke_canonical_guard(monkeypatch, tmp_path: Path):
    boundary = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(boundary), "missing canonical path-level turn-exit boundary"

    path = tmp_path / "continuity.json"
    receipt = tmp_path / "receipt.json"
    _save_checkpoint(path, continuity.ContinuityState.BLOCKED)

    calls = []

    def probe(checkpoint, *, expected_master_issue=None):
        calls.append((checkpoint, expected_master_issue))
        raise continuity.TurnExitBlocked("guard invocation probe")

    monkeypatch.setattr(continuity, "assert_turn_exitable", probe)
    with pytest.raises(continuity.TurnExitBlocked, match="guard invocation probe"):
        boundary(path, **_guard_kwargs(receipt))

    assert len(calls) == 1, "path boundary bypassed canonical assert_turn_exitable guard"
    assert calls[0][0].issue == EXPECTED_ISSUE
    assert calls[0][1] is None
    assert not receipt.exists(), "failed guard invocation must not mint turn-exit proof"


def test_valid_owning_checkpoint_without_guard_invocation_proof_fails_closed(tmp_path: Path):
    verify = getattr(continuity, "assert_turn_exit_permitted", None)
    assert callable(verify), "missing machine-verifiable guard invocation proof boundary"

    path = tmp_path / "continuity.json"
    receipt = tmp_path / "receipt.json"
    _save_checkpoint(path, continuity.ContinuityState.BLOCKED)

    with pytest.raises(continuity.TurnExitBlocked, match="guard invocation proof missing"):
        verify(
            path,
            receipt,
            expected_issue=EXPECTED_ISSUE,
            expected_branch=EXPECTED_BRANCH,
            expected_head_sha=EXPECTED_HEAD_SHA,
        )


def test_guard_invocation_mints_bound_proof_and_allows_genuine_blocked_checkpoint(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    verify = getattr(continuity, "assert_turn_exit_permitted", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"
    assert callable(verify), "missing machine-verifiable guard invocation proof boundary"

    path = tmp_path / "continuity.json"
    receipt = tmp_path / "receipt.json"
    _save_checkpoint(path, continuity.ContinuityState.BLOCKED)

    checkpoint = guard(
        path,
        blocked_exit_proof=_blocked_exit_proof(),
        **_guard_kwargs(receipt),
    )
    assert checkpoint.state is continuity.ContinuityState.BLOCKED
    assert receipt.exists(), "successful guard invocation must mint proof"

    verified = verify(
        path,
        receipt,
        expected_issue=EXPECTED_ISSUE,
        expected_branch=EXPECTED_BRANCH,
        expected_head_sha=EXPECTED_HEAD_SHA,
    )
    assert verified.state is continuity.ContinuityState.BLOCKED


def test_guard_invocation_proof_becomes_stale_if_checkpoint_changes(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    verify = getattr(continuity, "assert_turn_exit_permitted", None)
    assert callable(guard)
    assert callable(verify)

    path = tmp_path / "continuity.json"
    receipt = tmp_path / "receipt.json"
    _save_checkpoint(path, continuity.ContinuityState.BLOCKED)
    guard(
        path,
        blocked_exit_proof=_blocked_exit_proof(),
        **_guard_kwargs(receipt),
    )

    continuity.save_checkpoint(
        path,
        continuity.Checkpoint(
            issue=EXPECTED_ISSUE,
            branch=EXPECTED_BRANCH,
            head_sha=EXPECTED_HEAD_SHA,
            state=continuity.ContinuityState.BLOCKED,
            next_action="different external blocker",
            evidence=("checkpoint changed after guard",),
        ),
    )

    with pytest.raises(continuity.TurnExitBlocked, match="guard invocation proof stale"):
        verify(
            path,
            receipt,
            expected_issue=EXPECTED_ISSUE,
            expected_branch=EXPECTED_BRANCH,
            expected_head_sha=EXPECTED_HEAD_SHA,
        )


def test_outer_process_hook_fails_closed_without_guard_proof(tmp_path: Path):
    hook = ROOT / "tools" / "assistant_turn_exit_gate.py"
    assert hook.exists(), "missing outer executable assistant turn-exit hook"

    path = tmp_path / "continuity.json"
    receipt = tmp_path / "receipt.json"
    _save_checkpoint(path, continuity.ContinuityState.BLOCKED)

    result = subprocess.run(
        [
            sys.executable,
            str(hook),
            str(path),
            str(receipt),
            "--issue",
            EXPECTED_ISSUE,
            "--branch",
            EXPECTED_BRANCH,
            "--head-sha",
            EXPECTED_HEAD_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "guard invocation proof missing" in (result.stdout + result.stderr)


def test_outer_process_hook_accepts_only_after_actual_guard_invocation(tmp_path: Path):
    hook = ROOT / "tools" / "assistant_turn_exit_gate.py"
    assert hook.exists(), "missing outer executable assistant turn-exit hook"

    path = tmp_path / "continuity.json"
    receipt = tmp_path / "receipt.json"
    _save_checkpoint(path, continuity.ContinuityState.BLOCKED)
    continuity.assert_turn_exitable_path(
        path,
        blocked_exit_proof=_blocked_exit_proof(),
        **_guard_kwargs(receipt),
    )

    result = subprocess.run(
        [
            sys.executable,
            str(hook),
            str(path),
            str(receipt),
            "--issue",
            EXPECTED_ISSUE,
            "--branch",
            EXPECTED_BRANCH,
            "--head-sha",
            EXPECTED_HEAD_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TURN_EXIT_PERMITTED" in result.stdout


def test_canonical_controller_skill_requires_path_level_boundary():
    text = (
        ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "assert_turn_exitable_path" in text
    assert "missing / unreadable checkpoint" in text
    assert "guard invocation proof" in text
    assert "owning checkpoint" in text
