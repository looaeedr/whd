from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _build_startup_evidence(*, purpose, invocation_identity, issued_at=None, execution_mode="INTERACTIVE"):
    import json
    from tools.execution_entry_contract import build_startup_evidence as canonical_build_startup_evidence
    from tools.work_root_gate import (
        READ_MODE_GITHUB_MIRROR,
        READ_MODE_GOOGLE_DRIVE,
        build_work_root_gate_evidence,
    )

    mirror = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json").read_text(encoding="utf-8")
    )
    if execution_mode in {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}:
        gate_payload = mirror
        read_mode = READ_MODE_GITHUB_MIRROR
    else:
        gate_payload = dict(mirror)
        gate_payload.pop("role", None)
        gate_payload.pop("mirror_policy", None)
        gate_payload.pop("canonical_source", None)
        read_mode = READ_MODE_GOOGLE_DRIVE

    gate_evidence = build_work_root_gate_evidence(
        gate_payload=gate_payload,
        read_mode=read_mode,
        execution_mode=execution_mode,
    )
    return canonical_build_startup_evidence(
        purpose=purpose,
        invocation_identity=invocation_identity,
        execution_mode=execution_mode,
        work_root_gate_evidence=gate_evidence,
        issued_at=issued_at,
    )

def _root_gate_evidence(execution_mode="INTERACTIVE"):
    import json
    from tools.work_root_gate import (
        READ_MODE_GITHUB_MIRROR,
        READ_MODE_GOOGLE_DRIVE,
        build_work_root_gate_evidence,
    )

    payload = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json").read_text(
            encoding="utf-8"
        )
    )
    if execution_mode in {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}:
        read_mode = READ_MODE_GITHUB_MIRROR
    else:
        payload.pop("role", None)
        payload.pop("mirror_policy", None)
        payload.pop("canonical_source", None)
        read_mode = READ_MODE_GOOGLE_DRIVE
    return build_work_root_gate_evidence(
        gate_payload=payload,
        read_mode=read_mode,
        execution_mode=execution_mode,
    )



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


def test_non_seed_request_without_startup_evidence_is_rejected(tmp_path):
    import json
    import pytest
    import tools.control_transaction_request_ingress as ingress

    request = {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "no-startup-evidence",
        "issue": 940,
        "kind": "ACQUIRE",
        "lane_id": "chatgpt.flowv2.work0",
        "invocation_identity": "interactive:work0:issue940:test",
        "expected_coord_head": "a" * 40,
        "expected_generation": 1,
        "effect": {},
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(Exception, match="request missing startup_evidence"):
        ingress._load_request(path)


def test_startup_evidence_is_bound_to_exact_invocation_before_state_read(monkeypatch):
    import pytest
    import tools.control_transaction_request_ingress as ingress
    from tools.execution_entry_contract import build_startup_evidence

    def _unexpected_state_read(*args, **kwargs):
        raise AssertionError("execution state must not be read before startup gate")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_state_read)
    evidence = _build_startup_evidence(
        purpose="Issue #940 mutation",
        invocation_identity="interactive:work0:issue940:other",
        execution_mode="INTERACTIVE",
    )
    request = {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "cross-invocation",
        "issue": 940,
        "kind": "ACQUIRE",
        "lane_id": "chatgpt.flowv2.work0",
        "invocation_identity": "interactive:work0:issue940:current",
        "expected_coord_head": "a" * 40,
        "expected_generation": 1,
        "effect": {},
        "startup_evidence": evidence,
    }
    with pytest.raises(Exception, match="startup evidence invocation mismatch"):
        ingress.execute_request(
            request=request,
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
        )


