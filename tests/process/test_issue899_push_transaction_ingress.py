from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _root_entries():
    return [
        ".git", ".agents", ".github", "AGENTS.md", "tools", "tests",
        "ae_engine", "gui_modules", ".unpushed",
    ]


def _build_startup_evidence(*, purpose, invocation_identity, issued_at=None, execution_mode="INTERACTIVE"):
    import json
    from tools.execution_entry_contract import build_startup_evidence as canonical_build_startup_evidence
    from tools.work_root_gate import (
        READ_MODE_GITHUB_REPO,
        READ_MODE_WORKSPACE,
        build_work_root_gate_evidence,
    )

    payload = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text(encoding="utf-8")
    )
    read_mode = (
        READ_MODE_GITHUB_REPO
        if execution_mode in {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}
        else READ_MODE_WORKSPACE
    )
    gate_evidence = build_work_root_gate_evidence(
        gate_payload=payload,
        read_mode=read_mode,
        execution_mode=execution_mode,
        root_entries=_root_entries(), workspace_root="/workspace/whd",
    )
    return canonical_build_startup_evidence(
        purpose=purpose,
        invocation_identity=invocation_identity,
        execution_mode=execution_mode,
        work_root_gate_evidence=gate_evidence,
        issued_at=issued_at,
    )




def _build_preflight_evidence(*, issue, invocation_identity, execution_mode="INTERACTIVE", observed_at=None, branch="cleanup/2d-3d-sync", head_sha="a" * 40):
    from tools.execution_entry_contract import build_phase6_preflight_evidence

    required_skills = ["flow-v2-execution"]
    required_references = [".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"]
    return build_phase6_preflight_evidence(
        issue=issue,
        invocation_identity=invocation_identity,
        branch=branch,
        head_sha=head_sha,
        required_skills=required_skills,
        completed_skills=required_skills,
        required_references=required_references,
        completed_references=required_references,
        observed_at=observed_at,
    )


def _fresh_admission_fields(*, issue, invocation_identity, purpose, execution_mode="INTERACTIVE", issued_at=None, branch="cleanup/2d-3d-sync", head_sha="a" * 40):
    from tools.execution_entry_contract import build_startup_transition

    startup = _build_startup_evidence(
        purpose=purpose,
        invocation_identity=invocation_identity,
        execution_mode=execution_mode,
        issued_at=issued_at,
    )
    preflight = _build_preflight_evidence(
        issue=issue,
        invocation_identity=invocation_identity,
        execution_mode=execution_mode,
        observed_at=issued_at,
        branch=branch,
        head_sha=head_sha,
    )
    transition = build_startup_transition(
        startup_evidence=startup,
        preflight_evidence=preflight,
        invocation_identity=invocation_identity,
        issue=issue,
        execution_mode=execution_mode,
        now=issued_at,
    )
    return {
        "startup_evidence": startup,
        "preflight_evidence": preflight,
        "startup_transition": transition,
    }

