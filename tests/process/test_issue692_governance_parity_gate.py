from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_issue692_governance_parity_machine_is_retired():
    assert not (ROOT / "tools/governance_parity_gate.py").exists()
    assert not (ROOT / "docs/governance/governance_mirror_manifest.json").exists()

