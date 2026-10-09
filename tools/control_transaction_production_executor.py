"""Trusted production writer for one WHD Flow v2 control transaction.


This is the missing production companion to the read-only terminal shadow.
It fresh-reads coord/execution-v2, binds a transaction to the exact canonical
record, applies the pure transaction semantics, and atomically commits both the
post-record and rebuilt DERIVED_CACHE_ONLY ready-index with a non-force ref CAS.
"""


from __future__ import annotations


import argparse
import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from tools.control_transaction import (
    ControlTransactionError,
    ControlTransactionConflict,
    ControlTransactionReplay,
    execute_transaction,
    is_control_only_finalize_record,
    prepare_transaction,
    CONTROL_ONLY_TARGET_READBACK_SCHEMA,
    MERGE_ANCHOR_PROOF_SCHEMA,
    MERGE_ANCHOR_CORRECTION_PROOF_SCHEMA,
    POST_DELIVERY_RECOVERY_MODE,
    POST_DELIVERY_RECOVERY_PROOF_SCHEMA,
    is_post_delivery_recovery_finalize_record,
)
from tools.flow_v2_pre_merge_recovery import build_pre_merge_recovery_ready_record
from tools.execution_dispatch_ingress import (
    DispatchIngressError,
    DispatchIngressRequest,
    plan_dispatch_ingress,
)
from tools.execution_ready_index import build_ready_index, ready_index_to_payload
from tools.execution_work_slot_view import FIXED_SLOT_IDS
from tools.execution_invocation_exit import (
    InvocationExitError,
    assert_active_owning_issue_sticky,
    released_stale_reset_residue,
    terminal_tail_active,
)
from tools.execution_path_reservation import (
    PathReservationError,
    require_no_path_reservation_conflict,
)
from tools.flow_v2_runtime_observation import (
    project_terminal_record_exit,
    project_transaction_progress,
)
from tools.flow_v2_merge_precheck import (
    ALREADY_MERGED,
    PR_IDENTITY_MISMATCH,
    PR_NOT_MERGEABLE,
    READY_TO_MERGE,
    REQUIRED_CHECKS_PENDING,
    TARGET_DRIFT,
    evaluate_merge_precheck,
    REQUIRED_PR_WORKFLOW_PATHS,
    assert_required_pr_ci_evidence,
    select_pr_workflows_for_changed_paths,
)
from tools.execution_record import (
    ActionSpec,
    ClosureState,
    ExecutionRecord,
    ExecutionRecordError,
    LeaseState,
    execution_record_fingerprint,
    execution_record_from_payload,
    execution_record_to_payload,
)


from tools.control_transaction_runtime import (
    PRE_TRANSITION_EXTERNAL_MUTATION_PATHS, RuntimeMode, resolve_runtime_effect,
    RuntimePostEffectConflict,
)


RESULT_SCHEMA = "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2"
MONITOR_BRANCH = "coord/monitor-v2"
_RECORD_RE = re.compile(r"^\.dispatch/execution/issue-(\d+)\.json$")




class ProductionExecutorError(RuntimeError):
    pass




def _now() -> datetime:
    return datetime.now(timezone.utc)




def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")




def _github_403_diagnostic(exc: HTTPError, *, method: str, path: str) -> str:
    """Allowlisted permission/rate-limit telemetry; never serialize raw API errors.

    API response bodies, requested URLs, tokens and unsanitized header values
    are deliberately omitted. GitHub may put sensitive text in any of them.
    """
    endpoint = "ACTIONS_RUN_READ" if re.fullmatch(r"/actions/runs/[0-9]+", path) else "OTHER_GITHUB_API"
    try:
        raw = exc.read(4096).decode("utf-8", errors="replace")
        message = str(json.loads(raw).get("message", "")).lower()
    except (ValueError, AttributeError, TypeError, UnicodeError):
        message = ""
    if "resource not accessible by integration" in message:
        classification = "INTEGRATION_PERMISSION_DENIED"
    elif "rate limit" in message:
        classification = "GITHUB_RATE_LIMIT"
    else:
        classification = "FORBIDDEN_UNCLASSIFIED"

    def safe_integer_header(name: str) -> str:
        value = str(exc.headers.get(name, "")).strip() if exc.headers else ""
        return value if value.isascii() and value.isdecimal() and len(value) <= 12 else "unknown"

    request_id = str(exc.headers.get("X-GitHub-Request-Id", "")) if exc.headers else ""
    if not re.fullmatch(r"[a-zA-Z0-9:-]{1,80}", request_id):
        request_id = "unavailable"
    permissions = str(exc.headers.get("X-Accepted-GitHub-Permissions", "")) if exc.headers else ""
    safe_permission = "actions:read" if "actions=read" in permissions.lower() else "unavailable"
    return (
        f"GITHUB_API_403 method={method if method in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'} else 'OTHER'} "
        f"endpoint={endpoint} class={classification} "
        f"rate_remaining={safe_integer_header('X-RateLimit-Remaining')} "
        f"retry_after_seconds={safe_integer_header('Retry-After')} "
        f"request_id={request_id} accepted_permissions={safe_permission}"
    )


def _api(repo: str, method: str, path: str, token: str, payload: object | None = None) -> Any:
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "whd-flow-v2-production-executor",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read()
    except HTTPError as exc:
        if exc.code != 403:
            raise
        raise ProductionExecutorError(
            _github_403_diagnostic(exc, method=method, path=path)
        ) from None
    return json.loads(raw.decode("utf-8")) if raw else None




def _read_blob(repo: str, token: str, sha: str) -> str:
    obj = _api(repo, "GET", f"/git/blobs/{sha}", token)
    if obj.get("encoding") != "base64":
        raise ProductionExecutorError("execution blob is not base64 encoded")
    return base64.b64decode(obj["content"]).decode("utf-8")




def _load_state(repo: str, token: str, coord_branch: str) -> tuple[str, str, dict[int, ExecutionRecord]]:
    encoded = quote(coord_branch, safe="")
    ref = _api(repo, "GET", f"/git/ref/heads/{encoded}", token)
    parent_sha = ref["object"]["sha"]
    commit = _api(repo, "GET", f"/git/commits/{parent_sha}", token)
    tree_sha = commit["tree"]["sha"]
    tree = _api(repo, "GET", f"/git/trees/{tree_sha}?recursive=1", token)
    records: dict[int, ExecutionRecord] = {}
    for entry in tree.get("tree", []):
        if entry.get("type") != "blob":
            continue
        match = _RECORD_RE.fullmatch(str(entry.get("path") or ""))
        if not match:
            continue
        payload = json.loads(_read_blob(repo, token, entry["sha"]))
        record = execution_record_from_payload(payload)
        records[record.issue] = record
    return parent_sha, tree_sha, records




def _action_payload(action: ActionSpec | None) -> dict[str, object] | None:
    if action is None:
        return None
    return {"kind": action.kind, "args": dict(action.args), "display": action.display}




def _monitor_path(source: str) -> str:
    return f".dispatch/monitor/runtime/{source}.json"