def test_stale_startup_evidence_is_rejected_before_state_read(monkeypatch):
    from datetime import datetime, timezone
    import pytest
    import tools.control_transaction_request_ingress as ingress
    from tools.execution_entry_contract import build_startup_evidence

    def _unexpected_state_read(*args, **kwargs):
        raise AssertionError("execution state must not be read before startup gate")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_state_read)
    invocation = "interactive:work0:issue940:stale"
    evidence = _build_startup_evidence(
        purpose="Issue #940 mutation",
        invocation_identity=invocation,
        execution_mode="INTERACTIVE",
        issued_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    request = {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "stale-startup-evidence",
        "issue": 940,
        "kind": "ACQUIRE",
        "lane_id": "chatgpt.flowv2.work0",
        "invocation_identity": invocation,
        "expected_coord_head": "a" * 40,
        "expected_generation": 1,
        "effect": {},
        "startup_evidence": evidence,
    }
    with pytest.raises(Exception, match="startup evidence expired"):
        ingress.execute_request(
            request=request,
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
        )


def test_canonical_startup_evidence_ttl_and_declaration_are_machine_validated():
    from datetime import datetime, timedelta, timezone
    import pytest
    from tools.execution_entry_contract import (
        EVIDENCE_MAX_AGE_SECONDS,
        build_startup_evidence,
        validate_startup_evidence,
    )

    now = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)
    invocation = "scheduler-a:20:2026-09-28T14:00:00Z"
    evidence = _build_startup_evidence(
        purpose="resume Scheduler A issue",
        invocation_identity=invocation,
        execution_mode="SCHEDULER_LANE",
        issued_at=now,
    )
    validated = validate_startup_evidence(
        evidence,
        invocation_identity=invocation,
        repository="looaeedr/whd",
        now=now + timedelta(seconds=EVIDENCE_MAX_AGE_SECONDS),
    )
    assert validated["schema"] == "WHD_EXECUTION_ENTRY_EVIDENCE_V1"
    assert validated["declaration"].startswith(
        "WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1\n"
    )

    tampered = dict(evidence)
    tampered["declaration"] = "forged"
    with pytest.raises(ValueError, match="declaration mismatch"):
        validate_startup_evidence(
            tampered,
            invocation_identity=invocation,
            repository="looaeedr/whd",
            now=now,
        )


def _qa_record_for_fail_transaction():
    from tools.execution_record import execution_record_from_payload
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 7,
        "issue": 943,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": "chatgpt.flowv2.work1",
        "lane_id": "chatgpt.flowv2.work1",
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "work/receiving-ui-regression-20260928",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "VERIFYING",
        "semantic_state": "REMOTE_QA",
        "next_action": {
            "kind": "POLL_QA",
            "args": {"run_id": 36440753727, "head_sha": "b" * 40},
            "display": "poll exact QA",
        },
        "lease": {
            "token": "lease-943",
            "invocation_identity": "interactive:work1:issue943",
            "expires_at": "2026-09-28T16:00:00Z",
        },
        "active_run": {
            "id": 36440753727,
            "head_sha": "b" * 40,
            "purpose": "ISSUE943_FOCUSED_RED",
            "status": "in_progress",
        },
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T15:00:00Z",
    })


def test_fail_qa_consumes_exact_terminal_failure_and_returns_to_repair():
    from tools.control_transaction import execute_transaction, prepare_transaction

    record = _qa_record_for_fail_transaction()
    plan = prepare_transaction(
        record,
        kind="FAIL_QA",
        transaction_id="tx-fail-qa-943",
        invocation_identity="interactive:work1:issue943",
    )
    repaired = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": "2026-09-28T15:10:00Z",
            "run_id": 36440753727,
            "run_head_sha": "b" * 40,
            "conclusion": "failure",
            "next_action": {
                "kind": "RECONCILE",
                "args": {"reason": "AUTHOR_REPAIR_AFTER_FAILED_QA"},
                "display": "author repair commit",
            },
        },
    )
    assert repaired.state == "ACTIVE"
    assert repaired.semantic_state == "QA_FAILED_REPAIR"
    assert repaired.active_run is None
    assert repaired.work_branch == record.work_branch
    assert repaired.head_sha == record.head_sha
    assert repaired.target_sha == record.target_sha
    assert repaired.owner_id == record.owner_id
    assert repaired.lane_id == record.lane_id
    assert repaired.slot_id == record.slot_id
    assert repaired.qa == record.qa
    assert repaired.next_action.kind == "RECONCILE"
    assert repaired.transaction.kind == "FAIL_QA"


def test_fail_qa_rejects_wrong_run_head_and_success_conclusion():
    import pytest
    from tools.control_transaction import (
        ControlTransactionError,
        execute_transaction,
        prepare_transaction,
    )

    record = _qa_record_for_fail_transaction()
    base = {
        "updated_at": "2026-09-28T15:10:00Z",
        "run_id": 36440753727,
        "run_head_sha": "b" * 40,
        "conclusion": "failure",
        "next_action": {
            "kind": "RECONCILE",
            "args": {"reason": "AUTHOR_REPAIR_AFTER_FAILED_QA"},
            "display": "repair",
        },
    }

    with pytest.raises(ControlTransactionError, match="run_id"):
        execute_transaction(
            record,
            prepare_transaction(record, kind="FAIL_QA", transaction_id="tx-wrong-run"),
            effect={**base, "run_id": 999},
        )
    with pytest.raises(ControlTransactionError, match="run_head_sha"):
        execute_transaction(
            record,
            prepare_transaction(record, kind="FAIL_QA", transaction_id="tx-wrong-head"),
            effect={**base, "run_head_sha": "d" * 40},
        )
    with pytest.raises(ControlTransactionError, match="terminal non-success"):
        execute_transaction(
            record,
            prepare_transaction(record, kind="FAIL_QA", transaction_id="tx-success"),
            effect={**base, "conclusion": "success"},
        )


