import json
import subprocess
import sys
from pathlib import Path

from tools.control_transaction import prepare_transaction
from tools.control_transaction_transport import build_transport_request, transport_request_to_payload
from tools.execution_record import ActionSpec, ExecutionRecord, execution_record_to_payload

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/whd-control-transaction-v2-shadow.yml"
CLI = ROOT / "tools/control_transaction_shadow_executor.py"


def _record():
    return ExecutionRecord(
        issue=844,
        execution_intent="SCHEDULER_LANE",
        owner_kind="SCHEDULER",
        owner_id="scheduler.a",
        lane_id="scheduler.a",
        slot_id=None,
        source_branch="cleanup/2d-3d-sync",
        source_sha="a" * 40,
        work_branch="work/844",
        head_sha="b" * 40,
        target_branch="cleanup/2d-3d-sync",
        target_sha="c" * 40,
        state="ACTIVE",
        semantic_state="IMPLEMENTING",
        next_action=ActionSpec(kind="APPLY_COMMIT", args={}, display="apply"),
        generation=3,
        updated_at="2026-09-28T01:00:00+00:00",
    )


def test_shadow_workflow_is_manual_and_read_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "issues: write" not in text
    assert "contents: write" not in text
    assert "pull-requests: write" not in text
    assert "issue_comment" not in text
    assert "repository_dispatch" not in text
    assert "control_transaction_shadow_executor.py" in text


def test_shadow_workflow_does_not_embed_legacy_pending_authority_protocol():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "WHD_REMOTE_GUARD_REQUEST" not in text
    assert "WHD_REMOTE_GUARD_RESULT" not in text
    assert "UNCONSUMED_GREEN" not in text
    assert "claim-takeover" not in text


def test_shadow_cli_validates_exact_request_and_record(tmp_path):
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-shadow")
    request = build_transport_request(plan, candidate_effect_digest="d" * 64)
    req_path = tmp_path / "request.json"
    rec_path = tmp_path / "record.json"
    out_path = tmp_path / "out.json"
    req_path.write_text(json.dumps(transport_request_to_payload(request)), encoding="utf-8")
    rec_path.write_text(json.dumps(execution_record_to_payload(record)), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(CLI), "--request", str(req_path), "--record", str(rec_path), "--output", str(out_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["result"] == "SHADOW_VALIDATED"
    assert payload["issue"] == 844
    assert payload["transaction_id"] == "tx-shadow"


def test_shadow_cli_fails_closed_on_stale_generation(tmp_path):
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-shadow")
    request = build_transport_request(plan, candidate_effect_digest="d" * 64)
    record_payload = execution_record_to_payload(record)
    record_payload["generation"] = 4
    req_path = tmp_path / "request.json"
    rec_path = tmp_path / "record.json"
    req_path.write_text(json.dumps(transport_request_to_payload(request)), encoding="utf-8")
    rec_path.write_text(json.dumps(record_payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(CLI), "--request", str(req_path), "--record", str(rec_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["result"] == "SHADOW_CONFLICT"
    assert "generation drift" in payload["reason"]
