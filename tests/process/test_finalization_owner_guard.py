from pathlib import Path

import pytest

import tools.continuity_controller as continuity
from tools.continuity_controller import (
    Checkpoint,
    ContinuityState,
    FinalizationBlocked,
)


ROOT = Path(__file__).resolve().parents[2]
ISSUE = "#291"
BRANCH = "fix/fail-closed-owning-checkpoint-guard-20260916"
HEAD = "2bbf59fbb2ff2e79c67d9817964d3ff6213b2228"


def _terminal(**overrides) -> Checkpoint:
    values = dict(
        issue=ISSUE,
        branch=BRANCH,
        head_sha=HEAD,
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=continuity.ClosureState.ISSUE_CLOSE_PENDING,
        closure_next_action="verify bound proof then close owning Issue without checkpoint mutation",
        evidence=("acceptance green", "cleanup complete"),
    )
    values.update(overrides)
    return Checkpoint(**values)


def _owner(**overrides):
    values = dict(
        expected_issue=ISSUE,
        expected_branch=BRANCH,
        expected_head_sha=HEAD,
    )
    values.update(overrides)
    return values


def test_owned_finalization_guard_rejects_proof_before_issue_close_pending():
    guard = getattr(continuity, "authorize_finalization", None)
    assert callable(guard)

    checkpoint = _terminal(
        closure_state=continuity.ClosureState.FINALIZATION_PENDING,
        closure_next_action="advance to ISSUE_CLOSE_PENDING before minting proof",
    )

    with pytest.raises(FinalizationBlocked, match="ISSUE_CLOSE_PENDING"):
        guard(checkpoint, **_owner())


def test_bound_proof_becomes_stale_if_checkpoint_advances_after_authorization():
    guard = getattr(continuity, "authorize_finalization", None)
    verify = getattr(continuity, "assert_finalization_proof", None)
    assert callable(guard)
    assert callable(verify)

    checkpoint = _terminal()
    proof = guard(checkpoint, **_owner())
    verify(checkpoint, proof, **_owner())

    advanced = continuity.advance_closure(
        checkpoint,
        state=continuity.ClosureState.RELEASE_HANDOFF_PENDING,
        next_action="atomically close checkpoint and release claim after Issue readback",
        evidence=("owning Issue closed/completed readback verified",),
    )
    with pytest.raises(FinalizationBlocked, match="stale finalization proof"):
        verify(advanced, proof, **_owner())


def test_owned_finalization_guard_requires_explicit_owner_identity():
    guard = getattr(continuity, "authorize_finalization", None)
    assert callable(guard), "missing authorize_finalization owning-checkpoint guard"

    checkpoint = _terminal()
    for missing in ("expected_issue", "expected_branch", "expected_head_sha"):
        owner = _owner()
        owner[missing] = ""
        with pytest.raises(FinalizationBlocked, match="owning checkpoint"):
            guard(checkpoint, **owner)


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("expected_issue", "#999"),
        ("expected_branch", "fix/wrong-owner"),
        ("expected_head_sha", "deadbeef"),
    ],
)
def test_owned_finalization_guard_rejects_mismatched_checkpoint_owner(field, wrong):
    guard = getattr(continuity, "authorize_finalization", None)
    assert callable(guard), "missing authorize_finalization owning-checkpoint guard"

    owner = _owner(**{field: wrong})
    with pytest.raises(FinalizationBlocked, match="owning checkpoint mismatch"):
        guard(_terminal(), **owner)


def test_owned_finalization_guard_returns_bound_machine_proof():
    guard = getattr(continuity, "authorize_finalization", None)
    assert callable(guard), "missing authorize_finalization owning-checkpoint guard"

    proof = guard(_terminal(), **_owner())
    assert proof.issue == ISSUE
    assert proof.branch == BRANCH
    assert proof.head_sha == HEAD
    assert proof.checkpoint_fingerprint


def test_closure_verifier_fails_closed_without_actual_guard_invocation_proof():
    verify = getattr(continuity, "assert_finalization_proof", None)
    assert callable(verify), "missing assert_finalization_proof closure boundary guard"

    with pytest.raises(FinalizationBlocked, match="guard invocation proof"):
        verify(_terminal(), None, **_owner())


def test_closure_verifier_accepts_only_current_proof_from_owned_guard():
    guard = getattr(continuity, "authorize_finalization", None)
    verify = getattr(continuity, "assert_finalization_proof", None)
    assert callable(guard)
    assert callable(verify)

    checkpoint = _terminal()
    proof = guard(checkpoint, **_owner())
    verify(checkpoint, proof, **_owner())

    changed = _terminal(evidence=checkpoint.evidence + ("post-guard mutation",))
    with pytest.raises(FinalizationBlocked, match="stale finalization proof"):
        verify(changed, proof, **_owner())


def test_authorize_cli_writes_proof_and_verify_cli_requires_it(tmp_path: Path, capsys):
    checkpoint_path = tmp_path / "continuity.json"
    proof_path = tmp_path / "finalization-proof.json"
    continuity.save_checkpoint(checkpoint_path, _terminal())

    authorize_code = continuity.main(
        [
            "authorize-finalization",
            str(checkpoint_path),
            "--issue",
            ISSUE,
            "--branch",
            BRANCH,
            "--head-sha",
            HEAD,
            "--proof-out",
            str(proof_path),
        ]
    )
    authorize_output = capsys.readouterr().out
    assert authorize_code == 0
    assert "FINALIZATION_GUARD_PASS" in authorize_output
    assert proof_path.is_file()

    verify_code = continuity.main(
        [
            "verify-finalization-proof",
            str(checkpoint_path),
            str(proof_path),
            "--issue",
            ISSUE,
            "--branch",
            BRANCH,
            "--head-sha",
            HEAD,
        ]
    )
    verify_output = capsys.readouterr().out
    assert verify_code == 0
    assert "FINALIZATION_PROOF_VALID" in verify_output

    proof_path.unlink()
    missing_code = continuity.main(
        [
            "verify-finalization-proof",
            str(checkpoint_path),
            str(proof_path),
            "--issue",
            ISSUE,
            "--branch",
            BRANCH,
            "--head-sha",
            HEAD,
        ]
    )
    missing_output = capsys.readouterr().out
    assert missing_code == 2
    assert "FINALIZATION_GUARD_ERROR" in missing_output


def test_skills_and_pitfall_route_closure_through_owned_guard_proof():
    controller_skill = (ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md").read_text(encoding="utf-8")
    closure_skill = (ROOT / ".agents/skills/engineering/issue-closure-gate/SKILL.md").read_text(encoding="utf-8")
    pitfall = (ROOT / "個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md").read_text(encoding="utf-8")

    assert "OWNING_FINALIZATION_GUARD_V2" in controller_skill
    assert "authorize-finalization" in controller_skill
    assert "verify-finalization-proof" in controller_skill
    assert "Bare `assert_finalizable(checkpoint)` must never" in controller_skill

    assert "OWNING_FINALIZATION_GUARD_V2" in closure_skill
    assert "沒有 owning checkpoint" in closure_skill
    assert "沒有本次 guard invocation proof" in closure_skill
    assert "verify-finalization-proof" in closure_skill

    assert "OWNING_CHECKPOINT_GUARD_BYPASS_PITFALL" in pitfall
    assert "assert_finalizable` 僅為 state-only predicate" in pitfall
    assert "真正 close/finalize mutation 前必須再次 `verify-finalization-proof`" in pitfall