def test_push_ingress_accepts_fail_qa_kind(tmp_path):
    import json
    import tools.control_transaction_request_ingress as ingress
    from tools.execution_entry_contract import build_startup_evidence

    invocation = "interactive:work1:issue943:test"
    request = {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "fail-qa-test",
        "issue": 943,
        "kind": "FAIL_QA",
        "lane_id": "chatgpt.flowv2.work1",
        "invocation_identity": invocation,
        "expected_coord_head": "a" * 40,
        "expected_generation": 7,
        "effect": {},
        "startup_evidence": _build_startup_evidence(
            purpose="consume exact failed QA",
            invocation_identity=invocation,
            execution_mode="INTERACTIVE",
        ),
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    loaded = ingress._load_request(path)
    assert loaded["kind"] == "FAIL_QA"


def test_scheduler_lane_rejects_interactive_root_gate_before_state_read(monkeypatch):
    import pytest
    import tools.control_transaction_request_ingress as ingress

    def _unexpected_state_read(*args, **kwargs):
        raise AssertionError("execution state must not be read before root-gate mode validation")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_state_read)
    invocation = "scheduler-a:20:issue961:wrong-root-mode"
    request = {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "scheduler-wrong-root-mode",
        "issue": 961,
        "kind": "ACQUIRE",
        "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "invocation_identity": invocation,
        "expected_coord_head": "a" * 40,
        "expected_generation": 1,
        "effect": {},
        "startup_evidence": _build_startup_evidence(
            purpose="scheduler wrong root mode",
            invocation_identity=invocation,
            execution_mode="INTERACTIVE",
        ),
    }
    with pytest.raises(Exception, match="execution_mode mismatch"):
        ingress.execute_request(
            request=request,
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
        )


def _issue992_semantic_intent():
    from tools.control_transaction_request_builder import INTENT_SCHEMA

    return {
        "schema": INTENT_SCHEMA,
        "request_id": "issue992-b-acquire",
        "issue": 945,
        "kind": "ACQUIRE",
        "lane_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
        "invocation_identity": "scheduler-b:b15:issue945:issue992-regression",
        "expected_coord_head": "a" * 40,
        "expected_generation": 6,
        "effect": {},
        "purpose": "Resume Issue #945 through the canonical scheduler lane.",
        "work_root_gate_evidence": _root_gate_evidence("SCHEDULER_LANE"),
    }


def test_trusted_builder_materializes_scheduler_semantic_intent():
    from tools.control_transaction_request_builder import (
        REQUEST_SCHEMA,
        build_control_transaction_request_from_intent,
    )

    intent = _issue992_semantic_intent()
    assert "startup_evidence" not in intent
    request = build_control_transaction_request_from_intent(
        intent,
        repository="looaeedr/whd",
    )
    assert request["schema"] == REQUEST_SCHEMA
    assert request["startup_evidence"]["execution_mode"] == "SCHEDULER_LANE"
    assert request["startup_evidence"]["work_root_gate"]["read_mode"] == "GITHUB_MIRROR"


def test_semantic_intent_forbids_caller_supplied_startup_evidence(tmp_path):
    import json
    import pytest
    import tools.control_transaction_request_ingress as ingress

    intent = _issue992_semantic_intent()
    intent["startup_evidence"] = {"schema": "supplied"}
    path = tmp_path / "intent.json"
    path.write_text(json.dumps(intent), encoding="utf-8")
    with pytest.raises(Exception, match="startup_evidence"):
        ingress._load_request(path)


def test_push_ingress_accepts_semantic_intent_shape(tmp_path):
    import json
    import tools.control_transaction_request_ingress as ingress

    intent = _issue992_semantic_intent()
    path = tmp_path / "intent.json"
    path.write_text(json.dumps(intent), encoding="utf-8")
    loaded = ingress._load_request(path)
    assert loaded["schema"] == ingress.INTENT_SCHEMA
    assert loaded["purpose"] == intent["purpose"]


def test_scheduler_host_recovery_bootstrap_remains_non_authoritative():
    flow = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    scheduler = (ROOT / ".agents/skills/engineering/排程模擬/SKILL.md").read_text(encoding="utf-8")
    assert "SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1" in flow
    assert "SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1" in scheduler
    assert "CYCLE_END — KEEP_SCHEDULE_ENABLED" in flow
    assert "CYCLE_END — KEEP_SCHEDULE_ENABLED" in scheduler
    assert "不授權 ACQUIRE" in flow
