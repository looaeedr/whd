from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "workstation_poweroff_gate.py"
BRIDGE = ROOT / "tools" / "whd_poweroff_ha_bridge.py"
ACCEPTANCE = ROOT / "tools" / "whd_poweroff_end_to_end_acceptance.py"


def _request(*, request_id: str = "REQ-CURRENT", revision: str = "REV-1") -> dict:
    return {
        "schema": "WHD_HANDOFF_REQUEST_V1",
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "requested_at_epoch_seconds": 100,
        "timeout_seconds": 30,
    }


def _safe_slot() -> dict:
    return {
        "slot_id": "worker.slot.1",
        "local_dependent": True,
        "local_machine_state": "LOCAL_CLEAN_SYNCED",
        "local_mutation_in_progress": False,
        "local_worktree_clean": True,
        "local_head_matches_remote": True,
        "unpushed_commits": 0,
        "checkpoint_durable": True,
        "checkpoint_state": "RUNNING",
        "checkpoint_next_action": "resume exact durable next action",
        "checkpoint_head_matches_remote": True,
        "operation_state": "RECONCILED",
        "guard_transaction": "NONE",
        "handoff_verified": True,
        "claim_owner_matches_scheduler": True,
        "scheduler_enablement": "ENABLED",
        "local_runtime_end_durable": True,
        "dependency_error": None,
    }


def _snapshot(*, request_id: str = "REQ-CURRENT", revision: str = "REV-1", slot: dict | None = None) -> dict:
    return {
        "schema": "WHD_POWER_OFF_GATE_SNAPSHOT_V1",
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "slots": [_safe_slot() if slot is None else slot],
    }


