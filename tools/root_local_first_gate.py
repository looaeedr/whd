"""Machine gate for WHD root-local-first repository content work and remote handoff classification."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping

from tools.execution_path_reservation import validate_path_reservation_evidence
from tools.shared_unpushed_integration import (
    CONFLICT_CHECKPOINT_SCHEMA,
    CONFLICT_STATE,
    validate_lane_evidence,
)

SCHEMA = "WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1"
EVIDENCE_SCHEMA = "WHD_ROOT_SHARED_UNPUSHED_GATE_EVIDENCE_V1"
WORKSPACE_ROOT_POLICY = "EXECUTOR_LOCAL_REPO_WORKSPACE"
CANONICAL_DRIVE_ROOT = "/Google Drive/WHD"
DEFAULT_WORK_PREFIX = "/Google Drive/WHD/.unpushed"
TEST_PROFILE_SCHEMA = "WHD_CHANGE_TEST_PROFILE_V1"
TEST_PROFILE_OWNER = "tools/change_test_profile.py"
TEST_EXECUTION_RECEIPT_SCHEMA = "WHD_TEST_EXECUTION_RECEIPT_V1"
WORKER_CENSUS_SCHEMA = "WHD_SHARED_ZERO_WORKER_CENSUS_V1"
REQUIRED_ORDER = (
    "WORKSPACE_SOURCE_CURRENT",
    "WORKSPACE_MUTATIONS_COMPLETE",
    "WORKSPACE_TESTS_GREEN",
    "DELIVERY_BRANCH_READY",
    "POST_PUSH_CI",
    "MERGE_READBACK_VERIFIED",
)
INTERACTIVE_MODES = {"INTERACTIVE", "CHAT", "DEFAULT"}
REMOTE_MODES = {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}
REMOTE_CONTENT_POLICY = "WORKSPACE_MIRROR_IMPLEMENTATION"
WORKSPACE_ROOT = WORKSPACE_ROOT_POLICY
PRODUCTION_BRANCH = "cleanup/2d-3d-sync"
WORKSPACE_BASELINE_ACTIONS = {"READ", "FETCH", "COMPARE", "BRANCH_READ", "REPO_METADATA_READ"}
READ_ONLY_GIT_ACTIONS = WORKSPACE_BASELINE_ACTIONS
WORKSPACE_DELIVERY_ACTIONS = WORKSPACE_BASELINE_ACTIONS | {"CREATE_BRANCH", "COMMIT", "PUSH", "PR_READ", "CREATE_PR", "CI", "WORKFLOW_READ", "READBACK", "MERGE"}
CONTENT_ROUTE_SCHEMA = "WHD_REPOSITORY_CONTENT_ROUTE_V1"
ROOT_PATH_RESOLUTION_SCHEMA = "WHD_ROOT_PATH_RESOLUTION_EVIDENCE_V1"
REMOTE_CONNECTION_AUTHORITY_SCHEMA = "WHD_REMOTE_CONNECTION_AUTHORITY_V1"
REMOTE_CONNECTION_TARGETS = {"GITHUB", "REMOTE_LOCAL"}
REMOTE_AUTHORITY_KINDS = {
    "OPEN_ISSUE_ONLY",
    "USER_EXPLICIT_REMOTE",
    "PUSH_DOCS",
    "PUSH_BODY",
    "WORKSPACE_DELIVERY",
    "SCHEDULER_GITHUB_ONLY",
}
ISSUE_ONLY_ACTIONS = {"CREATE_ISSUE", "ISSUE_READBACK"}
PUSH_GITHUB_ACTIONS = {
    "READ", "FETCH", "COMPARE", "REPO_METADATA_READ", "CODE_SEARCH",
    "BRANCH_READ", "CREATE_BRANCH", "COMMIT", "PUSH",
    "PR_READ", "CREATE_PR", "PR_COMMENT", "CI", "WORKFLOW_READ", "REMOTE_QA",
    "MERGE", "ISSUE_READ", "ISSUE_COMMENT", "ISSUE_CLOSE", "READBACK",
}
DELIVERY_AUTHORITY_KINDS = {"WORKSPACE_DELIVERY", "PUSH_DOCS", "PUSH_BODY", "USER_EXPLICIT_REMOTE"}
EXECUTION_MODE_PROVENANCE_SCHEMA = "WHD_EXECUTION_MODE_PROVENANCE_V1"
GIT_UNLOCK_RECEIPT_SCHEMA = "ROOT_LOCAL_FIRST_GIT_UNLOCK_RECEIPT_V1"
SCHEDULER_LANE_IDS = {
    "scheduler.6ab13fa557fc8191935c671214b865e2",
    "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
}

ENTRY_ROUTER_SCHEMA = "WHD_ENTRY_ROUTER_FIRST_HARD_GATE_V1"
ENTRY_ROUTER_EVIDENCE_SCHEMA = "WHD_ENTRY_ROUTER_EVIDENCE_V1"
ENTRY_ROUTER_READY = "ENTRY_ROUTER_READY"
ENTRY_ROUTER_FRESH_READS = (
    ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
    ".agents/skills/engineering/root-local-first/SKILL.md",
)
ENTRY_ROUTER_BOOTSTRAP_ACTIONS = frozenset({
    "READ_CANONICAL_ENTRY_CONTRACT",
    "READ_ROOT_LOCAL_FIRST_SKILL",
})
ENTRY_ROUTER_FORBIDDEN_BEFORE_READY = frozenset({
    "GENERAL_FILE_DISCOVERY",
    "GENERIC_DRIVE_SEARCH",
    "REMOTE_DESKTOP",
    "LOCAL_MACHINE_SEARCH",
    "GITHUB_CONTENT_DISCOVERY",
    "GITHUB_MUTATION",
    "BRANCH_CREATE",
    "CLAIM",
    "FLOW_V2_DISCOVERY",
})

ORCHESTRATION_FAST_PATH_SCHEMA = "WHD_INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1"
OUTER_VISIBLE_PIPELINE = frozenset({
    "FRESH_READ",
    "ROOT_MUTATE",
    "TARGETED_TEST",
    "EXACT_DIFF",
    "POST_PUSH_CI",
    "MERGE_FINALIZE",
})
MACHINE_INTERNAL_CONTROL_ACTIONS = frozenset({
    "LEASE",
    "LEASE_RENEW",
    "ACQUIRE",
    "RESERVE_PATHS",
    "RELEASE_PATHS",
    "CAS_RETRY",
    "SESSION_REUSE",
    "RECONCILE",
    "START_BRANCH",
    "APPLY_COMMIT",
    "START_QA",
    "POLL_QA",
    "ACCEPT_QA",
    "CONSUME_QA",
    "FAIL_QA",
    "QA_CONSUME",
    "QA_FAILURE_CONSUME",
    "MERGE",
    "SYNC_TARGET",
    "HANDOFF",
    "YIELD",
    "FINALIZE",
    "FINALIZE_DRAIN",
})
BACKGROUND_ONLY_EVENTS = frozenset({
    "STALE_EXECUTION_RECORD",
    "EXPIRED_LEASE",
    "RESERVATION_MISMATCH",
    "GOVERNANCE_DRIFT",
    "TEST_RED",
    "STATUS_QUERY",
    "PROGRESS_QUERY",
})
REAL_ESCALATION_TRIGGERS = frozenset({
    "USER_EXPLICIT_TASK_CHANGE",
    "PATH_CONFLICT",
    "SAME_ISSUE_OTHER_WRITER",
    "SUBSTANTIVE_TARGET_OVERLAP",
    "MACHINE_FAIL_CLOSED",
    "USER_INPUT_REQUIRED",
})


def _event_token(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(value or "").strip().upper()).strip("_")


def build_entry_router_evidence(
    *, fresh_reads: Iterable[str], workspace_root: str | None = None, canonical_root: str | None = None
) -> dict[str, object]:
    """Bind an interactive WHD content invocation to its executor-local repository workspace."""
    resolved_root = str(workspace_root or canonical_root or "").strip()
    if not resolved_root:
        raise ValueError("ENTRY_ROUTER_FIRST_REQUIRED: executor workspace_root missing")
    reads = tuple(str(item).strip() for item in fresh_reads if str(item).strip())
    if reads != ENTRY_ROUTER_FRESH_READS:
        raise ValueError(
            "ENTRY_ROUTER_FIRST_REQUIRED: fresh-read canonical contract then root-local-first Skill"
        )
    return {
        "schema": ENTRY_ROUTER_EVIDENCE_SCHEMA,
        "gate_schema": ENTRY_ROUTER_SCHEMA,
        "state": ENTRY_ROUTER_READY,
        "workspace_root": resolved_root,
        "workspace_policy": WORKSPACE_ROOT_POLICY,
        "fresh_reads": list(reads),
        "fresh_each_invocation": True,
        "chat_memory_used_as_evidence": False,
    }


def validate_entry_router_evidence(evidence: object) -> dict[str, object]:
    item = _mapping(evidence, "entry router evidence")
    if item.get("schema") != ENTRY_ROUTER_EVIDENCE_SCHEMA:
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: invalid entry router evidence schema")
    if item.get("gate_schema") != ENTRY_ROUTER_SCHEMA:
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: invalid gate schema")
    if item.get("state") != ENTRY_ROUTER_READY:
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: entry router is not READY")
    if item.get("workspace_policy") != WORKSPACE_ROOT_POLICY:
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: workspace policy mismatch")
    if not str(item.get("workspace_root") or "").strip():
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: executor workspace_root missing")
    if tuple(item.get("fresh_reads") or ()) != ENTRY_ROUTER_FRESH_READS:
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: fresh-read order mismatch")
    if item.get("fresh_each_invocation") is not True:
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: evidence must be invocation-fresh")
    if item.get("chat_memory_used_as_evidence") is not False:
        raise ValueError("ENTRY_ROUTER_FIRST_HARD_GATE: chat memory is not entry evidence")
    return {str(k): v for k, v in item.items()}


def assert_entry_router_action_allowed(evidence: object | None, *, action: str) -> dict[str, object] | None:
    token = _event_token(action)
    if token in ENTRY_ROUTER_BOOTSTRAP_ACTIONS and evidence is None:
        return None
    if evidence is None:
        raise ValueError(
            f"ENTRY_ROUTER_FIRST_HARD_GATE action={token}: "
            "FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY"
        )
    return validate_entry_router_evidence(evidence)


def build_root_path_resolution_evidence(
    *, workspace_root: str, repo_relative_path: str, resolved_absolute_path: str,
    resolution_method: str = "WORKSPACE_REPO_RELATIVE_PATH"
) -> dict[str, object]:
    relative = str(repo_relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not relative or relative == "." or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError("WORKSPACE_PATH_UNRESOLVED_FAIL_CLOSED: invalid repo-relative path")
    root = str(workspace_root or "").strip().replace("\\", "/").rstrip("/")
    if not root:
        raise ValueError("WORKSPACE_PATH_UNRESOLVED_FAIL_CLOSED: workspace_root missing")
    expected = f"{root}/{relative}"
    if str(resolved_absolute_path or "").strip().replace("\\", "/") != expected:
        raise ValueError("WORKSPACE_PATH_UNRESOLVED_FAIL_CLOSED: workspace path mismatch")
    if str(resolution_method or "").strip().upper() != "WORKSPACE_REPO_RELATIVE_PATH":
        raise ValueError("WORKSPACE_PATH_UNRESOLVED_FAIL_CLOSED: non-workspace resolution method")
    return {
        "schema": ROOT_PATH_RESOLUTION_SCHEMA,
        "workspace_root": root,
        "workspace_policy": WORKSPACE_ROOT_POLICY,
        "repo_relative_path": relative,
        "resolved_absolute_path": expected,
        "resolution_method": "WORKSPACE_REPO_RELATIVE_PATH",
        "global_search_role": "CANDIDATE_ONLY",
        "remote_fallback_used": False,
    }


def validate_root_path_resolution_evidence(evidence: object) -> dict[str, object]:
    item = _mapping(evidence, "root path resolution evidence")
    if item.get("schema") != ROOT_PATH_RESOLUTION_SCHEMA:
        raise ValueError("WORKSPACE_PATH_UNRESOLVED_FAIL_CLOSED: invalid evidence schema")
    return build_root_path_resolution_evidence(
        workspace_root=str(item.get("workspace_root") or ""),
        repo_relative_path=str(item.get("repo_relative_path") or ""),
        resolved_absolute_path=str(item.get("resolved_absolute_path") or ""),
        resolution_method=str(item.get("resolution_method") or ""),
    )

def select_repository_content_route(*, shared_zero_drift_present: bool, workspace_root: str = WORKSPACE_ROOT_POLICY) -> dict[str, object]:
    """Choose the ordinary workspace path unless fresh shared-zero drift requires reconcile."""
    if shared_zero_drift_present:
        return {
            "schema": CONTENT_ROUTE_SCHEMA,
            "route": "SHARED_ZERO_FALLBACK",
            "workspace_root": str(workspace_root),
            "production_branch": PRODUCTION_BRANCH,
            "workspace_canonical_sync_required": True,
            "shared_zero_required": True,
        }
    return {
        "schema": CONTENT_ROUTE_SCHEMA,
        "route": "WORKSPACE_DEFAULT",
        "workspace_root": str(workspace_root),
        "production_branch": PRODUCTION_BRANCH,
        "workspace_canonical_sync_required": False,
        "shared_zero_required": False,
    }


def build_remote_connection_authority(
    *,
    kind: str,
    target: str,
    allowed_actions: Iterable[str] = (),
    user_explicit: bool = False,
    lane: str | None = None,
    user_authored_entry_contract: bool = False,
) -> dict[str, object]:
    authority_kind = _event_token(kind)
    remote_target = _event_token(target)
    if authority_kind not in REMOTE_AUTHORITY_KINDS:
        raise ValueError("REMOTE_CONNECTION_DENIED: unknown authority kind")
    if remote_target not in REMOTE_CONNECTION_TARGETS:
        raise ValueError("REMOTE_CONNECTION_DENIED: unknown remote target")
    actions = tuple(dict.fromkeys(_event_token(x) for x in allowed_actions if _event_token(x)))
    normalized_lane = str(lane or "").strip().lower() or None

    if authority_kind == "OPEN_ISSUE_ONLY":
        if remote_target != "GITHUB" or user_explicit is not True:
            raise ValueError("REMOTE_CONNECTION_DENIED: issue authority requires explicit GitHub request")
        actions = tuple(sorted(ISSUE_ONLY_ACTIONS))
    elif authority_kind in {"PUSH_DOCS", "PUSH_BODY"}:
        expected_lane = "docs" if authority_kind == "PUSH_DOCS" else "body"
        if remote_target != "GITHUB" or user_explicit is not True or normalized_lane != expected_lane:
            raise ValueError("REMOTE_CONNECTION_DENIED: /推推 authority lane/target mismatch")
        actions = tuple(sorted(PUSH_GITHUB_ACTIONS))
    elif authority_kind == "WORKSPACE_DELIVERY":
        if remote_target != "GITHUB" or user_explicit is not True:
            raise ValueError("REMOTE_CONNECTION_DENIED: workspace delivery requires explicit repository-content task")
        actions = tuple(sorted(WORKSPACE_DELIVERY_ACTIONS))
    elif authority_kind == "USER_EXPLICIT_REMOTE":
        if user_explicit is not True or not actions:
            raise ValueError("REMOTE_CONNECTION_DENIED: explicit remote authority requires exact actions")
    elif authority_kind == "SCHEDULER_GITHUB_ONLY":
        if remote_target != "GITHUB" or user_authored_entry_contract is not True or not actions:
            raise ValueError("REMOTE_CONNECTION_DENIED: scheduler remote authority requires user-authored entry contract")

    return {
        "schema": REMOTE_CONNECTION_AUTHORITY_SCHEMA,
        "kind": authority_kind,
        "target": remote_target,
        "allowed_actions": list(actions),
        "user_explicit": bool(user_explicit),
        "lane": normalized_lane,
        "user_authored_entry_contract": bool(user_authored_entry_contract),
    }


def validate_remote_connection_authority(
    authority: object, *, target: str, action: str
) -> dict[str, object]:
    item = _mapping(authority, "remote connection authority")
    if item.get("schema") != REMOTE_CONNECTION_AUTHORITY_SCHEMA:
        raise ValueError("REMOTE_CONNECTION_DENIED: invalid authority schema")
    rebuilt = build_remote_connection_authority(
        kind=str(item.get("kind") or ""),
        target=str(item.get("target") or ""),
        allowed_actions=item.get("allowed_actions") or (),
        user_explicit=item.get("user_explicit") is True,
        lane=str(item.get("lane") or "") or None,
        user_authored_entry_contract=item.get("user_authored_entry_contract") is True,
    )
    expected_target = _event_token(target)
    requested_action = _event_token(action)
    if rebuilt["target"] != expected_target:
        raise ValueError("REMOTE_CONNECTION_DENIED: target mismatch")
    if requested_action not in set(rebuilt["allowed_actions"]):
        raise ValueError(f"REMOTE_CONNECTION_DENIED: action={requested_action}")
    return rebuilt


def assert_remote_connection_allowed(
    authority: object | None, *, target: str, action: str
) -> dict[str, object]:
    remote_target = _event_token(target)
    requested_action = _event_token(action)
    if authority is None and remote_target == "GITHUB" and requested_action in WORKSPACE_BASELINE_ACTIONS:
        return {
            "schema": REMOTE_CONNECTION_AUTHORITY_SCHEMA,
            "kind": "WORKSPACE_BASELINE_READ",
            "target": "GITHUB",
            "allowed_actions": sorted(WORKSPACE_BASELINE_ACTIONS),
            "user_explicit": False,
            "lane": None,
            "user_authored_entry_contract": False,
        }
    if authority is None:
        raise ValueError("REMOTE_CONNECTION_DENIED: explicit authority required")
    return validate_remote_connection_authority(authority, target=target, action=action)


def classify_outer_orchestration_event(
    event: object, *, escalation_trigger: object | None = None
) -> dict[str, object]:
    """Classify one interactive outer-layer event without promoting control-plane plumbing.

    Low-level Flow v2 transactions and ordinary control-plane anomalies remain
    session-internal.  A real escalation may be reported to the user, but it does
    not make a low-level transaction kind a valid outer primary action.
    """

    token = _event_token(event)
    if not token:
        raise ValueError("outer orchestration event must be nonblank")
    trigger = _event_token(escalation_trigger) if escalation_trigger is not None else ""
    if trigger and trigger not in REAL_ESCALATION_TRIGGERS:
        raise ValueError(f"PRIMARY_TASK_SWITCH_FORBIDDEN: {trigger}")
    if token in MACHINE_INTERNAL_CONTROL_ACTIONS or token in BACKGROUND_ONLY_EVENTS:
        return {
            "event": token,
            "disposition": "BACKGROUND_CONTINUE_PRIMARY_TASK",
            "outer_visible": False,
            "primary_task_switch_allowed": False,
        }
    if token in OUTER_VISIBLE_PIPELINE:
        return {
            "event": token,
            "disposition": "OUTER_VISIBLE_PHASE",
            "outer_visible": True,
            "primary_task_switch_allowed": False,
        }
    if token == "REPORT_BLOCKER":
        if not trigger:
            raise ValueError("REPORT_BLOCKER requires a real escalation trigger")
        return {
            "event": token,
            "disposition": "REAL_ESCALATION_BLOCKER",
            "outer_visible": True,
            "primary_task_switch_allowed": trigger == "USER_EXPLICIT_TASK_CHANGE",
            "escalation_trigger": trigger,
        }
    raise ValueError(f"unknown outer orchestration event: {token}")


def is_background_only_outer_event(event: object) -> bool:
    token = _event_token(event)
    return token in MACHINE_INTERNAL_CONTROL_ACTIONS or token in BACKGROUND_ONLY_EVENTS


def assert_outer_primary_action(
    event: object, *, escalation_trigger: object | None = None
) -> dict[str, object]:
    classified = classify_outer_orchestration_event(
        event, escalation_trigger=escalation_trigger
    )
    if classified["disposition"] == "BACKGROUND_CONTINUE_PRIMARY_TASK":
        raise ValueError(
            "GOVERNANCE_MUST_REMAIN_MACHINE_INTERNAL: "
            f"{classified['event']} cannot become the interactive outer primary action"
        )
    return classified


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sha(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError(f"{label} must be a 40-character hex SHA")
    return text




def validate_test_execution_receipt(
    receipt: object,
    *,
    expected_source_sha: str,
    expected_issue: int,
    expected_generation: int,
    expected_commands: Iterable[str],
) -> dict[str, object]:
    item = _mapping(receipt, "test execution receipt")
    if item.get("schema") != TEST_EXECUTION_RECEIPT_SCHEMA:
        raise ValueError("unexpected WHD_TEST_EXECUTION_RECEIPT_V1 schema")
    if str(item.get("status") or "").strip().upper() != "GREEN":
        raise ValueError("WHD_TEST_EXECUTION_RECEIPT_V1 status must be GREEN")
    if _sha(item.get("source_sha"), "test receipt source_sha") != _sha(expected_source_sha, "expected source_sha"):
        raise ValueError("test receipt source_sha mismatch")
    if isinstance(item.get("issue"), bool) or int(item.get("issue") or 0) != int(expected_issue):
        raise ValueError("test receipt issue mismatch")
    if isinstance(item.get("generation"), bool):
        raise ValueError("test receipt generation must be positive historical provenance")
    receipt_generation = int(item.get("generation") or 0)
    if receipt_generation <= 0:
        raise ValueError("test receipt generation must be positive historical provenance")
    if receipt_generation > int(expected_generation):
        raise ValueError("test receipt generation cannot be from the future")
    commands = item.get("exact_commands")
    if not isinstance(commands, list) or tuple(str(x) for x in commands) != tuple(str(x) for x in expected_commands):
        raise ValueError("test receipt exact_commands mismatch")
    digest = str(item.get("manifest_digest") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("test receipt manifest_digest must be SHA256")
    return {str(k): v for k, v in item.items()}

def validate_execution_mode_provenance(*, execution_mode: str, provenance: object) -> dict[str, object]:
    """Prove that a remote/control-plane exception comes from a trusted runtime identity.

    A caller-controlled execution_mode string is never sufficient to bypass the
    interactive root-local-first gate.  Scheduler mode is bound to the canonical
    Flow v2 durable lane IDs; other remote modes require an explicit trusted
    runtime source marker.
    """
    mode = str(execution_mode or "").strip().upper()
    item = _mapping(provenance, "execution mode provenance")
    if item.get("schema") != EXECUTION_MODE_PROVENANCE_SCHEMA:
        raise ValueError("unexpected execution mode provenance schema")
    if str(item.get("execution_mode") or "").strip().upper() != mode:
        raise ValueError("execution mode provenance mismatch")
    source = str(item.get("source") or "").strip()
    if mode == "SCHEDULER_LANE":
        lane_id = str(item.get("lane_id") or "").strip()
        if source != "FLOW_V2_LANE_ID" or lane_id not in SCHEDULER_LANE_IDS:
            raise ValueError("SCHEDULER_LANE requires canonical Flow v2 lane provenance")
    elif mode in {"GITHUB_ONLY", "REMOTE_ACTION"}:
        if source != "TRUSTED_REMOTE_RUNTIME":
            raise ValueError(f"{mode} requires trusted remote runtime provenance")
        if not str(item.get("invocation_identity") or "").strip():
            raise ValueError(f"{mode} provenance requires invocation_identity")
    else:
        raise ValueError(f"execution mode provenance is not valid for {mode}")
    return {str(k): v for k, v in item.items()}


def build_git_unlock_receipt(evidence: object) -> dict[str, object]:
    """Create the exact receipt required by interactive START_BRANCH/APPLY_COMMIT ingress."""
    item = _mapping(evidence, "root-local-first evidence")
    assert_git_content_write_allowed(item, action="COMMIT")
    if str(item.get("execution_mode") or "").strip().upper() not in INTERACTIVE_MODES:
        raise ValueError("Git unlock receipt is only valid for interactive root-local-first work")
    reservation = validate_path_reservation_evidence(item.get("path_reservation"))
    return {
        "schema": GIT_UNLOCK_RECEIPT_SCHEMA,
        "execution_mode": "INTERACTIVE",
        "source_sha": str(reservation["base_sha"]),
        "diff_digest": str(item["diff_digest"]),
        "issue": int(reservation["issue"]),
        "generation": int(reservation["generation"]),
        "target_branch": str(reservation["target_branch"]),
        "write_paths": list(reservation["write_paths"]),
        "delete_paths": list(reservation["delete_paths"]),
        "record_fingerprint": str(reservation["record_fingerprint"]),
        "git_write_unlocked": True,
        "write_mode": "EXACT_TESTED_DIFF_ONLY",
    }


def validate_git_unlock_receipt(receipt: object) -> dict[str, object]:
    item = _mapping(receipt, "root-local-first Git write receipt")
    if item.get("schema") != GIT_UNLOCK_RECEIPT_SCHEMA:
        raise ValueError("unexpected root-local-first Git write receipt schema")
    if str(item.get("execution_mode") or "").strip().upper() != "INTERACTIVE":
        raise ValueError("root-local-first Git write receipt must be INTERACTIVE")
    _sha(item.get("source_sha"), "receipt source_sha")
    digest = str(item.get("diff_digest") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("receipt diff_digest must be SHA256")
    if item.get("git_write_unlocked") is not True:
        raise ValueError("receipt does not prove GIT_WRITE_UNLOCKED")
    if item.get("write_mode") != "EXACT_TESTED_DIFF_ONLY":
        raise ValueError("receipt write_mode must be EXACT_TESTED_DIFF_ONLY")
    if isinstance(item.get("issue"), bool) or int(item.get("issue") or 0) <= 0:
        raise ValueError("receipt issue must be positive")
    if isinstance(item.get("generation"), bool) or int(item.get("generation") or 0) <= 0:
        raise ValueError("receipt generation must be positive")
    if not str(item.get("target_branch") or "").strip():
        raise ValueError("receipt target_branch must be nonblank")
    write_paths = item.get("write_paths")
    delete_paths = item.get("delete_paths")
    if not isinstance(write_paths, list) or not isinstance(delete_paths, list):
        raise ValueError("receipt paths must be arrays")
    fingerprint = str(item.get("record_fingerprint") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("receipt record_fingerprint must be SHA256")
    return {str(k): v for k, v in item.items()}


def validate_contract(payload: object) -> dict[str, object]:
    contract = _mapping(payload, "root-local-first contract")
    if contract.get("schema") != SCHEMA:
        raise ValueError("unexpected root-local-first schema")
    if contract.get("status") != "CURRENT":
        raise ValueError("root-local-first contract is not CURRENT")
    root = _mapping(contract.get("canonical_root"), "canonical_root")
    if root.get("provider") != "executor_local_workspace" or root.get("path_policy") != WORKSPACE_ROOT_POLICY:
        raise ValueError("workspace root identity mismatch")
    if root.get("production_branch") != PRODUCTION_BRANCH or root.get("authority") is not False:
        raise ValueError("workspace root production identity mismatch")
    if root.get("canonical_drive_overlay") != CANONICAL_DRIVE_ROOT:
        raise ValueError("canonical Drive overlay mismatch")
    if tuple(contract.get("required_order") or ()) != REQUIRED_ORDER:
        raise ValueError("root-local-first required order mismatch")
    if contract.get("test_profile_schema") != TEST_PROFILE_SCHEMA:
        raise ValueError("test-profile schema mismatch")
    if contract.get("test_profile_owner") != TEST_PROFILE_OWNER:
        raise ValueError("test-profile owner mismatch")
    if set(contract.get("git_before_unlock") or ()) != WORKSPACE_BASELINE_ACTIONS:
        raise ValueError("workspace baseline Git read policy mismatch")
    if set(contract.get("git_after_remote_authority_before_unlock") or ()) != WORKSPACE_BASELINE_ACTIONS:
        raise ValueError("post-authority workspace Git read policy mismatch")
    root_path_gate = _mapping(contract.get("root_path_resolution_hard_gate"), "root_path_resolution_hard_gate")
    if root_path_gate.get("schema") != "WHD_ROOT_PATH_RESOLUTION_HARD_GATE_V1":
        raise ValueError("root path resolution hard gate schema mismatch")
    if root_path_gate.get("default_workspace_root_policy") != WORKSPACE_ROOT_POLICY:
        raise ValueError("workspace path policy mismatch")
    if root_path_gate.get("resolution_method") != "WORKSPACE_REPO_RELATIVE_PATH":
        raise ValueError("workspace path resolution method mismatch")
    if root_path_gate.get("shared_zero_fallback_root") != CANONICAL_DRIVE_ROOT:
        raise ValueError("shared-zero fallback root mismatch")
    remote_gate = _mapping(contract.get("remote_connection_hard_gate"), "remote_connection_hard_gate")
    if remote_gate.get("schema") != REMOTE_CONNECTION_AUTHORITY_SCHEMA:
        raise ValueError("remote connection hard gate schema mismatch")
    if remote_gate.get("default") != "ALLOW_WORKSPACE_BASELINE_READ_ONLY":
        raise ValueError("remote connection default must allow only workspace baseline reads")
    if remote_gate.get("pre_delivery_git_read_allowed_without_authority") is not True:
        raise ValueError("workspace baseline Git reads must be allowed without extra authority")
    if set(remote_gate.get("workspace_baseline_actions") or ()) != WORKSPACE_BASELINE_ACTIONS:
        raise ValueError("workspace baseline Git action set mismatch")
    if remote_gate.get("remote_local_fallback_forbidden") is not True:
        raise ValueError("remote local fallback must be forbidden")
    if remote_gate.get("covers_all_network_surfaces") is not True:
        raise ValueError("remote authority gate must cover all network surfaces")
    if remote_gate.get("authority_non_propagating") is not True:
        raise ValueError("remote authority must not propagate through Skill/Flow-v2 bridges")
    if remote_gate.get("skill_invocation_is_not_authority") is not True:
        raise ValueError("Skill invocation must not imply remote authority")
    fileset = _mapping(contract.get("delivery_fileset_lock"), "delivery_fileset_lock")
    if fileset.get("schema") != "WHD_DELIVERY_FILESET_LOCK_V1":
        raise ValueError("delivery fileset lock schema mismatch")
    if fileset.get("push_scope") != "EXACT_LOCK_EQUALITY":
        raise ValueError("delivery fileset push scope mismatch")
    if fileset.get("merge_precheck") != "FRESH_TARGET_HEAD_AND_LOCKED_BLOB_RECHECK":
        raise ValueError("delivery fileset merge precheck mismatch")
    cleanup = _mapping(contract.get("post_delivery_cleanup"), "post_delivery_cleanup")
    if cleanup.get("requires") != "MERGE_READBACK_VERIFIED":
        raise ValueError("post-delivery cleanup requires merge readback")
    if cleanup.get("clear_policy") != "ONLY_LOCKED_PATHS_WITH_EXACT_READBACK_HASH":
        raise ValueError("post-delivery cleanup clear policy mismatch")
    if cleanup.get("repository_file_delete_forbidden") is not True:
        raise ValueError("post-delivery cleanup must not delete repository files")
    if contract.get("git_write_mode") != "EXACT_TESTED_DIFF_ONLY":
        raise ValueError("Git write mode must be EXACT_TESTED_DIFF_ONLY")
    if contract.get("target_drift_action") != "REFRESH_WORKSPACE_BASELINE_RETEST_BEFORE_DELIVERY":
        raise ValueError("target drift action mismatch")
    default_flow = _mapping(contract.get("default_repository_content_flow"), "default_repository_content_flow")
    if default_flow.get("schema") != "WHD_WORKSPACE_FIRST_CONTENT_FLOW_V1" or default_flow.get("status") != "CURRENT":
        raise ValueError("workspace-first default flow schema mismatch")
    if default_flow.get("workspace_root") != WORKSPACE_ROOT or default_flow.get("production_branch") != PRODUCTION_BRANCH:
        raise ValueError("workspace-first default identity mismatch")
    if any(default_flow.get(key) is not False for key in (
        "startup_requires_drive", "startup_requires_shared_zero", "startup_requires_workspace_canonical_sync"
    )):
        raise ValueError("ordinary workspace startup must not require Drive/shared-zero sync")
    if default_flow.get("shared_zero_fallback_trigger") != "FRESH_SHARED_ZERO_DRIFT_ON_TOUCHED_PATHS":
        raise ValueError("shared-zero fallback trigger mismatch")
    if default_flow.get("delivery") != "TESTED_DELIVERY_BRANCH_PR" or default_flow.get("direct_production_push_forbidden") is not True:
        raise ValueError("workspace delivery policy mismatch")
    entry_router = _mapping(contract.get("entry_router_hard_gate"), "entry_router_hard_gate")
    if entry_router.get("schema") != ENTRY_ROUTER_SCHEMA:
        raise ValueError("entry router hard gate schema mismatch")
    if entry_router.get("fresh_each_invocation") is not True:
        raise ValueError("entry router must be fresh each invocation")
    if entry_router.get("chat_memory_is_not_evidence") is not True:
        raise ValueError("chat memory must not satisfy entry router")
    if tuple(entry_router.get("required_fresh_read_order") or ()) != ENTRY_ROUTER_FRESH_READS:
        raise ValueError("entry router fresh-read order mismatch")
    if entry_router.get("ready_state") != ENTRY_ROUTER_READY:
        raise ValueError("entry router ready state mismatch")
    if entry_router.get("failure_action") != "FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY":
        raise ValueError("entry router failure action mismatch")
    shared = _mapping(contract.get("shared_unpushed_integration"), "shared_unpushed_integration")
    if shared.get("schema") != "WHD_SHARED_UNPUSHED_INTEGRATION_V1":
        raise ValueError("shared unpushed integration schema mismatch")
    if shared.get("machine_owner") != "tools/shared_unpushed_integration.py":
        raise ValueError("shared unpushed integration owner mismatch")
    if shared.get("integration_root") != DEFAULT_WORK_PREFIX:
        raise ValueError("shared unpushed integration root mismatch")
    if shared.get("conflict_state") != CONFLICT_STATE:
        raise ValueError("merge conflict must block on explicit user decision")
    if shared.get("conflict_checkpoint_schema") != CONFLICT_CHECKPOINT_SCHEMA:
        raise ValueError("merge conflict checkpoint schema mismatch")
    if shared.get("mode") != "CONDITIONAL_FALLBACK_ONLY" or shared.get("default_route") is not False:
        raise ValueError("shared-zero must remain conditional fallback only")
    if shared.get("activation") != "FRESH_SHARED_ZERO_DRIFT_ON_TOUCHED_PATHS":
        raise ValueError("shared-zero activation mismatch")
    reservation = _mapping(contract.get("path_reservation"), "path_reservation")
    if reservation.get("schema") != "WHD_PATH_RESERVATION_V1":
        raise ValueError("path reservation schema mismatch")
    if reservation.get("state_owner") != "WHD_EXECUTION_RECORD_V2.mutation_scope":
        raise ValueError("path reservation state owner mismatch")
    if reservation.get("evaluator") != "tools/execution_path_reservation.py":
        raise ValueError("path reservation evaluator mismatch")
    if reservation.get("phase") != "DELIVERY_ONLY_AFTER_LANE_MANIFEST_FROZEN":
        raise ValueError("path reservation must be delivery-only")
    if reservation.get("release_policy") != "FINALIZE_OR_EXPLICIT_RELEASE_PATHS":
        raise ValueError("path reservation release policy mismatch")
    modes = _mapping(contract.get("execution_modes"), "execution_modes")
    if modes.get("INTERACTIVE") != "WORKSPACE_FIRST_CONTENT":
        raise ValueError("interactive execution mode must be workspace-first")
    for mode in REMOTE_MODES:
        if modes.get(mode) != REMOTE_CONTENT_POLICY:
            raise ValueError(f"remote execution mode must require root-workspace handoff for content: {mode}")
    remote_content = _mapping(contract.get("remote_content_implementation"), "remote_content_implementation")
    if remote_content.get("policy") != "WORKSPACE_MIRROR_IMPLEMENTATION":
        raise ValueError("remote repository-content implementation must use workspace mirror")
    if remote_content.get("qa_failure_action") != "FIX_IN_WORKSPACE_RETEST_REPUSH":
        raise ValueError("remote QA failure must return to workspace and retest")
    provenance = _mapping(contract.get("execution_mode_provenance"), "execution_mode_provenance")
    if provenance.get("schema") != EXECUTION_MODE_PROVENANCE_SCHEMA:
        raise ValueError("execution mode provenance schema mismatch")
    if provenance.get("remote_exception_requires") != "TRUSTED_RUNTIME_PROVENANCE":
        raise ValueError("remote execution exception must require trusted provenance")
    test_execution_receipt = _mapping(contract.get("test_execution_receipt"), "test_execution_receipt")
    if test_execution_receipt.get("schema") != TEST_EXECUTION_RECEIPT_SCHEMA:
        raise ValueError("test execution receipt schema mismatch")
    if test_execution_receipt.get("bare_tests_green_boolean_sufficient") is not False:
        raise ValueError("bare tests_green boolean must not unlock Git writes")
    if test_execution_receipt.get("generation_role") != "HISTORICAL_FREEZE_PROVENANCE_ONLY":
        raise ValueError("test receipt generation role must be historical provenance only")
    if tuple(test_execution_receipt.get("required_identity") or ()) != (
        "source_sha", "issue", "exact_commands", "manifest_digest"
    ):
        raise ValueError("test receipt required identity must exclude lease-renewal generation")
    direct_gate = _mapping(contract.get("direct_root_mutation_test_gate"), "direct_root_mutation_test_gate")
    if direct_gate.get("schema") != "WHD_DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1":
        raise ValueError("direct root mutation/test gate schema mismatch")
    if direct_gate.get("applies_when") != "SHARED_ZERO_FALLBACK_ACTIVE":
        raise ValueError("direct root mutation/test gate must be shared-zero fallback only")
    if direct_gate.get("canonical_surface") != DEFAULT_WORK_PREFIX:
        raise ValueError("direct root mutation/test canonical surface mismatch")
    if direct_gate.get("interactive_first_substantive_action") != "ROOT_MUTATE":
        raise ValueError("direct root mutation/test first action must be ROOT_MUTATE")
    if tuple(direct_gate.get("required_contiguous_outer_sequence") or ()) != (
        "ROOT_MUTATE", "MERGE_TO_0_OR_CONFLICT_CHECKPOINT",
        "POST_MERGE_0_TEST_CLASSIFIED", "POST_MERGE_0_TESTS_GREEN"
    ):
        raise ValueError("direct root mutation/test contiguous sequence mismatch")
    if direct_gate.get("same_invocation_until") != "ROOT_TESTS_GREEN_OR_REAL_BLOCKER":
        raise ValueError("direct root mutation/test same-invocation policy mismatch")
    if direct_gate.get("task_scope_sticky_until") != "ROOT_TESTS_GREEN_OR_REAL_BLOCKER_OR_USER_EXPLICIT_TASK_CHANGE":
        raise ValueError("current task scope must remain sticky until root green, real blocker, or explicit user task change")
    if direct_gate.get("control_plane_anomaly_action") != "RECORD_AS_EVIDENCE_AND_CONTINUE_CURRENT_ROOT_TASK":
        raise ValueError("control-plane anomaly must not become a new primary task")
    forbidden_scope_switch = set(direct_gate.get("forbidden_scope_switch_triggers") or ())
    required_scope_switch_forbidden = {
        "STALE_EXECUTION_RECORD", "EXPIRED_LEASE", "RESERVATION_MISMATCH",
        "GOVERNANCE_DRIFT", "TEST_RED", "STATUS_QUERY", "PROGRESS_QUERY",
    }
    if not required_scope_switch_forbidden.issubset(forbidden_scope_switch):
        raise ValueError("task-scope stickiness forbidden trigger set is incomplete")
    allowed_scope_switch = set(direct_gate.get("scope_switch_allowed_only_on") or ())
    required_scope_switch_allowed = {
        "USER_EXPLICIT_TASK_CHANGE", "PATH_CONFLICT", "SAME_ISSUE_OTHER_WRITER",
        "SUBSTANTIVE_TARGET_OVERLAP", "MACHINE_FAIL_CLOSED", "USER_INPUT_REQUIRED",
    }
    if allowed_scope_switch != required_scope_switch_allowed:
        raise ValueError("task scope may change only on explicit user change or a real escalation blocker")
    if direct_gate.get("root_capability_available_policy") != "NO_HANDOFF_ONLY_STOP":
        raise ValueError("direct root mutation/test root-capability policy mismatch")
    if direct_gate.get("status_or_progress_query_is_stop_reason") is not False:
        raise ValueError("status/progress query must not be a stop reason")
    if direct_gate.get("test_red_action") != "FIX_IN_SAME_ROOT_WORKSPACE_AND_RETEST":
        raise ValueError("TEST_RED must remain in the same root workspace")
    if direct_gate.get("remote_without_root_capability_action") != "HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK":
        raise ValueError("remote no-root-capability action mismatch")
    forbidden = set(direct_gate.get("forbidden_pre_root_green_outcomes") or ())
    required_forbidden = {"PLANNING_ONLY", "CLAIM_ONLY", "OWNER_ONLY", "HANDOFF_ONLY", "BRANCH_CREATED_ONLY", "GOVERNANCE_GREEN_ONLY", "GITHUB_PATCH", "REMOTE_QA_AS_FIRST_TEST_SURFACE"}
    if not required_forbidden.issubset(forbidden):
        raise ValueError("direct root mutation/test forbidden outcome set is incomplete")

    fast_path = _mapping(contract.get("orchestration_fast_path"), "orchestration_fast_path")
    if fast_path.get("schema") != ORCHESTRATION_FAST_PATH_SCHEMA:
        raise ValueError("interactive orchestration fast-path schema mismatch")
    if fast_path.get("default") != "SESSION_INTERNAL_ORCHESTRATION":
        raise ValueError("interactive orchestration must default to session-internal")
    if set(fast_path.get("outer_visible_pipeline") or ()) != OUTER_VISIBLE_PIPELINE:
        raise ValueError("outer visible pipeline must contain phase outcomes only")
    if set(fast_path.get("machine_internal_transaction_kinds") or ()) != MACHINE_INTERNAL_CONTROL_ACTIONS:
        raise ValueError("machine-internal transaction kind set is incomplete")
    if set(fast_path.get("background_only_events") or ()) != BACKGROUND_ONLY_EVENTS:
        raise ValueError("background-only event set is incomplete")
    if set(fast_path.get("escalate_only_on") or ()) != REAL_ESCALATION_TRIGGERS - {"USER_EXPLICIT_TASK_CHANGE"}:
        raise ValueError("interactive escalation trigger set mismatch")
    if fast_path.get("outer_action_gate") != "tools/root_local_first_gate.py::assert_outer_primary_action":
        raise ValueError("interactive outer action gate owner mismatch")
    if fast_path.get("outer_primary_action_policy") != "PHASE_OUTCOME_OR_REAL_BLOCKER_ONLY":
        raise ValueError("interactive outer primary action policy mismatch")
    if fast_path.get("control_plane_event_disposition") != "BACKGROUND_CONTINUE_PRIMARY_TASK":
        raise ValueError("control-plane events must remain background-only")
    if fast_path.get("user_update_policy") != "REPORT_PHASE_OUTCOME_NOT_CONTROL_PLANE_INTERNALS":
        raise ValueError("interactive user updates must hide control-plane internals")
    if fast_path.get("manual_transaction_orchestration_after_escalation_allowed") is not False:
        raise ValueError("manual transaction orchestration must remain forbidden")

    receipt = _mapping(contract.get("git_write_receipt"), "git_write_receipt")
    if receipt.get("schema") != GIT_UNLOCK_RECEIPT_SCHEMA:
        raise ValueError("Git write receipt schema mismatch")
    if set(receipt.get("required_for_repository_content_actions") or ()) != {"START_BRANCH", "APPLY_COMMIT"}:
        raise ValueError("Git write receipt action policy mismatch")
    return {str(k): v for k, v in contract.items()}


def validate_source_current(
    *,
    live_source_sha: str,
    live_tree_sha: str,
    workspace_git: object | None = None,
    manifest: object | None = None,
    touched_path_proofs: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Prove the Google Drive root is based on the live target.

    CURRENT mode is the real repo working tree under `/Google Drive/WHD`: its
    `.git` HEAD/tree is compared directly to the live target.  Legacy source
    manifests and scoped blob recovery are historical only and no longer mint
    ROOT_SOURCE_CURRENT evidence.
    """
    live_sha = _sha(live_source_sha, "live_source_sha")
    live_tree = _sha(live_tree_sha, "live_tree_sha")
    if workspace_git is not None:
        item = _mapping(workspace_git, "workspace git evidence")
        workspace_sha = _sha(item.get("head_sha"), "workspace head_sha")
        workspace_tree = _sha(item.get("tree_sha"), "workspace tree_sha")
        if workspace_sha != live_sha or workspace_tree != live_tree:
            raise ValueError(
                "ROOT_SOURCE_CURRENT_FAILED: workspace .git HEAD/tree does not match live target"
            )
        return {
            "status": "EXACT_SOURCE_CURRENT",
            "source_sha": live_sha,
            "tree_sha": live_tree,
            "source_mode": "ROOT_GIT_WORKTREE",
        }

    if manifest is not None or tuple(touched_path_proofs):
        raise ValueError(
            "ROOT_SOURCE_CURRENT_FAILED: legacy source manifest/scoped recovery is historical only; "
            "workspace_git evidence is required"
        )
    raise ValueError("ROOT_SOURCE_CURRENT_FAILED: workspace_git evidence is required")


