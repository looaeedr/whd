from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_issue816_bidirectional_governance_mirror_is_retired():
    assert not (ROOT / "docs/governance/governance_mirror_manifest.json").exists()
    assert not (ROOT / "tools/governance_parity_gate.py").exists()
    workflow = (ROOT / ".github/workflows/whd-governance-single-authority-gate.yml").read_text(encoding="utf-8")
    assert "NO_SYNC_COMPATIBILITY_V1" in workflow
    assert "fetch both governance authorities" not in workflow.lower()
    assert "verify-live-parity" not in workflow

