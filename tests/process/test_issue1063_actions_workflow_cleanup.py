from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED = {
    "drive-source-snapshot-export.yml",
    "knowledge-governance-bootstrap.yml",
    "phase6-bridge-anti-regrowth.yml",
    "receiving-divider-broader-acceptance.yml",
    "receiving-fw-formed-occupation-red.yml",
    "receiving-ui-regression.yml",
    "whd-control-plane-regression.yml",
    "whd-control-transaction-v2-request.yml",
    "whd-control-transaction-v2.yml",
    "whd-governance-single-authority-gate.yml",
    "whd-phase6-preflight.yml",
}


def test_active_workflow_surface_is_exact_and_reusable() -> None:
    assert {p.name for p in WORKFLOWS.glob("*.yml")} == EXPECTED


def test_no_issue_scoped_or_retired_legacy_workflow_regrows() -> None:
    actual = {p.name for p in WORKFLOWS.glob("*.yml")}
    assert not any(name.startswith("qa-issue") or name.startswith("issue") for name in actual)
    forbidden = {
        "whd-control-transaction-v2-shadow.yml",
        "whd-control-transaction-v2-terminal-shadow.yml",
        "whd-remote-claim-activation.yml",
        "whd-remote-execution-guard.yml",
        "whd-remote-finalization.yml",
        "whd-remote-parent-branch-identity-repair.yml",
        "whd-scheduler-host-watchdog.yml",
        "whd-turn-exit-gate.yml",
    }
    assert actual.isdisjoint(forbidden)


def test_required_status_context_and_current_flow_v2_transports_remain() -> None:
    gate = (WORKFLOWS / "whd-governance-single-authority-gate.yml").read_text(encoding="utf-8")
    assert "Governance Mirror Hard Gate" in gate
    request = (WORKFLOWS / "whd-control-transaction-v2-request.yml").read_text(encoding="utf-8")
    assert "WHD｜Flow v2｜Push Transaction Request" in request
    for branch in ("coord/transaction-requests-work0", "coord/transaction-requests-work1", "coord/transaction-requests-work2", "coord/transaction-requests-work3"):
        assert branch in request
    preflight = (WORKFLOWS / "whd-phase6-preflight.yml").read_text(encoding="utf-8")
    assert "WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1" in preflight


def test_remote_guard_registry_route_does_not_restore_deleted_workflow() -> None:
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    route = next(r for r in registry["routes"] if r["id"] == "remote-execution-guard")
    assert ".github/workflows/whd-remote-execution-guard.yml" not in route["file_globs"]
