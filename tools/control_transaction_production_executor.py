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
from tools.execution_record import (
    ActionSpec,
    ExecutionRecord,
    ExecutionRecordError,
    execution_record_fingerprint,
    execution_record_from_payload,
    execution_record_to_payload,
)

RESULT_SCHEMA = "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2"
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
        result = {"schema": RESULT_SCHEMA, "result": "CONFLICT", "reason": str(exc)}
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