def _root_gate_evidence(execution_mode="INTERACTIVE"):
    import json
    from tools.work_root_gate import (
        READ_MODE_GITHUB_REPO,
        READ_MODE_WORKSPACE,
        build_work_root_gate_evidence,
    )
    payload = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text(encoding="utf-8")
    )
    read_mode = (
        READ_MODE_GITHUB_REPO
        if execution_mode in {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}
        else READ_MODE_WORKSPACE
    )
    return build_work_root_gate_evidence(
        gate_payload=payload,
        read_mode=read_mode,
        execution_mode=execution_mode,
        root_entries=_root_entries(), workspace_root="/workspace/whd",
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
    assert "ref: cleanup/2d-3d-sync" in text
    assert "ref: main" not in text


def test_request_ingress_binds_coord_head_and_generation():
    text = (ROOT / "tools/control_transaction_request_ingress.py").read_text(encoding="utf-8")
    assert "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1" in text
    assert "expected_coord_head" in text
    assert "expected_generation" in text
    assert "coord head drift" in text
    assert "generation drift" in text
    assert "execute_one(" in text


def test_direct_production_workflow_stays_retired_and_request_ingress_owns_writes():
    assert not (ROOT / ".github/workflows/whd-control-transaction-v2.yml").exists()
    text = (ROOT / ".github/workflows/whd-control-transaction-v2-request.yml").read_text(encoding="utf-8")
    assert "contents: write" in text
    assert "issues: write" in text
    assert "control_transaction_request_ingress.py" in text


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

    with pytest.raises(ControlTransactionError, match="CONTINUE_TERMINAL_TAIL"):
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
    with pytest.raises(Exception, match="startup_evidence"):
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
        **_fresh_admission_fields(
            issue=943,
            invocation_identity=invocation,
            purpose="consume exact failed QA",
            execution_mode="INTERACTIVE",
            branch="work/receiving-ui-regression-20260928",
            head_sha="b" * 40,
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
        "preflight_evidence": _build_preflight_evidence(
            issue=945,
            invocation_identity="scheduler-b:b15:issue945:issue992-regression",
            execution_mode="SCHEDULER_LANE",
            branch="cleanup/2d-3d-sync",
            head_sha="a" * 40,
        ),
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
    assert request["startup_evidence"]["work_root_gate"]["read_mode"] == "GITHUB_REPO_CONTRACT"


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


def _root_unlock_receipt():
    from tools.root_local_first_gate import (
        build_entry_router_evidence,
        build_gate_evidence,
        build_git_unlock_receipt,
        build_remote_connection_authority,
        validate_source_current,
    )

    entry = build_entry_router_evidence(
        fresh_reads=[
            ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
            ".agents/skills/engineering/root-local-first/SKILL.md",
        ],
        workspace_root="/workspace/whd",
    )
    source = validate_source_current(
        workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40},
        live_source_sha="a" * 40, live_tree_sha="b" * 40,
    )
    reservation = {
        "schema": "WHD_PATH_RESERVATION_EVIDENCE_V1",
        "issue": 940,
        "generation": 4,
        "target_branch": "cleanup/2d-3d-sync",
        "base_sha": "a" * 40,
        "write_paths": ["AGENTS.md"],
        "delete_paths": [],
        "reservation_state": "ACTIVE",
        "phase": "DELIVERY_ONLY_AFTER_TESTED_DIFF_FROZEN",
        "record_fingerprint": "f" * 64,
    }
    authority = build_remote_connection_authority(
        kind="WORKSPACE_DELIVERY", target="GITHUB", user_explicit=True
    )
    gate = build_gate_evidence(
        execution_mode="INTERACTIVE",
        repository_content_implementation=True,
        entry_router_evidence=entry,
        source_evidence=source,
        workspace_mutations_complete=True,
        workspace_tests_green=True,
        workspace_delivery_authority=authority,
        path_reservation_evidence=reservation,
        test_receipt={
            "schema": "WHD_TEST_EXECUTION_RECEIPT_V1",
            "status": "GREEN",
            "source_sha": "a" * 40,
            "issue": 940,
            "generation": 4,
            "exact_commands": ["python tools/control_plane_regression.py"],
            "manifest_digest": "c" * 64,
        },
        expected_test_commands=["python tools/control_plane_regression.py"],
        diff_digest="c" * 64,
    )
    return build_git_unlock_receipt(gate)

def test_interactive_start_branch_requires_root_unlock_receipt_before_state_read(monkeypatch):
    import pytest
    import tools.control_transaction_request_ingress as ingress

    def _unexpected_state_read(*args, **kwargs):
        raise AssertionError("execution state must not be read before root-local-first Git receipt")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_state_read)
    invocation = "interactive:work0:issue940:branch"
    request = {
        "schema": ingress.REQUEST_SCHEMA, "request_id": "branch-no-root-receipt", "issue": 940,
        "kind": "START_BRANCH", "lane_id": "chatgpt.flowv2.work0",
        "invocation_identity": invocation, "expected_coord_head": "a" * 40, "expected_generation": 1,
        "effect": {"work_branch": "work/issue940", "head_sha": "a" * 40},
        **_fresh_admission_fields(
            issue=940, invocation_identity=invocation, purpose="Issue #940 branch"
        ),
    }
    with pytest.raises(Exception, match="root-local-first Git write receipt"):
        ingress.execute_request(request=request, repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2")


def test_interactive_start_branch_accepts_root_unlock_receipt_before_state_read(monkeypatch):
    import pytest
    import tools.control_transaction_request_ingress as ingress

    def _state_read(*args, **kwargs):
        raise RuntimeError("STATE_READ_REACHED")

    monkeypatch.setattr(ingress, "_load_state", _state_read)
    invocation = "interactive:work0:issue940:branch"
    request = {
        "schema": ingress.REQUEST_SCHEMA, "request_id": "branch-with-root-receipt", "issue": 940,
        "kind": "START_BRANCH", "lane_id": "chatgpt.flowv2.work0",
        "invocation_identity": invocation, "expected_coord_head": "a" * 40, "expected_generation": 1,
        "effect": {"work_branch": "work/issue940", "head_sha": "a" * 40,
                   "root_local_first_git_write_receipt": _root_unlock_receipt()},
        **_fresh_admission_fields(
            issue=940, invocation_identity=invocation, purpose="Issue #940 branch"
        ),
    }
    with pytest.raises(RuntimeError, match="STATE_READ_REACHED"):
        ingress.execute_request(request=request, repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2")


def test_scheduler_start_branch_requires_root_receipt_before_state_read(monkeypatch):
    import pytest
    import tools.control_transaction_request_ingress as ingress

    def _unexpected_state_read(*args, **kwargs):
        raise AssertionError("execution state must not be read before root-local-first Git receipt")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_state_read)
    lane = "scheduler.6ab13fa557fc8191935c671214b865e2"
    invocation = "scheduler:a:issue940:branch"
    request = {
        "schema": ingress.REQUEST_SCHEMA, "request_id": "scheduler-branch", "issue": 940,
        "kind": "START_BRANCH", "lane_id": lane, "invocation_identity": invocation,
        "expected_coord_head": "a" * 40, "expected_generation": 1,
        "effect": {"work_branch": "work/issue940", "head_sha": "a" * 40},
        **_fresh_admission_fields(
            issue=940,
            invocation_identity=invocation,
            purpose="Issue #940 scheduler branch",
            execution_mode="SCHEDULER_LANE",
        ),
    }
    with pytest.raises(Exception, match="SCHEDULER_LANE repository-content Git write requires root-local-first"):
        ingress.execute_request(request=request, repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2")


def test_push_request_workflow_reads_cleanup_single_production_authority():
    text = (ROOT / ".github/workflows/whd-control-transaction-v2-request.yml").read_text(encoding="utf-8")
    assert "ref: cleanup/2d-3d-sync" in text
    assert "ref: main" not in text


def test_trusted_consume_qa_generates_updated_at_when_caller_omits_it(monkeypatch):
    from tools.control_transaction import execute_transaction, prepare_transaction
    import tools.control_transaction_production_executor as executor
    from tools.execution_record import execution_record_from_payload

    invocation = "chatgpt.flowv2.work2.issue1069.test"
    head = "b" * 40
    target = "c" * 40
    run_id = 36731738806
    workflow = ".github/workflows/whd-control-plane-regression.yml"
    record = execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 5,
        "issue": 1069,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": "chatgpt.flowv2.work2",
        "lane_id": "chatgpt.flowv2.work2",
        "slot_id": "worker.slot.2",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": target,
        "work_branch": "governance/issue1069-consume-qa-updated-at",
        "head_sha": head,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": target,
        "state": "ACTIVE",
        "semantic_state": "ROOT_TESTED_DIFF_APPLIED",
        "next_action": {
            "kind": "START_QA",
            "args": {"workflow": workflow},
            "display": "consume existing exact-head QA",
        },
        "lease": {
            "token": "lease-1069",
            "invocation_identity": invocation,
            "expires_at": "2099-10-01T00:00:00Z",
        },
        "active_run": None,
        "transaction": None,
        "mutation_scope": {
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": target,
            "write_paths": ["tools/control_transaction_production_executor.py"],
            "delete_paths": [],
            "reservation_state": "ACTIVE",
        },
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-30T16:30:00Z",
    })

    def fake_api(repo, method, path, token, payload=None):
        assert repo == "looaeedr/whd"
        assert method == "GET"
        assert path == f"/actions/runs/{run_id}"
        return {
            "id": run_id,
            "head_sha": head,
            "path": workflow,
            "status": "completed",
            "conclusion": "success",
            "name": "WHD Control Plane Regression",
        }

    monkeypatch.setattr(executor, "_api", fake_api)
    effect = executor._trusted_consume_qa_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=invocation,
        supplied={
            "run_id": run_id,
            "next_state": "INTEGRATING",
            "semantic_state": "QA_ACCEPTED",
            "next_action": {
                "kind": "MERGE",
                "args": {"pr_number": 1070, "head_sha": head, "target_branch": record.target_branch},
                "display": "merge exact accepted head",
            },
        },
    )
    updated = execute_transaction(
        record,
        prepare_transaction(
            record,
            kind="CONSUME_QA",
            transaction_id="tx-issue1069-consume-qa",
            invocation_identity=invocation,
        ),
        effect=effect,
    )

    assert effect["updated_at"]
    assert updated.qa.last_accepted_run == run_id
    assert updated.qa.accepted_head_sha == head
    assert updated.next_action.kind == "MERGE"


