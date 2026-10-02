import json
from pathlib import Path
import subprocess
import sys

from tools.control_transaction import prepare_transaction
from tools.control_transaction_terminal_executor import canonical_json_digest, execute_terminal_request
from tools.control_transaction_transport import build_transport_request, transport_request_to_payload
from tools.execution_record import execution_record_from_payload, execution_record_to_payload

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "control_transaction_terminal_executor.py"


def _record():
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 3,
        "issue": 844,
        "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "SCHEDULER",
        "owner_id": "scheduler.a",
        "lane_id": "scheduler.a",
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "work/issue-844",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "ACTIVE",
        "semantic_state": "IMPLEMENTING",
        "next_action": {"kind": "APPLY_COMMIT", "args": {"candidate_commit_sha": "d" * 40}, "display": "apply"},
        "lease": {"token": "lease", "invocation_identity": "scheduled:00:a", "expires_at": "2026-09-28T03:00:00Z"},
        "active_run": None,
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": 842, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T02:00:00Z",
    })


def _request(record, candidate):
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-1", invocation_identity="scheduled:00:a")
    return build_transport_request(plan, candidate_effect_digest=canonical_json_digest(candidate))


def _effect():
    return {
        "updated_at": "2026-09-28T02:05:00Z",
        "head_sha": "d" * 40,
        "semantic_state": "IMPLEMENTING",
        "next_action": {"kind": "START_QA", "args": {"workflow": "qa-flow-v2"}, "display": "qa"},
    }


def test_terminal_executor_applies_and_emits_only_terminal_receipt():
    record = _record()
    candidate = {"candidate_commit_sha": "d" * 40}
    request = _request(record, candidate)
    result = execute_terminal_request(
        request_payload=transport_request_to_payload(request),
        record_payload=execution_record_to_payload(record),
        candidate_payload=candidate,
        effect_payload=_effect(),
    )
    assert result["result"] == "APPLIED"
    assert result["receipt"]["result"] == "APPLIED"
    assert result["post_record"]["generation"] == record.generation + 1
    assert result["post_record"]["head_sha"] == "d" * 40
    assert result["post_record"]["transaction"]["status"] == "RECONCILED"
    rendered = json.dumps(result)
    assert "GREEN" not in rendered
    assert "PENDING" not in rendered
    assert "AUTHORIZED" not in rendered


def test_terminal_executor_candidate_digest_mismatch_fails_without_post_record():
    record = _record()
    request = _request(record, {"candidate_commit_sha": "d" * 40})
    result = execute_terminal_request(
        request_payload=transport_request_to_payload(request),
        record_payload=execution_record_to_payload(record),
        candidate_payload={"candidate_commit_sha": "e" * 40},
        effect_payload=_effect(),
    )
    assert result["result"] == "FAILED"
    assert result["post_record"] is None
    assert "digest mismatch" in result["receipt"]["reason"]


def test_terminal_executor_stale_generation_returns_conflict():
    record = _record()
    candidate = {"candidate_commit_sha": "d" * 40}
    request = _request(record, candidate)
    stale = execution_record_to_payload(record)
    stale["generation"] = 4
    result = execute_terminal_request(
        request_payload=transport_request_to_payload(request),
        record_payload=stale,
        candidate_payload=candidate,
        effect_payload=_effect(),
    )
    assert result["result"] == "CONFLICT"
    assert result["post_record"] is None
    assert "generation drift" in result["receipt"]["reason"]


def test_terminal_executor_cli_is_directly_executable(tmp_path):
    record = _record()
    candidate = {"candidate_commit_sha": "d" * 40}
    request = _request(record, candidate)
    files = {
        "request.json": transport_request_to_payload(request),
        "record.json": execution_record_to_payload(record),
        "candidate.json": candidate,
        "effect.json": _effect(),
    }
    for name, payload in files.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run([
        sys.executable, str(CLI),
        "--request", str(tmp_path / "request.json"),
        "--record", str(tmp_path / "record.json"),
        "--candidate", str(tmp_path / "candidate.json"),
        "--effect", str(tmp_path / "effect.json"),
    ], cwd=ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["result"] == "APPLIED"
