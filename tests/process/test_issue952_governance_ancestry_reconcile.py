from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "governance_parity_gate.py"
MANIFEST = ROOT / "docs" / "governance" / "governance_mirror_manifest.json"
MIRROR_WORKFLOW = ROOT / ".github" / "workflows" / "whd-governance-mirror-gate.yml"
RECONCILE_WORKFLOW = ROOT / ".github" / "workflows" / "whd-governance-ancestry-reconcile.yml"
FLOW_SKILL = ROOT / ".agents" / "skills" / "engineering" / "flow-v2-execution" / "SKILL.md"
CONTROL_PLANE = ROOT / ".github" / "workflows" / "whd-control-plane-regression.yml"


def _load_gate():
    spec = importlib.util.spec_from_file_location("governance_parity_gate", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_issue952_manifest_declares_cleanup_owned_non_force_reconciliation():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = payload["ancestry_reconciliation"]
    assert contract == {
        "owner_branch": "cleanup/2d-3d-sync",
        "source_branch": "main",
        "strategy": "TWO_PARENT_OURS_MERGE_PRESERVE_CLEANUP_TREE",
        "force_push_allowed": False,
        "workflow": ".github/workflows/whd-governance-ancestry-reconcile.yml",
    }
    assert ".github/workflows/whd-governance-ancestry-reconcile.yml" in payload["governance_paths"]
    assert "tests/process/test_issue952_governance_ancestry_reconcile.py" in payload["governance_paths"]


def test_issue952_gate_fails_closed_until_main_is_ancestor_of_cleanup():
    gate = _load_gate()
    result = gate.evaluate_ancestry_reconciliation_state(
        main_sha="a" * 40,
        cleanup_sha="b" * 40,
        governance_parity_result={"result": "GREEN"},
        main_is_ancestor=False,
    )
    assert result["result"] == "FAIL"
    assert result["reason"] == "MAIN_NOT_ANCESTOR_OF_CLEANUP"

    green = gate.evaluate_ancestry_reconciliation_state(
        main_sha="a" * 40,
        cleanup_sha="b" * 40,
        governance_parity_result={"result": "GREEN"},
        main_is_ancestor=True,
    )
    assert green["result"] == "GREEN"
    assert green["reason"] == "MAIN_ANCESTRY_RECONCILED"


def test_issue952_gate_requires_governance_parity_before_ancestry():
    gate = _load_gate()
    result = gate.evaluate_ancestry_reconciliation_state(
        main_sha="a" * 40,
        cleanup_sha="b" * 40,
        governance_parity_result={"result": "FAIL", "reason": "UNKNOWN_DIVERGENCE"},
        main_is_ancestor=False,
    )
    assert result["result"] == "FAIL"
    assert result["reason"] == "GOVERNANCE_PARITY_REQUIRED_BEFORE_ANCESTRY_RECONCILE"


def test_issue952_live_mirror_push_gate_requires_ancestry_acceptance():
    text = MIRROR_WORKFLOW.read_text(encoding="utf-8")
    assert "--verify-live-ancestry" in text
    assert "refs/remotes/origin/main" in text
    assert "refs/remotes/origin/cleanup/2d-3d-sync" in text


def test_issue952_reconcile_workflow_preserves_cleanup_tree_and_never_force_pushes():
    assert RECONCILE_WORKFLOW.is_file(), "RED: ancestry reconciliation workflow is missing"
    text = RECONCILE_WORKFLOW.read_text(encoding="utf-8")
    required = (
        "expected_main_sha",
        "expected_cleanup_sha",
        "git merge --no-ff -s ours",
        "CLEANUP_TREE",
        "CANDIDATE_TREE",
        "PARENTS",
        "git push origin HEAD:refs/heads/cleanup/2d-3d-sync",
        "WHD_GOVERNANCE_ANCESTRY_RECONCILIATION_RESULT_V1",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"ancestry workflow missing safety tokens: {missing}"
    assert "--force" not in text


def test_issue952_flow_v2_requires_reconciliation_before_governance_finalize():
    text = FLOW_SKILL.read_text(encoding="utf-8")
    required = (
        "GOVERNANCE_ANCESTRY_RECONCILIATION_V1",
        "cleanup/2d-3d-sync",
        "WHD_GOVERNANCE_ANCESTRY_RECONCILIATION_RESULT_V1",
        "FINALIZE",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"Flow v2 missing governance ancestry contract: {missing}"


def test_issue952_control_plane_regression_executes_focused_ancestry_tests():
    text = CONTROL_PLANE.read_text(encoding="utf-8")
    assert "tools/governance_parity_gate.py" in text
    assert "tests/process/test_issue952_governance_ancestry_reconcile.py" in text
