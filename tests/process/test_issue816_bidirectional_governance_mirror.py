from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "governance_parity_gate.py"
MANIFEST = ROOT / "docs" / "governance" / "governance_mirror_manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "whd-governance-mirror-gate.yml"


def _load():
    spec = importlib.util.spec_from_file_location("governance_parity_gate", TOOL)
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
        "governance_paths": [
            "AGENTS.md",
            "tools/governance_parity_gate.py",
            ".github/workflows/whd-governance-mirror-gate.yml",
        ],
    }


def _payload(source_ref: str, target_ref: str, changed_paths: list[str]) -> dict:
    return {
        "schema": "WHD_GOVERNANCE_MIRROR_V1",
        "source_ref": source_ref,
        "target_ref": target_ref,
        "changed_paths": changed_paths,
        "artifacts": [
            {
                "path": path,
                "source_blob_sha": "1" * 40,
                "target_blob_sha": "1" * 40,
                "status": "EXACT",
            }
            for path in changed_paths
        ],
        "deployment_readback": {
            "durable": True,
            "evidence": ["issue:#816", "paired-pr-readback"],
        },
    }


def test_issue816_governance_mirror_is_bidirectional() -> None:
    gate = _load()
    manifest = _manifest()
    governed = ["tools/governance_parity_gate.py"]
    for source, target in (
        ("main", "cleanup/2d-3d-sync"),
        ("cleanup/2d-3d-sync", "main"),
    ):
        result = gate.evaluate_mirror_transaction(
            _payload(source, target, governed),
            manifest,
        )
        assert result == {
            "result": "GREEN",
            "reason": "GOVERNANCE_MIRROR_PARITY_PROVEN",
            "source_ref": source,
            "target_ref": target,
            "artifact_count": 1,
        }


def test_issue816_product_path_to_main_fails_closed() -> None:
    gate = _load()
    payload = _payload(
        "cleanup/2d-3d-sync",
        "main",
        ["ae_engine/manufacturing_api.py"],
    )
    result = gate.evaluate_mirror_transaction(payload, _manifest())
    assert result["result"] == "FAIL"
    assert result["reason"] == "NON_GOVERNANCE_PATH_TO_MAIN"
    assert result["path"] == "ae_engine/manufacturing_api.py"


def test_issue816_unknown_governance_divergence_fails_closed() -> None:
    gate = _load()
    payload = _payload(
        "main",
        "cleanup/2d-3d-sync",
        ["tools/governance_parity_gate.py"],
    )
    payload["artifacts"][0]["status"] = "UNKNOWN_DIVERGENCE"
    payload["artifacts"][0]["target_blob_sha"] = "2" * 40
    result = gate.evaluate_mirror_transaction(payload, _manifest())
    assert result["result"] == "FAIL"
    assert result["reason"] == "UNKNOWN_DIVERGENCE"


def test_issue816_compatible_equivalent_needs_reason() -> None:
    gate = _load()
    payload = _payload(
        "cleanup/2d-3d-sync",
        "main",
        ["tools/governance_parity_gate.py"],
    )
    payload["artifacts"][0]["status"] = "COMPATIBLE_EQUIVALENT"
    payload["artifacts"][0]["target_blob_sha"] = "2" * 40
    result = gate.evaluate_mirror_transaction(payload, _manifest())
    assert result["reason"] == "COMPATIBILITY_REASON_REQUIRED"

    payload["artifacts"][0]["compatibility_reason"] = (
        "branch-specific transport differs while the governance contract is identical"
    )
    assert gate.evaluate_mirror_transaction(payload, _manifest())["result"] == "GREEN"


def test_issue816_manifest_locks_product_authority_to_cleanup() -> None:
    assert MANIFEST.is_file(), "RED: governance mirror manifest is missing"
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema"] == "WHD_GOVERNANCE_MIRROR_MANIFEST_V1"
    assert set(payload["branches"]) == {"main", "cleanup/2d-3d-sync"}
    assert payload["product_authority"] == "cleanup/2d-3d-sync"
    assert payload["governance_mode"] == "BIDIRECTIONAL_MIRROR"
    assert "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md" in payload["governance_paths"]


def test_issue816_workflow_is_always_on_for_both_governance_branches() -> None:
    assert WORKFLOW.is_file(), "RED: always-on governance mirror workflow is missing"
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "Governance Mirror Hard Gate",
        "main",
        "cleanup/2d-3d-sync",
        "pull_request:",
        "push:",
        "tools/governance_parity_gate.py",
        "governance_mirror_manifest.json",
        "NON_GOVERNANCE_PATH_TO_MAIN",
        "core.quotePath=false",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: governance mirror workflow missing contract tokens: {missing}"
