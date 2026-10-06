import pytest

import tools.control_transaction_production_executor as executor
import tools.control_transaction_request_ingress as ingress
from tools.control_transaction_request_builder import build_control_transaction_request
from tools.work_root_gate import build_work_root_gate_evidence
from tools.execution_dispatch_ingress import (
    DispatchIngressRequest,
    plan_dispatch_ingress,
)


ISSUE = 1331
HEAD = "a" * 40
COORD = "c" * 40


def _interactive_request(**effect_overrides):
    effect = {
        "authority_kind": "USER_EXPLICIT",
        "authority_ref": "user-explicit:issue-1331",
    }
    effect.update(effect_overrides)
    return {
        "issue": ISSUE,
        "lane_id": "chatgpt.flowv2.work0",
        "effect": effect,
        "startup_transition": {
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
            "issued_at": "2026-10-06T15:00:00Z",
        },
    }


def _dispatch_request():
    return DispatchIngressRequest(
        issue=ISSUE,
        execution_intent="EXECUTE_TICKET",
        authority_kind="USER_EXPLICIT",
        authority_ref="user-explicit:issue-1331",
        source_branch="cleanup/2d-3d-sync",
        source_sha=HEAD,
        work_branch="work/issue-1331",
        target_branch="cleanup/2d-3d-sync",
        target_sha=HEAD,
        slot_id="worker.slot.0",
        created_at="2026-10-06T15:00:00Z",
    )


def test_dispatch_ready_is_a_trusted_request_kind():
    assert "DISPATCH_READY" in ingress.ALLOWED_KINDS

def test_dispatch_ready_is_machine_internal_orchestration():
    from tools.root_local_first_gate import classify_outer_orchestration_event

    classified = classify_outer_orchestration_event("DISPATCH_READY")
    assert classified["disposition"] == "BACKGROUND_CONTINUE_PRIMARY_TASK"
    assert classified["outer_visible"] is False


def _control_plane_root_evidence():
    gate = {
        "schema": "WHD_WORK_ROOT_HARD_GATE_V2",
        "status": "CURRENT",
        "default_work_root": {
            "provider": "executor_local_workspace",
            "path_policy": "EXECUTOR_LOCAL_REPO_WORKSPACE",
            "production_branch": "cleanup/2d-3d-sync",
            "authority": False,
        },
        "drive_mirror": {
            "library_path": "/Google Drive/WHD/WHD_MIRROR/CURRENT",
            "role": "MIRROR_BACKUP_ONLY",
            "authority": False,
            "ordinary_startup_required": False,
            "routing_forbidden": True,
        },
        "required_root_entries": [".git", ".agents", ".github", "AGENTS.md", "tools", "tests", "ae_engine", "gui_modules"],
        "root_identity_recovery": {
            "owner": "tools/work_root_gate.py::recover_canonical_root_to_current_production",
            "success_schema": "WHD_WORK_ROOT_RECOVERY_RECEIPT_V1",
            "failure_schema": "WHD_WORK_ROOT_RECOVERY_RESULT_V1",
            "terminal_gate": False,
            "closure_authority": False,
            "purpose": "OPTIONAL_WORKSPACE_BASELINE_CATCHUP",
        },
    }
    return build_work_root_gate_evidence(
        gate_payload=gate,
        read_mode="GITHUB_REPO_CONTRACT",
        execution_mode="INTERACTIVE",
        root_entries=gate["required_root_entries"],
        production_head_sha=HEAD,
        control_plane_only=True,
    )


def _preflight(invocation="chatgpt.issue1331.bootstrap"):
    return {
        "schema": "WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1",
        "status": "GREEN",
        "issue": ISSUE,
        "invocation_identity": invocation,
        "branch": "cleanup/2d-3d-sync",
        "head_sha": HEAD,
        "required_skills": ["phase6-corner-3d-model-integrity"],
        "completed_skills": ["phase6-corner-3d-model-integrity"],
        "required_references": ["ref.md"],
        "completed_references": ["ref.md"],
        "observed_at": "2026-10-06T15:49:43Z",
    }


