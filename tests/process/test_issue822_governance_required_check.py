from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_issue822_legacy_required_check_is_no_sync_compatibility_only():
    workflow = (ROOT / ".github/workflows/whd-governance-single-authority-gate.yml").read_text(encoding="utf-8")
    assert "name: Governance Mirror Hard Gate" in workflow
    assert "NO_SYNC_COMPATIBILITY_V1" in workflow
    assert "python tools/governance_parity_gate.py" not in workflow
    assert "--manifest docs/governance/governance_mirror_manifest.json" not in workflow
    assert "gh workflow run whd-governance-ancestry-reconcile.yml" not in workflow
    assert "verify-live-parity" not in workflow
    assert "Verify governance mirror machinery stays retired" in workflow

