"""Issue #1417: GitHub-only transaction-request branches need trusted preflight code."""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/whd-phase6-preflight.yml"


def test_preflight_uses_exact_requested_head_and_trusted_runner():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert '["git", "checkout", "--detach", head]' in content
    assert "requested branch HEAD drift" in content
    assert "name: Checkout trusted production Phase6 runner" in content
    assert "ref: cleanup/2d-3d-sync" in content
    assert "path: trusted-prod" in content
    assert "PYTHONPATH=trusted-prod python -m tools.phase6_remote_preflight" in content


def test_preflight_does_not_run_untrusted_requested_branch_runner():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "\n          python -m tools.phase6_remote_preflight" not in content


def test_optional_invocation_identity_is_forwarded_for_trusted_receipt():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert 'optional_single = {"invocation_identity"}' in content
    assert "key in required_single or key in optional_single" in content
