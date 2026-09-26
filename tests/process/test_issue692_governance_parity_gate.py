from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "governance_parity_gate.py"


def _load():
    assert TOOL.is_file(), "RED-STOP-15: executable governance parity owner is missing"
    spec = importlib.util.spec_from_file_location("governance_parity_gate", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_manifest():
    return {
        "schema": "WHD_GOVERNANCE_PARITY_V1",
        "production": {"ref": "cleanup/2d-3d-sync", "head_sha": "a" * 40},
        "trusted": {"ref": "main", "head_sha": "b" * 40},
        "artifacts": [
            {"domain": "continuity", "path": "tools/continuity_controller.py", "production_blob_sha": "1" * 40, "trusted_blob_sha": "1" * 40, "status": "EXACT"},
            {"domain": "turn_exit", "path": ".github/workflows/whd-turn-exit-gate.yml", "production_blob_sha": "2" * 40, "trusted_blob_sha": "2" * 40, "status": "EXACT"},
            {"domain": "scheduler_liveness", "path": "tools/scheduler_runtime_liveness.py", "production_blob_sha": "3" * 40, "trusted_blob_sha": "3" * 40, "status": "EXACT"},
            {"domain": "remote_guard", "path": ".github/workflows/whd-remote-execution-guard.yml", "production_blob_sha": "4" * 40, "trusted_blob_sha": "4" * 40, "status": "EXACT"},
            {"domain": "current_skills", "path": ".agents/skills/engineering/派工/SKILL.md", "production_blob_sha": "5" * 40, "trusted_blob_sha": "5" * 40, "status": "EXACT"},
        ],
        "deployment_readback": {"durable": True, "evidence": ["run:123", "commit:abc"]},
    }


def test_issue692_exact_parity_is_green():
    gate = _load()
    result = gate.evaluate_manifest(_base_manifest())
    assert result["result"] == "GREEN"
    assert result["reason"] == "PARITY_PROVEN"


def test_issue692_unknown_divergence_fails_closed():
    gate = _load()
    payload = _base_manifest()
    payload["artifacts"][0]["status"] = "UNKNOWN_DIVERGENCE"
    payload["artifacts"][0]["trusted_blob_sha"] = "9" * 40
    result = gate.evaluate_manifest(payload)
    assert result["result"] == "FAIL"
    assert result["reason"] == "UNKNOWN_DIVERGENCE"


def test_issue692_compatible_divergence_requires_explicit_reason():
    gate = _load()
    payload = _base_manifest()
    payload["artifacts"][2]["status"] = "COMPATIBLE_EQUIVALENT"
    payload["artifacts"][2]["trusted_blob_sha"] = "8" * 40
    result = gate.evaluate_manifest(payload)
    assert result["result"] == "FAIL"
    assert result["reason"] == "COMPATIBILITY_REASON_REQUIRED"

    payload["artifacts"][2]["compatibility_reason"] = "X preserves scheduler-specific liveness transport while satisfying the trusted contract."
    result = gate.evaluate_manifest(payload)
    assert result["result"] == "GREEN"


def test_issue692_required_domains_are_complete():
    gate = _load()
    payload = _base_manifest()
    payload["artifacts"] = [a for a in payload["artifacts"] if a["domain"] != "remote_guard"]
    result = gate.evaluate_manifest(payload)
    assert result["result"] == "FAIL"
    assert result["reason"] == "REQUIRED_DOMAIN_MISSING"


def test_issue692_requires_machine_readable_identity_and_durable_readback():
    gate = _load()
    payload = _base_manifest()
    payload["production"]["head_sha"] = "not-a-sha"
    result = gate.evaluate_manifest(payload)
    assert result["result"] == "FAIL"
    assert result["reason"] == "INVALID_IDENTITY"

    payload = _base_manifest()
    payload["deployment_readback"]["durable"] = False
    result = gate.evaluate_manifest(payload)
    assert result["result"] == "FAIL"
    assert result["reason"] == "DURABLE_READBACK_REQUIRED"
