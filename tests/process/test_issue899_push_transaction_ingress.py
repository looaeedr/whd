from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_push_request_workflow_is_scheduler_compatible():
    text = (ROOT / ".github/workflows/whd-control-transaction-v2-request.yml").read_text(encoding="utf-8")
    assert "coord/transaction-requests-a" in text
    assert "coord/transaction-requests-b" in text
    assert "coord/transaction-requests-work0" in text
    assert "coord/transaction-requests-work1" in text
    assert "coord/transaction-requests-work2" in text
    assert "coord/transaction-requests-work3" in text
    assert ".dispatch/transaction-request.json" in text
    assert "contents: write" in text
    assert "issues: write" in text
    assert "control_transaction_request_ingress.py" in text


def test_request_ingress_binds_coord_head_and_generation():
    text = (ROOT / "tools/control_transaction_request_ingress.py").read_text(encoding="utf-8")
    assert "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1" in text
    assert "expected_coord_head" in text
    assert "expected_generation" in text
    assert "coord head drift" in text
    assert "generation drift" in text
    assert "execute_one(" in text


def test_manual_production_workflow_can_finalize_issues():
    text = (ROOT / ".github/workflows/whd-control-transaction-v2.yml").read_text(encoding="utf-8")
    assert "contents: write" in text
    assert "issues: write" in text


def test_canonical_skill_uses_push_request_not_scheduler_workflow_dispatch():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "FLOW_V2_PRODUCTION_TRANSACTION_V2" in text
    assert "coord/transaction-requests-a" in text
    assert "coord/transaction-requests-b" in text
    assert "expected_coord_head" in text
    assert "expected_generation" in text
    assert "scheduler不得依賴 connector 未提供的 workflow_dispatch" in text


def test_seed_request_is_noop_without_execution_state(monkeypatch):
    import tools.control_transaction_request_ingress as ingress

    def _unexpected_load(*args, **kwargs):
        raise AssertionError("SEED must not read or mutate coord/execution-v2")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_load)
    request = {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "seed-test",
        "issue": 0,
        "kind": "SEED",
        "lane_id": "scheduler.seed-test",
        "invocation_identity": "bootstrap-seed",
        "expected_coord_head": "",
        "expected_generation": 0,
        "effect": {},
    }
    result = ingress.execute_request(
        request=request,
        repo="looaeedr/whd",
        token="unused-for-seed",
        coord_branch="coord/execution-v2",
    )
    assert result["result"] == "APPLIED"
    assert result["reason"] == "SEED_NOOP"
    assert result["transaction"] == {"status": "RECONCILED", "kind": "SEED"}


def test_canonical_skill_forbids_scheduler_host_lifecycle_mutation():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "FLOW_V2_HOST_LIFECYCLE_IMMUTABILITY_V1" in text
    assert "MUST NOT call automation-management APIs" in text
    assert "Invocation completion is only a cycle return" in text
    assert "recurring task object unchanged" in text


def test_request_branch_isolation_accepts_exact_lane():
    import tools.control_transaction_request_ingress as ingress

    request = {"lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2"}
    ingress._validate_request_branch(
        request=request,
        request_branch="coord/transaction-requests-a",
    )

    request = {"lane_id": "chatgpt.flowv2.work0"}
    ingress._validate_request_branch(
        request=request,
        request_branch="coord/transaction-requests-work0",
    )


def test_request_branch_isolation_rejects_cross_lane():
    import pytest
    import tools.control_transaction_request_ingress as ingress

    with pytest.raises(Exception, match="request lane mismatch"):
        ingress._validate_request_branch(
            request={"lane_id": "chatgpt.flowv2.work0"},
            request_branch="coord/transaction-requests-b",
        )


def test_request_branch_isolation_rejects_unknown_branch():
    import pytest
    import tools.control_transaction_request_ingress as ingress

    with pytest.raises(Exception, match="unsupported request branch"):
        ingress._validate_request_branch(
            request={"lane_id": "chatgpt.flowv2.work0"},
            request_branch="coord/transaction-requests-unknown",
        )


def test_trusted_transaction_projects_non_authoritative_progress_observation():
    text = (ROOT / "tools/control_transaction_production_executor.py").read_text(encoding="utf-8")
    adapter = (ROOT / "tools/flow_v2_runtime_observation.py").read_text(encoding="utf-8")
    assert "_publish_transaction_progress(" in text
    assert "runtime_observation_commit_sha" in text
    assert "runtime_last_heartbeat_at" in text
    assert "runtime_heartbeat_expires_at" in text
    assert 'event="PROGRESS"' in adapter
    assert '"HEARTBEAT"' in adapter
    assert "HEARTBEAT_TTL_SECONDS = 300" in adapter


def test_yield_trusted_writer_rejects_acquire_only_churn():
    from tools.control_transaction import (
        ControlTransactionError,
        execute_transaction,
        prepare_transaction,
    )
    from tools.execution_record import execution_record_from_payload
    import pytest

    invocation = "scheduler-a-20-run"
    record = execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 5,
        "issue": 889,
        "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "SCHEDULER",
        "owner_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "slot_id": None,
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "canary/issue889",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "INTEGRATING",
        "semantic_state": "QA_ACCEPTED",
        "next_action": {
            "kind": "MERGE",
            "args": {"pr_number": 891, "head_sha": "b" * 40, "target_branch": "cleanup/2d-3d-sync"},
            "display": "Merge exact PR",
        },
        "lease": {
            "token": "lease-889",
            "invocation_identity": invocation,
            "expires_at": "2026-09-28T14:00:00Z",
        },
        "active_run": None,
        "transaction": {
            "id": "gha:acquire",
            "kind": "ACQUIRE",
            "status": "RECONCILED",
            "expected_fingerprint": "d" * 64,
            "invocation_identity": invocation,
        },
        "qa": {"last_accepted_run": 36392993699, "accepted_head_sha": "b" * 40},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T13:40:00Z",
    })
    plan = prepare_transaction(
        record,
        kind="YIELD",
        transaction_id="tx-noop-yield",
        invocation_identity=invocation,
    )

    with pytest.raises(ControlTransactionError, match="SCHEDULER_EXECUTION_NO_PROGRESS"):
        execute_transaction(
            record,
            plan,
            effect={"updated_at": "2026-09-28T13:41:00Z"},
        )


def test_control_plane_regression_watches_core_flow_v2_exit_files():
    workflow = (ROOT / ".github/workflows/whd-control-plane-regression.yml").read_text(encoding="utf-8")
    for required in (
        ".agents/skills/engineering/flow-v2-execution/SKILL.md",
        "tools/control_transaction.py",
        "tools/execution_invocation_exit.py",
    ):
        assert required in workflow
