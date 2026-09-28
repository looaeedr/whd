"""Trusted production writer for one WHD Flow v2 control transaction.

This is the missing production companion to the read-only terminal shadow.
It fresh-reads coord/execution-v2, binds a transaction to the exact canonical
record, applies the pure transaction semantics, and atomically commits both the
post-record and rebuilt DERIVED_CACHE_ONLY ready-index with a non-force ref CAS.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
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
    prepare_transaction,
)
from tools.execution_ready_index import build_ready_index, ready_index_to_payload
from tools.flow_v2_runtime_observation import (
    project_terminal_record_exit,
    project_transaction_progress,
)
from tools.execution_record import (
    ActionSpec,
    ExecutionRecord,
    ExecutionRecordError,
    execution_record_fingerprint,
    execution_record_from_payload,
    execution_record_to_payload,
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
    with urlopen(req, timeout=30) as response:
        raw = response.read()
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
    projector = (
        project_terminal_record_exit
        if record.state == "DONE"
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
            next_action = effect.get("next_action")
            if not isinstance(next_action, dict):
                raise ProductionExecutorError("READY ACQUIRE requires explicit post-acquire next_action")
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


def _finalize_target_readback(
    repo: str,
    token: str,
    *,
    record: ExecutionRecord,
) -> dict[str, object]:
    """Prove that the accepted merge anchor still reaches the live target HEAD."""
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
) -> dict[str, object]:
    """Close/read back the GitHub Issue before a FINALIZE -> DONE transition."""
    if record.state != "INTEGRATING":
        raise ProductionExecutorError("FINALIZE requires INTEGRATING state before issue close")
    if record.qa.last_accepted_run is None or record.qa.accepted_head_sha != record.head_sha:
        raise ProductionExecutorError("FINALIZE requires accepted QA for current head before issue close")
    target_readback = _finalize_target_readback(repo, token, record=record)

    observed = _api(repo, "GET", f"/issues/{issue}", token)
    if (
        str(observed.get("state") or "").lower() != "closed"
        or str(observed.get("state_reason") or "").lower() != "completed"
    ):
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

    return {
        **target_readback,
        "issue_closed": True,
        "issue_state": "closed",
        "issue_state_reason": "completed",
        "issue_closed_at": fresh.get("closed_at"),
    }


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
) -> dict[str, object]:
    parent_sha, tree_sha, records = _load_state(repo, token, coord_branch)
    if issue not in records:
        raise ProductionExecutorError(f"native ExecutionRecord missing for issue {issue}")
    record = records[issue]
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
    if kind == "FINALIZE":
        # FINALIZE does not trust caller-supplied closure booleans.  The trusted
        # writer owns the GitHub side effect and fresh readback, so an accepted
        # merge cannot become DONE while the Issue remains open.
        effect.update(
            _ensure_issue_closed_for_finalize(
                repo,
                token,
                issue=issue,
                record=record,
            )
        )
    post = execute_transaction(record, plan, effect=effect)
    records[issue] = post
    commit_sha, record_blob_sha = _write_state(
        repo,
        token,
        coord_branch,
        parent_sha=parent_sha,
        base_tree_sha=tree_sha,
        records=records,
        issue=issue,
    )

    fresh_parent, _, fresh_records = _load_state(repo, token, coord_branch)
    fresh = fresh_records.get(issue)
    if fresh_parent != commit_sha or fresh is None:
        raise ProductionExecutorError("post-commit readback did not resolve exact transaction commit")
    if execution_record_fingerprint(fresh) != execution_record_fingerprint(post):
        raise ProductionExecutorError("post-commit ExecutionRecord fingerprint mismatch")

    monitor_commit_sha, observation = _publish_transaction_progress(
        repo,
        token,
        record=fresh,
        invocation_identity=invocation_identity,
        runtime_owner=lane_id,
        action=kind,
    )

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
        "runtime_observation_commit_sha": monitor_commit_sha,
        "runtime_observation_event": observation["event"],
        "runtime_liveness_state": observation["liveness_state"],
        "runtime_last_heartbeat_at": observation["last_heartbeat_at"],
        "runtime_heartbeat_expires_at": observation["heartbeat_expires_at"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--coord-branch", default="coord/execution-v2")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--invocation-identity", required=True)
    parser.add_argument("--effect-json", default="{}")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not args.repo or not token:
        raise SystemExit("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
    try:
        effect = json.loads(args.effect_json)
        if not isinstance(effect, dict):
            raise ProductionExecutorError("effect_json must be an object")
        result = execute_one(
            repo=args.repo,
            token=token,
            coord_branch=args.coord_branch,
            issue=args.issue,
            kind=args.kind,
            lane_id=args.lane_id,
            invocation_identity=args.invocation_identity,
            supplied_effect=effect,
        )
        code = 0
    except (ControlTransactionConflict, ControlTransactionReplay) as exc:
        reason = str(exc)
        if reason.startswith("coord/execution-v2 ref advanced"):
            conflict_class = "STALE_COORD_HEAD"
        elif reason.startswith("generation drift"):
            conflict_class = "STALE_GENERATION"
        elif "live lease" in reason:
            conflict_class = "LIVE_LEASE"
        else:
            conflict_class = "STALE_EXECUTION_RECORD"
        result = {
            "schema": RESULT_SCHEMA,
            "result": "CONFLICT",
            "reason": reason,
            "conflict_class": conflict_class,
            "retryable": True,
            "retry_action": "FRESH_READ_REBUILD_SAME_SEMANTIC_ACTION",
            "semantic_effect_applied": False,
        }
        code = 3
    except (ControlTransactionError, ExecutionRecordError, ProductionExecutorError, HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result = {"schema": RESULT_SCHEMA, "result": "FAILED", "reason": str(exc)}
        code = 2

    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