def _read_monitor_observation(repo: str, token: str, source: str) -> tuple[dict[str, object] | None, str | None]:
    path = _monitor_path(source)
    encoded_path = quote(path, safe="/")
    encoded_ref = quote(MONITOR_BRANCH, safe="")
    try:
        row = _api(repo, "GET", f"/contents/{encoded_path}?ref={encoded_ref}", token)
    except HTTPError as exc:
        if exc.code == 404:
            return None, None
        raise
    if str(row.get("encoding") or "") != "base64":
        raise ProductionExecutorError("runtime observation is not base64 encoded")
    payload = json.loads(base64.b64decode(str(row["content"])).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ProductionExecutorError("runtime observation must be a JSON object")
    return payload, str(row.get("sha") or "") or None




def _write_monitor_observation(repo: str, token: str, observation: dict[str, object]) -> str:
    source = str(observation.get("source") or "")
    if not source:
        raise ProductionExecutorError("runtime observation source is missing")
    path = _monitor_path(source)
    encoded_path = quote(path, safe="/")
    body = json.dumps(observation, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    content = base64.b64encode(body.encode("utf-8")).decode("ascii")


    last_error: Exception | None = None
    for _ in range(3):
        _, current_sha = _read_monitor_observation(repo, token, source)
        payload: dict[str, object] = {
            "message": f"monitor: {source} {observation.get('event')} issue {observation.get('issue')}",
            "content": content,
            "branch": MONITOR_BRANCH,
        }
        if current_sha:
            payload["sha"] = current_sha
        try:
            result = _api(repo, "PUT", f"/contents/{encoded_path}", token, payload)
            return str(result["commit"]["sha"])
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {409, 422}:
                raise
    raise ProductionExecutorError(
        f"runtime observation CAS failed after retries: {last_error}"
    )




def _publish_transaction_progress(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
    invocation_identity: str,
    runtime_owner: str,
    action: str,
) -> tuple[str, dict[str, object]]:
    has_delivery_continuation = (
        record.state == "DONE"
        and record.chain.next_issue is not None
        and record.chain.next_action is not None
    )
    projector = (
        project_terminal_record_exit
        if record.state == "DONE" and not has_delivery_continuation
        else project_transaction_progress
    )
    provisional = projector(
        record=record,
        invocation_identity=invocation_identity,
        runtime_owner=runtime_owner,
        action=action,
        previous=None,
    )
    previous, _ = _read_monitor_observation(repo, token, str(provisional["source"]))
    observation = projector(
        record=record,
        invocation_identity=invocation_identity,
        runtime_owner=runtime_owner,
        action=action,
        previous=previous,
    )
    commit_sha = _write_monitor_observation(repo, token, observation)
    return commit_sha, observation




def _normalize_effect(
    record: ExecutionRecord,
    *,
    kind: str,
    lane_id: str,
    invocation_identity: str,
    supplied: dict[str, object],
) -> dict[str, object]:
    effect = dict(supplied)
    now = _now()
    effect.setdefault("updated_at", _iso(now))


    if kind == "ACQUIRE":
        if record.state != "READY":
            if record.owner_kind != "SCHEDULER" or record.owner_id != lane_id or record.lane_id != lane_id:
                raise ProductionExecutorError("same-lane ACQUIRE owner/lane mismatch")
            next_action = _action_payload(record.next_action)
            owner_kind, owner_id, record_lane = record.owner_kind, record.owner_id, record.lane_id
        else:
            owner_kind, owner_id, record_lane = "SCHEDULER", lane_id, lane_id
            bound_post_acquire = None
            if record.next_action is not None and record.next_action.kind == "ACQUIRE":
                candidate = record.next_action.args.get("post_acquire")
                if candidate is not None:
                    if not isinstance(candidate, dict):
                        raise ProductionExecutorError(
                            "READY ACQUIRE bound post-acquire continuation must be an object"
                        )
                    bound_post_acquire = dict(candidate)
            supplied_next_action = effect.get("next_action")
            if bound_post_acquire is not None:
                if supplied_next_action is not None and supplied_next_action != bound_post_acquire:
                    raise ProductionExecutorError(
                        "READY ACQUIRE caller next_action conflicts with bound post-acquire continuation"
                    )
                next_action = bound_post_acquire
                if (
                    str(next_action.get("kind") or "").strip() == "FINALIZE"
                    and str((next_action.get("args") or {}).get("completion_mode") or "").strip().upper()
                    == "CONTROL_ONLY"
                    and effect.get("admission_reservation") is not None
                ):
                    raise ProductionExecutorError(
                        "CONTROL_ONLY bound post-acquire continuation forbids admission reservation"
                    )
            else:
                next_action = supplied_next_action
                if not isinstance(next_action, dict):
                    raise ProductionExecutorError(
                        "READY ACQUIRE requires explicit or ingress-bound post-acquire next_action"
                    )
        effect.update(
            {
                "observed_at": _iso(now),
                "owner_kind": owner_kind,
                "owner_id": owner_id,
                "lane_id": record_lane,
                "slot_id": record.slot_id,
                "semantic_state": record.semantic_state if record.state != "READY" else str(effect.get("semantic_state") or "CLAIMED"),
                "next_action": next_action,
                "lease": {
                    "token": f"lease:{record.issue}:{os.environ.get('GITHUB_RUN_ID','local')}:{os.environ.get('GITHUB_RUN_ATTEMPT','1')}",
                    "invocation_identity": invocation_identity,
                    "expires_at": _iso(now + timedelta(minutes=15)),
                },
            }
        )
    return effect






def _require_current_invocation_lease(
    record: ExecutionRecord,
    invocation_identity: str,
) -> None:
    if record.lease is None:
        raise ProductionExecutorError("trusted side effect requires an active Flow v2 lease")
    if record.lease.invocation_identity != invocation_identity:
        raise ControlTransactionConflict(
            "live lease belongs to a different invocation"
        )




def _read_branch_head(repo: str, token: str, branch: str) -> str:
    encoded = quote(branch, safe="")
    ref = _api(repo, "GET", f"/git/ref/heads/{encoded}", token)
    sha = str((ref.get("object") or {}).get("sha") or "").strip()
    if not sha:
        raise ProductionExecutorError(f"branch {branch!r} did not resolve to a SHA")
    return sha




def _is_ancestor(repo: str, token: str, ancestor: str, descendant: str) -> bool:
    """Return whether ``ancestor`` is proven to reach ``descendant``.


    This is used only for side-effect reconciliation after a trusted GitHub
    mutation may already have succeeded while the coord CAS lost a race.
    """
    if ancestor == descendant:
        return True
    compare = _api(repo, "GET", f"/compare/{ancestor}...{descendant}", token) or {}
    merge_base = str((compare.get("merge_base_commit") or {}).get("sha") or "").strip()
    return merge_base == ancestor




def _required_checks_for_target(
    repo: str,
    token: str,
    target_branch: str,
) -> list[str]:
    contexts: set[str] = set()
    target_ref = f"refs/heads/{target_branch}"
    try:
        summaries = _api(repo, "GET", "/rulesets", token) or []
        for summary in summaries:
            if str(summary.get("enforcement") or "").lower() != "active":
                continue
            ruleset_id = summary.get("id")
            if not ruleset_id:
                continue
            detail = _api(repo, "GET", f"/rulesets/{ruleset_id}", token) or {}
            conditions = detail.get("conditions") or {}
            ref_name = conditions.get("ref_name") or {}
            includes = set(ref_name.get("include") or [])
            excludes = set(ref_name.get("exclude") or [])
            if target_ref in excludes:
                continue
            if includes and target_ref not in includes and "~ALL" not in includes:
                continue
            for rule in detail.get("rules") or []:
                if rule.get("type") != "required_status_checks":
                    continue
                params = rule.get("parameters") or {}
                for item in params.get("required_status_checks") or []:
                    context = str(item.get("context") or "").strip()
                    if context:
                        contexts.add(context)
    except HTTPError:
        # GitHub Actions token permissions can make ruleset reads unavailable.
        # The protected production targets have a stable required context; this
        # fallback keeps the merge precheck fail-closed instead of silently
        # skipping required checks.
        pass


    if target_branch in {"main", "cleanup/2d-3d-sync"}:
        # Legacy branch-ruleset compatibility context. The workflow behind this
        # context no longer performs main/cleanup mirroring or ancestry checks.
        contexts.add("Governance Mirror Hard Gate")
    return sorted(contexts)




def _check_conclusions_for_head(
    repo: str,
    token: str,
    head_sha: str,
) -> dict[str, str]:
    """Use latest check run, never allow historical success to mask failure."""
    latest: dict[str, tuple[int, str]] = {}
    page = 1
    seen = 0
    while page <= 20:
        payload = _api(
            repo, "GET",
            f"/commits/{head_sha}/check-runs?per_page=100&page={page}",
            token,
        ) or {}
        rows = payload.get("check_runs")
        total = payload.get("total_count")
        if not isinstance(rows, list) or not isinstance(total, int) or total < 0:
            raise ControlTransactionConflict("PR_CI_CHECK_RUN_LIST_INCOMPLETE")
        for row in rows:
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            check_id = row.get("id")
            if not isinstance(check_id, int) or isinstance(check_id, bool):
                raise ControlTransactionConflict("PR_CI_CHECK_RUN_ID_MISSING")
            conclusion = str(row.get("conclusion") or "").strip().lower()
            if name not in latest or check_id > latest[name][0]:
                latest[name] = (check_id, conclusion)
        seen += len(rows)
        if seen >= total:
            if seen != total:
                raise ControlTransactionConflict("PR_CI_CHECK_RUN_LIST_INCOMPLETE")
            break
        if len(rows) != 100:
            raise ControlTransactionConflict("PR_CI_CHECK_RUN_LIST_INCOMPLETE")
        page += 1
    else:
        raise ControlTransactionConflict("PR_CI_CHECK_RUN_LIST_INCOMPLETE")
    return {name: conclusion for name, (_, conclusion) in latest.items()}



def _pr_body_closes_issue(body: object, issue: int) -> bool:
    text = str(body or "")
    return bool(
        re.search(
            rf"(?im)\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s+#\s*{issue}\b",
            text,
        )
    )



def _pr_body_closing_issues(body: object) -> tuple[int, ...]:
    text = str(body or "")
    values: list[int] = []
    for match in re.finditer(
        r"(?im)\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s+#\s*(\d+)\b",
        text,
    ):
        value = int(match.group(1))
        if value > 0 and value not in values:
            values.append(value)
    return tuple(values)



def _delivery_pr_number_for_finalize(record: ExecutionRecord) -> int | None:
    action = record.next_action
    if action is None or action.kind != "FINALIZE":
        return None
    pr_number = action.args.get("pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        return None
    return pr_number



def _discover_open_delivery_sibling(
    repo: str,
    token: str,
    *,
    issue: int,
    record: ExecutionRecord,
    records: dict[int, ExecutionRecord],
) -> tuple[int, int] | None:
    pr_number = _delivery_pr_number_for_finalize(record)
    if pr_number is None or not record.closure.merged_sha:
        return None
    pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}
    if pr.get("merged") is not True:
        raise ProductionExecutorError("FINALIZE sibling discovery requires merged PR")
    if str((pr.get("base") or {}).get("ref") or "").strip() != record.target_branch:
        raise ProductionExecutorError("FINALIZE sibling discovery PR base mismatch")
    merged_sha = str(pr.get("merge_commit_sha") or "").strip().lower()
    if merged_sha != str(record.closure.merged_sha).lower():
        raise ProductionExecutorError("FINALIZE sibling discovery merge anchor mismatch")
    closing = _pr_body_closing_issues(pr.get("body"))
    if issue not in closing:
        raise ProductionExecutorError("FINALIZE sibling discovery PR does not close current Issue")
    pivot = closing.index(issue)
    for candidate in closing[pivot + 1 :] + closing[:pivot]:
        if candidate in records:
            continue
        observed = _api(repo, "GET", f"/issues/{candidate}", token) or {}
        if observed.get("pull_request") is not None:
            continue
        if int(observed.get("number") or 0) != candidate:
            raise ProductionExecutorError("FINALIZE sibling Issue identity mismatch")
        if str(observed.get("state") or "").strip().lower() == "open":
            return candidate, pr_number
    return None



def _slot_for_lane(lane_id: str) -> str | None:
    return {
        "chatgpt.flowv2.work0": "worker.slot.0",
        "chatgpt.flowv2.work1": "worker.slot.1",
        "chatgpt.flowv2.work2": "worker.slot.2",
        "chatgpt.flowv2.work3": "worker.slot.3",
    }.get(lane_id)



def _build_post_delivery_recovery_record(
    repo: str,
    token: str,
    *,
    issue: int,
    lane_id: str,
    invocation_identity: str,
    supplied_effect: dict[str, object],
) -> ExecutionRecord:
    """Mint current-only recovery state from fresh GitHub delivery evidence.

    This deliberately does not reconstruct historical WAKE, lease, transaction,
    or QA acceptance.  The only lease created is the live recovery invocation.
    """
    pr_number = supplied_effect.get("pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ProductionExecutorError("RECOVER_POST_DELIVERY requires positive pr_number")

    pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}
    if pr.get("merged") is not True:
        raise ProductionExecutorError("RECOVER_POST_DELIVERY requires fresh merged PR readback")
    if str(pr.get("state") or "").strip().lower() != "closed":
        raise ProductionExecutorError("RECOVER_POST_DELIVERY merged PR must be closed")
    if not _pr_body_closes_issue(pr.get("body"), issue):
        raise ProductionExecutorError(
            "RECOVER_POST_DELIVERY PR body must contain an exact closing keyword for the Issue"
        )

    head = pr.get("head") or {}
    base = pr.get("base") or {}
    head_repo = head.get("repo") or {}
    head_ref = str(head.get("ref") or "").strip()
    head_sha = str(head.get("sha") or "").strip()
    target_branch = str(base.get("ref") or "").strip()
    merged_sha = str(pr.get("merge_commit_sha") or "").strip()
    if str(head_repo.get("full_name") or "").strip() != repo:
        raise ProductionExecutorError("RECOVER_POST_DELIVERY requires same-repository delivery PR")
    if not head_ref or not re.fullmatch(r"[0-9A-Za-z._/@-]+", head_ref):
        raise ProductionExecutorError("RECOVER_POST_DELIVERY PR head ref is invalid")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", head_sha):
        raise ProductionExecutorError("RECOVER_POST_DELIVERY PR head SHA is invalid")
    if target_branch != "cleanup/2d-3d-sync":
        raise ProductionExecutorError(
            "RECOVER_POST_DELIVERY delivery target must be cleanup/2d-3d-sync"
        )
    if not re.fullmatch(r"[0-9a-fA-F]{40}", merged_sha):
        raise ProductionExecutorError("RECOVER_POST_DELIVERY merge SHA is invalid")

    issue_readback = _api(repo, "GET", f"/issues/{issue}", token) or {}
    if issue_readback.get("pull_request") is not None:
        raise ProductionExecutorError("RECOVER_POST_DELIVERY issue identity resolves to a pull request")
    if int(issue_readback.get("number") or 0) != issue:
        raise ProductionExecutorError("RECOVER_POST_DELIVERY issue readback identity mismatch")

    observed_target = _read_branch_head(repo, token, target_branch)
    anchor_is_ancestor = observed_target == merged_sha or _is_ancestor(
        repo, token, merged_sha, observed_target
    )
    if not anchor_is_ancestor:
        raise ProductionExecutorError(
            "RECOVER_POST_DELIVERY merged anchor is not ancestor of current production target"
        )

    required_checks = _required_checks_for_target(repo, token, target_branch)
    conclusions = _check_conclusions_for_head(repo, token, head_sha)
    missing_or_red = [
        name for name in required_checks if conclusions.get(name) != "success"
    ]
    if missing_or_red:
        raise ProductionExecutorError(
            "RECOVER_POST_DELIVERY required checks are not GREEN: "
            + ",".join(missing_or_red)
        )

    observed_at = _iso(_now())
    lease_expires_at = _iso(_now() + timedelta(minutes=15))
    proof = {
        "schema": POST_DELIVERY_RECOVERY_PROOF_SCHEMA,
        "kind": POST_DELIVERY_RECOVERY_MODE,
        "issue": issue,
        "pr_number": pr_number,
        "pr_head_ref": head_ref,
        "pr_head_sha": head_sha.lower(),
        "target_branch": target_branch,
        "observed_target_sha": observed_target.lower(),
        "merged_sha": merged_sha.lower(),
        "merged_anchor_is_ancestor": True,
        "required_checks": required_checks,
        "required_check_conclusions": {
            name: conclusions.get(name) for name in required_checks
        },
        "required_checks_green": True,
        "issue_link_proof": "PR_CLOSING_KEYWORD",
        "issue_state_at_recovery": str(issue_readback.get("state") or "").lower(),
        "qa_history_reconstructed": False,
        "trusted_source": "control_transaction_production_executor",
        "observed_at": observed_at,
    }
    return ExecutionRecord(
        issue=issue,
        execution_intent="POST_DELIVERY_RECOVERY",
        owner_kind="RECOVERY",
        owner_id=lane_id,
        lane_id=lane_id,
        slot_id=_slot_for_lane(lane_id),
        source_branch=head_ref,
        source_sha=head_sha,
        work_branch=head_ref,
        head_sha=head_sha,
        target_branch=target_branch,
        target_sha=observed_target,
        state="INTEGRATING",
        semantic_state="POST_DELIVERY_RECOVERY_FINALIZATION",
        next_action=ActionSpec(
            kind="FINALIZE",
            args={
                "recovery_mode": POST_DELIVERY_RECOVERY_MODE,
                "pr_number": pr_number,
            },
            display="Finalize already-merged delivery from trusted recovery proof",
        ),
        lease=LeaseState(
            token=f"recovery:{issue}:{os.environ.get('GITHUB_RUN_ID','local')}",
            invocation_identity=invocation_identity,
            expires_at=lease_expires_at,
        ),
        closure=ClosureState(
            merged_sha=merged_sha,
            issue_closed=False,
            released_at=None,
        ),
        recovery_history=(proof,),
        generation=1,
        updated_at=observed_at,
    )



def _read_exact_pr_changed_paths(
    repo: str, token: str, pr_number: int
) -> tuple[str, ...]:
    """Read the current PR files completely or fail closed; never guess scope."""
    paths: list[str] = []
    for page in range(1, 5):
        rows = _api(repo, "GET", f"/pulls/{pr_number}/files?per_page=100&page={page}", token)
        if not isinstance(rows, list):
            raise ControlTransactionConflict("PR_CI_CHANGED_FILES_INCOMPLETE")
        for row in rows:
            if not isinstance(row, dict) or not str(row.get("filename") or "").strip():
                raise ControlTransactionConflict("PR_CI_CHANGED_FILES_INCOMPLETE")
            paths.append(str(row["filename"]))
            if row.get("status") == "renamed" and row.get("previous_filename"):
                paths.append(str(row["previous_filename"]))
        if len(rows) < 100:
            break
    else:
        raise ControlTransactionConflict("PR_CI_CHANGED_FILES_OVER_300")
    if not paths or len(paths) >= 300:
        raise ControlTransactionConflict("PR_CI_CHANGED_FILES_INCOMPLETE")
    return tuple(paths)


def _merge_precheck_readback(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
    pr_number: int,
) -> tuple[dict[str, object], object]:
    pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}
    if pr.get("mergeable") is None and not pr.get("merged"):
        # GitHub may return null while mergeability is being computed. One
        # immediate fresh read is enough; unresolved null remains fail-closed.
        pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}


    observed_target = _read_branch_head(repo, token, record.target_branch)
    required_checks = _required_checks_for_target(
        repo,
        token,
        record.target_branch,
    )
    check_conclusions = _check_conclusions_for_head(
        repo,
        token,
        record.head_sha,
    )


    result = evaluate_merge_precheck(
        record_head_sha=record.head_sha,
        record_target_branch=record.target_branch,
        record_target_sha=record.target_sha,
        pr_number=pr_number,
        pr_state=str(pr.get("state") or "").lower(),
        pr_merged=bool(pr.get("merged")),
        pr_head_sha=str((pr.get("head") or {}).get("sha") or ""),
        pr_base_branch=str((pr.get("base") or {}).get("ref") or ""),
        pr_base_sha=str((pr.get("base") or {}).get("sha") or ""),
        pr_mergeable=pr.get("mergeable") if isinstance(pr.get("mergeable"), bool) else None,
        observed_target_sha=observed_target,
        required_checks=required_checks,
        check_conclusions=check_conclusions,
    )
    if result.classification == READY_TO_MERGE:
        # A successful check-run alone does not prove a PR workflow executed.
        # Reconcile each mandatory workflow to the exact live PR head and jobs.
        pr_branch = str((pr.get("head") or {}).get("ref") or "").strip()
        if not pr_branch:
            raise ControlTransactionConflict("PR_CI_HEAD_BRANCH_MISSING")
        payload = _api(
            repo, "GET",
            f"/actions/runs?event=pull_request&head_sha={record.head_sha}&per_page=100",
            token,
        ) or {}
        workflow_runs = payload.get("workflow_runs")
        run_count = payload.get("total_count")
        if (
            isinstance(run_count, bool)
            or not isinstance(run_count, int)
            or not isinstance(workflow_runs, list)
            or run_count != len(workflow_runs)
        ):
            raise ControlTransactionConflict("PR_CI_RUN_LIST_INCOMPLETE")
        changed_paths = _read_exact_pr_changed_paths(repo, token, pr_number)
        try:
            required_pr_workflows = select_pr_workflows_for_changed_paths(changed_paths)
        except ValueError as exc:
            raise ControlTransactionConflict(str(exc)) from None
        jobs_by_run = {}
        for path in required_pr_workflows:
            matches = [
                run for run in workflow_runs
                if isinstance(run, dict)
                and run.get("path") == path
                and run.get("head_sha") == record.head_sha
                and run.get("head_branch") == pr_branch
                and run.get("event") == "pull_request"
                and isinstance(run.get("id"), int)
                and not isinstance(run.get("id"), bool)
            ]
            if matches:
                newest = max(matches, key=lambda run: (run["id"], int(run.get("run_attempt") or 1)))
                jobs_by_run[newest["id"]] = _api(
                    repo, "GET", f"/actions/runs/{newest['id']}/jobs?per_page=100",
                    token,
                ) or {}
        try:
            assert_required_pr_ci_evidence(
                pr_head_sha=record.head_sha,
                pr_head_branch=pr_branch,
                required_workflows=required_pr_workflows,
                workflow_runs=workflow_runs,
                jobs_by_run=jobs_by_run,
                repo_owner=repo.split("/", 1)[0],
            )
        except ValueError as exc:
            raise ControlTransactionConflict(str(exc)) from None
    return pr, result




