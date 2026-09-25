from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
ISSUE = 540
WORK_BRANCH = "feature/issue540-stale-takeover-20260923"
BASE_SHA = "a8be8a41dc56ed1af9eee50bc6177e10b5fc0a04"
CLAIM_HEAD = "a" * 40
LIVE_HEAD = "b" * 40


def _module():
    return importlib.import_module("tools.stale_claim_takeover")


def _claim(**overrides):
    payload = {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": "chatgpt",
        "executor_source": "chatgpt_interactive",
        "work_branch": WORK_BRANCH,
        "claimed_at": "2026-09-23T05:00:00+08:00",
        "base_sha": BASE_SHA,
        "head_sha": CLAIM_HEAD,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-23T06:00:00+08:00",
        "remote_qa": None,
        "next_action": "continue exact task",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _evaluate(*, now, claim=None, live_head=CLAIM_HEAD, live_commit_at=None, remote=None, threshold=600):
    module = _module()
    if live_commit_at is None:
        live_commit_at = now - timedelta(hours=1)
    return module.evaluate_stale_claim_takeover(
        claim or _claim(),
        now=now,
        live_head_sha=live_head,
        live_head_committed_at=live_commit_at,
        remote_run=remote,
        stale_after_seconds=threshold,
    )


def test_599_seconds_is_not_takeover_eligible():
    now = datetime(2026, 9, 23, 6, 9, 59, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T06:00:00Z")
    result = _evaluate(now=now, claim=claim)
    assert result.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert result.actionable is False
    assert result.stale_seconds == 599


def test_exactly_600_seconds_without_active_run_is_executor_stuck():
    now = datetime(2026, 9, 23, 6, 10, 0, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T06:00:00Z")
    result = _evaluate(now=now, claim=claim)
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.stale_seconds == 600
    assert result.previous_executor_source == "chatgpt_interactive"


def test_active_exact_remote_run_blocks_takeover_even_when_old():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    remote = {
        "found": True,
        "run_id": 12345,
        "head_sha": CLAIM_HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-23T05:00:00Z",
    }
    claim = _claim(
        last_update="2026-09-23T05:00:00Z",
        remote_qa={"run_id": 12345, "head_sha": CLAIM_HEAD},
    )
    result = _evaluate(now=now, claim=claim, remote=remote)
    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False


def test_recent_branch_commit_blocks_takeover():
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T05:00:00Z")
    result = _evaluate(
        now=now,
        claim=claim,
        live_head=LIVE_HEAD,
        live_commit_at=datetime(2026, 9, 23, 6, 15, 0, tzinfo=UTC),
    )
    assert result.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert result.actionable is False
    assert result.observed_live_head_sha == LIVE_HEAD
    assert result.stale_seconds == 300


def test_old_advanced_branch_can_be_taken_over_at_observed_live_head():
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T05:00:00Z")
    result = _evaluate(
        now=now,
        claim=claim,
        live_head=LIVE_HEAD,
        live_commit_at=datetime(2026, 9, 23, 6, 9, 0, tzinfo=UTC),
    )
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.observed_live_head_sha == LIVE_HEAD
    assert result.stale_seconds == 660


def test_scheduler_owned_claim_does_not_require_takeover():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    result = _evaluate(
        now=now,
        claim=_claim(
            executor_source="scheduler",
            last_update="2026-09-23T05:00:00Z",
        ),
    )
    assert result.classification.value == "ALREADY_SCHEDULER"
    assert result.actionable is False


def test_inactive_claim_is_terminal_not_takeover():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    result = _evaluate(
        now=now,
        claim=_claim(phase="RELEASED", last_update="2026-09-23T05:00:00Z"),
    )
    assert result.classification.value == "TERMINAL"
    assert result.actionable is False


def test_malformed_progress_timestamp_fails_closed():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    with pytest.raises(Exception, match="last_update|timestamp|ISO"):
        _evaluate(now=now, claim=_claim(last_update="not-a-time"))


def _write_takeover_evidence(tmp_path: Path, **overrides) -> Path:
    payload = {
        "schema": "WHD_STALE_CLAIM_TAKEOVER_V1",
        "classification": "EXECUTOR_STUCK",
        "actionable": True,
        "stale_seconds": 600,
        "stale_after_seconds": 600,
        "previous_executor_source": "chatgpt_interactive",
        "previous_worker": "chatgpt",
        "requesting_worker": "scheduler.test",
        "requesting_executor_source": "scheduler",
        "user_authority_comment_id": None,
        "observed_live_head_sha": LIVE_HEAD,
        "claim_head_sha": CLAIM_HEAD,
        "claim_last_update": "2026-09-23T05:00:00Z",
        "claim_phase": "IMPLEMENTING",
        "latest_progress_at": "2026-09-23T05:50:00Z",
    }
    payload.update(overrides)
    path = tmp_path / "takeover-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_claim_takeover_requires_machine_stale_evidence(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    assert "claim-takeover" in guard.ALLOWED_ACTIONS

    claim_path = tmp_path / "claim.json"
    claim_path.write_text(
        json.dumps(_claim(last_update="2026-09-23T05:00:00Z")),
        encoding="utf-8",
    )
    with pytest.raises(guard.ExecutionClaimError, match="takeover|evidence|stale"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker="chatgpt",
            branch=WORK_BRANCH,
            action="claim-takeover",
            expected_base_sha=BASE_SHA,
            expected_head_sha=LIVE_HEAD,
        )


def test_claim_takeover_accepts_bound_evidence_and_observed_live_head(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(
        json.dumps(_claim(last_update="2026-09-23T05:00:00Z")),
        encoding="utf-8",
    )
    evidence = _write_takeover_evidence(tmp_path)

    claim = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker="chatgpt",
        branch=WORK_BRANCH,
        action="claim-takeover",
        expected_base_sha=BASE_SHA,
        expected_head_sha=LIVE_HEAD,
        takeover_evidence=evidence,
    )
    assert claim.issue == ISSUE
    assert claim.work_branch == WORK_BRANCH
    assert claim.head_sha == CLAIM_HEAD


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("classification", "WAIT_ON_FOREIGN_RUNTIME"),
        ("actionable", False),
        ("stale_seconds", 599),
        ("previous_executor_source", "other-runtime"),
        ("observed_live_head_sha", "c" * 40),
        ("claim_head_sha", "d" * 40),
        ("claim_last_update", "2026-09-23T05:00:01Z"),
        ("claim_phase", "GREEN"),
    ],
)
def test_claim_takeover_rejects_unbound_or_nonactionable_evidence(
    tmp_path: Path,
    field: str,
    value,
):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(
        json.dumps(_claim(last_update="2026-09-23T05:00:00Z")),
        encoding="utf-8",
    )
    evidence = _write_takeover_evidence(tmp_path, **{field: value})
    with pytest.raises(guard.ExecutionClaimError, match="takeover|evidence|stale|head|source|phase"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker="chatgpt",
            branch=WORK_BRANCH,
            action="claim-takeover",
            expected_base_sha=BASE_SHA,
            expected_head_sha=LIVE_HEAD,
            takeover_evidence=evidence,
        )


def test_cli_require_actionable_uses_same_600_second_boundary(tmp_path: Path):
    import subprocess
    import sys

    module_path = Path(__file__).resolve().parents[2] / "tools" / "stale_claim_takeover.py"
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(
        json.dumps(_claim(last_update="2026-09-23T06:00:00Z")),
        encoding="utf-8",
    )
    common = [
        sys.executable,
        str(module_path),
        "--claim",
        str(claim_path),
        "--live-head-sha",
        CLAIM_HEAD,
        "--live-head-committed-at",
        "2026-09-23T05:00:00Z",
        "--require-actionable",
    ]

    early = subprocess.run(
        [*common, "--now", "2026-09-23T06:09:59Z"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert early.returncode == 3
    assert "WAIT_ON_FOREIGN_RUNTIME" in early.stdout
    assert "STALE_CLAIM_TAKEOVER_BLOCKED" in early.stdout

    stale = subprocess.run(
        [*common, "--now", "2026-09-23T06:10:00Z"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert stale.returncode == 0, stale.stdout + stale.stderr
    assert "EXECUTOR_STUCK" in stale.stdout
    assert "STALE_CLAIM_TAKEOVER_GREEN" in stale.stdout


def test_durable_skill_bridges_reference_executable_stale_takeover_authority():
    root = Path(__file__).resolve().parents[2]
    dispatch = (root / ".agents/skills/engineering/派工/SKILL.md").read_text(encoding="utf-8")
    remote = (root / ".agents/skills/engineering/remote-execution-guard/SKILL.md").read_text(encoding="utf-8")
    continuity = (root / ".agents/skills/engineering/executable-continuity-controller/SKILL.md").read_text(encoding="utf-8")
    pitfalls = (root / "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md").read_text(encoding="utf-8")

    assert "STALE_CLAIM_EXECUTABLE_TAKEOVER_V1" in dispatch
    assert "tools/stale_claim_takeover.py" in dispatch
    assert "claim-takeover" in dispatch

    assert "REMOTE_GUARD_CLAIM_TAKEOVER_V1" in remote
    assert "tools/stale_claim_takeover.py --require-actionable" in remote
    assert "action=claim-takeover" in remote

    assert "SCHEDULED_STALE_CLAIM_TAKEOVER_V1" in continuity
    assert "600 秒" in continuity
    assert "tools/stale_claim_takeover.py" in continuity

    assert "ISSUE540_STALE_CLAIM_TAKEOVER_PITFALL" in pitfalls


def test_evaluator_decision_out_is_bound_guard_evidence(tmp_path: Path):
    import subprocess
    import sys

    module_path = Path(__file__).resolve().parents[2] / "tools" / "stale_claim_takeover.py"
    claim_last_update = "2026-09-23T05:00:00.157943Z"
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(
        json.dumps(_claim(last_update=claim_last_update)),
        encoding="utf-8",
    )
    evidence = tmp_path / "decision.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(module_path),
            "--claim", str(claim_path),
            "--live-head-sha", LIVE_HEAD,
            "--live-head-committed-at", "2026-09-23T05:50:00Z",
            "--now", "2026-09-23T06:00:00Z",
            "--require-actionable",
            "--requesting-worker", "scheduler.test",
            "--decision-out", str(evidence),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["schema"] == "WHD_STALE_CLAIM_TAKEOVER_V1"
    assert payload["claim_head_sha"] == CLAIM_HEAD
    assert payload["observed_live_head_sha"] == LIVE_HEAD
    assert payload["stale_after_seconds"] == 600
    assert payload["claim_last_update"] == claim_last_update

    guard = importlib.import_module("tools.execution_claim_guard")
    claim = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker="chatgpt",
        branch=WORK_BRANCH,
        action="claim-takeover",
        expected_base_sha=BASE_SHA,
        expected_head_sha=LIVE_HEAD,
        takeover_evidence=evidence,
    )
    assert claim.head_sha == CLAIM_HEAD


def test_fractional_claim_last_update_mismatch_fails_closed(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(
        json.dumps(_claim(last_update="2026-09-23T05:00:00.157943Z")),
        encoding="utf-8",
    )
    evidence = _write_takeover_evidence(
        tmp_path,
        claim_last_update="2026-09-23T05:00:00.157944Z",
    )

    with pytest.raises(guard.ExecutionClaimError, match="last_update|timestamp|evidence"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker="chatgpt",
            branch=WORK_BRANCH,
            action="claim-takeover",
            expected_base_sha=BASE_SHA,
            expected_head_sha=LIVE_HEAD,
            takeover_evidence=evidence,
        )


def test_remote_run_head_mismatch_fails_closed():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    remote = {
        "found": True,
        "run_id": 12345,
        "head_sha": LIVE_HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-23T05:00:00Z",
    }
    claim = _claim(
        last_update="2026-09-23T05:00:00Z",
        remote_qa={"run_id": 12345, "head_sha": CLAIM_HEAD},
    )
    with pytest.raises(Exception, match="remote run head mismatch"):
        _evaluate(now=now, claim=claim, remote=remote)


DELEGATED_CHILD_ISSUE = 636
DELEGATED_CHILD_BRANCH = "governance/issue636-live-issue631-takeover-proof-20260925"
DELEGATED_CHILD_HEAD = "c" * 40


def _delegated_work(
    *,
    parent_issue=ISSUE,
    child_issue=DELEGATED_CHILD_ISSUE,
    helper_key="interactive-takeover-proof",
    relationship="proof",
    issue_state="open",
    phase="CLAIMED",
    last_update="2026-09-23T06:19:00Z",
):
    child_claim = {
        "issue": child_issue,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{child_issue}",
        "worker": "chatgpt.sol260925.issue636.proof",
        "executor_source": "chatgpt_interactive",
        "work_branch": DELEGATED_CHILD_BRANCH,
        "claimed_at": "2026-09-23T06:00:00Z",
        "base_sha": BASE_SHA,
        "head_sha": DELEGATED_CHILD_HEAD,
        "phase": phase,
        "last_update": last_update,
        "remote_qa": None,
        "next_action": "complete helper proof",
        "blocker": None,
    }
    return {
        "schema": "WHD_DELEGATED_WORK_V1",
        "parent_issue": parent_issue,
        "child_issue": child_issue,
        "relationship": relationship,
        "helper_key": helper_key,
        "issue_state": issue_state,
        "claim_blob_sha": "d" * 40,
        "claim": child_claim,
        "live_head_sha": DELEGATED_CHILD_HEAD,
        "live_head_committed_at": last_update,
    }


def test_active_bound_delegated_proof_blocks_parent_takeover():
    module = _module()
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    parent = _claim(
        last_update="2026-09-23T05:00:00Z",
        evidence={"proof_issue": DELEGATED_CHILD_ISSUE},
    )
    result = module.evaluate_stale_claim_takeover(
        parent,
        now=now,
        live_head_sha=CLAIM_HEAD,
        live_head_committed_at="2026-09-23T05:00:00Z",
        delegated_work=[_delegated_work()],
        stale_after_seconds=600,
    )
    assert result.classification.value == "ACTIVE_DELEGATED_WORK"
    assert result.actionable is False
    assert result.active_delegated_issue == DELEGATED_CHILD_ISSUE
    assert result.active_delegated_helper_key == "interactive-takeover-proof"


def test_parent_with_declared_helper_requires_fresh_delegated_evidence():
    module = _module()
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    parent = _claim(
        last_update="2026-09-23T05:00:00Z",
        evidence={"proof_issue": DELEGATED_CHILD_ISSUE},
    )
    with pytest.raises(module.StaleTakeoverError, match="delegated work evidence.*636"):
        module.evaluate_stale_claim_takeover(
            parent,
            now=now,
            live_head_sha=CLAIM_HEAD,
            live_head_committed_at="2026-09-23T05:00:00Z",
            delegated_work=[],
            stale_after_seconds=600,
        )


def test_terminal_delegated_helper_no_longer_blocks_parent_takeover():
    module = _module()
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    parent = _claim(
        last_update="2026-09-23T05:00:00Z",
        evidence={"proof_issue": DELEGATED_CHILD_ISSUE},
    )
    result = module.evaluate_stale_claim_takeover(
        parent,
        now=now,
        live_head_sha=CLAIM_HEAD,
        live_head_committed_at="2026-09-23T05:00:00Z",
        delegated_work=[
            _delegated_work(issue_state="closed", phase="RELEASED")
        ],
        stale_after_seconds=600,
    )
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True


def test_delegated_work_parent_binding_mismatch_fails_closed():
    module = _module()
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    with pytest.raises(module.StaleTakeoverError, match="parent issue mismatch"):
        module.evaluate_stale_claim_takeover(
            _claim(last_update="2026-09-23T05:00:00Z"),
            now=now,
            live_head_sha=CLAIM_HEAD,
            live_head_committed_at="2026-09-23T05:00:00Z",
            delegated_work=[_delegated_work(parent_issue=999)],
            stale_after_seconds=600,
        )


def test_active_helper_key_is_machine_deduped_before_new_helper_creation():
    module = _module()
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    parent = _claim(
        last_update="2026-09-23T05:00:00Z",
        evidence={"proof_issue": DELEGATED_CHILD_ISSUE},
    )
    with pytest.raises(module.StaleTakeoverError, match="ACTIVE_HELPER_DUPLICATE"):
        module.assert_helper_creation_allowed(
            parent,
            helper_key="interactive-takeover-proof",
            delegated_work=[_delegated_work()],
            now=now,
            stale_after_seconds=600,
        )


def test_canonical_delegated_link_requires_exact_relationship_and_helper_key():
    module = _module()
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    parent = _claim(
        last_update="2026-09-23T05:00:00Z",
        delegated_work=[{
            "child_issue": DELEGATED_CHILD_ISSUE,
            "relationship": "proof",
            "helper_key": "interactive-takeover-proof",
        }],
    )
    with pytest.raises(module.StaleTakeoverError, match="canonical relationship/helper_key mismatch"):
        module.evaluate_stale_claim_takeover(
            parent,
            now=now,
            live_head_sha=CLAIM_HEAD,
            live_head_committed_at="2026-09-23T05:00:00Z",
            delegated_work=[_delegated_work(helper_key="different-helper")],
            stale_after_seconds=600,
        )


def test_closed_delegated_issue_with_active_claim_fails_closed():
    module = _module()
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    parent = _claim(
        last_update="2026-09-23T05:00:00Z",
        evidence={"proof_issue": DELEGATED_CHILD_ISSUE},
    )
    with pytest.raises(module.StaleTakeoverError, match="closed delegated child issue.*active claim"):
        module.evaluate_stale_claim_takeover(
            parent,
            now=now,
            live_head_sha=CLAIM_HEAD,
            live_head_committed_at="2026-09-23T05:00:00Z",
            delegated_work=[_delegated_work(issue_state="closed", phase="IMPLEMENTING")],
            stale_after_seconds=600,
        )
