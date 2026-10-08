from datetime import datetime, timezone

import pytest

from tools.control_transaction_request_builder import (
    CONTROL_PLANE_ONLY_FRESH_KINDS,
    build_control_transaction_request,
)
from tools.execution_entry_contract import build_phase6_preflight_evidence


HEAD = "a" * 40
INVOCATION = "chatgpt.issue1378.dispatch.acquire.test"


def _control_plane_root() -> dict[str, object]:
    return {
        "schema": "WHD_WORK_ROOT_GATE_EVIDENCE_V2",
        "gate_schema": "WHD_WORK_ROOT_HARD_GATE_V2",
        "execution_mode": "INTERACTIVE",
        "scope": "CONTROL_PLANE_ONLY",
        "read_mode": "GITHUB_REPO_CONTRACT",
        "source": ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json",
        "provider": "github_repository_contract",
        "workspace_policy": "NOT_APPLICABLE_CONTROL_PLANE_ONLY",
        "workspace_root": "NOT_APPLICABLE_CONTROL_PLANE_ONLY",
        "production_branch": "cleanup/2d-3d-sync",
        "production_head_sha": HEAD,
        "drive_role": "MIRROR_BACKUP_ONLY",
        "drive_mirror_root": "/Google Drive/WHD/WHD_MIRROR/CURRENT",
        "root_entries": [
            ".git",
            ".agents",
            ".github",
            "AGENTS.md",
            "tools",
            "tests",
            "ae_engine",
            "gui_modules",
        ],
        "shared_zero_required": False,
        "repository_content_write_unlocked": False,
        "status": "GREEN",
    }


def _preflight(now: datetime) -> dict[str, object]:
    return build_phase6_preflight_evidence(
        issue=1378,
        invocation_identity=INVOCATION,
        branch="cleanup/2d-3d-sync",
        head_sha=HEAD,
        required_skills=("flow-v2-execution",),
        completed_skills=("flow-v2-execution",),
        required_references=(),
        completed_references=(),
        observed_at=now,
    )


def _build(kind: str):
    now = datetime.now(timezone.utc)
    return build_control_transaction_request(
        request_id=f"issue1378-{kind.lower()}",
        issue=1378,
        kind=kind,
        lane_id="chatgpt.flowv2.work1",
        invocation_identity=INVOCATION,
        expected_coord_head="b" * 40,
        expected_generation=1,
        effect={},
        purpose="/派工1378 GitHub-canonical control plane",
        work_root_gate_evidence=_control_plane_root(),
        preflight_evidence=_preflight(now),
        issued_at=now,
    )


def test_dispatch_control_plane_allowlist_contains_ready_and_acquire_only():
    assert CONTROL_PLANE_ONLY_FRESH_KINDS == frozenset({"DISPATCH_READY", "ACQUIRE", "RECONCILE", "HANDOFF", "RECOVER_POST_DELIVERY"})


def test_post_delivery_recovery_is_admitted_only_through_existing_trusted_ingress():
    request = _build("RECOVER_POST_DELIVERY")
    assert request["kind"] == "RECOVER_POST_DELIVERY"
    assert request["startup_evidence"]["work_root_gate"]["scope"] == "CONTROL_PLANE_ONLY"
    assert request["startup_transition"]["status"] == "READY_FOR_EXECUTION"
    # This request only admits the pre-write envelope; the trusted executor
    # still verifies merged PR closing keyword, required checks, ancestry,
    # missing same-Issue record and finalization before any DONE assertion.


def test_ready_issue_can_be_acquired_with_control_plane_only_github_admission():
    request = _build("ACQUIRE")
    assert request["kind"] == "ACQUIRE"
    assert request["startup_evidence"]["work_root_gate"]["scope"] == "CONTROL_PLANE_ONLY"
    assert request["startup_transition"]["status"] == "READY_FOR_EXECUTION"


def test_stale_ready_record_can_reconcile_with_control_plane_only_github_admission():
    request = _build("RECONCILE")
    assert request["kind"] == "RECONCILE"
    assert request["startup_evidence"]["work_root_gate"]["scope"] == "CONTROL_PLANE_ONLY"
    assert request["startup_transition"]["status"] == "READY_FOR_EXECUTION"


def test_routing_only_handoff_can_use_control_plane_only_github_admission():
    request = _build("HANDOFF")
    assert request["kind"] == "HANDOFF"
    assert request["startup_evidence"]["work_root_gate"]["scope"] == "CONTROL_PLANE_ONLY"
    assert request["startup_transition"]["status"] == "READY_FOR_EXECUTION"


def test_repository_content_mutation_cannot_borrow_dispatch_control_plane_scope():
    with pytest.raises(ValueError, match="control-plane-only admission is not allowed"):
        _build("START_BRANCH")