def _trusted_merge_anchor_fields(
    repo: str,
    token: str,
    *,
    pr: dict[str, object],
    pr_number: int,
    target_branch: str,
    observed_target: str,
) -> dict[str, object]:
    merged_sha = str(pr.get("merge_commit_sha") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", merged_sha):
        raise ProductionExecutorError(
            f"PR #{pr_number} merged readback is missing a valid merge_commit_sha"
        )
    if observed_target != merged_sha and not _is_ancestor(
        repo, token, merged_sha, observed_target
    ):
        raise ProductionExecutorError(
            f"PR #{pr_number} merge commit is not ancestor of current target"
        )
    return {
        "merged_sha": merged_sha,
        "target_sha": observed_target,
        "merge_anchor_proof": {
            "schema": MERGE_ANCHOR_PROOF_SCHEMA,
            "pr_number": pr_number,
            "target_branch": target_branch,
            "merged_sha": merged_sha,
            "observed_target_sha": observed_target,
            "merged_anchor_is_ancestor": True,
            "fresh_readback": True,
            "trusted_source": "control_transaction_production_executor",
        },
    }



def _trusted_merge_anchor_correction_effect(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
    supplied: dict[str, object],
) -> dict[str, object]:
    pr_number = supplied.get("repair_already_merged_anchor_pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ProductionExecutorError(
            "merge-anchor repair requires positive repair_already_merged_anchor_pr_number"
        )
    if (
        record.state != "INTEGRATING"
        or record.next_action is None
        or record.next_action.kind != "FINALIZE"
        or not record.closure.merged_sha
    ):
        raise ProductionExecutorError(
            "merge-anchor repair requires INTEGRATING/FINALIZE record with existing anchor"
        )

    pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}
    if pr.get("merged") is not True:
        raise ProductionExecutorError("merge-anchor repair requires merged PR")
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    if str(head.get("sha") or "").strip() != record.head_sha:
        raise ProductionExecutorError("merge-anchor repair PR head does not match record head")
    if str(base.get("ref") or "").strip() != record.target_branch:
        raise ProductionExecutorError("merge-anchor repair PR base does not match record target")

    observed_target = _read_branch_head(repo, token, record.target_branch)
    fields = _trusted_merge_anchor_fields(
        repo,
        token,
        pr=pr,
        pr_number=pr_number,
        target_branch=record.target_branch,
        observed_target=observed_target,
    )
    corrected = str(fields["merged_sha"])
    return {
        "observed_work_branch": record.work_branch,
        "observed_head_sha": record.head_sha,
        "observed_target_sha": observed_target,
        "state": record.state,
        "semantic_state": "MERGE_ANCHOR_CORRECTED",
        "next_action": _action_payload(record.next_action),
        "corrected_merged_sha": corrected,
        "merge_anchor_correction_proof": {
            "schema": MERGE_ANCHOR_CORRECTION_PROOF_SCHEMA,
            "pr_number": pr_number,
            "target_branch": record.target_branch,
            "previous_merged_sha": record.closure.merged_sha,
            "corrected_merged_sha": corrected,
            "observed_target_sha": observed_target,
            "corrected_anchor_is_ancestor": True,
            "fresh_readback": True,
            "trusted_source": "control_transaction_production_executor",
        },
        "updated_at": _iso(_now()),
    }



