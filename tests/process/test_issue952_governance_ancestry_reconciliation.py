from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "governance_parity_gate.py"
MANIFEST = ROOT / "docs" / "governance" / "governance_mirror_manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "whd-governance-mirror-gate.yml"
FLOW_SKILL = ROOT / ".agents" / "skills" / "engineering" / "flow-v2-execution" / "SKILL.md"


def _load():
    spec = importlib.util.spec_from_file_location("governance_parity_gate_issue952", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return {
        "schema": "WHD_GOVERNANCE_MIRROR_MANIFEST_V1",
        "branches": ["main", "cleanup/2d-3d-sync"],
        "product_authority": "cleanup/2d-3d-sync",
        "governance_mode": "BIDIRECTIONAL_MIRROR",
        "governance_paths": ["AGENTS.md"],
        "governance_prefixes": [],
        "ancestry_reconciliation": {
            "owner_branch": "cleanup/2d-3d-sync",
            "source_branch": "main",
            "strategy": "HISTORY_ONLY_SECOND_PARENT_MERGE",
            "preserve_tree": "FIRST_PARENT_EXACT",
            "force_push_allowed": False,
        },
    }


def _payload(*, base_contains_source: bool = False) -> dict:
    cleanup_base = "1" * 40
    first_parent = "2" * 40
    main_head = "3" * 40
    tree = "4" * 40
    return {
        "schema": "WHD_GOVERNANCE_ANCESTRY_RECONCILIATION_V1",
        "target_branch": "cleanup/2d-3d-sync",
        "source_branch": "main",
        "cleanup_base_sha": cleanup_base,
        "main_head_sha": main_head,
        "candidate_sha": "5" * 40,
        "candidate_parent_shas": [first_parent, main_head],
        "first_parent_tree_sha": tree,
        "candidate_tree_sha": tree,
        "base_is_ancestor_of_first_parent": True,
        "base_contains_source": base_contains_source,
        "force_push": False,
        "history_rewrite": False,
    }


def test_issue952_history_only_second_parent_merge_is_green() -> None:
    gate = _load()
    result = gate.evaluate_ancestry_reconciliation(_payload(), _manifest())
    assert result["result"] == "GREEN"
    assert result["reason"] == "GOVERNANCE_ANCESTRY_RECONCILIATION_PROVEN"
    assert result["owner_branch"] == "cleanup/2d-3d-sync"
    assert result["source_branch"] == "main"


def test_issue952_tree_change_fails_closed() -> None:
    gate = _load()
    payload = _payload()
    payload["candidate_tree_sha"] = "9" * 40
    result = gate.evaluate_ancestry_reconciliation(payload, _manifest())
    assert result["result"] == "FAIL"
    assert result["reason"] == "CLEANUP_PRODUCT_TREE_CHANGED"


def test_issue952_wrong_main_parent_fails_closed() -> None:
    gate = _load()
    payload = _payload()
    payload["candidate_parent_shas"][1] = "8" * 40
    result = gate.evaluate_ancestry_reconciliation(payload, _manifest())
    assert result["result"] == "FAIL"
    assert result["reason"] == "MAIN_HISTORY_NOT_RECONCILED"


def test_issue952_force_or_rewrite_fails_closed() -> None:
    gate = _load()
    for key in ("force_push", "history_rewrite"):
        payload = _payload()
        payload[key] = True
        result = gate.evaluate_ancestry_reconciliation(payload, _manifest())
        assert result["result"] == "FAIL"
        assert result["reason"] == "HISTORY_REWRITE_FORBIDDEN"


def test_issue952_already_reconciled_base_does_not_require_synthetic_merge() -> None:
    gate = _load()
    payload = _payload(base_contains_source=True)
    payload["candidate_parent_shas"] = ["2" * 40]
    result = gate.evaluate_ancestry_reconciliation(payload, _manifest())
    assert result == {
        "result": "GREEN",
        "reason": "GOVERNANCE_ANCESTRY_ALREADY_RECONCILED",
        "owner_branch": "cleanup/2d-3d-sync",
        "source_branch": "main",
    }


def test_issue952_current_manifest_declares_cleanup_as_final_ancestry_owner() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    policy = manifest["ancestry_reconciliation"]
    assert policy == {
        "owner_branch": "cleanup/2d-3d-sync",
        "source_branch": "main",
        "strategy": "HISTORY_ONLY_SECOND_PARENT_MERGE",
        "preserve_tree": "FIRST_PARENT_EXACT",
        "force_push_allowed": False,
    }
    assert "tests/process/test_issue952_governance_ancestry_reconciliation.py" in manifest[
        "governance_paths"
    ]


def test_issue952_workflow_enforces_pr_and_live_cleanup_ancestry() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "Verify cleanup ancestry reconciliation before merge",
        "--verify-pr-ancestry-reconciliation",
        "PR_HEAD_SHA",
        "PR_BASE_SHA",
        "refs/remotes/origin/main",
        "Verify live main ancestry after cleanup push",
        "--verify-live-ancestry",
        "GOVERNANCE_ANCESTRY_RECONCILIATION_PROVEN",
        "MAIN_HISTORY_NOT_RECONCILED",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: ancestry workflow contract missing tokens: {missing}"


def test_issue952_flow_skill_documents_future_invocation_order() -> None:
    text = FLOW_SKILL.read_text(encoding="utf-8")
    required = (
        "GOVERNANCE_ANCESTRY_RECONCILIATION_V1",
        "cleanup/2d-3d-sync owns the final ancestry reconciliation",
        "merge the paired main governance PR first",
        "history-only second-parent merge",
        "no force-push",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: Flow v2 governance ancestry contract missing tokens: {missing}"
