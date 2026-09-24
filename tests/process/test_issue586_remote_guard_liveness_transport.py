from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/whd-remote-execution-guard.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_claim_takeover_fresh_reads_owner_issue_comments_before_evaluator():
    text = _text()
    comments = 'gh api --paginate --slurp "repos/${GITHUB_REPOSITORY}/issues/${RG_ISSUE}/comments?per_page=100"'
    selector = "python tools/scheduler_runtime_liveness.py"
    evaluator = "python tools/stale_claim_takeover.py"
    assert comments in text
    assert selector in text
    assert text.index(comments) < text.index(selector) < text.index(evaluator)


def test_transport_passes_exact_claim_blob_and_selected_runtime_liveness():
    text = _text()
    assert 'liveness_arg=(--claim-blob-sha "$RG_CLAIM_BLOB_SHA")' in text
    assert 'liveness_arg+=(--runtime-liveness-json /tmp/runtime-liveness.json)' in text
    assert '"${liveness_arg[@]}"' in text


def test_missing_heartbeat_is_allowed_but_malformed_heartbeat_fails_closed():
    text = _text()
    assert 'if [ "$liveness_rc" -eq 0 ]; then' in text
    assert 'elif [ "$liveness_rc" -eq 3 ]; then' in text
    assert 'exit "$liveness_rc"' in text


def test_existing_active_run_observation_still_precedes_liveness_selection():
    text = _text()
    run_probe = 'gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}"'
    selector = "python tools/scheduler_runtime_liveness.py"
    assert run_probe in text
    assert text.index(run_probe) < text.index(selector)


def test_user_visible_remote_guard_name_stays_traditional_chinese():
    text = _text()
    assert 'run-name: "WHD｜工單 #' in text
    assert "排程接手" in text
    assert "聊天室接手" in text