def test_dispatch_ready_accepts_control_plane_only_fresh_admission():
    invocation = "chatgpt.issue1331.bootstrap"
    request = build_control_transaction_request(
        request_id="issue1331-ready-bootstrap",
        issue=ISSUE,
        kind="DISPATCH_READY",
        lane_id="chatgpt.flowv2.work0",
        invocation_identity=invocation,
        expected_coord_head=COORD,
        expected_generation=1,
        effect={
            "authority_kind": "USER_EXPLICIT",
            "authority_ref": "user-explicit:issue-1331",
        },
        purpose="bootstrap issue 1331 READY",
        work_root_gate_evidence=_control_plane_root_evidence(),
        preflight_evidence=_preflight(invocation),
        issued_at=__import__("datetime").datetime.fromisoformat("2026-10-06T15:49:43+00:00"),
    )

    root = request["startup_evidence"]["work_root_gate"]
    assert root["scope"] == "CONTROL_PLANE_ONLY"
    assert root["provider"] == "github_repository_contract"
    assert root["repository_content_write_unlocked"] is False
    assert request["startup_transition"]["status"] == "READY_FOR_EXECUTION"


def test_control_plane_only_admission_cannot_unlock_other_transaction_kind():
    invocation = "chatgpt.issue1331.bootstrap"
    with pytest.raises(ValueError, match="not allowed for transaction kind ACQUIRE"):
        build_control_transaction_request(
            request_id="issue1331-illegal-acquire",
            issue=ISSUE,
            kind="ACQUIRE",
            lane_id="chatgpt.flowv2.work0",
            invocation_identity=invocation,
            expected_coord_head=COORD,
            expected_generation=1,
            effect={},
            purpose="illegal control-only acquire",
            work_root_gate_evidence=_control_plane_root_evidence(),
            preflight_evidence=_preflight(invocation),
            issued_at=__import__("datetime").datetime.fromisoformat("2026-10-06T15:49:43+00:00"),
        )


def test_interactive_dispatch_ready_binds_preflight_identity_and_lane_slot():
    request = ingress._build_dispatch_ready_ingress_request(
        _interactive_request(),
        execution_mode="INTERACTIVE",
        repo="looaeedr/whd",
        token="unused",
    )
    plan = plan_dispatch_ingress(request)

    assert request.source_branch == "cleanup/2d-3d-sync"
    assert request.source_sha == HEAD
    assert request.target_branch == "cleanup/2d-3d-sync"
    assert request.target_sha == HEAD
    assert request.work_branch == "work/issue-1331"
    assert request.slot_id == "worker.slot.0"
    assert plan.record.generation == 1
    assert plan.record.state == "READY"
    assert plan.record.owner_kind == "UNCLAIMED"
    assert plan.record.owner_id == "NONE"
    assert plan.record.lease is None
    assert plan.record.next_action.kind == "ACQUIRE"


def test_interactive_dispatch_ready_rejects_slot_spoof():
    with pytest.raises(
        executor.ProductionExecutorError,
        match="slot_id conflicts with request lane",
    ):
        ingress._build_dispatch_ready_ingress_request(
            _interactive_request(slot_id="worker.slot.3"),
            execution_mode="INTERACTIVE",
            repo="looaeedr/whd",
            token="unused",
        )