def frozen_diff_digest(entries: Iterable[Mapping[str, object]]) -> str:
    normalized = []
    for entry in entries:
        path = str(entry.get("path") or "").strip()
        sha256 = str(entry.get("sha256") or "").strip().lower()
        if not path or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("frozen diff entries require path + sha256")
        normalized.append({"path": path, "sha256": sha256})
    if not normalized:
        raise ValueError("frozen diff must contain at least one entry")
    body = json.dumps(sorted(normalized, key=lambda x: x["path"]), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_worker_census_evidence(
    payload: Mapping[str, object], *, expected_lane: str, expected_generation: int
) -> dict[str, object]:
    """Validate optional legacy/shared-zero worker census evidence.

    The current root-first fast path no longer requires this census to progress,
    but older trusted callers still supply it.  Accept and validate it when
    present so the compatibility field cannot silently become an unchecked
    authority bypass.
    """
    evidence = _mapping(payload, "worker census evidence")
    if evidence.get("schema") != WORKER_CENSUS_SCHEMA:
        raise ValueError("worker census evidence schema mismatch")
    lane = str(evidence.get("lane") or "").strip().lower()
    if lane != str(expected_lane or "").strip().lower():
        raise ValueError("worker census lane mismatch")
    generation = evidence.get("latest_zero_generation")
    if not isinstance(generation, int) or isinstance(generation, bool):
        raise ValueError("worker census latest_zero_generation must be integer")
    if generation != int(expected_generation):
        raise ValueError("worker census generation mismatch")
    if evidence.get("fresh") is not True:
        raise ValueError("worker census must be fresh")
    for key in ("mergeable_green_count", "blocking_candidate_count"):
        value = evidence.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"worker census {key} must be non-negative integer")
    return dict(evidence)


