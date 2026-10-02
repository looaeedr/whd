from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools.control_transaction import ControlTransactionConflict, execute_transaction, prepare_transaction
from tools.control_transaction_request_builder import build_control_transaction_request
from tools.execution_record import execution_record_from_payload

ROOT = Path(__file__).resolve().parents[2]
INV = "interactive:work1:issue1025:test"
LANE = "chatgpt.flowv2.work1"
HEAD = "a" * 40
TARGET = "b" * 40


def _root_gate():
    return {
        "schema": "WHD_WORK_ROOT_GATE_EVIDENCE_V1",
        "gate_schema": "WHD_WORK_ROOT_HARD_GATE_V1",
        "gate_status": "CURRENT",
        "read_mode": "GOOGLE_DRIVE_CANONICAL",
        "execution_mode": "INTERACTIVE",
        "source": "/Google Drive/WHD/WHD_WORK_ROOT_HARD_GATE_V1.json",
        "provider": "google_drive",
        "library_path": "/Google Drive/WHD",
        "drive_folder_id": "1z-P-VXPd1xjK-PS3Jj7RreT2BLEmDvf_",
        "current_source_manifest_file_id": "manifest",
    }


def _payload(**overrides):
    payload = {
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 7,
        "issue": 1025,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": LANE,
        "lane_id": LANE,
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": TARGET,
        "work_branch": "governance/issue1025-flow-v2-roundtrip-reduction",
        "head_sha": HEAD,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": TARGET,
        "state": "ACTIVE",
        "semantic_state": "ROOT_TESTED_DIFF_APPLIED",
        "next_action": {
            "kind": "START_QA",
            "args": {"workflow": ".github/workflows/whd-control-plane-regression.yml"},
            "display": "verify exact head",
        },
        "lease": {
            "token": "lease-1025",
            "invocation_identity": INV,
            "expires_at": "2099-09-29T15:00:00Z",
        },
        "active_run": None,
        "transaction": None,
        "mutation_scope": {
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": TARGET,
            "write_paths": ["tools/control_transaction.py"],
            "delete_paths": [],
            "reservation_state": "ACTIVE",
        },
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-29T14:45:00Z",
    }
    payload.update(overrides)
    return payload


def _record(**overrides):
    return execution_record_from_payload(_payload(**overrides))


def test_builder_session_reuse_omits_transaction_level_startup_envelope():
    request = build_control_transaction_request(
        request_id="reuse-1",
        issue=1025,
        kind="MERGE",
        lane_id=LANE,
        invocation_identity=INV,
        expected_coord_head="c" * 40,
        expected_generation=7,
        effect={},
        reuse_admission_session=True,
    )
    assert "startup_evidence" not in request
    assert request["session_reuse"] == {
        "schema": "WHD_INVOCATION_ADMISSION_SESSION_REUSE_V1",
        "mode": "LIVE_LEASE_CONTINUATION",
    }


@pytest.mark.parametrize("kind", ["ACQUIRE", "RECONCILE", "SYNC_TARGET", "RESERVE_PATHS", "HANDOFF"])
def test_builder_rejects_session_reuse_for_readmission_kinds(kind):
    with pytest.raises(ValueError, match="requires fresh admission"):
        build_control_transaction_request(
            request_id=f"reuse-{kind}",
            issue=1025,
            kind=kind,
            lane_id=LANE,
            invocation_identity=INV,
            expected_coord_head="c" * 40,
            expected_generation=7,
            effect={},
            reuse_admission_session=True,
        )


