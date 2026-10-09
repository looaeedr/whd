"""Issue #1441: required PR workflows must have real exact-head successful jobs."""
from pathlib import Path

import pytest

from tools.flow_v2_merge_precheck import (
    REQUIRED_PR_WORKFLOW_PATHS,
    assert_required_pr_ci_evidence,
)

HEAD = "a" * 40
BRANCH = "work/issue-1441-flowv2-ci-e2e"


def sample():
    runs = []
    jobs = {}
    for i, path in enumerate(REQUIRED_PR_WORKFLOW_PATHS, start=101):
        runs.append({
            "id": i, "path": path, "event": "pull_request",
            "head_sha": HEAD, "head_branch": BRANCH,
            "status": "completed", "conclusion": "success",
            "actor": {"login": "looaeedr", "type": "User"},
            "run_attempt": 1,
        })
        jobs[i] = {"total_count": 1, "jobs": [
            {"run_id": i, "status": "completed", "conclusion": "success"}
        ]}
    return runs, jobs


def validate(runs, jobs):
    return assert_required_pr_ci_evidence(
        pr_head_sha=HEAD, pr_head_branch=BRANCH,
        required_workflows=REQUIRED_PR_WORKFLOW_PATHS,
        workflow_runs=runs, jobs_by_run=jobs, repo_owner="looaeedr",
    )


def test_three_real_required_pr_runs_with_real_jobs_green():
    runs, jobs = sample()
    assert set(validate(runs, jobs)) == set(REQUIRED_PR_WORKFLOW_PATHS)


@pytest.mark.parametrize("mutation", [
    "missing", "action_required", "queued", "failed", "skipped",
    "stale_head", "different_branch", "wrong_event", "bot_actor",
    "wrong_user", "no_jobs", "failed_job", "skipped_job",
    "pending_job", "job_run_drift", "incomplete_jobs", "missing_jobs",
])
def test_fail_closed_if_any_required_workflow_lacks_real_exact_jobs(mutation):
    runs, jobs = sample()
    run = runs[0]
    if mutation == "missing":
        runs.pop(0)
    elif mutation == "action_required":
        run["conclusion"] = "action_required"
    elif mutation == "queued":
        run["status"] = "queued"
    elif mutation == "failed":
        run["conclusion"] = "failure"
    elif mutation == "skipped":
        run["conclusion"] = "skipped"
    elif mutation == "stale_head":
        run["head_sha"] = "b" * 40
    elif mutation == "different_branch":
        run["head_branch"] = "work/other-issue"
    elif mutation == "wrong_event":
        run["event"] = "push"
    elif mutation == "bot_actor":
        run["actor"] = {"login": "github-actions[bot]", "type": "Bot"}
    elif mutation == "wrong_user":
        run["actor"] = {"login": "unauthorized", "type": "User"}
    elif mutation == "no_jobs":
        jobs[101] = {"total_count": 0, "jobs": []}
    elif mutation == "failed_job":
        jobs[101]["jobs"][0]["conclusion"] = "failure"
    elif mutation == "skipped_job":
        jobs[101]["jobs"][0]["conclusion"] = "skipped"
    elif mutation == "pending_job":
        jobs[101]["jobs"][0]["status"] = "in_progress"
    elif mutation == "job_run_drift":
        jobs[101]["jobs"][0]["run_id"] = 999
    elif mutation == "incomplete_jobs":
        jobs[101]["total_count"] = 2
    elif mutation == "missing_jobs":
        jobs.pop(101)
    with pytest.raises(ValueError, match="PR_CI_"):
        validate(runs, jobs)


def test_latest_attempt_must_be_green_not_historical_success():
    runs, jobs = sample()
    old = dict(runs[0], id=100, conclusion="success")
    runs[0]["conclusion"] = "action_required"
    runs.append(old)
    jobs[100] = {"total_count": 1, "jobs": [
        {"run_id": 100, "status": "completed", "conclusion": "success"}
    ]}
    with pytest.raises(ValueError, match="PR_CI_"):
        validate(runs, jobs)


def test_no_required_workflows_is_not_success():
    runs, jobs = sample()
    with pytest.raises(ValueError, match="PR_CI_"):
        assert_required_pr_ci_evidence(
            pr_head_sha=HEAD, pr_head_branch=BRANCH, required_workflows=(),
            workflow_runs=runs, jobs_by_run=jobs, repo_owner="looaeedr",
        )


def test_canonical_regression_runner_discovers_issue1441_tests():
    from tools import control_plane_regression
    assert "tests/process/test_issue1441_real_pr_ci_gate.py" in control_plane_regression.PYTEST_PATHS


