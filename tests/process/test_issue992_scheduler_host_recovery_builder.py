from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.control_transaction_request_builder import (
    INTENT_SCHEMA,
    build_control_transaction_request_from_intent,
)
from tools.control_transaction_request_ingress import _load_request


LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"


def _root_gate() -> dict[str, object]:
    return {
        "schema": "WHD_WORK_ROOT_GATE_EVIDENCE_V1",
        "gate_schema": "WHD_WORK_ROOT_HARD_GATE_V1",
        "gate_status": "CURRENT",
        "read_mode": "GITHUB_MIRROR",
        "execution_mode": "SCHEDULER_LANE",
        "source": ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json",
        "provider": "google_drive",
        "library_path": "/Google Drive/WHD",
        "drive_folder_id": "1z-P-VXPd1xjK-PS3Jj7RreT2BLEmDvf_",
        "current_source_manifest_file_id": "1NnUvzJGz7_SPpHvQ_IJvGR-3QgwbMfGCfgfj1hlpD9U",
    }


def _intent() -> dict[str, object]:
    return {
        "schema": INTENT_SCHEMA,
        "request_id": "issue992-b-acquire",
        "issue": 945,
        "kind": "ACQUIRE",
        "lane_id": LANE_B,
        "invocation_identity": "scheduler-b:b15:issue945:issue992-regression",
        "expected_coord_head": "a" * 40,
        "expected_generation": 6,
        "effect": {},
        "purpose": "Resume Issue #945 through the canonical scheduler lane.",
        "work_root_gate_evidence": _root_gate(),
    }


def test_trusted_builder_materializes_scheduler_intent_without_startup_evidence() -> None:
    intent = _intent()
    assert "startup_evidence" not in intent
    request = build_control_transaction_request_from_intent(intent, repository="looaeedr/whd")
    assert request["schema"] == "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1"
    assert request["startup_evidence"]["execution_mode"] == "SCHEDULER_LANE"
    assert request["startup_evidence"]["work_root_gate"]["read_mode"] == "GITHUB_MIRROR"


def test_intent_schema_forbids_supplied_startup_evidence(tmp_path: Path) -> None:
    intent = _intent()
    intent["startup_evidence"] = {"schema": "supplied"}
    path = tmp_path / "request.json"
    path.write_text(json.dumps(intent), encoding="utf-8")
    with pytest.raises(Exception, match="startup_evidence"):
        _load_request(path)


def test_ingress_accepts_semantic_intent_shape(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    path.write_text(json.dumps(_intent()), encoding="utf-8")
    loaded = _load_request(path)
    assert loaded["schema"] == INTENT_SCHEMA
    assert loaded["purpose"]