def _trusted_merge_effect(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
    invocation_identity: str,
    supplied: dict[str, object],
    before_mutation: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    _require_current_invocation_lease(record, invocation_identity)
    if record.next_action is None or record.next_action.kind != "MERGE":
        raise ProductionExecutorError("MERGE requires current structured MERGE next_action")


    pr_number = record.next_action.args.get("pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ProductionExecutorError("MERGE next_action.pr_number is invalid")


    pr, precheck = _merge_precheck_readback(
        repo,
        token,
        record=record,
        pr_number=pr_number,
    )


    if precheck.classification == TARGET_DRIFT:
        revalidation_workflow = str(
            record.next_action.args.get("revalidation_workflow")
            or supplied.get("revalidation_workflow")
            or ""
        ).strip()
        if not revalidation_workflow:
            raise ProductionExecutorError(
                "MERGE target drift requires structured revalidation_workflow"
            )
        return {
            "merge_precheck_status": TARGET_DRIFT,
            "target_sha": precheck.observed_target_sha,
            "semantic_state": "TARGET_DRIFT_REQUIRES_SYNC",
            "next_action": {
                "kind": "SYNC_TARGET",
                "args": {
                    "target_sha": precheck.observed_target_sha,
                    "pr_number": pr_number,
                    "target_branch": record.target_branch,
                    "qa_workflow": revalidation_workflow,
                },
                "display": "Sync live target into work branch and revalidate exact head",
            },
            "updated_at": _iso(_now()),
        }


    if precheck.classification == REQUIRED_CHECKS_PENDING:
        missing = ",".join(precheck.missing_required_checks)
        raise ControlTransactionConflict(
            f"merge precheck required checks pending: {missing}"
        )
    if precheck.classification == PR_NOT_MERGEABLE:
        raise ControlTransactionConflict(
            "merge precheck PR is not mergeable"
        )
    if precheck.classification == PR_IDENTITY_MISMATCH:
        raise ProductionExecutorError(
            f"merge precheck PR identity mismatch: {precheck.reason}"
        )


    if precheck.classification == ALREADY_MERGED:
        observed_target = _read_branch_head(repo, token, record.target_branch)
        anchor_fields = _trusted_merge_anchor_fields(
            repo,
            token,
            pr=pr,
            pr_number=pr_number,
            target_branch=record.target_branch,
            observed_target=observed_target,
        )
        return {
            "merge_precheck_status": ALREADY_MERGED,
            **anchor_fields,
            "semantic_state": "MERGED",
            "next_action": {
                "kind": "FINALIZE",
                "args": {"pr_number": pr_number},
                "display": "Finalize exact merged Issue",
            },
            "updated_at": _iso(_now()),
        }


    if precheck.classification != READY_TO_MERGE:
        raise ProductionExecutorError(
            f"unsupported merge precheck classification {precheck.classification}"
        )


    if before_mutation is not None:
        before_mutation("PUT", f"/pulls/{pr_number}/merge")
    merge_result = _api(
        repo,
        "PUT",
        f"/pulls/{pr_number}/merge",
        token,
        {
            "sha": record.head_sha,
            "merge_method": "merge",
            "commit_title": f"Merge PR #{pr_number}: Flow v2 trusted merge",
        },
    ) or {}
    if merge_result.get("merged") is not True:
        raise ProductionExecutorError(
            f"trusted PR merge was rejected: {merge_result.get('message')}"
        )


    fresh_pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}
    if fresh_pr.get("merged") is not True:
        raise ProductionExecutorError("trusted PR merge readback is not merged")
    observed_target = _read_branch_head(repo, token, record.target_branch)
    anchor_fields = _trusted_merge_anchor_fields(
        repo,
        token,
        pr=fresh_pr,
        pr_number=pr_number,
        target_branch=record.target_branch,
        observed_target=observed_target,
    )


    return {
        "merge_precheck_status": READY_TO_MERGE,
        **anchor_fields,
        "semantic_state": "MERGED",
        "next_action": {
            "kind": "FINALIZE",
            "args": {"pr_number": pr_number},
            "display": "Finalize exact merged Issue",
        },
        "updated_at": _iso(_now()),
    }





def _verified_sync_target_user_token(repo: str) -> str:
    """Verify user-owned TOK/PAT; never replace native app control-plane authority."""
    token = os.environ.get("WHD_PR_BRANCH_WRITE_TOKEN", "").strip()
    if not token:
        raise ProductionExecutorError("SYNC_TARGET_TOK_MISSING: secrets.TOK is required for branch Git writes")
    request = Request(
        "https://api.github.com/user",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "whd-flow-v2-sync-target-identity",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            identity = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Never log the token, HTTP response body, or caller Authorization header.
        raise ProductionExecutorError(
            f"SYNC_TARGET_TOK_IDENTITY_REJECTED: GitHub /user status {exc.code}"
        ) from None
    except (OSError, ValueError, TypeError):
        raise ProductionExecutorError(
            "SYNC_TARGET_TOK_IDENTITY_UNAVAILABLE: GitHub /user readback failed"
        ) from None
    if not isinstance(identity, dict):
        raise ProductionExecutorError("SYNC_TARGET_TOK_IDENTITY_INVALID")
    owner = repo.split("/", 1)[0]
    login = str(identity.get("login") or "")
    account_type = str(identity.get("type") or "")
    if account_type != "User" or login.casefold() != owner.casefold():
        raise ProductionExecutorError(
            "SYNC_TARGET_TOK_IDENTITY_MISMATCH: expected repository-owner User, not Bot/App"
        )
    return token



def _trusted_sync_target_effect(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
    invocation_identity: str,
    before_mutation: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    _require_current_invocation_lease(record, invocation_identity)
    if record.next_action is None or record.next_action.kind != "SYNC_TARGET":
        raise ProductionExecutorError(
            "SYNC_TARGET requires current structured SYNC_TARGET next_action"
        )


    args = record.next_action.args
    target_sha = str(args.get("target_sha") or "").strip()
    target_branch = str(args.get("target_branch") or "").strip()
    qa_workflow = str(args.get("qa_workflow") or "").strip()
    pr_number = args.get("pr_number")
    if target_branch != record.target_branch:
        raise ProductionExecutorError("SYNC_TARGET target branch identity mismatch")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ProductionExecutorError("SYNC_TARGET pr_number is invalid")
    if not qa_workflow:
        raise ProductionExecutorError("SYNC_TARGET qa_workflow is missing")


    live_target = _read_branch_head(repo, token, target_branch)
    if live_target != target_sha:
        raise ControlTransactionConflict(
            f"SYNC_TARGET target drift: expected {target_sha}, observed {live_target}"
        )
    live_work = _read_branch_head(repo, token, record.work_branch)


    if live_work != record.head_sha:
        # The target->work merge may already have succeeded in a previous
        # attempt whose coord/execution-v2 CAS lost a race.  Do not report a
        # permanent WORK_HEAD_DRIFT when both the prior work head and exact
        # target are proven ancestors of the live work head; reconcile the
        # already-applied side effect into the canonical record instead.
        prior_work_reaches_live = _is_ancestor(
            repo, token, record.head_sha, live_work
        )
        target_reaches_live = _is_ancestor(repo, token, target_sha, live_work)
        if not (prior_work_reaches_live and target_reaches_live):
            raise ControlTransactionConflict(
                f"SYNC_TARGET work head drift: expected {record.head_sha}, observed {live_work}"
            )
        new_head = live_work
    else:
        # Fail closed before a content mutation if the user's TOK is missing or
        # resolves to a GitHub App/Bot. Native CAS reads/writes still use token.
        write_token = _verified_sync_target_user_token(repo)
        if before_mutation is not None:
            before_mutation("POST", "/merges")
        try:
            _api(
                repo,
                "POST",
                "/merges",
                write_token,
                {
                    "base": record.work_branch,
                    "head": target_sha,
                    "commit_message": (
                        f"Flow v2 SYNC_TARGET for Issue #{record.issue}: "
                        f"{target_branch}@{target_sha}"
                    ),
                },
            )
        except HTTPError as exc:
            if exc.code == 409:
                raise ProductionExecutorError(
                    "SYNC_TARGET merge conflict requires explicit repair"
                ) from exc
            raise


        new_head = _read_branch_head(repo, token, record.work_branch)
    if new_head == record.head_sha:
        next_action = {
            "kind": "MERGE",
            "args": {
                "pr_number": pr_number,
                "head_sha": new_head,
                "target_branch": target_branch,
                "expected_target_sha": target_sha,
                "revalidation_workflow": qa_workflow,
            },
            "display": f"Merge exact PR #{pr_number} after target reconciliation",
        }
        semantic_state = "TARGET_RECONCILED"
    else:
        next_action = {
            "kind": "START_QA",
            "args": {
                "workflow": qa_workflow,
                "post_accept_pr_number": pr_number,
                "post_accept_target_branch": target_branch,
                "post_accept_revalidation_workflow": qa_workflow,
            },
            "display": "Revalidate exact head after target synchronization",
        }
        semantic_state = "QA_INVALIDATED_BY_TARGET_SYNC"


    return {
        "head_sha": new_head,
        "target_sha": target_sha,
        "semantic_state": semantic_state,
        "next_action": next_action,
        "updated_at": _iso(_now()),
    }




def _finalize_target_readback(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
) -> dict[str, object]:
    """Read back the live target for normal merge-finalize or CONTROL_ONLY close."""
    if is_control_only_finalize_record(record):
        observed_target = _read_branch_head(repo, token, record.target_branch)
        return {
            "observed_target_sha": observed_target,
            "control_only_target_readback": {
                "schema": CONTROL_ONLY_TARGET_READBACK_SCHEMA,
                "target_branch": record.target_branch,
                "observed_target_sha": observed_target,
                "fresh_readback": True,
                "trusted_source": "control_transaction_production_executor",
            },
        }


    anchor = str(record.closure.merged_sha or "").strip()
    if not anchor:
        raise ProductionExecutorError("FINALIZE requires a merged anchor before target readback")


    encoded_branch = quote(record.target_branch, safe="")
    ref = _api(repo, "GET", f"/git/ref/heads/{encoded_branch}", token)
    observed_target = str((ref.get("object") or {}).get("sha") or "").strip()
    if not observed_target:
        raise ProductionExecutorError("FINALIZE target ref readback did not return a SHA")


    if observed_target == anchor:
        return {"observed_target_sha": observed_target}


    compare = _api(repo, "GET", f"/compare/{anchor}...{observed_target}", token)
    merge_base = str((compare.get("merge_base_commit") or {}).get("sha") or "").strip()
    if merge_base != anchor:
        raise ProductionExecutorError(
            "FINALIZE target advanced outside accepted merge-anchor ancestry"
        )


    return {
        "observed_target_sha": observed_target,
        "target_advance_proof": {
            "schema": "WHD_FLOW_V2_TARGET_ADVANCE_PROOF_V1",
            "target_branch": record.target_branch,
            "anchor_sha": anchor,
            "observed_target_sha": observed_target,
            "anchor_is_ancestor": True,
            "fresh_readback": True,
            "trusted_source": "control_transaction_production_executor",
        },
    }




def _ensure_issue_closed_for_finalize(
    repo: str,
    token: str,
    *,
    issue: int,
    record: ExecutionRecord,
    records: dict[int, ExecutionRecord] | None = None,
    before_mutation: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    """Close/read back the GitHub Issue before a FINALIZE -> DONE transition."""
    control_only = is_control_only_finalize_record(record)
    post_delivery_recovery = is_post_delivery_recovery_finalize_record(record)
    if not control_only:
        if record.state != "INTEGRATING":
            raise ProductionExecutorError("FINALIZE requires INTEGRATING state before issue close")
        if (
            not post_delivery_recovery
            and (record.qa.last_accepted_run is None or record.qa.accepted_head_sha != record.head_sha)
        ):
            raise ProductionExecutorError("FINALIZE requires accepted QA for current head before issue close")
    target_readback = _finalize_target_readback(repo, token, record=record)


    observed = _api(repo, "GET", f"/issues/{issue}", token)
    if (
        str(observed.get("state") or "").lower() != "closed"
        or str(observed.get("state_reason") or "").lower() != "completed"
    ):
        if before_mutation is not None:
            before_mutation("PATCH", f"/issues/{issue}")
        _api(
            repo,
            "PATCH",
            f"/issues/{issue}",
            token,
            {"state": "closed", "state_reason": "completed"},
        )


    fresh = _api(repo, "GET", f"/issues/{issue}", token)
    if str(fresh.get("state") or "").lower() != "closed":
        raise ProductionExecutorError("FINALIZE issue close readback is not closed")
    if str(fresh.get("state_reason") or "").lower() != "completed":
        raise ProductionExecutorError("FINALIZE issue close readback is not completed")


    trusted_released_at = str(fresh.get("closed_at") or _iso(_now())).strip()
    if not trusted_released_at:
        raise ProductionExecutorError("FINALIZE trusted released_at readback is blank")


    effect: dict[str, object] = {
        **target_readback,
        "issue_closed": True,
        "issue_state": "closed",
        "issue_state_reason": "completed",
        "issue_closed_at": fresh.get("closed_at"),
        "released_at": trusted_released_at,
    }
    sibling = _discover_open_delivery_sibling(
        repo,
        token,
        issue=issue,
        record=record,
        records=records if records is not None else {issue: record},
    )
    if sibling is not None:
        next_issue, pr_number = sibling
        effect.update({
            "next_issue": next_issue,
            "chain_next_action": {
                "kind": "RECOVER_POST_DELIVERY",
                "args": {"pr_number": pr_number},
                "display": f"Recover and finalize sibling Issue #{next_issue} from PR #{pr_number}",
            },
        })
    return effect






def _trusted_stale_release_effect(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
    records: dict[int, ExecutionRecord] | None = None,
    supplied: dict[str, object],
    before_mutation: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    """Delete one proven-safe stale work ref, then prove absence before READY reset.


    The GitHub connector/runtime is not granted an ad-hoc branch-delete bypass.
    RELEASE_PATHS remains the sole semantic owner: this trusted GitHub executor
    may delete only the exact stale work ref after proving that it is released,
    inactive, unprotected, unshared, unchanged, and fully contained in the live
    target history.  If the ref is already absent, the operation is idempotent.
    """
    scope = record.mutation_scope
    if scope is None or scope.reservation_state != "RELEASED":
        return dict(supplied)


    now = _now()
    if record.lease is None:
        raise ProductionExecutorError("stale RELEASE_PATHS cleanup requires an expired lease")
    lease_expires = datetime.fromisoformat(record.lease.expires_at.replace("Z", "+00:00"))
    if lease_expires.tzinfo is None or lease_expires.utcoffset() is None:
        raise ProductionExecutorError("stale RELEASE_PATHS cleanup lease expiry must be timezone-aware")
    if lease_expires >= now:
        raise ProductionExecutorError("stale RELEASE_PATHS cleanup requires an expired lease")
    if record.active_run is not None:
        raise ProductionExecutorError("stale RELEASE_PATHS cleanup requires active_run=null")
    if record.qa.last_accepted_run is not None or record.qa.accepted_head_sha is not None:
        raise ProductionExecutorError("stale RELEASE_PATHS cleanup requires no QA lock")


    if (
        record.work_branch in {"main", "cleanup/2d-3d-sync", record.source_branch, record.target_branch}
        or record.work_branch.startswith("coord/")
    ):
        raise ProductionExecutorError(
            f"stale RELEASE_PATHS cleanup refuses protected/control branch {record.work_branch!r}"
        )


    observed_records = records if records is not None else {record.issue: record}
    for other in observed_records.values():
        if (
            other.issue != record.issue
            and other.state != "DONE"
            and other.work_branch == record.work_branch
        ):
            raise ProductionExecutorError(
                "stale RELEASE_PATHS cleanup refuses work branch referenced by another nonterminal Issue"
            )


    fresh_target_sha = _read_branch_head(repo, token, record.target_branch)
    encoded_work = quote(record.work_branch, safe="")
    branch_exists = False
    observed_work_sha: str | None = None
    try:
        ref = _api(repo, "GET", f"/git/ref/heads/{encoded_work}", token) or {}
        observed_work_sha = str((ref.get("object") or {}).get("sha") or "").strip()
        if not observed_work_sha:
            raise ProductionExecutorError(
                "stale RELEASE_PATHS cleanup work branch resolved without SHA"
            )
        branch_exists = True
    except HTTPError as exc:
        if exc.code != 404:
            raise


    deleted = False
    if branch_exists:
        if supplied.get("delete_stale_work_branch") is not True:
            raise ProductionExecutorError(
                "stale RELEASE_PATHS cleanup requires delete_stale_work_branch=true while work branch exists"
            )
        if observed_work_sha != record.head_sha:
            raise ControlTransactionConflict(
                "stale RELEASE_PATHS cleanup work branch head drift: "
                f"expected {record.head_sha}, observed {observed_work_sha}"
            )


        branch_meta = _api(repo, "GET", f"/branches/{encoded_work}", token) or {}
        branch_meta_sha = str((branch_meta.get("commit") or {}).get("sha") or "").strip()
        if branch_meta_sha and branch_meta_sha != observed_work_sha:
            raise ControlTransactionConflict(
                "stale RELEASE_PATHS cleanup branch metadata head drift"
            )
        if branch_meta.get("protected") is True:
            raise ProductionExecutorError(
                "stale RELEASE_PATHS cleanup refuses protected work branch"
            )


        if not _is_ancestor(repo, token, observed_work_sha, fresh_target_sha):
            raise ControlTransactionConflict(
                "stale RELEASE_PATHS cleanup refuses branch with commits not contained in current target"
            )


        if before_mutation is not None:
            before_mutation("DELETE", f"/git/refs/heads/{encoded_work}")
        _api(repo, "DELETE", f"/git/refs/heads/{encoded_work}", token)
        deleted = True


        try:
            _api(repo, "GET", f"/git/ref/heads/{encoded_work}", token)
        except HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            raise ProductionExecutorError(
                "stale RELEASE_PATHS cleanup delete readback still resolves work branch"
            )


    effect = dict(supplied)
    effect.update(
        {
            "work_branch_exists": False,
            "fresh_target_sha": fresh_target_sha,
            "stale_work_branch_sha": observed_work_sha or record.head_sha,
            "stale_work_branch_deleted": deleted,
            "stale_work_branch_readback": "ABSENT",
            "updated_at": _iso(now),
        }
    )
    return effect




def _trusted_consume_qa_effect(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
    invocation_identity: str,
    supplied: dict[str, object],
) -> dict[str, object]:
    """Fresh-read one already-terminal exact-head QA run and consume it atomically."""
    _require_current_invocation_lease(record, invocation_identity)
    if record.next_action is None or record.next_action.kind != "START_QA":
        raise ControlTransactionConflict(
            "CONSUME_QA requires current structured START_QA next_action"
        )
    run_id = supplied.get("run_id")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise ProductionExecutorError("CONSUME_QA run_id must be a positive integer")
    expected_workflow = str(record.next_action.args.get("workflow") or "").strip()
    if not expected_workflow:
        raise ProductionExecutorError("CONSUME_QA START_QA workflow is missing")
    run = _api(repo, "GET", f"/actions/runs/{run_id}", token) or {}
    observed_id = run.get("id")
    observed_head = str(run.get("head_sha") or "").strip()
    observed_path = str(run.get("path") or "").strip()
    observed_status = str(run.get("status") or "").strip().lower()
    observed_conclusion = str(run.get("conclusion") or "").strip().lower()
    if observed_id != run_id:
        raise ProductionExecutorError("CONSUME_QA run identity mismatch")
    if observed_head != record.head_sha:
        raise ControlTransactionConflict(
            f"CONSUME_QA head mismatch: expected {record.head_sha}, observed {observed_head}"
        )
    if observed_path != expected_workflow:
        raise ControlTransactionConflict(
            f"CONSUME_QA workflow mismatch: expected {expected_workflow}, observed {observed_path}"
        )
    if observed_status != "completed":
        raise ControlTransactionConflict(
            f"CONSUME_QA run is not terminal: {observed_status or 'unknown'}"
        )
    if observed_conclusion != "success":
        raise ControlTransactionConflict(
            f"CONSUME_QA requires success: observed {observed_conclusion or 'none'}"
        )
    # Real PR-triggered CI must have executed jobs. A run record without jobs
    # cannot be used as QA evidence, even if a status endpoint is misleading.
    # GitHub always includes "event" for an actual run; legacy synthetic unit
    # fixtures that do not represent pull_request runs are left unchanged.
    if str(run.get("event") or "").lower() == "pull_request":
        jobs_payload = _api(repo, "GET", f"/actions/runs/{run_id}/jobs?per_page=100", token) or {}
        jobs = jobs_payload.get("jobs")
        count = jobs_payload.get("total_count")
        if (
            not isinstance(jobs, list)
            or not jobs
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count != len(jobs)
            or any(
                not isinstance(job, dict)
                or job.get("run_id") != run_id
                or str(job.get("status") or "").lower() != "completed"
                or str(job.get("conclusion") or "").lower() != "success"
                for job in jobs
            )
        ):
            raise ControlTransactionConflict("CONSUME_QA_PR_JOBS_NOT_GREEN: missing, empty, incomplete or non-success jobs")
    effect = dict(supplied)
    effect.update(
        {
            "run_id": run_id,
            "run_head_sha": observed_head,
            "run_status": observed_status,
            "conclusion": observed_conclusion,
            "purpose": str(run.get("name") or expected_workflow),
            "updated_at": _iso(_now()),
        }
    )
    return effect


class _ProductionRuntimeProvider:
    """Transport/effect adapter only; no transition or retry state."""

    def __init__(self, repo, token, coord_branch):
        self.repo, self.token = repo, token
        self.coord_branch = coord_branch

    def read_state(self):
        return _load_state(self.repo, self.token, self.coord_branch)

    def read_branch_head(self, branch):
        return _read_branch_head(self.repo, self.token, branch)

    def is_ancestor(self, ancestor, descendant):
        return _is_ancestor(self.repo, self.token, ancestor, descendant)

    def resolve_effect(self, record, plan, supplied_effect, *, records, before_mutation):
        kwargs = {"record": record, "before_mutation": before_mutation}
        if plan.kind == "MERGE":
            return _trusted_merge_effect(self.repo, self.token, **kwargs,
                invocation_identity=plan.invocation_identity, supplied=dict(supplied_effect))
        if plan.kind == "SYNC_TARGET":
            return _trusted_sync_target_effect(self.repo, self.token, **kwargs,
                invocation_identity=plan.invocation_identity)
        if plan.kind == "RELEASE_PATHS":
            return _trusted_stale_release_effect(self.repo, self.token, **kwargs,
                records=records, supplied=dict(supplied_effect))
        if plan.kind == "FINALIZE":
            _require_current_invocation_lease(record, plan.invocation_identity)
            if record.next_action is None or record.next_action.kind != "FINALIZE":
                raise ControlTransactionConflict(
                    "FINALIZE requires current structured FINALIZE next_action")
            # FINALIZE does not trust caller-supplied closure booleans.
            # The production provider owns Issue close and fresh readback.
            effect = dict(supplied_effect)
            effect.update(_ensure_issue_closed_for_finalize(
                self.repo, self.token, issue=record.issue, records=records, **kwargs))
            return effect
        raise ProductionExecutorError(f"unsupported runtime effect: {plan.kind}")


def build_runtime_provider(repo, token, coord_branch="coord/execution-v2"):
    return _ProductionRuntimeProvider(repo, token, coord_branch)


def _write_state(
    repo: str,
    token: str,
    coord_branch: str,
    *,
    parent_sha: str,
    base_tree_sha: str,
    records: dict[int, ExecutionRecord],
    issue: int,
) -> tuple[str, str]:
    record = records[issue]
    record_text = json.dumps(execution_record_to_payload(record), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    index_text = json.dumps(
        ready_index_to_payload(build_ready_index(records.values())),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"


    record_blob = _api(repo, "POST", "/git/blobs", token, {"content": record_text, "encoding": "utf-8"})
    index_blob = _api(repo, "POST", "/git/blobs", token, {"content": index_text, "encoding": "utf-8"})
    tree = _api(
        repo,
        "POST",
        "/git/trees",
        token,
        {
            "base_tree": base_tree_sha,
            "tree": [
                {"path": f".dispatch/execution/issue-{issue}.json", "mode": "100644", "type": "blob", "sha": record_blob["sha"]},
                {"path": ".dispatch/execution/ready-index.json", "mode": "100644", "type": "blob", "sha": index_blob["sha"]},
            ],
        },
    )
    commit = _api(
        repo,
        "POST",
        "/git/commits",
        token,
        {
            "message": f"flow-v2({issue}): apply {record.transaction.kind if record.transaction else 'transaction'} generation {record.generation}",
            "tree": tree["sha"],
            "parents": [parent_sha],
        },
    )
    encoded = quote(coord_branch, safe="")
    try:
        _api(repo, "PATCH", f"/git/refs/heads/{encoded}", token, {"sha": commit["sha"], "force": False})
    except HTTPError as exc:
        if exc.code in {409, 422}:
            raise ControlTransactionConflict("coord/execution-v2 ref advanced during transaction") from exc
        raise
    return commit["sha"], record_blob["sha"]





def assert_unique_ready_slot_candidate(records: dict[int, ExecutionRecord], candidate: ExecutionRecord) -> None:
    """Reject the candidate's occupied slot, not unrelated pre-existing debt.

    Legacy duplicate records may exist on a different slot. The atomic writer
    must still prevent a *new* collision while allowing other EMPTY lanes to
    make progress. Never infer that any existing duplicate was repaired.
    """
    if candidate.slot_id is None:
        return
    if candidate.slot_id not in FIXED_SLOT_IDS:
        raise ProductionExecutorError("DISPATCH_READY_SLOT_COLLISION: candidate has unknown fixed slot")
    for existing in records.values():
        if not isinstance(existing, ExecutionRecord):
            raise ProductionExecutorError("DISPATCH_READY requires native ExecutionRecords")
        if existing.state != "DONE" and existing.slot_id == candidate.slot_id:
            raise ProductionExecutorError(
                f"DISPATCH_READY_SLOT_COLLISION: slot {candidate.slot_id} belongs to "
                f"Issue #{existing.issue}; requested Issue #{candidate.issue}"
            )


def plan_ready_slot_repair(
    records: dict[int, ExecutionRecord], *,
    authority_issue: int, expected_authority_generation: int,
    target_issue: int, expected_target_generation: int,
    expected_old_slot_id: str, new_slot_id: str,
    lane_id: str, invocation_identity: str,
    observed_at: datetime | None = None,
) -> ExecutionRecord:
    """Pure repair; never fabricate ACQUIRE, lease, owner, QA or work-head history."""
    current = observed_at or _now()
    if current.tzinfo is None or current.utcoffset() is None:
        raise ProductionExecutorError("REPAIR_READY_SLOT clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    if authority_issue == target_issue:
        raise ProductionExecutorError("REPAIR_READY_SLOT authority cannot repair itself")
    if (expected_old_slot_id not in FIXED_SLOT_IDS or new_slot_id not in FIXED_SLOT_IDS
            or expected_old_slot_id == new_slot_id):
        raise ProductionExecutorError("REPAIR_READY_SLOT requires distinct fixed work slots")
    authority, target = records.get(authority_issue), records.get(target_issue)
    if authority is None or target is None:
        raise ProductionExecutorError("REPAIR_READY_SLOT requires existing native records")
    if authority.generation != expected_authority_generation:
        raise ProductionExecutorError("REPAIR_READY_SLOT authority generation drift")
    if (authority.state != "ACTIVE" or authority.owner_id != lane_id
            or authority.lane_id != lane_id or authority.lease is None
            or authority.lease.invocation_identity != invocation_identity):
        raise ProductionExecutorError("REPAIR_READY_SLOT requires owning ACTIVE lease")
    expires = datetime.fromisoformat(authority.lease.expires_at.replace("Z", "+00:00"))
    if expires <= current:
        raise ProductionExecutorError("REPAIR_READY_SLOT authority lease expired")
    if (target.state != "READY" or target.generation != expected_target_generation
            or target.slot_id != expected_old_slot_id or target.owner_kind != "UNCLAIMED"
            or target.owner_id != "NONE" or target.lane_id is not None
            or target.lease is not None or target.active_run is not None
            or target.transaction is not None or target.mutation_scope is not None
            or target.next_action is None or target.next_action.kind != "ACQUIRE"
            or target.qa.last_accepted_run is not None or target.qa.accepted_head_sha is not None):
        raise ProductionExecutorError("REPAIR_READY_SLOT target must be exact unclaimed READY")
    if any(
        number != target_issue and rec.state != "DONE" and rec.slot_id == new_slot_id
        for number, rec in records.items()
    ):
        raise ProductionExecutorError("REPAIR_READY_SLOT destination slot occupied")
    audit = {
        "kind": "READY_SLOT_REPAIR", "authority_issue": authority_issue,
        "from_slot_id": expected_old_slot_id, "to_slot_id": new_slot_id,
        "observed_at": _iso(current),
    }
    return replace(
        target, slot_id=new_slot_id, generation=target.generation + 1,
        updated_at=_iso(current), recovery_history=(*target.recovery_history, audit),
    )


def repair_ready_slot(
    *, repo: str, token: str, coord_branch: str,
    authority_issue: int, expected_authority_generation: int,
    target_issue: int, expected_target_generation: int,
    expected_old_slot_id: str, new_slot_id: str,
    lane_id: str, invocation_identity: str, expected_coord_head: str,
) -> dict[str, object]:
    """Atomic native CAS writer; slot repair never claims the repaired Issue."""
    parent, tree, records = _load_state(repo, token, coord_branch)
    if parent != expected_coord_head:
        raise ControlTransactionConflict(
            f"coord head drift: expected {expected_coord_head}, observed {parent}"
        )
    for attempt in range(5):
        updated = plan_ready_slot_repair(
            records, authority_issue=authority_issue,
            expected_authority_generation=expected_authority_generation,
            target_issue=target_issue, expected_target_generation=expected_target_generation,
            expected_old_slot_id=expected_old_slot_id, new_slot_id=new_slot_id,
            lane_id=lane_id, invocation_identity=invocation_identity,
        )
        candidates = dict(records)
        candidates[target_issue] = updated
        try:
            commit_sha, blob_sha = _write_state(
                repo, token, coord_branch, parent_sha=parent,
                base_tree_sha=tree, records=candidates, issue=target_issue,
            )
            break
        except ControlTransactionConflict as exc:
            if not str(exc).startswith("coord/execution-v2 ref advanced during transaction") or attempt == 4:
                raise
            parent, tree, records = _load_state(repo, token, coord_branch)
            if (records.get(target_issue) is None
                    or records[target_issue].generation != expected_target_generation
                    or records.get(authority_issue) is None
                    or records[authority_issue].generation != expected_authority_generation):
                raise ControlTransactionConflict("REPAIR_READY_SLOT exact native record drift") from exc
    _, _, latest = _load_state(repo, token, coord_branch)
    readback = latest.get(target_issue)
    if readback is None or execution_record_fingerprint(readback) != execution_record_fingerprint(updated):
        raise ProductionExecutorError("REPAIR_READY_SLOT post-write record fingerprint mismatch")
    return {
        "schema": RESULT_SCHEMA, "result": "APPLIED", "kind": "REPAIR_READY_SLOT",
        "issue": target_issue, "authority_issue": authority_issue,
        "coord_commit_sha": commit_sha, "record_blob_sha": blob_sha,
        "post_generation": readback.generation, "post_state": readback.state,
        "post_next_action": readback.next_action.kind if readback.next_action else None,
        "post_slot_id": readback.slot_id,
        "post_record_fingerprint": execution_record_fingerprint(readback),
    }


def dispatch_ready_missing_record(
    *,
    repo: str,
    token: str,
    coord_branch: str,
    issue: int,
    expected_coord_head: str,
    ingress_request: DispatchIngressRequest,
) -> dict[str, object]:
    """Create one generation-1 READY record from explicit typed authority.

    This is the canonical bootstrap for a genuinely missing ExecutionRecord.
    It is create-only, CAS-protected, rebuilds the derived ready-index, and
    fresh-reads the record after the write.  It never claims a lease; ACQUIRE
    remains the next trusted transaction.
    """
    parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
    if parent_sha != expected_coord_head:
        raise ControlTransactionConflict(
            f"coord head drift: expected {expected_coord_head}, observed {parent_sha}"
        )
    if issue in records:
        raise ControlTransactionConflict(
            f"DISPATCH_READY requires missing ExecutionRecord; issue {issue} now exists"
        )
    if not isinstance(ingress_request, DispatchIngressRequest):
        raise ProductionExecutorError("DISPATCH_READY requires DispatchIngressRequest")
    if ingress_request.issue != issue:
        raise ProductionExecutorError("DISPATCH_READY ingress issue mismatch")
    try:
        plan = plan_dispatch_ingress(ingress_request)
    except DispatchIngressError as exc:
        raise ProductionExecutorError(f"DISPATCH_READY ingress rejected: {exc}") from exc
    record = plan.record
    if (
        record.generation != 1
        or record.state != "READY"
        or record.owner_kind != "UNCLAIMED"
        or record.owner_id != "NONE"
        or record.lease is not None
        or record.next_action is None
        or record.next_action.kind != "ACQUIRE"
    ):
        raise ProductionExecutorError("DISPATCH_READY planner did not produce canonical READY record")

    last_conflict: ControlTransactionConflict | None = None
    for attempt in range(1, 6):
        if issue in records:
            raise ControlTransactionConflict(
                f"DISPATCH_READY same-Issue record appeared during bootstrap: {issue}"
            )
        assert_unique_ready_slot_candidate(records, record)
        candidate_records = dict(records)
        candidate_records[issue] = record
        try:
            commit_sha, record_blob_sha = _write_state(
                repo,
                token,
                coord_branch,
                parent_sha=parent_sha,
                base_tree_sha=tree_sha,
                records=candidate_records,
                issue=issue,
            )
            break
        except ControlTransactionConflict as exc:
            last_conflict = exc
            if not str(exc).startswith(
                "coord/execution-v2 ref advanced during transaction"
            ) or attempt >= 5:
                raise
            parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
            if issue in records:
                raise ControlTransactionConflict(
                    "DISPATCH_READY same-Issue record appeared during coord retry"
                ) from exc
    else:  # pragma: no cover
        assert last_conflict is not None
        raise last_conflict

    _, _, fresh_records = _load_state(repo, token, coord_branch)
    fresh = fresh_records.get(issue)
    if fresh is None:
        raise ProductionExecutorError("DISPATCH_READY post-write record is missing")
    if execution_record_fingerprint(fresh) != execution_record_fingerprint(record):
        raise ProductionExecutorError("DISPATCH_READY post-write record fingerprint mismatch")

    return {
        "schema": RESULT_SCHEMA,
        "result": "APPLIED",
        "issue": issue,
        "kind": "DISPATCH_READY",
        "coord_commit_sha": commit_sha,
        "record_blob_sha": record_blob_sha,
        "request_fingerprint": plan.request_fingerprint,
        "authority_fingerprint": plan.authority_fingerprint,
        "post_generation": fresh.generation,
        "post_record_fingerprint": execution_record_fingerprint(fresh),
        "post_state": fresh.state,
        "post_next_action": fresh.next_action.kind if fresh.next_action else None,
        "lease_invocation_identity": None,
        "runtime_observation_status": "NOT_APPLICABLE_UNCLAIMED_READY",
    }



def recover_pre_merge_missing_record(
    *,
    repo: str, token: str, coord_branch: str,
    issue: int, lane_id: str, invocation_identity: str,
    expected_coord_head: str, supplied_effect: dict[str, object],
) -> dict[str, object]:
    """Create-only pre-merge READY from trusted live PR; no historical ACQUIRE.

    Not a recovery owner or merger. The real owner ACQUIRE/QA/MERGE/FINALIZE
    transactions are still mandatory. Same-Issue races fail closed.
    """
    parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
    if parent_sha != expected_coord_head:
        raise ControlTransactionConflict(
            f"coord head drift: expected {expected_coord_head}, observed {parent_sha}"
        )
    if issue in records:
        raise ControlTransactionConflict(
            f"RECOVER_PRE_MERGE requires missing record; issue {issue} exists"
        )
    permitted_fields = {
        "authority_kind", "authority_ref", "pr_number",
        "expected_pr_head_sha", "expected_target_sha",
    }
    unexpected = set(supplied_effect) - permitted_fields
    if unexpected:
        raise ProductionExecutorError(
            "RECOVER_PRE_MERGE cannot import owner, QA or historical state: "
            + ",".join(sorted(unexpected))
        )
    if supplied_effect.get("authority_kind") != "USER_EXPLICIT" or not str(
        supplied_effect.get("authority_ref") or ""
    ).strip():
        raise ProductionExecutorError(
            "RECOVER_PRE_MERGE requires user-explicit authority reference"
        )
    pr_number = supplied_effect.get("pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ProductionExecutorError("RECOVER_PRE_MERGE requires exact pr_number")
    pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}
    owning = _api(repo, "GET", f"/issues/{issue}", token) or {}
    target = _read_branch_head(repo, token, "cleanup/2d-3d-sync")
    checks = list(_required_checks_for_target(repo, token, "cleanup/2d-3d-sync"))
    conclusions = _check_conclusions_for_head(
        repo, token, str((pr.get("head") or {}).get("sha") or "")
    )
    try:
        record = build_pre_merge_recovery_ready_record(
            repository=repo, issue=issue,
            pr_number=pr_number,
            lane_id=lane_id,
            slot_id=_slot_for_lane(lane_id),
            issue_readback=owning,
            pr_readback=pr,
            observed_target_sha=target,
            required_checks=checks,
            check_conclusions=conclusions,
            expected_pr_head_sha=str(supplied_effect.get("expected_pr_head_sha") or ""),
            expected_target_sha=str(supplied_effect.get("expected_target_sha") or ""),
            pr_closes_issue=_pr_body_closes_issue(pr.get("body"), issue),
            observed_at=_iso(_now()),
        )
    except (ValueError, ExecutionRecordError) as exc:
        raise ProductionExecutorError(str(exc)) from exc

    last_conflict: ControlTransactionConflict | None = None
    for attempt in range(1, 6):
        if issue in records:
            raise ControlTransactionConflict(
                "RECOVER_PRE_MERGE same-Issue record appeared during bootstrap"
            )
        candidate_records = dict(records)
        candidate_records[issue] = record
        try:
            commit_sha, blob_sha = _write_state(
                repo, token, coord_branch, parent_sha=parent_sha,
                base_tree_sha=tree_sha, records=candidate_records, issue=issue,
            )
            break
        except ControlTransactionConflict as exc:
            last_conflict = exc
            if not str(exc).startswith(
                "coord/execution-v2 ref advanced during transaction"
            ) or attempt >= 5:
                raise
            parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
            if issue in records:
                raise ControlTransactionConflict(
                    "RECOVER_PRE_MERGE same-Issue record appeared during coord retry"
                ) from exc
    else:  # pragma: no cover
        assert last_conflict is not None
        raise last_conflict

    _, _, fresh_records = _load_state(repo, token, coord_branch)
    fresh = fresh_records.get(issue)
    if fresh is None or execution_record_fingerprint(fresh) != execution_record_fingerprint(record):
        raise ProductionExecutorError("RECOVER_PRE_MERGE post-write readback mismatch")
    return {
        "schema": RESULT_SCHEMA, "result": "APPLIED",
        "issue": issue, "kind": "RECOVER_PRE_MERGE",
        "coord_commit_sha": commit_sha, "record_blob_sha": blob_sha,
        "post_generation": fresh.generation,
        "post_record_fingerprint": execution_record_fingerprint(fresh),
        "post_state": fresh.state,
        "post_next_action": fresh.next_action.kind if fresh.next_action else None,
        "lease_invocation_identity": None,
        "runtime_observation_status": "NOT_APPLICABLE_UNCLAIMED_READY",
    }


def recover_post_delivery_missing_record(
    *,
    repo: str,
    token: str,
    coord_branch: str,
    issue: int,
    lane_id: str,
    invocation_identity: str,
    expected_coord_head: str,
    supplied_effect: dict[str, object],
) -> dict[str, object]:
    """Create one current-only recovery record for an already-merged delivery.

    The create is CAS-protected and retries only unrelated coord-branch races.
    Same-Issue creation by another writer fails closed.  Historical execution
    events are never synthesized.
    """
    parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
    if parent_sha != expected_coord_head:
        raise ControlTransactionConflict(
            f"coord head drift: expected {expected_coord_head}, observed {parent_sha}"
        )
    if issue in records:
        raise ControlTransactionConflict(
            f"RECOVER_POST_DELIVERY requires missing ExecutionRecord; issue {issue} now exists"
        )

    last_conflict: ControlTransactionConflict | None = None
    for attempt in range(1, 6):
        if issue in records:
            raise ControlTransactionConflict(
                f"RECOVER_POST_DELIVERY same-Issue record appeared during recovery: {issue}"
            )
        record = _build_post_delivery_recovery_record(
            repo,
            token,
            issue=issue,
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            supplied_effect=supplied_effect,
        )
        candidate_records = dict(records)
        candidate_records[issue] = record
        try:
            commit_sha, record_blob_sha = _write_state(
                repo,
                token,
                coord_branch,
                parent_sha=parent_sha,
                base_tree_sha=tree_sha,
                records=candidate_records,
                issue=issue,
            )
            break
        except ControlTransactionConflict as exc:
            last_conflict = exc
            if not str(exc).startswith(
                "coord/execution-v2 ref advanced during transaction"
            ) or attempt >= 5:
                raise
            parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
            if issue in records:
                raise ControlTransactionConflict(
                    "RECOVER_POST_DELIVERY same-Issue record appeared during coord retry"
                ) from exc
    else:  # pragma: no cover
        assert last_conflict is not None
        raise last_conflict

    _, _, fresh_records = _load_state(repo, token, coord_branch)
    fresh = fresh_records.get(issue)
    if fresh is None:
        raise ProductionExecutorError("RECOVER_POST_DELIVERY post-write record is missing")
    if execution_record_fingerprint(fresh) != execution_record_fingerprint(record):
        raise ProductionExecutorError(
            "RECOVER_POST_DELIVERY post-write record fingerprint mismatch"
        )

    try:
        monitor_commit_sha, observation = _publish_transaction_progress(
            repo,
            token,
            record=fresh,
            invocation_identity=invocation_identity,
            runtime_owner=lane_id,
            action="RECOVER_POST_DELIVERY",
        )
        monitor_payload = {
            "runtime_observation_status": "APPLIED",
            "runtime_observation_commit_sha": monitor_commit_sha,
            "runtime_observation_event": observation["event"],
            "runtime_liveness_state": observation["liveness_state"],
        }
    except Exception as exc:
        monitor_payload = {
            "runtime_observation_status": "DEGRADED",
            "runtime_observation_error": str(exc),
            "runtime_observation_commit_sha": None,
            "runtime_observation_event": None,
            "runtime_liveness_state": "UNKNOWN",
        }

    return {
        "schema": RESULT_SCHEMA,
        "result": "APPLIED",
        "issue": issue,
        "kind": "RECOVER_POST_DELIVERY",
        "coord_commit_sha": commit_sha,
        "record_blob_sha": record_blob_sha,
        "post_generation": fresh.generation,
        "post_record_fingerprint": execution_record_fingerprint(fresh),
        "post_state": fresh.state,
        "post_next_action": fresh.next_action.kind if fresh.next_action else None,
        "post_chain_next_issue": fresh.chain.next_issue,
        "post_chain_next_action": fresh.chain.next_action.kind if fresh.chain.next_action else None,
        "post_chain_next_action_args": dict(fresh.chain.next_action.args) if fresh.chain.next_action else None,
        "lease_invocation_identity": fresh.lease.invocation_identity if fresh.lease else None,
        **monitor_payload,
    }



_READBACK_CONTINUATION_KINDS = frozenset({"MERGE", "SYNC_TARGET", "FINALIZE"})
_TERMINAL_TAIL_SOURCE_KINDS = frozenset({"MERGE", "RECONCILE", "ACQUIRE"})




class _PostEffectCoordConflict(RuntimePostEffectConflict):
    def __init__(self, conflict_class, *, record, current, kind, envelope, work_ref_readback=None):
        self.previous_record, self.observed_record = record, current
        diagnostics = {
            "issue": record.issue, "kind": kind,
            "pre_generation": record.generation,
            "pre_fingerprint": execution_record_fingerprint(record),
            "observed_generation": current.generation if current else None,
            "observed_fingerprint": execution_record_fingerprint(current) if current else None,
            "pre_work_branch": record.work_branch, "pre_work_head": record.head_sha,
            "pre_target_branch": record.target_branch, "pre_target_head": record.target_sha,
            "observed_work_branch": current.work_branch if current else None,
            "observed_work_head": current.head_sha if current else None,
            "observed_target_head": current.target_sha if current else None,
            "pre_next_action": record.next_action.kind if record.next_action else None,
            "observed_next_action": current.next_action.kind if current and current.next_action else None,
            "provider_mutation_performed": envelope.provider_mutation_performed,
        }
        if work_ref_readback is not None:
            diagnostics["work_ref_readback"] = work_ref_readback
        super().__init__(conflict_class, diagnostics)


def _fresh_stale_work_ref_observation(repo, token, record):
    """Only a new GET 404 proves absence; errors and malformed refs are UNKNOWN."""
    try:
        payload = _api(repo, "GET", f"/git/ref/heads/{quote(record.work_branch, safe='')}", token)
    except HTTPError as exc:
        return "ABSENT" if exc.code == 404 else "UNKNOWN"
    except Exception:
        return "UNKNOWN"
    return "PRESENT" if isinstance(payload, dict) and (payload.get("object") or {}).get("sha") else "UNKNOWN"


def _readback_continuation_matches(previous, current, kind, invocation_identity):
    # Identity checks are eligibility only. A newly prepared exact plan and the
    # READBACK_ONLY mutation fence remain the sole continuation authority.
    if current is None or kind not in _READBACK_CONTINUATION_KINDS:
        return False
    if current.next_action is None or current.next_action.kind != kind:
        return False
    fields = ("issue", "source_branch", "source_sha", "work_branch", "target_branch",
              "owner_kind", "owner_id", "lane_id", "slot_id")
    if any(getattr(previous, key) != getattr(current, key) for key in fields):
        return False
    if previous.lease is None or current.lease is None:
        return False
    if (previous.lease.token != current.lease.token
        or current.lease.invocation_identity != invocation_identity):
        return False
    if previous.next_action is None:
        return False
    if previous.next_action.args.get("pr_number") != current.next_action.args.get("pr_number"):
        return False
    if kind in {"MERGE", "FINALIZE"} and previous.head_sha != current.head_sha:
        return False
    if kind == "FINALIZE" and previous.closure.merged_sha != current.closure.merged_sha:
        return False
    return True


def _independent_post_delivery_finalizers(
    requested: ExecutionRecord,
    foreign: ExecutionRecord,
    *,
    kind: str,
    lane_id: str,
) -> bool:
    """Only two trusted, already-merged recovery terminal tails may coexist.

    The postmerge lane is a service identity, not a single interactive writer.
    This never exempts arbitrary work, QA, merge, or repository mutations from
    active-owning-Issue stickiness.
    """
    return bool(
        kind == "FINALIZE"
        and lane_id == "github.flowv2.postmerge"
        and requested.lane_id == foreign.lane_id == lane_id
        and requested.owner_kind == foreign.owner_kind == "RECOVERY"
        and requested.owner_id == foreign.owner_id == lane_id
        and is_post_delivery_recovery_finalize_record(requested)
        and is_post_delivery_recovery_finalize_record(foreign)
    )


def _assert_owning_issue_open_for_acquire(repo: str, token: str, issue: int) -> None:
    """Fail closed before ACQUIRE when GitHub Issue and stale READY disagree.

    The ExecutionRecord and ready-index remain untouched; reconciliation must
    use a separately authorized trusted transaction, never an implicit delete.
    """
    observed = _api(repo, "GET", f"/issues/{issue}", token) or {}
    if observed.get("pull_request") is not None:
        raise ProductionExecutorError(
            f"ACQUIRE_ISSUE_IDENTITY_MISMATCH: issue {issue} resolves to a PR"
        )
    if int(observed.get("number") or 0) != issue:
        raise ProductionExecutorError(
            f"ACQUIRE_ISSUE_IDENTITY_MISMATCH: issue {issue} readback mismatch"
        )
    state = str(observed.get("state") or "").strip().lower()
    if state != "open":
        raise ProductionExecutorError(
            f"ACQUIRE_ISSUE_NOT_OPEN: issue={issue} state={state or 'UNKNOWN'}; "
            "preserve native record and reconcile GitHub Issue status before retry"
        )


def _execute_one_attempt(
    *,
    repo: str,
    token: str,
    coord_branch: str,
    issue: int,
    kind: str,
    lane_id: str,
    invocation_identity: str,
    supplied_effect: dict[str, object],
    _continuation_fingerprint: str | None = None,
) -> dict[str, object]:
    parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
    if issue not in records:
        raise ProductionExecutorError(f"native ExecutionRecord missing for issue {issue}")
    record = records[issue]

    if (_continuation_fingerprint is not None
        and execution_record_fingerprint(record) != _continuation_fingerprint):
        raise RuntimePostEffectConflict("POST_EFFECT_CONTINUATION_DRIFT", {
            "issue": issue, "kind": kind, "observed_generation": record.generation,
        })
    envelope = None


    # ACTIVE_OWNING_ISSUE_STICKINESS_HARD_GATE_V1.  Classify same-lane
    # records at one exact observed time and in issue order so result never
    # depends on dict/tree iteration order. A RELEASED stale-reset residue is
    # not an owning authority, but the residue itself may execute only the
    # narrow trusted RELEASE_PATHS cleanup. Terminal tail remains stronger.
    stickiness_observed_at = _iso(_now())
    requested_stale_residue = released_stale_reset_residue(
        record, observed_at=stickiness_observed_at
    )
    if requested_stale_residue and kind != "RELEASE_PATHS":
        raise ControlTransactionConflict(
            "STALE_RELEASED_RESIDUE_REQUIRES_RELEASE_PATHS_CLEANUP "
            f"issue={issue} requested_action={kind}"
        )
    requested_stale_cleanup = requested_stale_residue and kind == "RELEASE_PATHS"


    same_lane_owners = sorted(
        (
            owning_record
            for owning_record in records.values()
            if owning_record.issue != issue
            and owning_record.state != "DONE"
            and owning_record.lane_id == lane_id
            and owning_record.owner_kind != "NONE"
            and owning_record.owner_id != "NONE"
        ),
        key=lambda row: row.issue,
    )
    for owning_record in same_lane_owners:
        if _independent_post_delivery_finalizers(
            record, owning_record, kind=kind, lane_id=lane_id,
        ):
            continue
        if released_stale_reset_residue(
            owning_record, observed_at=stickiness_observed_at
        ):
            continue
        if requested_stale_cleanup and not terminal_tail_active(owning_record):
            continue
        try:
            assert_active_owning_issue_sticky(
                owning_record,
                requested_issue=issue,
                requested_action_kind=kind,
            )
        except InvocationExitError as exc:
            raise ControlTransactionConflict(str(exc)) from exc


    if kind == "ACQUIRE":
        _assert_owning_issue_open_for_acquire(repo, token, issue)

    plan = prepare_transaction(
        record,
        kind=kind,
        transaction_id=f"gha:{os.environ.get('GITHUB_RUN_ID','local')}:{issue}:{kind}:{record.generation}",
        invocation_identity=invocation_identity,
    )
    effect = _normalize_effect(
        record,
        kind=kind,
        lane_id=lane_id,
        invocation_identity=invocation_identity,
        supplied=supplied_effect,
    )
    if kind in PRE_TRANSITION_EXTERNAL_MUTATION_PATHS:
        envelope = resolve_runtime_effect(
            record, plan, RuntimeMode(supplied_effect.get("runtime_mode", "MUTATION_ALLOWED")),
            build_runtime_provider(repo, token, coord_branch), effect,
        )
        effect = dict(envelope.effect)
    elif kind == "CONSUME_QA":
        effect = _trusted_consume_qa_effect(
            repo,
            token,
            record=record,
            invocation_identity=invocation_identity,
            supplied=supplied_effect,
        )
    elif (
        kind == "RECONCILE"
        and supplied_effect.get("repair_already_merged_anchor_pr_number") is not None
    ):
        _require_current_invocation_lease(record, invocation_identity)
        effect = _trusted_merge_anchor_correction_effect(
            repo,
            token,
            record=record,
            supplied=supplied_effect,
        )
    try:
        post = execute_transaction(record, plan, effect=effect)
    except ControlTransactionConflict as exc:
        if envelope is not None:
            raise RuntimePostEffectConflict("POST_EFFECT_SEMANTIC_REJECTED", {
                "issue": issue, "kind": kind, "pre_generation": record.generation,
                "provider_mutation_performed": envelope.provider_mutation_performed,
            }) from exc
        raise


    admission_reserved = (
        kind == "ACQUIRE"
        and supplied_effect.get("admission_reservation") is not None
    )
    reservation_write = kind == "RESERVE_PATHS" or admission_reserved
    if reservation_write and post.mutation_scope is None:
        raise ProductionExecutorError(
            f"{kind} produced no mutation_scope for reservation"
        )


    # UNRELATED_COORD_CAS_RETRY_V1: a non-force coord ref CAS may lose only
    # because another Issue advanced the shared coord branch.  Rebuild the
    # exact same post-record atop the fresh coord tree inside this workflow iff
    # a fresh read proves the current Issue fingerprint is unchanged.  A
    # same-Issue change remains fail-closed and must be semantically rebuilt.
    pre_transaction_fingerprint = execution_record_fingerprint(record)
    write_parent = parent_sha
    write_tree = tree_sha
    write_records = records
    last_coord_conflict: ControlTransactionConflict | None = None
    for write_attempt in range(1, 6):
        if reservation_write:
            try:
                require_no_path_reservation_conflict(
                    write_records.values(),
                    candidate_issue=issue,
                    candidate_scope=post.mutation_scope,
                )
            except PathReservationError as exc:
                raise ControlTransactionConflict(str(exc)) from exc


        candidate_records = dict(write_records)
        candidate_records[issue] = post
        try:
            commit_sha, record_blob_sha = _write_state(
                repo,
                token,
                coord_branch,
                parent_sha=write_parent,
                base_tree_sha=write_tree,
                records=candidate_records,
                issue=issue,
            )
            break
        except ControlTransactionConflict as exc:
            last_coord_conflict = exc
            if not str(exc).startswith(
                "coord/execution-v2 ref advanced during transaction"
            ):
                if envelope is not None:
                    raise _PostEffectCoordConflict(
                        "POST_EFFECT_COORD_WRITE_REJECTED", record=record, current=None,
                        kind=kind, envelope=envelope,
                    ) from exc
                raise
            fresh_parent, fresh_tree, fresh_records = _load_state(
                repo, token, coord_branch
            )
            current = fresh_records.get(issue)
            if write_attempt >= 5 and envelope is not None:
                raise _PostEffectCoordConflict(
                    "POST_EFFECT_COORD_CAS_EXHAUSTED", record=record, current=current,
                    kind=kind, envelope=envelope,
                ) from exc
            if write_attempt >= 5:
                raise
            if (
                current is None
                or execution_record_fingerprint(current)
                != pre_transaction_fingerprint
            ):
                if envelope is not None:
                    observation = (
                        _fresh_stale_work_ref_observation(repo, token, record)
                        if requested_stale_cleanup else None
                    )
                    raise _PostEffectCoordConflict(
                        "POST_EFFECT_SAME_ISSUE_DRIFT", record=record, current=current,
                        kind=kind, envelope=envelope, work_ref_readback=observation,
                    ) from exc
                raise ControlTransactionConflict(
                    "coord/execution-v2 ref advanced during transaction; "
                    "current Issue changed; fresh semantic rebuild required"
                ) from exc
            write_parent = fresh_parent
            write_tree = fresh_tree
            write_records = fresh_records
    else:  # pragma: no cover - defensive
        assert last_coord_conflict is not None
        raise last_coord_conflict


    fresh_parent, _, fresh_records = _load_state(repo, token, coord_branch)
    fresh = fresh_records.get(issue)
    if fresh_parent != commit_sha or fresh is None:
        raise ProductionExecutorError(
            "post-commit readback did not resolve exact transaction commit"
        )
    if execution_record_fingerprint(fresh) != execution_record_fingerprint(post):
        raise ProductionExecutorError(
            "post-commit ExecutionRecord fingerprint mismatch"
        )


    monitor_payload: dict[str, object]
    try:
        monitor_commit_sha, observation = _publish_transaction_progress(
            repo,
            token,
            record=fresh,
            invocation_identity=invocation_identity,
            runtime_owner=lane_id,
            action=kind,
        )
        monitor_payload = {
            "runtime_observation_status": "APPLIED",
            "runtime_observation_commit_sha": monitor_commit_sha,
            "runtime_observation_event": observation["event"],
            "runtime_liveness_state": observation["liveness_state"],
            "runtime_last_heartbeat_at": observation["last_heartbeat_at"],
            "runtime_heartbeat_expires_at": observation["heartbeat_expires_at"],
        }
    except Exception as exc:
        # coord/execution-v2 is authoritative; coord/monitor-v2 is explicitly
        # NON_AUTHORITY.  A monitor transport failure must never convert an
        # already committed control transaction into a false FAILED result.
        monitor_payload = {
            "runtime_observation_status": "DEGRADED",
            "runtime_observation_error": str(exc),
            "runtime_observation_commit_sha": None,
            "runtime_observation_event": None,
            "runtime_liveness_state": "UNKNOWN",
            "runtime_last_heartbeat_at": None,
            "runtime_heartbeat_expires_at": None,
        }


    return {
        "schema": RESULT_SCHEMA,
        "result": "APPLIED",
        "issue": issue,
        "kind": kind,
        "coord_commit_sha": commit_sha,
        "record_blob_sha": record_blob_sha,
        "post_generation": fresh.generation,
        "post_record_fingerprint": execution_record_fingerprint(fresh),
        "post_state": fresh.state,
        "post_next_action": fresh.next_action.kind if fresh.next_action else None,
        "lease_invocation_identity": fresh.lease.invocation_identity if fresh.lease else None,
        **monitor_payload,
    }




def execute_one(
    *,
    repo: str,
    token: str,
    coord_branch: str,
    issue: int,
    kind: str,
    lane_id: str,
    invocation_identity: str,
    supplied_effect: dict[str, object],
    _allow_terminal_drain: bool = True,
    _allow_delivery_sibling_drain: bool = True,
) -> dict[str, object]:
    """Execute one transaction with bounded side-effect and delivery-tail recovery."""
    try:
        result = _execute_one_attempt(
            repo=repo, token=token, coord_branch=coord_branch,
            issue=issue, kind=kind, lane_id=lane_id,
            invocation_identity=invocation_identity, supplied_effect=supplied_effect,
        )
        result["attempt"] = 1
    except _PostEffectCoordConflict as exc:
        current = exc.observed_record
        if (exc.conflict_class != "POST_EFFECT_SAME_ISSUE_DRIFT"
            or not _readback_continuation_matches(
                exc.previous_record, current, kind, invocation_identity)):
            raise
        try:
            result = _execute_one_attempt(
                repo=repo, token=token, coord_branch=coord_branch,
                issue=issue, kind=kind, lane_id=lane_id,
                invocation_identity=invocation_identity,
                supplied_effect={"runtime_mode": "READBACK_ONLY"},
                _continuation_fingerprint=execution_record_fingerprint(current),
            )
        except Exception as continuation_error:
            if isinstance(continuation_error, RuntimePostEffectConflict):
                raise
            raise RuntimePostEffectConflict(
                "POST_EFFECT_READBACK_CONTINUATION_REJECTED", exc.diagnostics,
            ) from continuation_error
        result["attempt"] = 1
        result["readback_continuation"] = exc.diagnostics

    if (
        _allow_terminal_drain
        and kind in _TERMINAL_TAIL_SOURCE_KINDS
        and result.get("post_state") == "INTEGRATING"
        and result.get("post_next_action") == "FINALIZE"
    ):
        terminal = execute_one(
            repo=repo,
            token=token,
            coord_branch=coord_branch,
            issue=issue,
            kind="FINALIZE",
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            supplied_effect={},
            _allow_terminal_drain=False,
            _allow_delivery_sibling_drain=_allow_delivery_sibling_drain,
        )
        result["terminal_tail_drained"] = terminal.get("post_state") == "DONE"
        result["terminal_tail_finalize"] = {
            "coord_commit_sha": terminal.get("coord_commit_sha"),
            "post_generation": terminal.get("post_generation"),
            "post_state": terminal.get("post_state"),
            "post_next_action": terminal.get("post_next_action"),
            "runtime_observation_status": terminal.get("runtime_observation_status"),
        }
        for key in (
            "post_generation",
            "post_state",
            "post_next_action",
            "post_chain_next_issue",
            "post_chain_next_action",
            "post_chain_next_action_args",
            "lease_invocation_identity",
            "chain_terminal_issue",
        ):
            if key in terminal:
                result[key] = terminal.get(key)

    if (
        _allow_delivery_sibling_drain
        and kind == "FINALIZE"
        and result.get("post_state") == "DONE"
        and result.get("post_chain_next_action") == "RECOVER_POST_DELIVERY"
    ):
        next_issue = result.get("post_chain_next_issue")
        args = result.get("post_chain_next_action_args")
        if (
            isinstance(next_issue, bool)
            or not isinstance(next_issue, int)
            or next_issue <= 0
            or not isinstance(args, dict)
        ):
            raise ProductionExecutorError(
                "FINALIZE delivery sibling continuation is malformed"
            )
        pr_number = args.get("pr_number")
        if (
            isinstance(pr_number, bool)
            or not isinstance(pr_number, int)
            or pr_number <= 0
        ):
            raise ProductionExecutorError(
                "FINALIZE delivery sibling continuation pr_number is invalid"
            )

        recovery = recover_post_delivery_missing_record(
            repo=repo,
            token=token,
            coord_branch=coord_branch,
            issue=next_issue,
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            expected_coord_head=str(result["coord_commit_sha"]),
            supplied_effect={"pr_number": pr_number},
        )
        sibling_terminal = execute_one(
            repo=repo,
            token=token,
            coord_branch=coord_branch,
            issue=next_issue,
            kind="FINALIZE",
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            supplied_effect={},
            _allow_terminal_drain=False,
            _allow_delivery_sibling_drain=True,
        )
        result["delivery_sibling_drained"] = (
            sibling_terminal.get("post_state") == "DONE"
        )
        result["delivery_sibling_recovery"] = {
            "issue": next_issue,
            "coord_commit_sha": recovery.get("coord_commit_sha"),
            "post_generation": recovery.get("post_generation"),
            "post_state": recovery.get("post_state"),
        }
        result["delivery_sibling_finalize"] = {
            "issue": next_issue,
            "coord_commit_sha": sibling_terminal.get("coord_commit_sha"),
            "post_generation": sibling_terminal.get("post_generation"),
            "post_state": sibling_terminal.get("post_state"),
            "post_chain_next_issue": sibling_terminal.get("post_chain_next_issue"),
        }
        result["chain_terminal_issue"] = sibling_terminal.get(
            "chain_terminal_issue", next_issue
        )
        for key in (
            "post_generation",
            "post_state",
            "post_next_action",
            "post_chain_next_issue",
            "post_chain_next_action",
            "post_chain_next_action_args",
            "lease_invocation_identity",
        ):
            result[key] = sibling_terminal.get(key)

    return result




def main() -> int:
    # DIRECT_PRODUCTION_EXECUTOR_CLI_RETIRED_V1
    # The trusted request ingress imports execute_one() directly after validating
    # startup/preflight/runtime provenance.  A standalone CLI would bypass that
    # envelope, so fail closed before parsing args or touching GitHub.
    print(
        "DIRECT_PRODUCTION_EXECUTOR_CLI_RETIRED: "
        "use tools/control_transaction_request_ingress.py via the trusted push-request workflow",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