def _issue1072_start_branch_record(*, generation=5, base_sha="a" * 40, write_paths=None):
    from tools.execution_record import execution_record_from_payload

    invocation = "chatgpt.flowv2.work2.issue1072.test"
    write_paths = list(write_paths or ["AGENTS.md"])
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": generation,
        "issue": 940,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": "chatgpt.flowv2.work2",
        "lane_id": "chatgpt.flowv2.work2",
        "slot_id": "worker.slot.2",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": base_sha,
        "work_branch": "work/issue940",
        "head_sha": base_sha,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": base_sha,
        "state": "ACTIVE",
        "semantic_state": "ROOT_DIFF_FROZEN",
        "next_action": {
            "kind": "START_BRANCH",
            "args": {"diff_digest": "c" * 64},
            "display": "create branch",
        },
        "lease": {
            "token": "lease-940-renewed",
            "invocation_identity": invocation,
            "expires_at": "2099-10-01T00:00:00Z",
        },
        "active_run": None,
        "transaction": None,
        "mutation_scope": {
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": base_sha,
            "write_paths": write_paths,
            "delete_paths": [],
            "reservation_state": "ACTIVE",
        },
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-30T22:52:05Z",
    })


def test_issue1072_lease_renewal_generation_does_not_invalidate_frozen_root_receipt(monkeypatch):
    from tools.control_transaction import build_mutation_writer_guard
    import tools.control_transaction_request_ingress as ingress

    record = _issue1072_start_branch_record(generation=5)
    invocation = record.lease.invocation_identity
    guard = build_mutation_writer_guard(
        record, kind="START_BRANCH", invocation_identity=invocation
    )
    request = {
        "kind": "START_BRANCH",
        "invocation_identity": invocation,
        "effect": {
            "head_sha": record.head_sha,
            "root_local_first_git_write_receipt": _root_unlock_receipt(),
            "mutation_writer_guard": guard,
        },
    }

    monkeypatch.setattr(
        ingress,
        "_read_branch_head",
        lambda repo, token, branch: record.target_sha if branch == record.target_branch else record.head_sha,
    )

    ingress._validate_repository_content_git_write_receipt(
        request,
        execution_mode="INTERACTIVE",
        record=record,
        repo="looaeedr/whd",
        token="token",
    )


