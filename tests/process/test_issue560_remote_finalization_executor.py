from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "whd-remote-finalization.yml"
CLOSURE_SKILL = ROOT / ".agents" / "skills" / "engineering" / "issue-closure-gate" / "SKILL.md"


def test_marker_only_finalization_is_explicitly_invalid_remote_evidence():
    text = CLOSURE_SKILL.read_text(encoding="utf-8")
    assert "INVALID_FINALIZATION_EVIDENCE" in text
    assert "Issue-comment-only" in text or "comment-only" in text
    assert "trusted finalization executor" in text


def test_trusted_remote_finalization_executor_is_narrow_and_canonical():
    assert WORKFLOW.is_file(), "missing trusted narrow remote finalization executor"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch" in text
    assert "authorize-finalization" in text
    assert "verify-finalization-proof" in text
    assert "continuity_controller" in text
    for forbidden in ("command_payload", "shell_payload", "arbitrary_command", "generic_shell"):
        assert forbidden not in text
