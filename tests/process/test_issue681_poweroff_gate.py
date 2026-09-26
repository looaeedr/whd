import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _materialize_gate(tmp_path: Path, *, requirement: str) -> Path:
    gate = ROOT / "tools" / "workstation_poweroff_gate.py"
    assert gate.is_file(), (
        f"{requirement}: missing production owner tools/workstation_poweroff_gate.py "
        f"at working tree {ROOT}"
    )
    return gate

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
        "checkpoint_state": "RUNNING",
        "checkpoint_next_action": "continue exact durable next action",
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
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", timeout=10,
    )
    assert p.returncode == 0, (
        f"poweroff evaluator CLI failed rc={p.returncode} "
        f"stdout={p.stdout!r} stderr={p.stderr!r}"
    )
    try:
        payload = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"poweroff evaluator stdout is not one JSON object: {p.stdout!r}"
        ) from exc
    assert isinstance(payload, dict)
    return payload


def _evaluate(gate: Path, tmp_path: Path, snapshot: dict) -> dict:
    inp = tmp_path / "snapshot.json"
    inp.write_text(json.dumps(snapshot), encoding="utf-8")
    return _run_cli(gate, tmp_path, "evaluate", "--snapshot", str(inp))


def _validate_safe(
    gate: Path, tmp_path: Path, receipt: dict, *, request_id: str, revision: str
) -> dict:
    inp = tmp_path / "receipt.json"
    inp.write_text(json.dumps(receipt), encoding="utf-8")
    return _run_cli(
        gate, tmp_path,
        "validate-safe",
        "--receipt", str(inp),
        "--request-id", request_id,
        "--evidence-revision", revision,
    )


def _assert_decision(out: dict, result: str, reason: str | None = None) -> None:
    assert out.get("schema") == "WHD_POWER_OFF_GATE_V1"
    assert out.get("result") == result, f"expected result={result}, got {out}"
    if reason is not None:
        assert out.get("reason") == reason, f"expected reason={reason}, got {out}"


def _safe_receipt(gate: Path, tmp_path: Path) -> dict:
    receipt = _evaluate(gate, tmp_path, _snapshot(_base_slot()))
    assert receipt.get("result") == "SAFE", f"precondition requires SAFE receipt, got {receipt}"
    return receipt


# T3 / R3 ??Guard drain, including positive pass-through cases.

def test_R3_pending_guard_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R3_PENDING")
    s = _base_slot(); s["guard_transaction"] = "PENDING"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "PENDING_GUARD_TRANSACTION")


def test_R3_reconcile_guard_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R3_RECONCILE")
    s = _base_slot(); s["guard_transaction"] = "MUTATION_DONE_RECONCILE_ONLY"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "GUARD_RECONCILIATION_REQUIRED")


def test_R3_ambiguous_guard_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R3_AMBIGUOUS")
    s = _base_slot(); s["guard_transaction"] = "AMBIGUOUS"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "GUARD_AMBIGUOUS")


def test_R3_consumed_guard_does_not_block_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R3_CONSUMED")
    s = _base_slot(); s["guard_transaction"] = "CONSUMED"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "SAFE")


def test_R3_none_guard_does_not_block_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R3_NONE")
    s = _base_slot(); s["guard_transaction"] = "NONE"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "SAFE")


# T4 / R4 ??six independent scheduler-readiness cases.

def test_R4_ready_scheduler_allows_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R4_READY")
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(_base_slot())), "SAFE")


def test_R4_owner_mismatch_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R4_OWNER")
    s = _base_slot(); s["claim_owner_matches_scheduler"] = False
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "CLAIM_OWNER_NOT_SCHEDULER")


def test_R4_scheduler_unverified_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R4_UNVERIFIED")
    s = _base_slot(); s["scheduler_enablement"] = "UNVERIFIED"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "SCHEDULER_ENABLEMENT_UNVERIFIED")


def test_R4_scheduler_disabled_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R4_DISABLED")
    s = _base_slot(); s["scheduler_enablement"] = "DISABLED"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "SCHEDULER_DISABLED")


def test_R4_nonterminal_missing_next_action_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R4_NEXT_ACTION")
    s = _base_slot(); s["checkpoint_next_action"] = ""
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "CHECKPOINT_NEXT_ACTION_MISSING")


def test_R4_checkpoint_head_mismatch_blocks_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R4_HEAD")
    s = _base_slot(); s["checkpoint_head_matches_remote"] = False
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "CHECKPOINT_HEAD_MISMATCH")


# T5 / R5 ??core tristate behavior.

def test_R5_all_safe_is_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R5_SAFE")
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(_base_slot())), "SAFE")


def test_R5_local_mutation_is_not_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R5_NOT_SAFE")
    s = _base_slot(); s["local_mutation_in_progress"] = True
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "LOCAL_MUTATION_IN_PROGRESS")


def test_R5_machine_unreachable_is_error(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R5_ERROR")
    s = _base_slot(); s["dependency_error"] = "LOCAL_MACHINE_UNREACHABLE"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "ERROR", "LOCAL_MACHINE_UNREACHABLE")


# T6 / R6 ??three receipt freshness cases + five state mutation cases.

