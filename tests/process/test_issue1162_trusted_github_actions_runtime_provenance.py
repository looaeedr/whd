from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

import tools.control_transaction_request_ingress as ingress
from tools.execution_entry_contract import (
    build_phase6_preflight_evidence,
    build_startup_evidence,
    build_startup_transition,
    validate_phase6_preflight_evidence,
    validate_startup_evidence,
    validate_startup_transition,
)
from tools.work_root_gate import READ_MODE_WORKSPACE, build_work_root_gate_evidence


ROOT = Path(__file__).resolve().parents[2]
SENTINEL = ingress.TRUSTED_GITHUB_ACTIONS_INVOCATION_SENTINEL
REQUEST_BRANCH = "coord/transaction-requests-work0"
LANE = "chatgpt.flowv2.work0"
REPO = "looaeedr/whd"
HEAD = "a" * 40


def _root_entries():
    return [
        ".git",
        ".agents",
        ".github",
        "AGENTS.md",
        "tools",
        "tests",
        "ae_engine",
        "gui_modules",
        ".unpushed",
    ]


def _fresh_request(*, invocation_identity=SENTINEL):
    now = datetime.now(timezone.utc)
    gate_payload = __import__("json").loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text(encoding="utf-8")
    )
    gate = build_work_root_gate_evidence(
        gate_payload=gate_payload,
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=_root_entries(), workspace_root="/workspace/whd",
    )
    startup = build_startup_evidence(
        purpose="Issue #1162 trusted GitHub Actions runtime provenance",
        invocation_identity=invocation_identity,
        execution_mode="INTERACTIVE",
        work_root_gate_evidence=gate,
        issued_at=now,
    )
    preflight = build_phase6_preflight_evidence(
        issue=1112,
        invocation_identity=invocation_identity,
        branch="cleanup/2d-3d-sync",
        head_sha=HEAD,
        required_skills=["flow-v2-execution"],
        completed_skills=["flow-v2-execution"],
        required_references=[".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"],
        completed_references=[".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"],
        observed_at=now,
    )
    transition = build_startup_transition(
        startup_evidence=startup,
        preflight_evidence=preflight,
        invocation_identity=invocation_identity,
        issue=1112,
        execution_mode="INTERACTIVE",
        now=now,
    )
    return {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "issue1162-runtime-provenance",
        "issue": 1112,
        "kind": "ACQUIRE",
        "lane_id": LANE,
        "invocation_identity": invocation_identity,
        "expected_coord_head": "b" * 40,
        "expected_generation": 3,
        "effect": {},
        "startup_evidence": startup,
        "preflight_evidence": preflight,
        "startup_transition": transition,
    }


def _trusted_env(*, branch=REQUEST_BRANCH, workflow_path=None):
    path = workflow_path or ingress.TRUSTED_GITHUB_ACTIONS_WORKFLOW_PATH
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_RUN_ID": "37150000001",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_WORKFLOW_REF": f"{REPO}/{path}@refs/heads/cleanup/2d-3d-sync",
        "GITHUB_REF_NAME": branch,
    }


def _enable_runtime_provenance(request):
    request = deepcopy(request)
    request["runtime_provenance"] = {
        "schema": ingress.TRUSTED_GITHUB_ACTIONS_PROVENANCE_SCHEMA,
        "mode": ingress.TRUSTED_GITHUB_ACTIONS_PROVENANCE_MODE,
    }
    return request


def test_issue1162_trusted_runtime_rebinds_fresh_admission_to_exact_gha_identity():
    request = _enable_runtime_provenance(_fresh_request())
    original_effect = deepcopy(request["effect"])

    rebound = ingress._bind_trusted_github_actions_runtime_provenance(
        request,
        repo=REPO,
        request_branch=REQUEST_BRANCH,
        runtime_env=_trusted_env(),
    )

    minted = rebound["invocation_identity"]
    assert minted.startswith(f"gha:{REPO}:run:37150000001:attempt:2:")
    assert f"workflow:{_trusted_env()['GITHUB_WORKFLOW_REF']}" in minted
    assert minted.endswith(f":ref:{REQUEST_BRANCH}")
    assert rebound["effect"] == original_effect
    assert request["invocation_identity"] == SENTINEL
    for key in ("startup_evidence", "preflight_evidence", "startup_transition"):
        assert rebound[key]["invocation_identity"] == minted
        assert request[key]["invocation_identity"] == SENTINEL

    validate_startup_evidence(
        rebound["startup_evidence"],
        invocation_identity=minted,
        execution_mode="INTERACTIVE",
        repository=REPO,
    )
    validate_phase6_preflight_evidence(
        rebound["preflight_evidence"],
        issue=1112,
        invocation_identity=minted,
    )
    validate_startup_transition(
        rebound["startup_transition"],
        invocation_identity=minted,
        issue=1112,
        execution_mode="INTERACTIVE",
        repository=REPO,
    )


