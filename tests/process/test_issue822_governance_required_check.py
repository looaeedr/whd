from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_issue822_legacy_required_check_is_no_sync_compatibility_only():
    legacy = ROOT / ".github/workflows/whd-governance-single-authority-gate.yml"
    active = ROOT / ".github/workflows/whd-localx-governance-tests.yml"
    assert not legacy.exists(), "retired Flow-v2 workflow must not be resurrected"
    workflow = active.read_text(encoding="utf-8")
    assert "name: WHD localX Governance Tests" in workflow
    assert "name: Governance Contract Tests" in workflow
    assert "tests/process/" in workflow
    assert "process-contracts:" in workflow
    assert "xvfb-run -a python -m pytest -q tests/process" in workflow
    assert "python tools/governance_parity_gate.py" not in workflow
    assert "--manifest docs/governance/governance_mirror_manifest.json" not in workflow
    assert "gh workflow run whd-governance-ancestry-reconcile.yml" not in workflow
    assert "verify-live-parity" not in workflow