def test_existing_tok_guard_is_not_regressed():
    workflow = Path(__file__).resolve().parents[2] / ".github/workflows/whd-control-transaction-v2-request.yml"
    body = workflow.read_text(encoding="utf-8")
    assert "WHD_PR_BRANCH_WRITE_TOKEN: " + chr(36) + "{{ secrets.TOK }}" in body
    assert "GITHUB_TOKEN: " + chr(36) + "{{ steps.app-token.outputs.token }}" in body
    assert "WHD_PR_BRANCH_WRITE_TOKEN: " + chr(36) + "{{ steps.app-token.outputs.token }}" not in body


def test_native_merge_readback_checks_live_pr_runs_and_jobs(monkeypatch):
    """Integration seam: a check-run success cannot skip the real jobs gate."""
    from types import SimpleNamespace
    from tools import control_transaction_production_executor as ex

    runs, jobs = sample()
    record = SimpleNamespace(
        head_sha=HEAD,
        target_branch="cleanup/2d-3d-sync",
        target_sha="b" * 40,
    )
    pr = {
        "state": "open", "merged": False, "mergeable": True,
        "head": {"sha": HEAD, "ref": BRANCH},
        "base": {"sha": "b" * 40, "ref": "cleanup/2d-3d-sync"},
    }
    calls = []
    def fake_api(repo, method, path, token, payload=None):
        calls.append(path)
        if path == "/pulls/1442":
            return pr
        if path.startswith("/actions/runs?event=pull_request&head_sha="):
            return {"total_count": len(runs), "workflow_runs": runs}
        if path.startswith("/actions/runs/") and path.endswith("/jobs?per_page=100"):
            run_id = int(path.split("/")[3])
            return jobs[run_id]
        raise AssertionError(f"unexpected API path: {path}")
    monkeypatch.setattr(ex, "_api", fake_api)
    monkeypatch.setattr(ex, "_read_branch_head", lambda *args: "b" * 40)
    monkeypatch.setattr(ex, "_required_checks_for_target", lambda *args: ["Governance Mirror Hard Gate"])
    monkeypatch.setattr(ex, "_check_conclusions_for_head", lambda *args: {"Governance Mirror Hard Gate": "success"})
    _, outcome = ex._merge_precheck_readback("looaeedr/whd", "read-token", record=record, pr_number=1442)
    assert outcome.classification == "READY_TO_MERGE"
    assert len([p for p in calls if p.endswith("/jobs?per_page=100")]) == len(REQUIRED_PR_WORKFLOW_PATHS)


def test_native_merge_rejects_fake_check_green_if_any_run_has_zero_jobs(monkeypatch):
    from types import SimpleNamespace
    from tools import control_transaction_production_executor as ex

    runs, jobs = sample()
    jobs[101] = {"total_count": 0, "jobs": []}
    record = SimpleNamespace(
        head_sha=HEAD, target_branch="cleanup/2d-3d-sync", target_sha="b" * 40,
    )
    pr = {
        "state": "open", "merged": False, "mergeable": True,
        "head": {"sha": HEAD, "ref": BRANCH},
        "base": {"sha": "b" * 40, "ref": "cleanup/2d-3d-sync"},
    }
    def fake_api(repo, method, path, token, payload=None):
        if path == "/pulls/1442":
            return pr
        if path.startswith("/actions/runs?event=pull_request&head_sha="):
            return {"total_count": len(runs), "workflow_runs": runs}
        if path.startswith("/actions/runs/") and path.endswith("/jobs?per_page=100"):
            return jobs[int(path.split("/")[3])]
        raise AssertionError(f"unexpected API path: {path}")
    monkeypatch.setattr(ex, "_api", fake_api)
    monkeypatch.setattr(ex, "_read_branch_head", lambda *args: "b" * 40)
    monkeypatch.setattr(ex, "_required_checks_for_target", lambda *args: ["Governance Mirror Hard Gate"])
    monkeypatch.setattr(ex, "_check_conclusions_for_head", lambda *args: {"Governance Mirror Hard Gate": "success"})
    with pytest.raises(ex.ControlTransactionConflict, match="PR_CI_JOBS_INCOMPLETE"):
        ex._merge_precheck_readback("looaeedr/whd", "read-token", record=record, pr_number=1442)


def test_runner_observation_only_can_never_mint_interactive_git_unlock():
    from tools.root_local_first_gate import (
        GIT_UNLOCK_RECEIPT_SCHEMA,
        validate_git_unlock_receipt,
    )
    fake = {
        "schema": GIT_UNLOCK_RECEIPT_SCHEMA,
        "execution_mode": "GITHUB_ONLY",
        "source_sha": HEAD,
        "diff_digest": "c" * 64,
        "issue": 1441,
        "generation": 2,
        "target_branch": "cleanup/2d-3d-sync",
        "write_paths": ["tools/flow_v2_merge_precheck.py"],
        "delete_paths": [],
        "record_fingerprint": "d" * 64,
        "git_write_unlocked": True,
        "write_mode": "EXACT_TESTED_DIFF_ONLY",
    }
    with pytest.raises(ValueError, match="INTERACTIVE"):
        validate_git_unlock_receipt(fake)