def test_ingress_session_reuse_accepts_matching_live_lease_without_startup(monkeypatch):
    import tools.control_transaction_request_ingress as ingress

    record = _record()
    monkeypatch.setattr(
        ingress,
        "_load_state",
        lambda *args, **kwargs: ("c" * 40, "d" * 40, {1025: record}),
    )
    captured = {}

    def fake_execute_one(**kwargs):
        captured.update(kwargs)
        return {"result": "APPLIED", "post_state": "INTEGRATING"}

    monkeypatch.setattr(ingress, "execute_one", fake_execute_one)
    request = build_control_transaction_request(
        request_id="reuse-merge",
        issue=1025,
        kind="MERGE",
        lane_id=LANE,
        invocation_identity=INV,
        expected_coord_head="c" * 40,
        expected_generation=7,
        effect={},
        reuse_admission_session=True,
    )
    result = ingress.execute_request(
        request=request,
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
    )
    assert result["result"] == "APPLIED"
    assert captured["invocation_identity"] == INV
    assert captured["kind"] == "MERGE"


def test_ingress_session_reuse_rejects_expired_or_foreign_lease(monkeypatch):
    import tools.control_transaction_request_ingress as ingress

    request = {
        "schema": "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1",
        "request_id": "reuse-bad",
        "issue": 1025,
        "kind": "MERGE",
        "lane_id": LANE,
        "invocation_identity": INV,
        "expected_coord_head": "c" * 40,
        "expected_generation": 7,
        "effect": {},
        "session_reuse": {
            "schema": "WHD_INVOCATION_ADMISSION_SESSION_REUSE_V1",
            "mode": "LIVE_LEASE_CONTINUATION",
        },
    }
    expired = _record(
        lease={
            "token": "lease-expired",
            "invocation_identity": INV,
            "expires_at": "2020-01-01T00:00:00Z",
        }
    )
    monkeypatch.setattr(
        ingress,
        "_load_state",
        lambda *args, **kwargs: ("c" * 40, "d" * 40, {1025: expired}),
    )
    with pytest.raises(Exception, match="session reuse.*expired"):
        ingress.execute_request(
            request=request,
            repo="looaeedr/whd",
            token="token",
            coord_branch="coord/execution-v2",
        )


def test_consume_qa_atomically_accepts_already_terminal_exact_head_run():
    record = _record()
    plan = prepare_transaction(
        record,
        kind="CONSUME_QA",
        transaction_id="tx-consume-qa",
        invocation_identity=INV,
    )
    updated = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": "2026-09-29T14:47:00Z",
            "run_id": 36599900001,
            "run_head_sha": HEAD,
            "run_status": "completed",
            "conclusion": "success",
            "next_state": "INTEGRATING",
            "semantic_state": "QA_ACCEPTED",
            "next_action": {
                "kind": "MERGE",
                "args": {
                    "pr_number": 1026,
                    "target_branch": "cleanup/2d-3d-sync",
                    "expected_target_sha": TARGET,
                    "head_sha": HEAD,
                    "revalidation_workflow": ".github/workflows/whd-control-plane-regression.yml",
                },
                "display": "merge exact accepted head",
            },
        },
    )
    assert updated.generation == 8
    assert updated.state == "INTEGRATING"
    assert updated.active_run is None
    assert updated.qa.last_accepted_run == 36599900001
    assert updated.qa.accepted_head_sha == HEAD
    assert updated.next_action.kind == "MERGE"


def test_consume_qa_requires_structured_start_qa_continuation():
    record = _record(next_action={"kind": "APPLY_COMMIT", "args": {}, "display": "continue"})
    plan = prepare_transaction(
        record,
        kind="CONSUME_QA",
        transaction_id="tx-consume-qa-invalid",
        invocation_identity=INV,
    )
    with pytest.raises(Exception, match="START_QA"):
        execute_transaction(
            record,
            plan,
            effect={
                "updated_at": "2026-09-29T14:47:00Z",
                "run_id": 36599900001,
                "run_head_sha": HEAD,
                "run_status": "completed",
                "conclusion": "success",
                "next_state": "INTEGRATING",
                "next_action": {"kind": "MERGE", "args": {}, "display": "merge"},
            },
        )


