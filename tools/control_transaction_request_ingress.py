"""Scheduler-compatible push ingress for WHD Flow v2 control transactions."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_transaction import (
    ControlTransactionConflict,
    assert_mutation_writer_guard,
)
from tools.execution_entry_contract import (
    assert_startup_transition_matches_record,
    rebind_scheduler_phase6_preflight_receipt,
    validate_phase6_preflight_evidence,
    validate_startup_evidence,
    validate_startup_transition,
)
from tools.execution_dispatch_ingress import (
    CANONICAL_DISPATCH_TRANSPORT,
    DispatchIngressRequest,
)
from tools.scheduler_ready_ingress import (
    SchedulerIssueCandidateError,
    build_scheduler_dispatch_candidate,
)
from tools.root_local_first_gate import validate_git_unlock_receipt
from tools.control_transaction_request_builder import (
    INTENT_SCHEMA,
    REQUEST_SCHEMA,
    SESSION_REUSE_KINDS,
    SESSION_REUSE_SCHEMA,
    build_control_transaction_request_from_intent,
    execution_mode_for_lane,
)

# Backward-compatible schema marker; canonical owner remains the request builder.
# WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1
from tools.control_transaction_production_executor import (
    ProductionExecutorError,
    _is_ancestor,
    _load_state,
    _read_branch_head,
    dispatch_ready_missing_record,
    execute_one,
    recover_post_delivery_missing_record,
)

ALLOWED_KINDS = {
    "SEED","ACQUIRE","START_BRANCH","APPLY_COMMIT","START_QA","ACCEPT_QA","CONSUME_QA","FAIL_QA",
    "BLOCK","MERGE","SYNC_TARGET","HANDOFF","FINALIZE","RECONCILE","RESERVE_PATHS","RELEASE_PATHS","YIELD",
    "DISPATCH_READY","RECOVER_POST_DELIVERY",
}

REQUEST_BRANCH_LANES = {
    "coord/transaction-requests-a": "scheduler.6ab13fa557fc8191935c671214b865e2",
    "coord/transaction-requests-b": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
    "coord/transaction-requests-work0": "chatgpt.flowv2.work0",
    "coord/transaction-requests-work1": "chatgpt.flowv2.work1",
    "coord/transaction-requests-work2": "chatgpt.flowv2.work2",
    "coord/transaction-requests-work3": "chatgpt.flowv2.work3",
}

INTERACTIVE_SLOT_BY_LANE = {
    "chatgpt.flowv2.work0": "worker.slot.0",
    "chatgpt.flowv2.work1": "worker.slot.1",
    "chatgpt.flowv2.work2": "worker.slot.2",
    "chatgpt.flowv2.work3": "worker.slot.3",
}


def _validate_request_branch(*, request: dict[str, object], request_branch: str) -> None:
    expected_lane = REQUEST_BRANCH_LANES.get(request_branch)
    if expected_lane is None:
        raise ProductionExecutorError(f"unsupported request branch: {request_branch}")
    observed_lane = str(request["lane_id"])
    if observed_lane != expected_lane:
        raise ProductionExecutorError(
            f"request lane mismatch: branch {request_branch} requires {expected_lane}, observed {observed_lane}"
        )


def _execution_mode_for_request(request: dict[str, object]) -> str:
    try:
        return execution_mode_for_lane(str(request.get("lane_id") or ""))
    except ValueError as exc:
        raise ProductionExecutorError(str(exc)) from exc




REPOSITORY_CONTENT_GIT_WRITE_KINDS = {"START_BRANCH", "APPLY_COMMIT"}
STALE_RECORD_LIVE_TARGET_RECONCILE_PROOF_SCHEMA = "WHD_FLOW_V2_STALE_RECORD_LIVE_TARGET_RECONCILE_PROOF_V1"
TRUSTED_GITHUB_ACTIONS_PROVENANCE_SCHEMA = "WHD_TRUSTED_GITHUB_ACTIONS_RUNTIME_PROVENANCE_REQUEST_V1"
TRUSTED_GITHUB_ACTIONS_PROVENANCE_MODE = "MINT_EXACT_INVOCATION_IDENTITY"
TRUSTED_GITHUB_ACTIONS_INVOCATION_SENTINEL = "GITHUB_ACTIONS_RUNTIME"
TRUSTED_GITHUB_ACTIONS_WORKFLOW_PATH = ".github/workflows/whd-control-transaction-v2-request.yml"
SCHEDULER_PREFLIGHT_RECEIPT_REF_SCHEMA = "WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1"
REMOTE_PHASE6_RESULT_MARKER = "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1"
TRUSTED_PHASE6_COMMENT_AUTHOR = "github-actions[bot]"


def _bind_trusted_github_actions_runtime_provenance(
    request: dict[str, object],
    *,
    repo: str,
    request_branch: str | None,
    runtime_env,
) -> dict[str, object]:
    """Replace an explicit fresh-admission sentinel only inside the trusted GHA workflow.

    The caller cannot mint an execution identity.  It may only opt into this narrow
    provenance mode by supplying the sentinel consistently in the fresh admission
    envelope.  The trusted push workflow then binds all invocation-bearing fields
    to immutable GitHub Actions context before ordinary startup validation runs.
    """
    provenance = request.get("runtime_provenance")
    observed_invocation = str(request.get("invocation_identity") or "").strip()

    if provenance is None:
        if observed_invocation == TRUSTED_GITHUB_ACTIONS_INVOCATION_SENTINEL:
            raise ProductionExecutorError(
                "trusted GitHub Actions invocation sentinel requires explicit runtime_provenance mode"
            )
        return request

    if observed_invocation != TRUSTED_GITHUB_ACTIONS_INVOCATION_SENTINEL:
        raise ProductionExecutorError(
            "trusted GitHub Actions runtime_provenance requires the exact invocation sentinel"
        )
    if request.get("schema") != REQUEST_SCHEMA:
        raise ProductionExecutorError(
            "trusted GitHub Actions runtime_provenance only supports materialized fresh requests"
        )
    if not isinstance(provenance, dict):
        raise ProductionExecutorError("runtime_provenance must be an object")
    if provenance.get("schema") != TRUSTED_GITHUB_ACTIONS_PROVENANCE_SCHEMA:
        raise ProductionExecutorError("unexpected trusted GitHub Actions runtime_provenance schema")
    if provenance.get("mode") != TRUSTED_GITHUB_ACTIONS_PROVENANCE_MODE:
        raise ProductionExecutorError("unsupported trusted GitHub Actions runtime_provenance mode")
    if "session_reuse" in request:
        raise ProductionExecutorError(
            "trusted GitHub Actions runtime_provenance requires fresh admission, not session reuse"
        )

    fresh_fields = ("startup_evidence", "preflight_evidence", "startup_transition")
    for key in fresh_fields:
        payload = request.get(key)
        if not isinstance(payload, dict):
            raise ProductionExecutorError(
                f"trusted GitHub Actions runtime_provenance requires {key}"
            )
        nested_invocation = str(payload.get("invocation_identity") or "").strip()
        if nested_invocation != TRUSTED_GITHUB_ACTIONS_INVOCATION_SENTINEL:
            raise ProductionExecutorError(
                f"trusted GitHub Actions runtime_provenance {key} invocation must use the exact sentinel"
            )

    if runtime_env is None or str(runtime_env.get("GITHUB_ACTIONS") or "").lower() != "true":
        raise ProductionExecutorError(
            "trusted GitHub Actions runtime_provenance requires GITHUB_ACTIONS=true"
        )
    observed_repo = str(runtime_env.get("GITHUB_REPOSITORY") or "").strip()
    if observed_repo != repo:
        raise ProductionExecutorError(
            f"trusted GitHub Actions runtime repository mismatch: expected {repo}, observed {observed_repo}"
        )

    ref_name = str(runtime_env.get("GITHUB_REF_NAME") or "").strip()
    if not request_branch or ref_name != request_branch:
        raise ProductionExecutorError(
            "trusted GitHub Actions runtime request branch mismatch"
        )

    workflow_ref = str(runtime_env.get("GITHUB_WORKFLOW_REF") or "").strip()
    workflow_identity = workflow_ref.split("@", 1)[0]
    expected_workflow_identity = f"{repo}/{TRUSTED_GITHUB_ACTIONS_WORKFLOW_PATH}"
    if workflow_identity != expected_workflow_identity:
        raise ProductionExecutorError(
            "trusted GitHub Actions runtime workflow identity mismatch"
        )

    run_id = str(runtime_env.get("GITHUB_RUN_ID") or "").strip()
    run_attempt = str(runtime_env.get("GITHUB_RUN_ATTEMPT") or "").strip()
    if not run_id.isdigit() or int(run_id) <= 0:
        raise ProductionExecutorError("trusted GitHub Actions runtime GITHUB_RUN_ID is invalid")
    if not run_attempt.isdigit() or int(run_attempt) <= 0:
        raise ProductionExecutorError("trusted GitHub Actions runtime GITHUB_RUN_ATTEMPT is invalid")

    minted_invocation = (
        f"gha:{repo}:run:{run_id}:attempt:{run_attempt}:"
        f"workflow:{workflow_ref}:ref:{ref_name}"
    )
    rebound = deepcopy(request)
    rebound["invocation_identity"] = minted_invocation
    for key in fresh_fields:
        payload = rebound[key]
        assert isinstance(payload, dict)
        payload["invocation_identity"] = minted_invocation
    return rebound


def _fetch_issue_snapshot(repo: str, token: str, issue: int) -> dict[str, object]:
    url = f"https://api.github.com/repos/{repo}/issues/{int(issue)}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "whd-flow-v2-ingress",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProductionExecutorError(
            f"DISPATCH_READY Issue readback failed: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProductionExecutorError("DISPATCH_READY Issue readback must be an object")
    payload["issue_number"] = int(payload.get("number") or issue)
    return {str(k): v for k, v in payload.items()}


def _fetch_issue_comment(repo: str, token: str, comment_id: int) -> dict[str, object]:
    url = f"https://api.github.com/repos/{repo}/issues/comments/{comment_id}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "whd-flow-v2-ingress",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProductionExecutorError(
            f"scheduler Phase6 receipt comment readback failed: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProductionExecutorError("scheduler Phase6 receipt comment must be an object")
    return {str(k): v for k, v in payload.items()}


def _receipt_from_trusted_comment(
    comment: dict[str, object],
    *,
    issue: int,
    comment_id: int,
) -> dict[str, object]:
    if int(comment.get("id") or 0) != int(comment_id):
        raise ProductionExecutorError("scheduler Phase6 receipt comment id mismatch")
    user = comment.get("user")
    if not isinstance(user, dict) or str(user.get("login") or "") != TRUSTED_PHASE6_COMMENT_AUTHOR:
        raise ProductionExecutorError("scheduler Phase6 receipt comment author is not trusted Actions")
    issue_url = str(comment.get("issue_url") or "")
    if not issue_url.endswith(f"/issues/{int(issue)}"):
        raise ProductionExecutorError("scheduler Phase6 receipt comment Issue mismatch")
    body = str(comment.get("body") or "").strip()
    lines = body.splitlines()
    if not lines or lines[0].strip() != REMOTE_PHASE6_RESULT_MARKER:
        raise ProductionExecutorError("scheduler Phase6 receipt comment marker mismatch")
    try:
        start = lines.index("~~~json") + 1
        end = lines.index("~~~", start)
    except ValueError as exc:
        raise ProductionExecutorError("scheduler Phase6 receipt comment JSON fence missing") from exc
    try:
        payload = json.loads("\n".join(lines[start:end]))
    except json.JSONDecodeError as exc:
        raise ProductionExecutorError("scheduler Phase6 receipt comment JSON invalid") from exc
    if not isinstance(payload, dict):
        raise ProductionExecutorError("scheduler Phase6 receipt payload must be an object")
    return {str(k): v for k, v in payload.items()}


def _resolve_scheduler_preflight_receipt_ref(
    request: dict[str, object],
    *,
    repo: str,
    token: str,
) -> dict[str, object]:
    ref = request.get("scheduler_preflight_receipt_ref")
    if ref is None:
        return request
    if request.get("schema") != INTENT_SCHEMA:
        raise ProductionExecutorError(
            "scheduler Phase6 receipt reference is only valid on semantic transaction intent"
        )
    if "preflight_evidence" in request:
        raise ProductionExecutorError(
            "scheduler transaction intent must not carry both preflight_evidence and receipt reference"
        )
    if not isinstance(ref, dict) or ref.get("schema") != SCHEDULER_PREFLIGHT_RECEIPT_REF_SCHEMA:
        raise ProductionExecutorError("scheduler Phase6 receipt reference schema mismatch")

    lane_id = str(request.get("lane_id") or "").strip()
    if execution_mode_for_lane(lane_id) != "SCHEDULER_LANE":
        raise ProductionExecutorError("scheduler Phase6 receipt reference requires scheduler lane")

    raw_comment_id = ref.get("comment_id")
    if isinstance(raw_comment_id, bool):
        raise ProductionExecutorError("scheduler Phase6 receipt comment_id must be positive")
    try:
        comment_id = int(raw_comment_id)
    except (TypeError, ValueError) as exc:
        raise ProductionExecutorError("scheduler Phase6 receipt comment_id must be positive") from exc
    if comment_id <= 0:
        raise ProductionExecutorError("scheduler Phase6 receipt comment_id must be positive")

    request_id = str(ref.get("request_id") or "").strip()
    branch = str(ref.get("branch") or "").strip()
    head_sha = str(ref.get("head_sha") or "").strip().lower()
    if not request_id or not branch or not head_sha:
        raise ProductionExecutorError(
            "scheduler Phase6 receipt reference requires request_id + branch + head_sha"
        )

    live_head = _read_branch_head(repo, token, branch).lower()
    if live_head != head_sha:
        raise ProductionExecutorError(
            f"scheduler Phase6 receipt live branch/head drift: expected {head_sha}, observed {live_head}"
        )

    comment = _fetch_issue_comment(repo, token, comment_id)
    receipt = _receipt_from_trusted_comment(
        comment,
        issue=int(request["issue"]),
        comment_id=comment_id,
    )
    try:
        rebound = rebind_scheduler_phase6_preflight_receipt(
            receipt,
            issue=int(request["issue"]),
            lane_id=lane_id,
            invocation_identity=str(request["invocation_identity"]),
            branch=branch,
            head_sha=head_sha,
            request_id=request_id,
        )
    except (TypeError, ValueError) as exc:
        raise ProductionExecutorError(
            f"scheduler Phase6 receipt rejected: {exc}"
        ) from exc

    resolved = deepcopy(request)
    resolved["preflight_evidence"] = rebound
    return resolved


def _prevalidate_repository_content_git_write_receipt(
    request: dict[str, object], *, execution_mode: str
) -> None:
    """Fail closed on the root-local-first receipt before any execution-state read."""
    if str(request.get("kind") or "") not in REPOSITORY_CONTENT_GIT_WRITE_KINDS:
        return
    effect = request.get("effect")
    if not isinstance(effect, dict):
        raise ProductionExecutorError("effect must be an object")
    receipt = effect.get("root_local_first_git_write_receipt")
    if receipt is None:
        raise ProductionExecutorError(
            f"{execution_mode} repository-content Git write requires root-local-first Git write receipt"
        )
    try:
        validate_git_unlock_receipt(receipt)
    except ValueError as exc:
        raise ProductionExecutorError(f"root-local-first Git write receipt rejected: {exc}") from exc


def _validate_repository_content_git_write_receipt(
    request: dict[str, object],
    *,
    execution_mode: str,
    record,
    repo: str,
    token: str,
) -> None:
    if str(request.get("kind") or "") not in REPOSITORY_CONTENT_GIT_WRITE_KINDS:
        return
    effect = request.get("effect")
    if not isinstance(effect, dict):
        raise ProductionExecutorError("effect must be an object")
    receipt = effect.get("root_local_first_git_write_receipt")
    if receipt is None:
        raise ProductionExecutorError(
            f"{execution_mode} repository-content Git write requires root-local-first Git write receipt"
        )
    try:
        validated_receipt = validate_git_unlock_receipt(receipt)
    except ValueError as exc:
        raise ProductionExecutorError(f"root-local-first Git write receipt rejected: {exc}") from exc

    guard = effect.get("mutation_writer_guard")
    kind = str(request.get("kind") or "")
    invocation = str(request.get("invocation_identity") or "")
    assert_mutation_writer_guard(record, guard, kind=kind, invocation_identity=invocation)

    if int(validated_receipt.get("issue") or 0) != record.issue:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt issue drift")

    # ROOT_LOCAL_FIRST evidence is freeze-time content provenance.  A same-scope
    # ACQUIRE may renew the lease and advance ExecutionRecord.generation without
    # changing the tested source, reservation, or frozen diff.  Current writer
    # identity is fenced above by mutation_writer_guard; do not re-bind historical
    # root evidence to the renewed generation/fingerprint.
    receipt_generation = int(validated_receipt.get("generation") or 0)
    if receipt_generation > record.generation:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt future generation")

    scope = record.mutation_scope
    if scope is None or scope.reservation_state != "ACTIVE":
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt requires ACTIVE reservation")
    if str(validated_receipt.get("source_sha") or "") != scope.base_sha:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt source/base drift")
    if str(validated_receipt.get("target_branch") or "") != scope.target_branch:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt target branch drift")
    if tuple(validated_receipt.get("write_paths") or ()) != tuple(scope.write_paths) or tuple(
        validated_receipt.get("delete_paths") or ()
    ) != tuple(scope.delete_paths):
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt reserved paths drift")

    frozen_diff = ""
    if record.next_action is not None:
        frozen_diff = str(record.next_action.args.get("diff_digest") or "").strip().lower()
    if frozen_diff and str(validated_receipt.get("diff_digest") or "").strip().lower() != frozen_diff:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt diff digest drift")

    live_target = _read_branch_head(repo, token, record.target_branch)
    if live_target != record.target_sha or live_target != str(guard.get("expected_target_head") or ""):
        raise ControlTransactionConflict(
            f"STALE_PLAN_MUST_DIE live target drift: expected {record.target_sha}, observed {live_target}"
        )

    expected_post_head = str(effect.get("head_sha") or "").strip()
    if not expected_post_head:
        raise ProductionExecutorError(f"{kind} effect requires head_sha for writer guard")
    live_work = _read_branch_head(repo, token, record.work_branch)
    if live_work != expected_post_head:
        raise ControlTransactionConflict(
            "ONE_ISSUE_ONE_MUTATION_WRITER live work head changed before ingress: "
            f"expected {expected_post_head}, observed {live_work}"
        )



def _session_reuse_requested(request: dict[str, object]) -> bool:
    payload = request.get("session_reuse")
    if payload is None:
        return False
    if not isinstance(payload, dict):
        raise ProductionExecutorError("session_reuse must be an object")
    if payload.get("schema") != SESSION_REUSE_SCHEMA:
        raise ProductionExecutorError("unexpected session_reuse schema")
    if payload.get("mode") != "LIVE_LEASE_CONTINUATION":
        raise ProductionExecutorError("unsupported session_reuse mode")
    kind = str(request.get("kind") or "")
    if kind not in SESSION_REUSE_KINDS:
        raise ProductionExecutorError(f"transaction kind {kind} requires fresh admission")
    if any(key in request for key in ("startup_evidence", "preflight_evidence", "startup_transition")):
        raise ProductionExecutorError("session reuse must not carry fresh startup/preflight evidence")
    return True


def _validate_live_session_reuse(record, *, request: dict[str, object]) -> None:
    invocation = str(request.get("invocation_identity") or "").strip()
    lane_id = str(request.get("lane_id") or "").strip()
    if record.state == "DONE":
        raise ProductionExecutorError("session reuse cannot mutate DONE record")
    if record.lease is None:
        raise ProductionExecutorError("session reuse requires active live lease")
    if record.lease.invocation_identity != invocation:
        raise ControlTransactionConflict("session reuse live lease belongs to a different invocation")
    try:
        expires = datetime.fromisoformat(record.lease.expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductionExecutorError("session reuse lease expiry is invalid") from exc
    if expires.tzinfo is None or expires.utcoffset() is None:
        raise ProductionExecutorError("session reuse lease expiry must be timezone-aware")
    if expires <= datetime.now(timezone.utc):
        raise ControlTransactionConflict("session reuse lease expired; fresh ACQUIRE required")
    if record.owner_kind != "SCHEDULER" or record.owner_id != lane_id or record.lane_id != lane_id:
        raise ControlTransactionConflict("session reuse owner/lane identity mismatch")

def _text_field(payload: dict[str, object], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ControlTransactionConflict(f"STALE_PLAN_MUST_DIE stale-record reconcile proof missing {key}")
    return value


def _validate_stale_record_live_target_reconcile_bridge(
    *,
    request: dict[str, object],
    record,
    repo: str,
    token: str,
    stale_identity_error: ValueError,
) -> bool:
    """Allow only explicit RECONCILE closure recovery from stale record identity."""
    if not str(stale_identity_error).startswith("STARTUP_TRANSITION_STALE_IDENTITY "):
        return False
    if str(request.get("kind") or "") != "RECONCILE":
        return False

    effect = request.get("effect")
    if not isinstance(effect, dict):
        raise ProductionExecutorError("effect must be an object")
    proof = effect.get("stale_record_live_target_reconcile_proof")
    if not isinstance(proof, dict):
        return False
    if proof.get("schema") != STALE_RECORD_LIVE_TARGET_RECONCILE_PROOF_SCHEMA:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile proof schema mismatch")

    transition = request.get("startup_transition")
    if not isinstance(transition, dict):
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile requires startup transition")

    if int(proof.get("issue") or 0) != int(record.issue):
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile issue mismatch")

    live_target_branch = _text_field(proof, "live_target_branch")
    live_target_sha = _text_field(proof, "live_target_sha").lower()
    if live_target_branch != record.target_branch:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile target branch mismatch")

    if str(transition.get("branch") or "").strip() != live_target_branch:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile transition branch mismatch")
    if str(transition.get("head_sha") or "").strip().lower() != live_target_sha:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile transition head mismatch")

    stale_source_branch = _text_field(proof, "stale_source_branch")
    stale_source_sha = _text_field(proof, "stale_source_sha").lower()
    stale_target_branch = _text_field(proof, "stale_target_branch")
    stale_target_sha = _text_field(proof, "stale_target_sha").lower()
    if stale_source_branch != record.source_branch or stale_source_sha != str(record.source_sha).lower():
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile source identity mismatch")
    if stale_target_branch != record.target_branch or stale_target_sha != str(record.target_sha).lower():
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale-record reconcile target identity mismatch")

    observed_live_target = _read_branch_head(repo, token, live_target_branch).lower()
    if observed_live_target != live_target_sha:
        raise ControlTransactionConflict(
            f"STALE_PLAN_MUST_DIE stale-record reconcile live target drift: expected {live_target_sha}, observed {observed_live_target}"
        )
    if not _is_ancestor(repo, token, stale_target_sha, live_target_sha):
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale target is not ancestor of live target")
    if not _is_ancestor(repo, token, stale_source_sha, live_target_sha):
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE stale source is not ancestor of live target")
    return True




def _build_dispatch_ready_ingress_request(
    request: dict[str, object],
    *,
    execution_mode: str,
    repo: str,
    token: str,
) -> DispatchIngressRequest:
    """Bind missing-record READY creation to the already-validated startup identity."""
    effect = dict(request["effect"])
    authority_kind = str(effect.get("authority_kind") or "").strip()
    authority_ref = str(effect.get("authority_ref") or "").strip()
    if not authority_kind:
        raise ProductionExecutorError("DISPATCH_READY effect requires authority_kind")
    if not authority_ref:
        raise ProductionExecutorError("DISPATCH_READY effect requires authority_ref")

    transition = request.get("startup_transition")
    if not isinstance(transition, dict):
        raise ProductionExecutorError("DISPATCH_READY requires startup_transition")
    branch = str(transition.get("branch") or "").strip()
    head_sha = str(transition.get("head_sha") or "").strip()
    if not branch or not head_sha:
        raise ProductionExecutorError("DISPATCH_READY startup transition identity is incomplete")

    issue = int(request["issue"])
    lane_id = str(request["lane_id"])
    if execution_mode == "SCHEDULER_LANE":
        issue_snapshot = _fetch_issue_snapshot(repo, token, issue)
        try:
            candidate = build_scheduler_dispatch_candidate(
                issue_snapshot,
                repository_owner=repo.split("/", 1)[0],
                source_branch=branch,
                source_sha=head_sha,
                target_branch=branch,
                target_sha=head_sha,
            )
        except SchedulerIssueCandidateError as exc:
            raise ProductionExecutorError(
                f"DISPATCH_READY scheduler authority rejected: {exc}"
            ) from exc
        if not candidate.matches_lane(lane_id):
            raise ProductionExecutorError(
                "DISPATCH_READY scheduler marker does not authorize this lane"
            )
        canonical = candidate.ingress_request
        for key, expected in (
            ("authority_kind", canonical.authority_kind),
            ("authority_ref", canonical.authority_ref),
            ("work_branch", canonical.work_branch),
        ):
            supplied = effect.get(key)
            if supplied not in (None, "", expected):
                raise ProductionExecutorError(
                    f"DISPATCH_READY scheduler effect {key} conflicts with live Issue authority"
                )
        return canonical
    elif execution_mode == "INTERACTIVE":
        execution_intent = "EXECUTE_TICKET"
        slot_id = INTERACTIVE_SLOT_BY_LANE.get(lane_id)
        if slot_id is None:
            raise ProductionExecutorError("DISPATCH_READY interactive lane has no canonical work slot")
        supplied_slot = effect.get("slot_id")
        if supplied_slot not in (None, "", slot_id):
            raise ProductionExecutorError("DISPATCH_READY effect slot_id conflicts with request lane")
        default_work_branch = f"work/issue-{issue}"
    else:
        raise ProductionExecutorError(
            f"DISPATCH_READY unsupported execution mode: {execution_mode}"
        )

    work_branch = str(effect.get("work_branch") or default_work_branch).strip()
    if not work_branch:
        raise ProductionExecutorError("DISPATCH_READY work_branch must be nonblank")

    return DispatchIngressRequest(
        issue=issue,
        execution_intent=execution_intent,
        authority_kind=authority_kind,
        authority_ref=authority_ref,
        source_branch=branch,
        source_sha=head_sha,
        work_branch=work_branch,
        target_branch=branch,
        target_sha=head_sha,
        parent_issue=effect.get("parent_issue"),
        slot_id=slot_id,
        created_at=str(transition.get("issued_at") or "").strip() or None,
        dispatch_transport=str(
            effect.get("dispatch_transport") or CANONICAL_DISPATCH_TRANSPORT
        ).strip(),
    )

def _load_request(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProductionExecutorError("request must be a JSON object")
    schema = payload.get("schema")
    if schema not in {REQUEST_SCHEMA, INTENT_SCHEMA}:
        raise ProductionExecutorError("unexpected request schema")
    for key in ("request_id","issue","kind","lane_id","invocation_identity","expected_coord_head","expected_generation","effect"):
        if key not in payload:
            raise ProductionExecutorError(f"request missing {key}")
    kind = str(payload["kind"])
    if kind not in ALLOWED_KINDS:
        raise ProductionExecutorError("unsupported transaction kind")
    if not isinstance(payload["effect"], dict):
        raise ProductionExecutorError("effect must be an object")

    delete_stale_intent = payload["effect"].get("delete_stale_work_branch")
    if delete_stale_intent is not None:
        if kind != "RELEASE_PATHS" or delete_stale_intent is not True:
            raise ProductionExecutorError(
                "delete_stale_work_branch is only valid as true on RELEASE_PATHS"
            )

    if schema == REQUEST_SCHEMA:
        reuse = _session_reuse_requested(payload)
        if kind != "SEED" and not reuse:
            missing = [key for key in ("startup_evidence", "preflight_evidence", "startup_transition") if key not in payload]
            if missing:
                raise ProductionExecutorError(f"request missing fresh admission field: {missing[0]}")
        return payload

    if kind == "SEED":
        raise ProductionExecutorError("semantic intent does not support SEED")
    if "startup_evidence" in payload or "startup_transition" in payload:
        raise ProductionExecutorError("semantic intent must not supply startup_evidence/startup_transition")
    reuse = payload.get("reuse_admission_session") is True
    if not reuse:
        for key in ("purpose", "work_root_gate_evidence"):
            if key not in payload:
                raise ProductionExecutorError(f"transaction intent missing {key}")
        if not isinstance(payload["work_root_gate_evidence"], dict):
            raise ProductionExecutorError("work_root_gate_evidence must be an object")
        has_preflight = "preflight_evidence" in payload
        has_receipt_ref = "scheduler_preflight_receipt_ref" in payload
        if has_preflight == has_receipt_ref:
            raise ProductionExecutorError(
                "transaction intent requires exactly one of preflight_evidence or scheduler_preflight_receipt_ref"
            )
        if has_preflight and not isinstance(payload["preflight_evidence"], dict):
            raise ProductionExecutorError("preflight_evidence must be an object")
        if has_receipt_ref and not isinstance(payload["scheduler_preflight_receipt_ref"], dict):
            raise ProductionExecutorError("scheduler_preflight_receipt_ref must be an object")
    return payload


def _materialize_request(request: dict[str, object], *, repo: str) -> dict[str, object]:
    if request.get("schema") == REQUEST_SCHEMA:
        return request
    try:
        return build_control_transaction_request_from_intent(request, repository=repo)
    except (TypeError, ValueError) as exc:
        raise ProductionExecutorError(f"transaction intent rejected: {exc}") from exc


def execute_request(
    *,
    request: dict[str, object],
    repo: str,
    token: str,
    coord_branch: str,
    trusted_runtime_env=None,
    request_branch: str | None = None,
) -> dict[str, object]:
    request = _resolve_scheduler_preflight_receipt_ref(
        request,
        repo=repo,
        token=token,
    )
    request = _materialize_request(request, repo=repo)
    request = _bind_trusted_github_actions_runtime_provenance(
        request,
        repo=repo,
        request_branch=request_branch,
        runtime_env=trusted_runtime_env,
    )
    if str(request["kind"]) == "SEED":
        if int(request["issue"]) != 0:
            raise ProductionExecutorError("SEED request issue must be 0")
        return {
            "schema": "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2",
            "result": "APPLIED",
            "reason": "SEED_NOOP",
            "issue": 0,
            "generation_before": int(request["expected_generation"]),
            "generation_after": int(request["expected_generation"]),
            "transaction": {"status": "RECONCILED", "kind": "SEED"},
        }

    execution_mode = _execution_mode_for_request(request)
    reuse_session = _session_reuse_requested(request)
    if not reuse_session:
        startup_payload = request.get("startup_evidence")
        if isinstance(startup_payload, dict):
            root_payload = startup_payload.get("work_root_gate")
            if (
                isinstance(root_payload, dict)
                and str(root_payload.get("scope") or "") == "CONTROL_PLANE_ONLY"
                and str(request["kind"]) != "DISPATCH_READY"
            ):
                raise ProductionExecutorError(
                    "control-plane-only admission is restricted to DISPATCH_READY"
                )
        try:
            validate_startup_evidence(
                request.get("startup_evidence"),
                invocation_identity=str(request["invocation_identity"]),
                execution_mode=execution_mode,
                repository=repo,
            )
            validate_phase6_preflight_evidence(
                request.get("preflight_evidence"),
                issue=int(request["issue"]),
                invocation_identity=str(request["invocation_identity"]),
            )
            validate_startup_transition(
                request.get("startup_transition"),
                invocation_identity=str(request["invocation_identity"]),
                issue=int(request["issue"]),
                execution_mode=execution_mode,
                repository=repo,
            )
        except ValueError as exc:
            raise ProductionExecutorError(f"startup hard gate rejected request: {exc}") from exc

    _prevalidate_repository_content_git_write_receipt(
        request, execution_mode=execution_mode
    )

    parent_sha, _, records = _load_state(repo, token, coord_branch)
    expected_parent = str(request["expected_coord_head"])
    if parent_sha != expected_parent:
        raise ControlTransactionConflict(
            f"coord head drift: expected {expected_parent}, observed {parent_sha}"
        )

    issue = int(request["issue"])
    record = records.get(issue)
    expected_generation = int(request["expected_generation"])
    kind = str(request["kind"])
    if record is None:
        if kind == "DISPATCH_READY":
            if expected_generation != 1:
                raise ProductionExecutorError(
                    "DISPATCH_READY missing-record bootstrap requires expected_generation=1"
                )
            ingress_request = _build_dispatch_ready_ingress_request(
                request,
                execution_mode=execution_mode,
                repo=repo,
                token=token,
            )
            return dispatch_ready_missing_record(
                repo=repo,
                token=token,
                coord_branch=coord_branch,
                issue=issue,
                expected_coord_head=expected_parent,
                ingress_request=ingress_request,
            )
        if kind != "RECOVER_POST_DELIVERY":
            raise ProductionExecutorError(f"native ExecutionRecord missing for issue {issue}")
        if expected_generation != 1:
            raise ProductionExecutorError(
                "RECOVER_POST_DELIVERY missing-record bootstrap requires expected_generation=1"
            )
        recovery = recover_post_delivery_missing_record(
            repo=repo,
            token=token,
            coord_branch=coord_branch,
            issue=issue,
            lane_id=str(request["lane_id"]),
            invocation_identity=str(request["invocation_identity"]),
            expected_coord_head=expected_parent,
            supplied_effect=dict(request["effect"]),
        )
        if (
            recovery.get("post_state") != "INTEGRATING"
            or recovery.get("post_next_action") != "FINALIZE"
        ):
            raise ProductionExecutorError(
                "RECOVER_POST_DELIVERY did not produce exact FINALIZE continuation"
            )
        terminal = execute_one(
            repo=repo,
            token=token,
            coord_branch=coord_branch,
            issue=issue,
            kind="FINALIZE",
            lane_id=str(request["lane_id"]),
            invocation_identity=str(request["invocation_identity"]),
            supplied_effect={},
            _allow_terminal_drain=False,
        )
        recovery["terminal_tail_drained"] = terminal.get("post_state") == "DONE"
        recovery["terminal_tail_finalize"] = {
            "coord_commit_sha": terminal.get("coord_commit_sha"),
            "post_generation": terminal.get("post_generation"),
            "post_state": terminal.get("post_state"),
            "post_next_action": terminal.get("post_next_action"),
            "runtime_observation_status": terminal.get("runtime_observation_status"),
        }
        recovery["post_generation"] = terminal.get("post_generation")
        recovery["post_state"] = terminal.get("post_state")
        recovery["post_next_action"] = terminal.get("post_next_action")
        recovery["lease_invocation_identity"] = terminal.get("lease_invocation_identity")
        return recovery
    if kind == "DISPATCH_READY":
        raise ControlTransactionConflict(
            f"DISPATCH_READY requires missing ExecutionRecord; issue {issue} already exists"
        )
    if kind == "RECOVER_POST_DELIVERY":
        raise ControlTransactionConflict(
            f"RECOVER_POST_DELIVERY requires missing ExecutionRecord; issue {issue} already exists"
        )
    if record.generation != expected_generation:
        raise ControlTransactionConflict(
            f"generation drift: expected {expected_generation}, observed {record.generation}"
        )
    if reuse_session:
        _validate_live_session_reuse(record, request=request)
    else:
        try:
            assert_startup_transition_matches_record(
                request.get("startup_transition"),
                issue=record.issue,
                source_branch=record.source_branch,
                source_sha=record.source_sha,
                work_branch=record.work_branch,
                head_sha=record.head_sha,
                target_branch=record.target_branch,
                target_sha=record.target_sha,
            )
        except ValueError as exc:
            if not _validate_stale_record_live_target_reconcile_bridge(
                request=request,
                record=record,
                repo=repo,
                token=token,
                stale_identity_error=exc,
            ):
                raise ControlTransactionConflict(str(exc)) from exc

    _validate_repository_content_git_write_receipt(
        request,
        execution_mode=execution_mode,
        record=record,
        repo=repo,
        token=token,
    )

    return execute_one(
        repo=repo,
        token=token,
        coord_branch=coord_branch,
        issue=issue,
        kind=str(request["kind"]),
        lane_id=str(request["lane_id"]),
        invocation_identity=str(request["invocation_identity"]),
        supplied_effect=dict(request["effect"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coord-branch", default="coord/execution-v2")
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repo or not token:
        raise SystemExit("GITHUB_REPOSITORY and GITHUB_TOKEN are required")

    try:
        request = _load_request(args.request_file)
        request_branch = os.environ.get("GITHUB_REF_NAME", "").strip()
        if not request_branch:
            raise ProductionExecutorError("GITHUB_REF_NAME is required for push request branch binding")
        _validate_request_branch(request=request, request_branch=request_branch)
        result = execute_request(
            request=request,
            repo=repo,
            token=token,
            coord_branch=args.coord_branch,
            trusted_runtime_env=os.environ,
            request_branch=request_branch,
        )
        result["request_id"] = request["request_id"]
        code = 0
    except ControlTransactionConflict as exc:
        reason = str(exc)
        if reason.startswith("coord head drift"):
            conflict_class = "STALE_COORD_HEAD"
        elif reason.startswith("generation drift"):
            conflict_class = "STALE_GENERATION"
        elif "live lease" in reason:
            conflict_class = "LIVE_LEASE"
        elif reason.startswith("merge precheck required checks pending:"):
            conflict_class = "REQUIRED_CHECKS_PENDING"
        elif reason.startswith("merge precheck PR is not mergeable"):
            conflict_class = "PR_NOT_MERGEABLE"
        elif reason.startswith("SYNC_TARGET target drift:"):
            conflict_class = "TARGET_DRIFT"
        elif reason.startswith("SYNC_TARGET work head drift:"):
            conflict_class = "WORK_HEAD_DRIFT"
        else:
            conflict_class = "STALE_EXECUTION_RECORD"
        result = {
            "schema": "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2",
            "result": "CONFLICT",
            "reason": reason,
            "conflict_class": conflict_class,
            "retryable": True,
            "retry_action": (
                "POLL_REQUIRED_CHECKS"
                if conflict_class == "REQUIRED_CHECKS_PENDING"
                else "FRESH_READ_REBUILD_SAME_SEMANTIC_ACTION"
            ),
            "semantic_effect_applied": False,
        }
        code = 3
    except Exception as exc:
        reason = str(exc)
        result = {
            "schema": "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2",
            "result": "FAILED",
            "reason": reason,
            "error_class": (
                "STARTUP_EVIDENCE_INVALID"
                if reason.startswith("startup hard gate rejected request:")
                else "NON_RETRYABLE_REQUEST_FAILURE"
            ),
            "retryable": False,
        }
        code = 2

    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
