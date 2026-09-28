from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"Z:\新WHD")
REF = "87eb35b3f5ae5211673c941cb56c4c4343fa5405"


def git_show(path: str) -> str | None:
    p = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{REF}:{path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return p.stdout if p.returncode == 0 else None


def git_grep_fixed(token: str, pathspec: str = "tools") -> str:
    p = subprocess.run(
        ["git", "-C", str(ROOT), "grep", "-n", "-F", token, REF, "--", pathspec],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return p.stdout if p.returncode == 0 else ""


def require_file(path: str, *, requirement: str) -> str:
    text = git_show(path)
    assert text is not None, f"{requirement}: missing production owner {path} at {REF}"
    return text


def _allowed_actions() -> set[str]:
    text = require_file("tools/execution_claim_guard.py", requirement="R2_PLANNED_HANDOFF")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            else:
                names = [node.target.id] if isinstance(node.target, ast.Name) else []
                value = node.value
            if "ALLOWED_ACTIONS" in names:
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "frozenset"
                    and value.args
                ):
                    return set(ast.literal_eval(value.args[0]))
                return set(ast.literal_eval(value))
    raise AssertionError("R2_PLANNED_HANDOFF: ALLOWED_ACTIONS not statically readable")


def _materialize_gate(tmp_path: Path, *, requirement: str) -> Path:
    override = os.environ.get("WHD_POWER_OFF_GATE_OVERRIDE")
    if override:
        p = Path(override)
        assert p.is_file(), f"{requirement}: override gate missing: {p}"
        return p
    text = git_show("tools/workstation_poweroff_gate.py")
    assert text is not None, (
        f"{requirement}: missing production owner tools/workstation_poweroff_gate.py at {REF}"
    )
    p = tmp_path / "workstation_poweroff_gate.py"
    p.write_text(text, encoding="utf-8")
    return p


def _base_slot(slot_id: str = "worker.slot.1") -> dict:
    return {
        "slot_id": slot_id,
        "local_dependent": True,
        "local_machine_state": "LOCAL_CLEAN_SYNCED",
        "local_mutation_in_progress": False,
        "local_worktree_clean": True,
        "local_head_matches_remote": True,
        "unpushed_commits": 0,
        "checkpoint_durable": True,
        "checkpoint_head_matches_remote": True,
        "guard_transaction": "NONE",
        "handoff_verified": True,
        "claim_owner_matches_scheduler": True,
        "scheduler_enablement": "ENABLED",
        "local_runtime_end_durable": True,
        "dependency_error": None,
    }


def _snapshot(*slots: dict, request_id: str = "REQ-1", revision: str = "REV-1") -> dict:
    return {
        "schema": "WHD_POWER_OFF_GATE_SNAPSHOT_V1",
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "slots": list(slots),
    }


def _run_cli(gate: Path, tmp_path: Path, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(gate), *args],
        cwd=str(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    assert p.returncode == 0, (
        f"poweroff evaluator CLI failed rc={p.returncode} stdout={p.stdout!r} stderr={p.stderr!r}"
    )
    try:
        payload = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"poweroff evaluator stdout is not one JSON object: {p.stdout!r}") from exc
    assert isinstance(payload, dict)
    return payload


def _evaluate(gate: Path, tmp_path: Path, snapshot: dict) -> dict:
    inp = tmp_path / "snapshot.json"
    inp.write_text(json.dumps(snapshot), encoding="utf-8")
    return _run_cli(gate, tmp_path, "evaluate", "--snapshot", str(inp))


def _validate_safe(
    gate: Path,
    tmp_path: Path,
    receipt: dict,
    *,
    request_id: str,
    revision: str,
) -> dict:
    inp = tmp_path / "receipt.json"
    inp.write_text(json.dumps(receipt), encoding="utf-8")
    return _run_cli(
        gate,
        tmp_path,
        "validate-safe",
        "--receipt",
        str(inp),
        "--request-id",
        request_id,
        "--evidence-revision",
        revision,
    )


def _assert_decision(out: dict, result: str, reason: str) -> None:
    assert out.get("schema") == "WHD_POWER_OFF_GATE_V1"
    assert out.get("result") == result, f"expected result={result}, got {out}"
    assert out.get("reason") == reason, f"expected reason={reason}, got {out}"


def test_R0_poweroff_gate_production_owner_exists():
    text = require_file("tools/workstation_poweroff_gate.py", requirement="R0_POWER_OFF_GATE_OWNER")
    assert "WHD_POWER_OFF_GATE_V1" in text


def test_R0A_planned_handoff_evaluator_contract_exists():
    matches = git_grep_fixed("WHD_WORK_EXECUTOR_HANDOFF_V1", "tools")
    assert matches, (
        "R0A_PLANNED_HANDOFF_EVALUATOR: WHD_WORK_EXECUTOR_HANDOFF_V1 "
        f"machine contract is absent from tools at {REF}"
    )


def test_R1_local_durability_classifier_maps_machine_unavailable():
    text = require_file("tools/local_durability_gate.py", requirement="R1_LOCAL_DURABILITY")
    assert "LOCAL_MACHINE_UNAVAILABLE" in text
    assert "LOCAL_MACHINE_UNREACHABLE" in text


def test_R2_guard_exposes_distinct_planned_claim_handoff_action():
    actions = _allowed_actions()
    assert "claim-handoff" in actions, (
        "R2_PLANNED_HANDOFF: execution_claim_guard has no distinct claim-handoff action; "
        f"actual actions={sorted(actions)}"
    )


def test_R3_guard_drain_is_behavioral(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R3_GUARD_DRAIN")
    cases = [
        ("PENDING", "NOT_SAFE", "PENDING_GUARD_TRANSACTION"),
        ("MUTATION_DONE_RECONCILE_ONLY", "NOT_SAFE", "GUARD_RECONCILIATION_REQUIRED"),
        ("AMBIGUOUS", "NOT_SAFE", "GUARD_AMBIGUOUS"),
    ]
    for guard_state, result, reason in cases:
        slot = _base_slot()
        slot["guard_transaction"] = guard_state
        out = _evaluate(gate, tmp_path, _snapshot(slot))
        _assert_decision(out, result, reason)


def test_R4_scheduler_readiness_is_behavioral(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R4_SCHEDULER_READINESS")

    slot = _base_slot()
    slot["claim_owner_matches_scheduler"] = False
    _assert_decision(
        _evaluate(gate, tmp_path, _snapshot(slot)),
        "NOT_SAFE",
        "CLAIM_OWNER_NOT_SCHEDULER",
    )

    slot = _base_slot()
    slot["scheduler_enablement"] = "UNVERIFIED"
    _assert_decision(
        _evaluate(gate, tmp_path, _snapshot(slot)),
        "NOT_SAFE",
        "SCHEDULER_ENABLEMENT_UNVERIFIED",
    )

    slot = _base_slot()
    slot["checkpoint_head_matches_remote"] = False
    _assert_decision(
        _evaluate(gate, tmp_path, _snapshot(slot)),
        "NOT_SAFE",
        "CHECKPOINT_HEAD_MISMATCH",
    )


def test_R5_poweroff_truth_table_is_behavioral(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R5_POWER_OFF_TRISTATE")

    out = _evaluate(gate, tmp_path, _snapshot(_base_slot()))
    assert out.get("result") == "SAFE", f"all-safe snapshot must be SAFE, got {out}"

    slot = _base_slot()
    slot["local_mutation_in_progress"] = True
    _assert_decision(
        _evaluate(gate, tmp_path, _snapshot(slot)),
        "NOT_SAFE",
        "LOCAL_MUTATION_IN_PROGRESS",
    )

    slot = _base_slot()
    slot["dependency_error"] = "LOCAL_MACHINE_UNREACHABLE"
    _assert_decision(
        _evaluate(gate, tmp_path, _snapshot(slot)),
        "ERROR",
        "LOCAL_MACHINE_UNREACHABLE",
    )


def test_R6_safe_receipt_invalidation_is_behavioral(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_SAFE_INVALIDATION")
    receipt = _evaluate(gate, tmp_path, _snapshot(_base_slot(), request_id="REQ-1", revision="REV-1"))
    assert receipt.get("result") == "SAFE", f"precondition requires SAFE receipt, got {receipt}"

    out = _validate_safe(gate, tmp_path, receipt, request_id="REQ-2", revision="REV-1")
    assert out.get("valid") is False
    assert out.get("reason") == "REQUEST_ID_MISMATCH"

    out = _validate_safe(gate, tmp_path, receipt, request_id="REQ-1", revision="REV-2")
    assert out.get("valid") is False
    assert out.get("reason") == "EVIDENCE_REVISION_MISMATCH"


def test_R7_ha_projection_requires_current_request_bound_safe():
    bridge = git_show("tools/whd_poweroff_ha_bridge.py")
    gate = git_show("tools/workstation_poweroff_gate.py")
    text = "\n".join(x for x in (bridge, gate) if x)
    assert text, "R7_HA_CURRENT_REQUEST_SAFE: no HA-facing bridge or poweroff-gate owner exists"
    assert "poweroff_request_id" in text and "SAFE" in text


def test_R8_timeout_is_fail_closed_not_shutdown_fallback():
    bridge = git_show("tools/whd_poweroff_ha_bridge.py")
    gate = git_show("tools/workstation_poweroff_gate.py")
    text = "\n".join(x for x in (bridge, gate) if x)
    assert text, "R8_TIMEOUT_FAIL_CLOSED: no HA/poweroff machine owner exists to enforce timeout behavior"
    assert "TIMEOUT" in text.upper()
    assert ("NOT_SAFE" in text) or ("ERROR" in text)


def test_R9_outage_recovery_distinguishes_unknown_local_state_and_mutation():
    text = "\n".join(
        x for x in (
            git_show("tools/workstation_poweroff_gate.py"),
            git_show("tools/stale_claim_takeover.py"),
            git_show("tools/continuity_controller.py"),
        )
        if x
    )
    missing = [
        token for token in ("LOCAL_UNPERSISTED_STATE_UNKNOWN", "UNKNOWN_MUTATION_OUTCOME")
        if token not in text
    ]
    assert not missing, (
        "R9_OUTAGE_UNKNOWN_STATE: outage recovery cannot explicitly classify "
        f"unknown local state/mutation; missing={missing}"
    )


def test_R10_multi_slot_aggregation_is_behavioral(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R10_MULTI_SLOT_AGGREGATION")

    s1 = _base_slot("worker.slot.1")
    s2 = _base_slot("worker.slot.2")
    out = _evaluate(gate, tmp_path, _snapshot(s1, s2))
    assert out.get("result") == "SAFE", f"two safe local slots must aggregate SAFE, got {out}"

    s2 = _base_slot("worker.slot.2")
    s2["guard_transaction"] = "PENDING"
    out = _evaluate(gate, tmp_path, _snapshot(s1, s2))
    assert out.get("result") != "SAFE", f"one NOT_SAFE slot must prevent aggregate SAFE, got {out}"
    assert "worker.slot.2" in out.get("active_slots", []), f"blocking slot evidence missing: {out}"

    s2 = _base_slot("worker.slot.2")
    s2["dependency_error"] = "LOCAL_MACHINE_UNREACHABLE"
    out = _evaluate(gate, tmp_path, _snapshot(s1, s2))
    assert out.get("result") == "ERROR", f"one ERROR slot must make aggregate ERROR, got {out}"


def test_R11_real_shutdown_integration_requires_end_to_end_acceptance_gate():
    bridge = git_show("tools/whd_poweroff_ha_bridge.py")
    gate = git_show("tools/workstation_poweroff_gate.py")
    text = "\n".join(x for x in (bridge, gate) if x)
    assert text, (
        "R11_REAL_SHUTDOWN_ACCEPTANCE: no HA/poweroff owner exists to gate real shutdown integration"
    )
    assert (
        "END_TO_END_ACCEPTANCE" in text
        or "T11" in text
        or "REAL_SHUTDOWN_ACCEPTANCE" in text
    )
