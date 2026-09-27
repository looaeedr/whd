from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "tools" / "whd_poweroff_ha_bridge.py"
AUTHORITY_MAP = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "09_WHD_Canonical_Authority_Map.md"


def _request(*, request_id: str = "REQ-CURRENT", revision: str = "REV-1", requested_at: int = 100, timeout: int = 30) -> dict:
    return {
        "schema": "WHD_HANDOFF_REQUEST_V1",
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "requested_at_epoch_seconds": requested_at,
        "timeout_seconds": timeout,
    }


def _receipt(*, result: str = "SAFE", request_id: str = "REQ-CURRENT", revision: str = "REV-1", reason: str = "SAFE_TO_POWER_OFF") -> dict:
    return {
        "schema": "WHD_POWER_OFF_GATE_V1",
        "result": result,
        "reason": reason,
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "active_slots": ["worker.slot.1"],
    }


def _project(tmp_path: Path, request: dict, receipt: dict, *, now: int = 110) -> dict:
    assert BRIDGE.is_file(), (
        "R7_R8_MISSING_HA_BRIDGE: expected canonical transport/projection owner "
        "tools/whd_poweroff_ha_bridge.py"
    )
    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(BRIDGE),
            "project",
            "--request",
            str(request_path),
            "--gate-receipt",
            str(receipt_path),
            "--now-epoch-seconds",
            str(now),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    assert proc.returncode == 0, f"bridge failed rc={proc.returncode}: {proc.stderr}"
    payload = json.loads(proc.stdout)
    assert payload["schema"] == "WHD_HA_POWER_OFF_PROJECTION_V1"
    assert "shutdown_command" not in payload
    assert "actuator" not in payload
    return payload


def test_R7_current_request_bound_safe_projects_safe(tmp_path: Path) -> None:
    out = _project(tmp_path, _request(), _receipt())
    assert out["result"] == "SAFE"
    assert out["poweroff_request_id"] == "REQ-CURRENT"
    assert out["evidence_revision"] == "REV-1"


def test_R7_stale_safe_request_id_cannot_authorize_current_request(tmp_path: Path) -> None:
    out = _project(tmp_path, _request(request_id="REQ-CURRENT"), _receipt(request_id="REQ-OLD"))
    assert out["result"] != "SAFE"
    assert out["reason"] == "REQUEST_ID_MISMATCH"


def test_R7_stale_safe_revision_cannot_authorize_current_request(tmp_path: Path) -> None:
    out = _project(tmp_path, _request(revision="REV-2"), _receipt(revision="REV-1"))
    assert out["result"] != "SAFE"
    assert out["reason"] == "EVIDENCE_REVISION_MISMATCH"


def test_R8_timeout_is_error_not_shutdown_fallback(tmp_path: Path) -> None:
    out = _project(tmp_path, _request(requested_at=100, timeout=30), _receipt(), now=131)
    assert out["result"] == "ERROR"
    assert out["reason"] == "TIMEOUT"


def test_R8_not_safe_gate_result_remains_not_safe(tmp_path: Path) -> None:
    out = _project(
        tmp_path,
        _request(),
        _receipt(result="NOT_SAFE", reason="LOCAL_MUTATION_IN_PROGRESS"),
    )
    assert out["result"] == "NOT_SAFE"
    assert out["reason"] == "LOCAL_MUTATION_IN_PROGRESS"


def test_R8_error_gate_result_remains_error(tmp_path: Path) -> None:
    out = _project(
        tmp_path,
        _request(),
        _receipt(result="ERROR", reason="LOCAL_MACHINE_UNREACHABLE"),
    )
    assert out["result"] == "ERROR"
    assert out["reason"] == "LOCAL_MACHINE_UNREACHABLE"


def test_bridge_is_transport_only_and_has_no_shutdown_actuator() -> None:
    assert BRIDGE.is_file(), "R7_R8_MISSING_HA_BRIDGE"
    source = BRIDGE.read_text(encoding="utf-8")
    assert "workstation_poweroff_gate" in source
    forbidden = ("shutdown /", "shutdown.exe", "Stop-Computer", "os.system(", "subprocess.run(")
    assert all(token not in source for token in forbidden)


def test_ha_projection_authority_writeback_is_current_and_transport_only() -> None:
    text = AUTHORITY_MAP.read_text(encoding="utf-8")
    assert (
        "<!-- WHD_AUTHORITY contract=ha-poweroff-projection role=CURRENT "
        "path=tools/whd_poweroff_ha_bridge.py -->"
    ) in text
    assert "### ha-poweroff-projection" in text
    assert "NODE_RED_EXEC" in text
    assert "WHD_HANDOFF_REQUEST_V1" in text
    assert "WHD_HA_POWER_OFF_PROJECTION_V1" in text
    assert "validate_safe_receipt" in text
    assert "HA / Node-RED 不是 WHD authority" in text
    assert "不連接真正 Windows shutdown actuator" in text