def test_scheduler_dispatch_ready_revalidates_live_owner_marker(monkeypatch):
    monkeypatch.setattr(
        ingress,
        "_fetch_issue_snapshot",
        lambda *args, **kwargs: {
            "issue_number": ISSUE,
            "state": "open",
            "user": {"login": "looaeedr"},
            "body": "WHD_SCHEDULER_DISPATCH_REQUEST_V1\nlane=A",
            "created_at": "2026-10-06T15:00:00Z",
        },
    )
    request = {
        "issue": ISSUE,
        "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "effect": {
            "authority_kind": "USER_EXPLICIT",
            "authority_ref": f"github-issue:{ISSUE}:WHD_SCHEDULER_DISPATCH_REQUEST_V1",
        },
        "startup_transition": {
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
            "issued_at": "2026-10-06T15:00:00Z",
        },
    }

    built = ingress._build_dispatch_ready_ingress_request(
        request,
        execution_mode="SCHEDULER_LANE",
        repo="looaeedr/whd",
        token="unused",
    )

    assert built.execution_intent == "SCHEDULER_LANE"
    assert built.authority_ref == f"github-issue:{ISSUE}:WHD_SCHEDULER_DISPATCH_REQUEST_V1"
    assert built.work_branch == f"scheduler/issue{ISSUE}-auto-dispatch"


def test_scheduler_dispatch_ready_rejects_non_owner_marker(monkeypatch):
    monkeypatch.setattr(
        ingress,
        "_fetch_issue_snapshot",
        lambda *args, **kwargs: {
            "issue_number": ISSUE,
            "state": "open",
            "user": {"login": "someone-else"},
            "body": "WHD_SCHEDULER_DISPATCH_REQUEST_V1\nlane=A",
        },
    )
    request = {
        "issue": ISSUE,
        "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "effect": {
            "authority_kind": "USER_EXPLICIT",
            "authority_ref": f"github-issue:{ISSUE}:WHD_SCHEDULER_DISPATCH_REQUEST_V1",
        },
        "startup_transition": {
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
            "issued_at": "2026-10-06T15:00:00Z",
        },
    }

    with pytest.raises(
        executor.ProductionExecutorError,
        match="scheduler authority rejected",
    ):
        ingress._build_dispatch_ready_ingress_request(
            request,
            execution_mode="SCHEDULER_LANE",
            repo="looaeedr/whd",
            token="unused",
        )

def test_dispatch_ready_writer_is_create_only_and_rebuilds_state(monkeypatch):
    ingress_request = _dispatch_request()
    planned = plan_dispatch_ingress(ingress_request).record
    reads = iter([
        (COORD, "tree-before", {}),
        ("d" * 40, "tree-after", {ISSUE: planned}),
    ])
    written = {}

    monkeypatch.setattr(executor, "_load_state", lambda *args, **kwargs: next(reads))

    def fake_write_state(repo, token, coord_branch, *, parent_sha, base_tree_sha, records, issue):
        written["parent_sha"] = parent_sha
        written["base_tree_sha"] = base_tree_sha
        written["records"] = records
        written["issue"] = issue
        return "d" * 40, "e" * 40

    monkeypatch.setattr(executor, "_write_state", fake_write_state)

    result = executor.dispatch_ready_missing_record(
        repo="looaeedr/whd",
        token="unused",
        coord_branch="coord/execution-v2",
        issue=ISSUE,
        expected_coord_head=COORD,
        ingress_request=ingress_request,
    )

    assert written["parent_sha"] == COORD
    assert written["issue"] == ISSUE
    assert written["records"][ISSUE].state == "READY"
    assert result["result"] == "APPLIED"
    assert result["kind"] == "DISPATCH_READY"
    assert result["post_generation"] == 1
    assert result["post_state"] == "READY"
    assert result["post_next_action"] == "ACQUIRE"
    assert result["lease_invocation_identity"] is None


def test_dispatch_ready_writer_rejects_existing_same_issue(monkeypatch):
    ingress_request = _dispatch_request()
    existing = plan_dispatch_ingress(ingress_request).record
    monkeypatch.setattr(
        executor,
        "_load_state",
        lambda *args, **kwargs: (COORD, "tree", {ISSUE: existing}),
    )

    with pytest.raises(
        executor.ControlTransactionConflict,
        match="requires missing ExecutionRecord",
    ):
        executor.dispatch_ready_missing_record(
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
            issue=ISSUE,
            expected_coord_head=COORD,
            ingress_request=ingress_request,
        )