def test_R6_request_id_change_invalidates_safe_receipt(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_REQUEST")
    receipt = _safe_receipt(gate, tmp_path)
    out = _validate_safe(gate, tmp_path, receipt, request_id="REQ-2", revision="REV-1")
    assert out.get("valid") is False
    assert out.get("reason") == "REQUEST_ID_MISMATCH"


def test_R6_evidence_revision_change_invalidates_safe_receipt(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_REVISION")
    receipt = _safe_receipt(gate, tmp_path)
    out = _validate_safe(gate, tmp_path, receipt, request_id="REQ-1", revision="REV-2")
    assert out.get("valid") is False
    assert out.get("reason") == "EVIDENCE_REVISION_MISMATCH"


def test_R6_non_safe_receipt_is_invalid(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_RECEIPT_NOT_SAFE")
    receipt = {
        "schema": "WHD_POWER_OFF_GATE_V1",
        "result": "NOT_SAFE",
        "reason": "LOCAL_MUTATION_IN_PROGRESS",
        "poweroff_request_id": "REQ-1",
        "evidence_revision": "REV-1",
        "active_slots": ["worker.slot.1"],
    }
    out = _validate_safe(gate, tmp_path, receipt, request_id="REQ-1", revision="REV-1")
    assert out.get("valid") is False
    assert out.get("reason") == "RECEIPT_NOT_SAFE"


def test_R6_new_dirty_file_invalidates_safe_state(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_DIRTY")
    s = _base_slot(); s["local_worktree_clean"] = False
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "LOCAL_DIRTY_NOT_DURABLE")


def test_R6_new_pending_guard_invalidates_safe_state(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_GUARD")
    s = _base_slot(); s["guard_transaction"] = "PENDING"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "PENDING_GUARD_TRANSACTION")


def test_R6_claim_owner_change_invalidates_safe_state(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_OWNER")
    s = _base_slot(); s["claim_owner_matches_scheduler"] = False
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "CLAIM_OWNER_NOT_SCHEDULER")


def test_R6_scheduler_disable_invalidates_safe_state(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_SCHEDULER")
    s = _base_slot(); s["scheduler_enablement"] = "DISABLED"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "SCHEDULER_DISABLED")


def test_R6_remote_head_advance_invalidates_safe_state(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R6_HEAD")
    s = _base_slot(); s["checkpoint_head_matches_remote"] = False
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s)), "NOT_SAFE", "CHECKPOINT_HEAD_MISMATCH")


# T10 / R10 ??all six aggregation/exclusion cases.

def test_R10_zero_slots_is_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R10_ZERO")
    _assert_decision(_evaluate(gate, tmp_path, _snapshot()), "SAFE")


def test_R10_one_local_safe_slot_is_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R10_ONE")
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(_base_slot())), "SAFE")


def test_R10_two_local_safe_slots_are_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R10_TWO")
    _assert_decision(
        _evaluate(gate, tmp_path, _snapshot(_base_slot("worker.slot.1"), _base_slot("worker.slot.2"))),
        "SAFE",
    )


def test_R10_one_not_safe_slot_blocks_aggregate_safe(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R10_NOT_SAFE")
    s1 = _base_slot("worker.slot.1")
    s2 = _base_slot("worker.slot.2"); s2["guard_transaction"] = "PENDING"
    out = _evaluate(gate, tmp_path, _snapshot(s1, s2))
    assert out.get("result") != "SAFE", f"one NOT_SAFE slot must prevent aggregate SAFE, got {out}"
    assert "worker.slot.2" in out.get("active_slots", []), f"blocking slot evidence missing: {out}"


def test_R10_one_error_slot_makes_aggregate_error(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R10_ERROR")
    s1 = _base_slot("worker.slot.1")
    s2 = _base_slot("worker.slot.2"); s2["dependency_error"] = "LOCAL_MACHINE_UNREACHABLE"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(s1, s2)), "ERROR", "LOCAL_MACHINE_UNREACHABLE")


def test_R10_non_local_dependent_slot_does_not_block_shutdown(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="R10_NON_LOCAL")
    local = _base_slot("worker.slot.1")
    remote = _base_slot("worker.slot.2")
    remote["local_dependent"] = False
    remote["local_worktree_clean"] = False
    remote["local_mutation_in_progress"] = True
    remote["guard_transaction"] = "PENDING"
    remote["claim_owner_matches_scheduler"] = False
    remote["scheduler_enablement"] = "DISABLED"
    remote["dependency_error"] = "LOCAL_MACHINE_UNREACHABLE"
    _assert_decision(_evaluate(gate, tmp_path, _snapshot(local, remote)), "SAFE")



def test_issue681_same_snapshot_is_deterministic(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="ISSUE681_DETERMINISTIC")
    snapshot = _snapshot(_base_slot())
    first = _evaluate(gate, tmp_path, snapshot)
    second = _evaluate(gate, tmp_path, snapshot)
    assert first == second


def test_issue681_malformed_snapshot_fails_closed(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="ISSUE681_MALFORMED")
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    out = _run_cli(gate, tmp_path, "evaluate", "--snapshot", str(malformed))
    _assert_decision(out, "ERROR", "SNAPSHOT_INVALID")


def test_issue681_unknown_guard_state_fails_closed(tmp_path):
    gate = _materialize_gate(tmp_path, requirement="ISSUE681_UNKNOWN_GUARD")
    s = _base_slot()
    s["guard_transaction"] = "SOMETHING_NEW"
    _assert_decision(
        _evaluate(gate, tmp_path, _snapshot(s)),
        "ERROR",
        "GUARD_TRANSACTION_UNKNOWN",
    )


def test_issue681_evaluator_has_no_mutation_capable_imports():
    import ast

    gate = ROOT / "tools" / "workstation_poweroff_gate.py"
    tree = ast.parse(gate.read_text(encoding="utf-8"))
    forbidden_roots = {
        "ctypes",
        "http",
        "os",
        "requests",
        "shutil",
        "socket",
        "subprocess",
        "urllib",
        "winreg",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not (imported & forbidden_roots), (
        f"side-effect-free evaluator imports mutation-capable modules: "
        f"{sorted(imported & forbidden_roots)}"
    )
