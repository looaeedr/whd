from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "whd-remote-finalization.yml"
CLOSURE_SKILL = ROOT / ".agents" / "skills" / "engineering" / "issue-closure-gate" / "SKILL.md"
CONTINUITY_SKILL = ROOT / ".agents" / "skills" / "engineering" / "executable-continuity-controller" / "SKILL.md"
REMOTE_GUARD_SKILL = ROOT / ".agents" / "skills" / "engineering" / "remote-execution-guard" / "SKILL.md"
DISPATCH_SKILL = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"


def test_marker_only_finalization_is_explicitly_invalid_remote_evidence():
    text = CLOSURE_SKILL.read_text(encoding="utf-8")
    assert "INVALID_FINALIZATION_EVIDENCE" in text
    assert "Issue comment" in text
    assert "trusted narrow executor" in text


def test_trusted_remote_finalization_executor_is_narrow_and_canonical():
    assert WORKFLOW.is_file(), "missing trusted narrow remote finalization executor"
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "workflow_dispatch",
        "checkpoint_blob_sha",
        "checkpoint_fingerprint",
        "claim_blob_sha",
        "guard_authority_sha",
        "authorize-finalization",
        "verify-finalization-proof",
        "WHD_REMOTE_FINALIZATION_RECEIPT_V1",
        "actions/upload-artifact@v4",
    ):
        assert required in text
    for forbidden in ("command_payload", "shell_payload", "arbitrary_command", "generic_shell"):
        assert forbidden not in text


def test_scheduler_skills_route_no_shell_closure_to_trusted_executor():
    for path in (DISPATCH_SKILL, REMOTE_GUARD_SKILL, CONTINUITY_SKILL):
        text = path.read_text(encoding="utf-8")
        assert "TRUSTED_REMOTE_FINALIZATION_EXECUTOR_V1" in text
        assert "whd-remote-finalization.yml" in text
