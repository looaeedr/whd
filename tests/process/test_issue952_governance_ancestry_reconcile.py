from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_issue952_governance_ancestry_reconciliation_is_retired():
    assert not (ROOT / ".github/workflows/whd-governance-ancestry-reconcile.yml").exists()
    flow = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "GOVERNANCE_SINGLE_AUTHORITY_V1" in flow
    assert "MAIN_NOT_ANCESTOR_OF_CLEANUP" not in flow
    assert "## Governance ancestry reconciliation" not in flow
    assert "whd-governance-ancestry-reconcile.yml" not in flow