def test_trusted_consume_qa_reads_run_instead_of_trusting_caller(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _record()

    def fake_api(repo, method, path, token, payload=None):
        assert method == "GET"
        assert path == "/actions/runs/36599900001"
        return {
            "id": 36599900001,
            "head_sha": HEAD,
            "path": ".github/workflows/whd-control-plane-regression.yml",
            "status": "completed",
            "conclusion": "success",
        }

    monkeypatch.setattr(executor, "_api", fake_api)
    effect = executor._trusted_consume_qa_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=INV,
        supplied={
            "run_id": 36599900001,
            "next_state": "INTEGRATING",
            "next_action": {"kind": "MERGE", "args": {}, "display": "merge"},
        },
    )
    assert effect["run_head_sha"] == HEAD
    assert effect["run_status"] == "completed"
    assert effect["conclusion"] == "success"


def test_flow_skill_documents_session_reuse_and_consume_qa():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "WHD_INVOCATION_ADMISSION_SESSION_REUSE_V1" in text
    assert "CONSUME_QA" in text
    assert "START_QA → ACCEPT_QA" in text


def test_unrelated_coord_cas_race_retries_without_caller_resubmit(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _record()
    written = {"attempts": 0}

    def fake_write(repo, token, coord_branch, *, parent_sha, base_tree_sha, records, issue):
        written["attempts"] += 1
        if written["attempts"] == 1:
            raise ControlTransactionConflict(
                "coord/execution-v2 ref advanced during transaction"
            )
        written["record"] = records[issue]
        return "1" * 40, "2" * 40

    loads = {"count": 0}

    def fake_load_with_post(*args, **kwargs):
        loads["count"] += 1
        if loads["count"] <= 2:
            return "f" * 40, "e" * 40, {1025: record}
        return "1" * 40, "9" * 40, {1025: written["record"]}

    monkeypatch.setattr(executor, "_load_state", fake_load_with_post)
    monkeypatch.setattr(executor, "_write_state", fake_write)
    monkeypatch.setattr(
        executor,
        "_publish_transaction_progress",
        lambda *args, **kwargs: ("3" * 40, {
            "event": "PROGRESS",
            "liveness_state": "LIVE",
            "last_heartbeat_at": "2026-09-29T15:00:00Z",
            "heartbeat_expires_at": "2026-09-29T15:05:00Z",
        }),
    )

    result = executor._execute_one_attempt(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=1025,
        kind="RECONCILE",
        lane_id=LANE,
        invocation_identity=INV,
        supplied_effect={
            "observed_work_branch": record.work_branch,
            "observed_head_sha": record.head_sha,
            "observed_target_sha": record.target_sha,
            "next_action": {
                "kind": "APPLY_COMMIT",
                "args": {},
                "display": "continue",
            },
        },
    )
    assert result["result"] == "APPLIED"
    assert written["attempts"] == 2


def test_unrelated_coord_retry_fails_closed_if_same_issue_changed(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _record()
    changed = replace(record, generation=record.generation + 1)
    loads = {"count": 0}

    def fake_load(*args, **kwargs):
        loads["count"] += 1
        if loads["count"] == 1:
            return "f" * 40, "e" * 40, {1025: record}
        return "a" * 40, "b" * 40, {1025: changed}

    monkeypatch.setattr(executor, "_load_state", fake_load)
    monkeypatch.setattr(
        executor,
        "_write_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ControlTransactionConflict(
                "coord/execution-v2 ref advanced during transaction"
            )
        ),
    )

    with pytest.raises(ControlTransactionConflict, match="current Issue changed"):
        executor._execute_one_attempt(
            repo="looaeedr/whd",
            token="token",
            coord_branch="coord/execution-v2",
            issue=1025,
            kind="RECONCILE",
            lane_id=LANE,
            invocation_identity=INV,
            supplied_effect={
                "observed_work_branch": record.work_branch,
                "observed_head_sha": record.head_sha,
                "observed_target_sha": record.target_sha,
                "next_action": {
                    "kind": "APPLY_COMMIT",
                    "args": {},
                    "display": "continue",
                },
            },
        )


def test_flow_skill_documents_unrelated_coord_cas_retry():
    text = (
        ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "UNRELATED_COORD_CAS_RETRY_V1" in text
    assert "current Issue fingerprint" in text
    assert "cross-Issue path-conflict check" in text
