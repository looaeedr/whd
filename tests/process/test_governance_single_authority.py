import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cleanup_is_single_governance_authority():
    agents = _text("AGENTS.md")
    flow = _text(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    assert "governance authority 固定為 `cleanup/2d-3d-sync`" in agents
    assert "GOVERNANCE_SINGLE_AUTHORITY_V1" in flow
    assert "唯一 production authority 固定為 `cleanup/2d-3d-sync`" in flow


def test_mirror_and_ancestry_owners_are_absent():
    for path in (
        "docs/governance/governance_mirror_manifest.json",
        "tools/governance_parity_gate.py",
        ".github/workflows/whd-governance-mirror-gate.yml",
        ".github/workflows/whd-governance-ancestry-reconcile.yml",
    ):
        assert not (ROOT / path).exists(), path


def test_governance_profile_uses_authority_consistency_not_mirror():
    contract = json.loads(_text(".agents/contracts/WHD_CHANGE_TEST_PROFILE_V1.json"))
    stages = contract["primary_change_types"]["GOVERNANCE"]
    assert stages == ["CONTRACT", "CONTROL_PLANE_REGRESSION", "AUTHORITY_CONSISTENCY"]


def test_legacy_required_check_transport_has_no_sync_behavior():
    workflow = _text(".github/workflows/whd-governance-single-authority-gate.yml")
    assert "NO_SYNC_COMPATIBILITY_V1" in workflow
    assert "name: Governance Mirror Hard Gate" in workflow  # legacy job context only
    for token in (
        "verify-live-parity",
        "WHD-Governance-Mirror-Pair",
        "ANCESTRY_CANDIDATE",
        "git fetch origin main",
        "git push origin main",
    ):
        assert token not in workflow
