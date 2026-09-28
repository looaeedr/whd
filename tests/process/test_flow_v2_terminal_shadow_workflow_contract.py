from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "whd-control-transaction-v2-terminal-shadow.yml"


def _text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_terminal_shadow_workflow_is_manual_and_read_only():
    text = _text()
    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "contents: write" not in text
    assert "issues: write" not in text
    assert "pull-requests: write" not in text


def test_terminal_shadow_requires_request_record_candidate_and_fresh_effect():
    text = _text()
    for key in ("request_json:", "execution_record_json:", "candidate_json:", "fresh_effect_json:"):
        assert key in text


def test_terminal_shadow_runs_checked_in_terminal_executor_and_only_emits_artifact():
    text = _text()
    assert "tools/control_transaction_terminal_executor.py" in text
    assert "terminal-result.json" in text
    assert "actions/upload-artifact@v4" in text
    assert "WHD_REMOTE_GUARD" not in text
    assert "claim-takeover" not in text
    assert "GREEN" not in text


def test_github_visible_labels_are_traditional_chinese():
    text = _text()
    assert "WHD｜Flow v2｜終態交易 Shadow" in text
    assert "唯讀產生 terminal receipt 與 reconciled record" in text
    assert "建立終態 Shadow 輸入" in text
    assert "保存 terminal receipt diagnostic" in text