def _run_json(script: Path, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    assert proc.returncode == 0, (
        f"{script.name} failed rc={proc.returncode}: stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    return payload


def _gate(tmp_path: Path, snapshot: dict) -> dict:
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return _run_json(GATE, "evaluate", "--snapshot", str(path))


def _project(tmp_path: Path, request: dict, receipt: dict) -> dict:
    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return _run_json(
        BRIDGE,
        "project",
        "--request",
        str(request_path),
        "--gate-receipt",
        str(receipt_path),
        "--now-epoch-seconds",
        "110",
    )


def _actuator(
    *,
    request_id: str = "REQ-CURRENT",
    revision: str = "REV-1",
    decision: str = "ALLOW",
    invoked: bool = True,
) -> dict:
    return {
        "schema": "WHD_HA_ACTUATOR_DECISION_V1",
        "authority": "HA_NODE_RED",
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "decision": decision,
        "actuator_invoked": invoked,
    }


def _resume(
    *,
    request_id: str = "REQ-CURRENT",
    exact_next_action: str | None = "resume exact durable next action",
) -> dict:
    return {
        "schema": "WHD_SCHEDULER_RESUME_EVIDENCE_V1",
        "poweroff_request_id": request_id,
        "pre_shutdown_local_head": "LOCAL-HEAD-1",
        "remote_head": "REMOTE-HEAD-1",
        "checkpoint": ".dispatch/checkpoints/issue-684.json",
        "claim_owner_pre": "chatgpt.interactive.before",
        "claim_owner_post": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
        "handoff_receipt": {
            "schema": "WHD_WORK_EXECUTOR_HANDOFF_V1",
            "poweroff_request_id": request_id,
            "result": "GREEN",
        },
        "scheduler_invocation_identity": "scheduler.B15.run.example",
        "exact_next_action": exact_next_action,
    }


def _verify(
    tmp_path: Path,
    *,
    request: dict,
    receipt: dict,
    projection: dict,
    actuator: dict,
    resume: dict | None,
) -> dict:
    assert ACCEPTANCE.is_file(), (
        "R11_REAL_SHUTDOWN_ACCEPTANCE: missing canonical owner "
        "tools/whd_poweroff_end_to_end_acceptance.py"
    )
    inputs = {
        "request": request,
        "gate_receipt": receipt,
        "projection": projection,
        "actuator_decision": actuator,
        "scheduler_resume": resume,
    }
    paths = {}
    for name, payload in inputs.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    return _run_json(
        ACCEPTANCE,
        "verify",
        "--request",
        str(paths["request"]),
        "--gate-receipt",
        str(paths["gate_receipt"]),
        "--projection",
        str(paths["projection"]),
        "--actuator-decision",
        str(paths["actuator_decision"]),
        "--scheduler-resume",
        str(paths["scheduler_resume"]),
    )


def test_R11_safe_current_request_accepts_ha_allow_and_scheduler_resume(tmp_path: Path) -> None:
    request = _request()
    receipt = _gate(tmp_path, _snapshot())
    projection = _project(tmp_path, request, receipt)
    out = _verify(
        tmp_path,
        request=request,
        receipt=receipt,
        projection=projection,
        actuator=_actuator(),
        resume=_resume(),
    )
    assert out["schema"] == "WHD_END_TO_END_ACCEPTANCE_V1"
    assert out["result"] == "ACCEPTED"
    assert out["reason"] == "END_TO_END_ACCEPTANCE"
    assert out["actuator_allowed"] is True
    assert out["poweroff_request_id"] == "REQ-CURRENT"
    assert out["scheduler_resume"]["exact_next_action"] == "resume exact durable next action"


def test_R11_not_safe_current_request_requires_ha_block(tmp_path: Path) -> None:
    slot = _safe_slot()
    slot["local_mutation_in_progress"] = True
    request = _request()
    receipt = _gate(tmp_path, _snapshot(slot=slot))
    projection = _project(tmp_path, request, receipt)
    out = _verify(
        tmp_path,
        request=request,
        receipt=receipt,
        projection=projection,
        actuator=_actuator(decision="BLOCK", invoked=False),
        resume=None,
    )
    assert projection["result"] == "NOT_SAFE"
    assert out["result"] == "ACCEPTED"
    assert out["reason"] == "NEGATIVE_PATH_ACCEPTED"
    assert out["actuator_allowed"] is False


def test_R11_error_current_request_requires_ha_block(tmp_path: Path) -> None:
    slot = _safe_slot()
    slot["dependency_error"] = "LOCAL_MACHINE_UNREACHABLE"
    request = _request()
    receipt = _gate(tmp_path, _snapshot(slot=slot))
    projection = _project(tmp_path, request, receipt)
    out = _verify(
        tmp_path,
        request=request,
        receipt=receipt,
        projection=projection,
        actuator=_actuator(decision="BLOCK", invoked=False),
        resume=None,
    )
    assert projection["result"] == "ERROR"
    assert out["result"] == "ACCEPTED"
    assert out["actuator_allowed"] is False


def test_R11_not_safe_cannot_reach_actuator(tmp_path: Path) -> None:
    slot = _safe_slot()
    slot["local_mutation_in_progress"] = True
    request = _request()
    receipt = _gate(tmp_path, _snapshot(slot=slot))
    projection = _project(tmp_path, request, receipt)
    out = _verify(
        tmp_path,
        request=request,
        receipt=receipt,
        projection=projection,
        actuator=_actuator(decision="ALLOW", invoked=True),
        resume=None,
    )
    assert out["result"] == "REJECTED"
    assert out["reason"] == "ACTUATOR_MUST_NOT_RUN"


def test_R11_previous_request_safe_cannot_be_replayed(tmp_path: Path) -> None:
    request = _request(request_id="REQ-CURRENT")
    old_receipt = _gate(tmp_path, _snapshot(request_id="REQ-OLD"))
    projection = _project(tmp_path, request, old_receipt)
    assert projection["result"] == "ERROR"
    assert projection["reason"] == "REQUEST_ID_MISMATCH"
    out = _verify(
        tmp_path,
        request=request,
        receipt=old_receipt,
        projection=projection,
        actuator=_actuator(decision="ALLOW", invoked=True),
        resume=None,
    )
    assert out["result"] == "REJECTED"
    assert out["reason"] in {"ACTUATOR_MUST_NOT_RUN", "GATE_RECEIPT_REQUEST_MISMATCH"}


def test_R11_safe_path_requires_exact_scheduler_resume_next_action(tmp_path: Path) -> None:
    request = _request()
    receipt = _gate(tmp_path, _snapshot())
    projection = _project(tmp_path, request, receipt)
    out = _verify(
        tmp_path,
        request=request,
        receipt=receipt,
        projection=projection,
        actuator=_actuator(),
        resume=_resume(exact_next_action=None),
    )
    assert out["result"] == "REJECTED"
    assert out["reason"] == "SCHEDULER_RESUME_EVIDENCE_INVALID"


def test_R11_safe_path_rejects_scheduler_resume_for_other_request(tmp_path: Path) -> None:
    request = _request()
    receipt = _gate(tmp_path, _snapshot())
    projection = _project(tmp_path, request, receipt)
    out = _verify(
        tmp_path,
        request=request,
        receipt=receipt,
        projection=projection,
        actuator=_actuator(),
        resume=_resume(request_id="REQ-OLD"),
    )
    assert out["result"] == "REJECTED"
    assert out["reason"] == "SCHEDULER_RESUME_REQUEST_MISMATCH"


def test_R11_acceptance_evidence_preserves_required_identity_fields(tmp_path: Path) -> None:
    request = _request()
    receipt = _gate(tmp_path, _snapshot())
    projection = _project(tmp_path, request, receipt)
    out = _verify(
        tmp_path,
        request=request,
        receipt=receipt,
        projection=projection,
        actuator=_actuator(),
        resume=_resume(),
    )
    for key in (
        "gate_receipt",
        "projection",
        "actuator_decision",
        "scheduler_resume",
    ):
        assert key in out["evidence"]
    resume = out["scheduler_resume"]
    for key in (
        "pre_shutdown_local_head",
        "remote_head",
        "checkpoint",
        "claim_owner_pre",
        "claim_owner_post",
        "handoff_receipt",
        "scheduler_invocation_identity",
        "exact_next_action",
    ):
        assert resume.get(key)


def test_R11_whd_acceptance_owner_has_no_windows_shutdown_actuator() -> None:
    assert ACCEPTANCE.is_file(), "R11_REAL_SHUTDOWN_ACCEPTANCE"
    source = ACCEPTANCE.read_text(encoding="utf-8")
    assert "END_TO_END_ACCEPTANCE" in source
    forbidden = (
        "shutdown /",
        "shutdown.exe",
        "Stop-Computer",
        "os.system(",
        "subprocess.run(",
        "powershell.exe",
    )
    assert all(token not in source for token in forbidden)