def build_gate_evidence(
    *,
    execution_mode: str,
    execution_mode_provenance: Mapping[str, object] | None = None,
    repository_content_implementation: bool = False,
    entry_router_evidence: Mapping[str, object] | None = None,
    source_evidence: Mapping[str, object] | None = None,
    unpushed_lane_evidence: Mapping[str, object] | None = None,
    root_mutations_complete: bool = False,
    merge_to_zero_complete: bool = False,
    conflict_checkpoint: Mapping[str, object] | None = None,
    test_classified: bool = False,
    tests_green: bool = False,
    test_receipt: Mapping[str, object] | None = None,
    expected_test_commands: Iterable[str] = (),
    worker_census_evidence: Mapping[str, object] | None = None,
    diff_digest: str | None = None,
    remote_connection_authority: Mapping[str, object] | None = None,
    path_reservation_evidence: Mapping[str, object] | None = None,
    target_drift: bool = False,
) -> dict[str, object]:
    mode = str(execution_mode or "INTERACTIVE").strip().upper()
    if mode in REMOTE_MODES:
        provenance = validate_execution_mode_provenance(
            execution_mode=mode, provenance=execution_mode_provenance
        )
        if repository_content_implementation:
            return {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "execution_mode_provenance": provenance, "scope": "REMOTE_CONTENT_IMPLEMENTATION_REQUIRES_HANDOFF", "applicable": False, "git_write_unlocked": False, "next_action": "HANDOFF_TO_ROOT_WORKSPACE_IMPLEMENTATION"}
        return {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "execution_mode_provenance": provenance, "scope": "REMOTE_CONTROL_PLANE_EXCEPTION", "applicable": False, "git_write_unlocked": False, "next_action": "FOLLOW_FLOW_V2_REMOTE_AUTHORITY"}
    if mode not in INTERACTIVE_MODES:
        raise ValueError(f"unsupported execution mode: {mode}")

    entry_router = None
    if repository_content_implementation:
        if entry_router_evidence is None:
            raise ValueError("repository-content gate requires entry router evidence")
        entry_router = validate_entry_router_evidence(entry_router_evidence)

    completed: list[str] = []
    lane = None
    reservation = None
    remote_authority = None
    if not source_evidence:
        next_action = "ROOT_SOURCE_CURRENT"
    else:
        status = str(source_evidence.get("status") or "")
        if status not in {"EXACT_SOURCE_CURRENT", "SCOPED_CURRENT_RECOVERY"}:
            raise ValueError("invalid ROOT_SOURCE_CURRENT evidence")
        completed.append("ROOT_SOURCE_CURRENT")
        if not unpushed_lane_evidence:
            next_action = "UNPUSHED_LANE_CLASSIFIED"
        else:
            try:
                lane = validate_lane_evidence(unpushed_lane_evidence)
            except ValueError as exc:
                raise ValueError(f"invalid UNPUSHED_LANE evidence: {exc}") from exc
            if str(lane.get("source_sha") or "") != str(source_evidence.get("source_sha") or ""):
                raise ValueError("LATEST_0 base source_sha must match ROOT_SOURCE_CURRENT source_sha")
            completed.extend(("UNPUSHED_LANE_CLASSIFIED", "LATEST_0_BASE_BOUND"))
            if not root_mutations_complete:
                next_action = "ROOT_MUTATIONS_COMPLETE"
            else:
                completed.append("ROOT_MUTATIONS_COMPLETE")
                if conflict_checkpoint:
                    cp = _mapping(conflict_checkpoint, "conflict checkpoint")
                    if cp.get("schema") != CONFLICT_CHECKPOINT_SCHEMA or cp.get("state") != CONFLICT_STATE:
                        raise ValueError("invalid merge conflict checkpoint")
                    return {
                        "schema": EVIDENCE_SCHEMA,
                        "execution_mode": mode,
                        "applicable": True,
                        "completed": completed,
                        "git_write_unlocked": False,
                        "next_action": "USER_CONFLICT_DECISION",
                        "blocked_state": CONFLICT_STATE,
                        "conflict_checkpoint": dict(cp),
                        "unpushed_lane": dict(lane),
                    }
                if not merge_to_zero_complete:
                    next_action = "MERGE_TO_0_OR_CONFLICT_CHECKPOINT"
                else:
                    completed.append("MERGE_TO_0_OR_CONFLICT_CHECKPOINT")
                    if not test_classified:
                        next_action = "POST_MERGE_0_TEST_CLASSIFIED"
                    else:
                        completed.append("POST_MERGE_0_TEST_CLASSIFIED")
                        if not tests_green:
                            next_action = "POST_MERGE_0_TESTS_GREEN"
                        elif not test_receipt:
                            raise ValueError("POST_MERGE_0_TESTS_GREEN requires WHD_TEST_EXECUTION_RECEIPT_V1")
                        else:
                            validate_test_execution_receipt(
                                test_receipt,
                                expected_source_sha=str(source_evidence.get("source_sha") or ""),
                                expected_issue=int(lane.get("issue") or 0),
                                expected_generation=int(lane.get("generation") or 0),
                                expected_commands=expected_test_commands,
                            )
                            completed.append("POST_MERGE_0_TESTS_GREEN")
                            worker_census_blocks = False
                            if worker_census_evidence is not None:
                                census = validate_worker_census_evidence(
                                    worker_census_evidence,
                                    expected_lane=str(lane.get("lane") or ""),
                                    expected_generation=int(lane.get("generation") or 0),
                                )
                                if int(census.get("mergeable_green_count") or 0) > 0:
                                    next_action = "MERGE_TO_FRESH_LATEST_ZERO"
                                    worker_census_blocks = True
                                elif int(census.get("blocking_candidate_count") or 0) > 0:
                                    next_action = "RESOLVE_WORKER_CENSUS_BLOCKERS"
                                    worker_census_blocks = True
                                else:
                                    completed.append("WORKER_CENSUS_NO_MERGEABLE_GREEN")
                            if not worker_census_blocks and not diff_digest:
                                next_action = "LANE_MANIFEST_FROZEN"
                            elif not worker_census_blocks:
                                if not re.fullmatch(r"[0-9a-f]{64}", diff_digest):
                                    raise ValueError("diff_digest must be SHA256")
                                completed.append("LANE_MANIFEST_FROZEN")
                                if remote_connection_authority is None:
                                    next_action = "REMOTE_CONNECTION_AUTHORIZED"
                                else:
                                    remote_authority = validate_remote_connection_authority(
                                        remote_connection_authority, target="GITHUB", action="READ"
                                    )
                                    if remote_authority.get("kind") not in DELIVERY_AUTHORITY_KINDS:
                                        raise ValueError("delivery Git authority must be /推推 or explicit user remote authority")
                                    expected_lane = str(lane.get("lane") or "").strip().lower()
                                    if remote_authority.get("kind") == "PUSH_DOCS" and expected_lane != "docs":
                                        raise ValueError("PUSH_DOCS authority cannot deliver non-docs lane")
                                    if remote_authority.get("kind") == "PUSH_BODY" and expected_lane != "body":
                                        raise ValueError("PUSH_BODY authority cannot deliver non-body lane")
                                    completed.append("REMOTE_CONNECTION_AUTHORIZED")
                                    if not path_reservation_evidence:
                                        next_action = "DELIVERY_PATHS_RESERVED"
                                    else:
                                        try:
                                            reservation = validate_path_reservation_evidence(path_reservation_evidence)
                                        except ValueError as exc:
                                            raise ValueError(f"invalid DELIVERY_PATHS_RESERVED evidence: {exc}") from exc
                                        if str(reservation.get("base_sha") or "") != str(source_evidence.get("source_sha") or ""):
                                            raise ValueError("delivery reservation base_sha must match source_sha")
                                        if int(reservation.get("issue") or 0) != int(lane.get("issue") or 0):
                                            raise ValueError("delivery reservation issue must match lane issue")
                                        if str(reservation.get("target_branch") or "") != str(lane.get("target_branch") or ""):
                                            raise ValueError("delivery reservation target must match lane target")
                                        if tuple(reservation.get("write_paths") or ()) != tuple(lane.get("write_paths") or ()) or tuple(reservation.get("delete_paths") or ()) != tuple(lane.get("delete_paths") or ()):
                                            raise ValueError("delivery reservation scope must equal lane manifest scope")
                                        completed.append("DELIVERY_PATHS_RESERVED")
                                        if target_drift:
                                            return {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "applicable": True, "completed": completed, "git_write_unlocked": False, "next_action": "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE", "diff_digest": diff_digest, "path_reservation": reservation, "unpushed_lane": dict(lane)}
                                        completed.append("GIT_WRITE_UNLOCKED")
                                        next_action = "EXACT_TESTED_DIFF_ONLY"
    result = {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "applicable": True, "completed": completed, "git_write_unlocked": "GIT_WRITE_UNLOCKED" in completed, "next_action": next_action}
    if entry_router is not None:
        result["entry_router"] = entry_router
    if diff_digest:
        result["diff_digest"] = diff_digest
    if lane:
        result["unpushed_lane"] = dict(lane)
    if remote_authority:
        result["remote_connection_authority"] = dict(remote_authority)
    if reservation:
        result["path_reservation"] = dict(reservation)
    return result


def assert_git_content_write_allowed(evidence: object, *, action: str) -> None:
    item = _mapping(evidence, "root-local-first evidence")
    action_name = str(action or "").strip().upper()
    assert_remote_connection_allowed(
        item.get("remote_connection_authority"), target="GITHUB", action=action_name
    )
    if action_name in READ_ONLY_GIT_ACTIONS:
        return
    if item.get("applicable") is False:
        raise ValueError("root-local-first does not authorize remote control-plane Git content writes")
    if not item.get("git_write_unlocked"):
        raise ValueError("GIT_WRITE_LOCKED_UNTIL_ROOT_DIFF_FROZEN")
    if item.get("next_action") != "EXACT_TESTED_DIFF_ONLY":
        raise ValueError("Git content write is not bound to exact tested diff")