def test_issue1162_ordinary_explicit_identity_is_unchanged():
    request = _fresh_request(invocation_identity="interactive:work0:issue1112:explicit")
    rebound = ingress._bind_trusted_github_actions_runtime_provenance(
        request,
        repo=REPO,
        request_branch=None,
        runtime_env=None,
    )
    assert rebound is request
    assert rebound["invocation_identity"] == "interactive:work0:issue1112:explicit"


def test_issue1162_sentinel_without_explicit_mode_is_rejected():
    with pytest.raises(ingress.ProductionExecutorError, match="requires explicit runtime_provenance"):
        ingress._bind_trusted_github_actions_runtime_provenance(
            _fresh_request(),
            repo=REPO,
            request_branch=REQUEST_BRANCH,
            runtime_env=_trusted_env(),
        )


def test_issue1162_caller_cannot_spoof_trusted_runtime_outside_github_actions():
    request = _enable_runtime_provenance(_fresh_request())
    env = _trusted_env()
    env["GITHUB_ACTIONS"] = "false"
    with pytest.raises(ingress.ProductionExecutorError, match="GITHUB_ACTIONS=true"):
        ingress._bind_trusted_github_actions_runtime_provenance(
            request,
            repo=REPO,
            request_branch=REQUEST_BRANCH,
            runtime_env=env,
        )


def test_issue1162_wrong_trusted_workflow_is_rejected():
    request = _enable_runtime_provenance(_fresh_request())
    with pytest.raises(ingress.ProductionExecutorError, match="workflow identity mismatch"):
        ingress._bind_trusted_github_actions_runtime_provenance(
            request,
            repo=REPO,
            request_branch=REQUEST_BRANCH,
            runtime_env=_trusted_env(workflow_path=".github/workflows/other.yml"),
        )


def test_issue1162_request_branch_and_lane_binding_remain_exact():
    request = _enable_runtime_provenance(_fresh_request())
    request["lane_id"] = "chatgpt.flowv2.work1"
    with pytest.raises(ingress.ProductionExecutorError, match="request lane mismatch"):
        ingress._validate_request_branch(request=request, request_branch=REQUEST_BRANCH)


def test_issue1162_runtime_ref_name_must_match_exact_request_branch():
    request = _enable_runtime_provenance(_fresh_request())
    with pytest.raises(ingress.ProductionExecutorError, match="request branch mismatch"):
        ingress._bind_trusted_github_actions_runtime_provenance(
            request,
            repo=REPO,
            request_branch=REQUEST_BRANCH,
            runtime_env=_trusted_env(branch="coord/transaction-requests-work1"),
        )


def test_issue1162_nested_identity_spoof_is_rejected_before_rebinding():
    request = _enable_runtime_provenance(_fresh_request())
    request["preflight_evidence"]["invocation_identity"] = "caller-spoof"
    with pytest.raises(ingress.ProductionExecutorError, match="preflight_evidence invocation"):
        ingress._bind_trusted_github_actions_runtime_provenance(
            request,
            repo=REPO,
            request_branch=REQUEST_BRANCH,
            runtime_env=_trusted_env(),
        )


def test_issue1162_execute_request_accepts_trusted_binding_before_state_read(monkeypatch):
    request = _enable_runtime_provenance(_fresh_request())

    def _state_read_reached(*args, **kwargs):
        raise RuntimeError("STATE_READ_REACHED")

    monkeypatch.setattr(ingress, "_load_state", _state_read_reached)
    with pytest.raises(RuntimeError, match="STATE_READ_REACHED"):
        ingress.execute_request(
            request=request,
            repo=REPO,
            token="unused",
            coord_branch="coord/execution-v2",
            trusted_runtime_env=_trusted_env(),
            request_branch=REQUEST_BRANCH,
        )


def test_issue1162_execute_request_rejects_sentinel_without_trusted_context(monkeypatch):
    request = _enable_runtime_provenance(_fresh_request())

    def _unexpected_state_read(*args, **kwargs):
        raise AssertionError("state must not be read when trusted runtime provenance is absent")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_state_read)
    with pytest.raises(ingress.ProductionExecutorError, match="GITHUB_ACTIONS=true"):
        ingress.execute_request(
            request=request,
            repo=REPO,
            token="unused",
            coord_branch="coord/execution-v2",
        )
