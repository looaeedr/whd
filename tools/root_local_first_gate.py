"""Machine gate for WHD root-local-first repository content work and remote handoff classification."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping

from tools.execution_path_reservation import validate_path_reservation_evidence

SCHEMA = "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1"
EVIDENCE_SCHEMA = "WHD_ROOT_LOCAL_FIRST_GATE_EVIDENCE_V1"
DEFAULT_ROOT = "/Google Drive/WHD"
DEFAULT_WORK_PREFIX = "/Google Drive/WHD/work/active"
TEST_PROFILE_SCHEMA = "WHD_CHANGE_TEST_PROFILE_V1"
TEST_PROFILE_OWNER = "tools/change_test_profile.py"
TEST_EXECUTION_RECEIPT_SCHEMA = "WHD_TEST_EXECUTION_RECEIPT_V1"
REQUIRED_ORDER = (
    "ROOT_SOURCE_CURRENT",
    "PATHS_RESERVED",
    "ROOT_MUTATIONS_COMPLETE",
    "ROOT_TEST_CLASSIFIED",
    "ROOT_TESTS_GREEN",
    "ROOT_DIFF_FROZEN",
    "GIT_WRITE_UNLOCKED",
)
INTERACTIVE_MODES = {"INTERACTIVE", "CHAT", "DEFAULT"}
REMOTE_MODES = {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}
REMOTE_CONTENT_POLICY = "CONTROL_PLANE_OR_POST_PUSH_ONLY_REPOSITORY_CONTENT_REQUIRES_ROOT_WORKSPACE_HANDOFF"
READ_ONLY_GIT_ACTIONS = {"READ", "FETCH", "COMPARE"}
EXECUTION_MODE_PROVENANCE_SCHEMA = "WHD_EXECUTION_MODE_PROVENANCE_V1"
GIT_UNLOCK_RECEIPT_SCHEMA = "ROOT_LOCAL_FIRST_GIT_UNLOCK_RECEIPT_V1"
SCHEDULER_LANE_IDS = {
    "scheduler.6ab13fa557fc8191935c671214b865e2",
    "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
}
FAST_PATH_ROOT_REPAIR_EVENTS = {"TEST_RED"}
FAST_PATH_ESCALATION_EVENTS = {
    "PATH_CONFLICT",
    "SAME_ISSUE_OTHER_WRITER",
    "SUBSTANTIVE_TARGET_OVERLAP",
    "MACHINE_FAIL_CLOSED",
    "USER_INPUT_REQUIRED",
}



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
    if isinstance(item.get("generation"), bool) or int(item.get("generation") or 0) != int(expected_generation):
        raise ValueError("test receipt generation mismatch")
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


def classify_interactive_fast_path_event(event: object) -> dict[str, object]:
    """Classify one outer interactive event without exposing Flow v2 choreography.

    TEST_RED is deliberately *not* a governance escalation.  It returns directly
    to canonical root repair while any FAIL_QA/lease/CAS bookkeeping remains
    machine-internal.  No event in this classifier may authorize chat-layer
    per-transaction orchestration.
    """
    name = str(event or "").strip().upper()
    if not name:
        raise ValueError("interactive fast-path event must be nonblank")
    if name in FAST_PATH_ROOT_REPAIR_EVENTS:
        return {
            "event": name,
            "classification": "ROOT_REPAIR_CONTINUATION",
            "outer_action": "RETURN_TO_ROOT_REPAIR_IN_SAME_SESSION",
            "outer_pipeline_step": "ROOT_MUTATE",
            "chat_transaction_orchestration_allowed": False,
            "machine_internal_transitions": ["FAIL_QA", "LEASE", "CAS_RETRY", "SESSION_REUSE"],
        }
    if name in FAST_PATH_ESCALATION_EVENTS:
        return {
            "event": name,
            "classification": "MACHINE_GOVERNANCE_ESCALATION",
            "outer_action": "ESCALATE_MACHINE_GOVERNANCE",
            "chat_transaction_orchestration_allowed": False,
        }
    return {
        "event": name,
        "classification": "SESSION_FAST_PATH_CONTINUATION",
        "outer_action": "CONTINUE_SESSION_FAST_PATH",
        "chat_transaction_orchestration_allowed": False,
    }


def validate_contract(payload: object) -> dict[str, object]:
    contract = _mapping(payload, "root-local-first contract")
    if contract.get("schema") != SCHEMA:
        raise ValueError("unexpected root-local-first schema")
    if contract.get("status") != "CURRENT":
        raise ValueError("root-local-first contract is not CURRENT")
    root = _mapping(contract.get("canonical_root"), "canonical_root")
    if root.get("library_path") != DEFAULT_ROOT:
        raise ValueError("canonical root path mismatch")
    if root.get("interactive_work_prefix") != DEFAULT_WORK_PREFIX:
        raise ValueError("interactive work prefix mismatch")
    if tuple(contract.get("required_order") or ()) != REQUIRED_ORDER:
        raise ValueError("root-local-first required order mismatch")
    if contract.get("test_profile_schema") != TEST_PROFILE_SCHEMA:
        raise ValueError("test-profile schema mismatch")
    if contract.get("test_profile_owner") != TEST_PROFILE_OWNER:
        raise ValueError("test-profile owner mismatch")
    if set(contract.get("git_before_unlock") or ()) != READ_ONLY_GIT_ACTIONS:
        raise ValueError("pre-unlock Git action policy mismatch")
    if contract.get("git_write_mode") != "EXACT_TESTED_DIFF_ONLY":
        raise ValueError("Git write mode must be EXACT_TESTED_DIFF_ONLY")
    if contract.get("target_drift_action") != "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE":
        raise ValueError("target drift action mismatch")
    reservation = _mapping(contract.get("path_reservation"), "path_reservation")
    if reservation.get("schema") != "WHD_PATH_RESERVATION_V1":
        raise ValueError("path reservation schema mismatch")
    if reservation.get("state_owner") != "WHD_EXECUTION_RECORD_V2.mutation_scope":
        raise ValueError("path reservation state owner mismatch")
    if reservation.get("evaluator") != "tools/execution_path_reservation.py":
        raise ValueError("path reservation evaluator mismatch")
    if reservation.get("conflict_policy") != "SAME_TARGET_EXACT_PATH_SINGLE_WRITER":
        raise ValueError("path reservation conflict policy mismatch")
    if reservation.get("release_policy") != "FINALIZE_OR_EXPLICIT_RELEASE_PATHS":
        raise ValueError("path reservation release policy mismatch")
    modes = _mapping(contract.get("execution_modes"), "execution_modes")
    if modes.get("INTERACTIVE") != "ROOT_LOCAL_FIRST_REQUIRED":
        raise ValueError("interactive execution mode must require root-local-first")
    for mode in REMOTE_MODES:
        if modes.get(mode) != REMOTE_CONTENT_POLICY:
            raise ValueError(f"remote execution mode must require root-workspace handoff for content: {mode}")
    remote_content = _mapping(contract.get("remote_content_implementation"), "remote_content_implementation")
    if remote_content.get("policy") != "ROOT_WORKSPACE_HANDOFF_REQUIRED":
        raise ValueError("remote repository-content implementation must require root workspace handoff")
    if remote_content.get("github_side_hotfix_forbidden") is not True:
        raise ValueError("GitHub-side hotfix must be forbidden for remote content implementation")
    if remote_content.get("qa_failure_action") != "RETURN_TO_ROOT_RETEST_REFREEZE_REPUSH":
        raise ValueError("remote QA failure must return to root and retest/refreeze")
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
    fast_path = _mapping(contract.get("orchestration_fast_path"), "orchestration_fast_path")
    if fast_path.get("schema") != "WHD_INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1":
        raise ValueError("interactive orchestration fast-path schema mismatch")
    if fast_path.get("manual_transaction_orchestration_after_escalation_allowed") is not False:
        raise ValueError("chat-layer per-transaction orchestration must remain forbidden after escalation")
    if set(fast_path.get("root_repair_events") or ()) != FAST_PATH_ROOT_REPAIR_EVENTS:
        raise ValueError("TEST_RED must be the exact root-repair event set")
    if "TEST_RED" in set(fast_path.get("escalate_only_on") or ()):
        raise ValueError("TEST_RED must not escalate out of the interactive session fast path")
    if set(fast_path.get("escalate_only_on") or ()) != FAST_PATH_ESCALATION_EVENTS:
        raise ValueError("interactive fast-path escalation set mismatch")
    if fast_path.get("test_red_outer_action") != "RETURN_TO_ROOT_REPAIR_IN_SAME_SESSION":
        raise ValueError("TEST_RED must return directly to root repair")
    receipt = _mapping(contract.get("git_write_receipt"), "git_write_receipt")
    if receipt.get("schema") != GIT_UNLOCK_RECEIPT_SCHEMA:
        raise ValueError("Git write receipt schema mismatch")
    if set(receipt.get("required_for_interactive_actions") or ()) != {"START_BRANCH", "APPLY_COMMIT"}:
        raise ValueError("Git write receipt action policy mismatch")
    return {str(k): v for k, v in contract.items()}


def validate_source_current(*, manifest: object, live_source_sha: str, live_tree_sha: str, touched_path_proofs: Iterable[Mapping[str, object]] = ()) -> dict[str, object]:
    item = _mapping(manifest, "source manifest")
    live_sha = _sha(live_source_sha, "live_source_sha")
    live_tree = _sha(live_tree_sha, "live_tree_sha")
    manifest_sha = _sha(item.get("source_sha"), "manifest source_sha")
    manifest_tree = _sha(item.get("tree_sha"), "manifest tree_sha")
    if manifest_sha == live_sha and manifest_tree == live_tree:
        return {"status": "EXACT_SOURCE_CURRENT", "source_sha": live_sha, "tree_sha": live_tree, "snapshot_status": str(item.get("durable_snapshot_status") or "UNKNOWN")}
    proofs = list(touched_path_proofs)
    if not proofs:
        raise ValueError("ROOT_SOURCE_CURRENT_FAILED: manifest stale and no touched-path proof")
    for proof in proofs:
        path = str(proof.get("path") or "").strip()
        expected = str(proof.get("live_blob_sha") or "").strip().lower()
        observed = str(proof.get("workspace_blob_sha") or "").strip().lower()
        if not path or not re.fullmatch(r"[0-9a-f]{40}", expected) or expected != observed:
            raise ValueError(f"ROOT_SOURCE_CURRENT_FAILED: invalid touched-path proof for {path!r}")
    return {"status": "SCOPED_CURRENT_RECOVERY", "source_sha": live_sha, "tree_sha": live_tree, "verified_paths": sorted(str(p["path"]) for p in proofs)}


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


def build_gate_evidence(
    *,
    execution_mode: str,
    execution_mode_provenance: Mapping[str, object] | None = None,
    repository_content_implementation: bool = False,
    source_evidence: Mapping[str, object] | None = None,
    path_reservation_evidence: Mapping[str, object] | None = None,
    root_mutations_complete: bool = False,
    test_classified: bool = False,
    tests_green: bool = False,
    test_receipt: Mapping[str, object] | None = None,
    expected_test_commands: Iterable[str] = (),
    diff_digest: str | None = None,
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
    completed: list[str] = []
    if not source_evidence:
        next_action = "ROOT_SOURCE_CURRENT"
    else:
        status = str(source_evidence.get("status") or "")
        if status not in {"EXACT_SOURCE_CURRENT", "SCOPED_CURRENT_RECOVERY"}:
            raise ValueError("invalid ROOT_SOURCE_CURRENT evidence")
        completed.append("ROOT_SOURCE_CURRENT")
        if not path_reservation_evidence:
            next_action = "PATHS_RESERVED"
        else:
            try:
                reservation = validate_path_reservation_evidence(path_reservation_evidence)
            except ValueError as exc:
                raise ValueError(f"invalid PATHS_RESERVED evidence: {exc}") from exc
            if str(reservation.get("base_sha") or "") != str(source_evidence.get("source_sha") or ""):
                raise ValueError("PATHS_RESERVED base_sha must match ROOT_SOURCE_CURRENT source_sha")
            completed.append("PATHS_RESERVED")
            if not root_mutations_complete:
                next_action = "ROOT_MUTATIONS_COMPLETE"
            else:
                completed.append("ROOT_MUTATIONS_COMPLETE")
                if not test_classified:
                    next_action = "ROOT_TEST_CLASSIFIED"
                else:
                    completed.append("ROOT_TEST_CLASSIFIED")
                    if not tests_green:
                        next_action = "ROOT_TESTS_GREEN"
                    elif not test_receipt:
                        raise ValueError("ROOT_TESTS_GREEN requires WHD_TEST_EXECUTION_RECEIPT_V1")
                    else:
                        validate_test_execution_receipt(
                            test_receipt,
                            expected_source_sha=str(source_evidence.get("source_sha") or ""),
                            expected_issue=int(reservation.get("issue") or 0),
                            expected_generation=int(reservation.get("generation") or 0),
                            expected_commands=expected_test_commands,
                        )
                        completed.append("ROOT_TESTS_GREEN")
                        if not diff_digest:
                            next_action = "ROOT_DIFF_FROZEN"
                        else:
                            if not re.fullmatch(r"[0-9a-f]{64}", diff_digest):
                                raise ValueError("diff_digest must be SHA256")
                            completed.append("ROOT_DIFF_FROZEN")
                            if target_drift:
                                return {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "applicable": True, "completed": completed, "git_write_unlocked": False, "next_action": "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE", "diff_digest": diff_digest, "path_reservation": reservation}
                            completed.append("GIT_WRITE_UNLOCKED")
                            next_action = "EXACT_TESTED_DIFF_ONLY"
    result = {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "applicable": True, "completed": completed, "git_write_unlocked": "GIT_WRITE_UNLOCKED" in completed, "next_action": next_action}
    if diff_digest:
        result["diff_digest"] = diff_digest
    if path_reservation_evidence:
        result["path_reservation"] = dict(path_reservation_evidence)
    return result


def assert_git_content_write_allowed(evidence: object, *, action: str) -> None:
    item = _mapping(evidence, "root-local-first evidence")
    action_name = str(action or "").strip().upper()
    if action_name in READ_ONLY_GIT_ACTIONS:
        return
    if item.get("applicable") is False:
        raise ValueError("root-local-first does not authorize remote control-plane Git content writes")
    if not item.get("git_write_unlocked"):
        raise ValueError("GIT_WRITE_LOCKED_UNTIL_ROOT_DIFF_FROZEN")
    if item.get("next_action") != "EXACT_TESTED_DIFF_ONLY":
        raise ValueError("Git content write is not bound to exact tested diff")
