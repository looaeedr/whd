from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_WORKFLOW = ROOT / ".github/workflows/whd-governance-single-authority-gate.yml"


def test_issue816_bidirectional_governance_mirror_is_retired():
    # The October 9 Flow-v2 retirement deleted the whole compatibility
    # workflow. Restoring that workflow is not a valid test repair.
    assert not (ROOT / "docs/governance/governance_mirror_manifest.json").exists()
    assert not (ROOT / "tools/governance_parity_gate.py").exists()
    assert not LEGACY_WORKFLOW.exists()
    workflows = tuple((ROOT / ".github/workflows").glob("*.yml"))
    assert workflows, "active governance workflows must remain"
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        assert "verify-live-parity" not in text
        assert "fetch both governance authorities" not in text.lower()