def test_issue1072_fresh_mutation_guard_still_fences_current_execution_identity(monkeypatch):
    import pytest
    from tools.control_transaction import build_mutation_writer_guard
    import tools.control_transaction_request_ingress as ingress

    record = _issue1072_start_branch_record(generation=5)
    invocation = record.lease.invocation_identity
    guard = build_mutation_writer_guard(
        record, kind="START_BRANCH", invocation_identity=invocation
    )
    guard["generation"] = 4
    request = {
        "kind": "START_BRANCH",
        "invocation_identity": invocation,
        "effect": {
            "head_sha": record.head_sha,
            "root_local_first_git_write_receipt": _root_unlock_receipt(),
            "mutation_writer_guard": guard,
        },
    }
    monkeypatch.setattr(
        ingress,
        "_read_branch_head",
        lambda repo, token, branch: record.target_sha if branch == record.target_branch else record.head_sha,
    )

    with pytest.raises(Exception, match="mutation guard generation drift"):
        ingress._validate_repository_content_git_write_receipt(
            request,
            execution_mode="INTERACTIVE",
            record=record,
            repo="looaeedr/whd",
            token="token",
        )


def test_issue1072_root_contract_treats_generation_as_provenance_not_content_identity():
    import json

    contract = json.loads(
        (ROOT / ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = contract["test_execution_receipt"]
    assert "generation" not in receipt["required_identity"]
    assert receipt["generation_role"] == "HISTORICAL_FREEZE_PROVENANCE_ONLY"
    git_receipt = contract["git_write_receipt"]
    assert git_receipt["current_execution_fence"] == "WHD_FLOW_V2_MUTATION_WRITER_GUARD_V1"
    assert git_receipt["lease_renewal_generation_drift"] == "DOES_NOT_INVALIDATE_UNCHANGED_FROZEN_EVIDENCE"


def test_issue1072_frozen_root_receipt_still_fails_closed_on_content_identity_drift(monkeypatch):
    import copy
    import pytest
    from tools.control_transaction import build_mutation_writer_guard
    import tools.control_transaction_request_ingress as ingress

    record = _issue1072_start_branch_record(generation=5)
    invocation = record.lease.invocation_identity
    guard = build_mutation_writer_guard(record, kind="START_BRANCH", invocation_identity=invocation)
    monkeypatch.setattr(
        ingress,
        "_read_branch_head",
        lambda repo, token, branch: record.target_sha if branch == record.target_branch else record.head_sha,
    )

    cases = [
        ("source_sha", "d" * 40, "source/base drift"),
        ("write_paths", ["README.md"], "reserved paths drift"),
        ("diff_digest", "d" * 64, "diff digest drift"),
    ]
    for field, value, message in cases:
        receipt = copy.deepcopy(_root_unlock_receipt())
        receipt[field] = value
        request = {
            "kind": "START_BRANCH",
            "invocation_identity": invocation,
            "effect": {
                "head_sha": record.head_sha,
                "root_local_first_git_write_receipt": receipt,
                "mutation_writer_guard": guard,
            },
        }
        with pytest.raises(Exception, match=message):
            ingress._validate_repository_content_git_write_receipt(
                request,
                execution_mode="INTERACTIVE",
                record=record,
                repo="looaeedr/whd",
                token="token",
            )


def test_issue1072_flow_skill_assigns_current_execution_fence_to_mutation_guard():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "freeze-time provenance" in text
    assert "mutation_writer_guard" in text
    assert "lease renewal" in text
    assert "不得要求重跑 root tests" in text
