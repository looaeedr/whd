from pathlib import Path

WORKFLOW = Path(".github/workflows/whd-remote-execution-guard.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_claim_takeover_action_is_explicit_and_scheduler_only():
    text = _text()
    assert '"claim-takeover"' in text
    assert 'claim-takeover requires executor_source=scheduler' in text
    assert 'claim-takeover must not carry changed_file' in text


def test_claim_takeover_allows_claim_head_to_differ_from_observed_live_head():
    text = _text()
    assert 'singles["action"] != "claim-takeover"' in text
    assert 'test "$current_branch_sha" = "$RG_TESTED_TARGET_SHA"' in text
    assert '--head-sha "$RG_TESTED_TARGET_SHA"' in text


def test_claim_takeover_runs_executable_stale_evaluator():
    text = _text()
    assert 'tools/stale_claim_takeover.py' in text
    assert '--require-actionable' in text
    assert '--decision-out /tmp/stale-takeover-decision.json' in text
    assert '--takeover-evidence /tmp/stale-takeover-decision.json' in text


def test_claim_takeover_fresh_reads_exact_remote_run_and_binds_head():
    text = _text()
    assert 'actions: read' in text
    assert 'gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}"' in text
    assert '"head_sha": raw["head_sha"]' in text
    assert '"run_id": int(raw["id"])' in text


def test_claim_takeover_receipt_and_artifact_include_machine_evidence():
    text = _text()
    assert '"takeover_evidence": takeover_evidence' in text
    assert 'stale-takeover-decision.json' in text
    assert 'stale-takeover.log' in text
