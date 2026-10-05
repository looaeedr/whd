"""CURRENT post-integration durability boundary for WHD.

Flow v2 DONE plus trusted merge/Issue readback is terminal authority.
Google Drive is mirror/backup/DR only. Direct Drive-root synchronization and
shared-zero lane cleanup are retired and cannot block or reopen a terminal Issue.
"""
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path

CONTRACT_SCHEMA = "WHD_POST_INTEGRATION_DURABILITY_V2"
ROOT_SYNC_RECEIPT_SCHEMA = "WHD_CANONICAL_ROOT_SYNC_RECEIPT_V1"
HISTORICAL_LANE_RECEIPT_SCHEMA = "HISTORICAL_WHD_UNPUSHED_LANE_DELIVERY_RECEIPT_V1"
PRODUCTION_AUTHORITY = "GITHUB_PRODUCTION_X"
PRODUCTION_BRANCH = "cleanup/2d-3d-sync"
DRIVE_MIRROR_ROOT = "/Google Drive/WHD/WHD_MIRROR/CURRENT"
RETIRED_ROOT_SYNC_ERROR = "CANONICAL_DRIVE_ROOT_SYNC_RETIRED_USE_MIRROR_PIPELINE"
RETIRED_LANE_ERROR = "SHARED_ZERO_LANE_CLEANUP_RETIRED"


class RootSyncError(RuntimeError):
    pass


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sha(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError(f"{label} must be a 40-character hex SHA")
    return text


def _sha256(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError(f"{label} must be SHA256")
    return text


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be positive")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be positive") from exc
    if number <= 0:
        raise ValueError(f"{label} must be positive")
    return number


def validate_contract(payload: object) -> dict[str, object]:
    item = _mapping(payload, "post-integration durability contract")
    if item.get("schema") != CONTRACT_SCHEMA or item.get("status") != "CURRENT":
        raise ValueError("post-integration durability contract is not CURRENT V2")
    if item.get("owner") != "tools/post_integration_durability.py":
        raise ValueError("post-integration durability owner mismatch")
    if item.get("execution_state_owner") != "WHD_EXECUTION_RECORD_V2":
        raise ValueError("execution state owner must remain WHD_EXECUTION_RECORD_V2")
    if item.get("canonical_root") != PRODUCTION_AUTHORITY:
        raise ValueError("production authority mismatch")
    if item.get("production_branch") != PRODUCTION_BRANCH:
        raise ValueError("production branch mismatch")
    if item.get("drive_role") != "MIRROR_BACKUP_ONLY":
        raise ValueError("Drive must remain mirror/backup only")
    if item.get("root_sync_transport") != "RETIRED_USE_MIRROR_PIPELINE":
        raise ValueError("direct Drive-root sync must remain retired")
    ingress = _mapping(item.get("root_sync_ingress"), "root sync ingress")
    if ingress.get("status") != "RETIRED" or ingress.get("owner") is not None:
        raise ValueError("root sync ingress must remain retired")
    if ingress.get("terminal_gate") is not False or ingress.get("closure_authority") is not False:
        raise ValueError("retired root sync ingress cannot own terminal state")
    policy = _mapping(item.get("root_sync_policy"), "root sync policy")
    if policy.get("mode") != "OPTIONAL_MIRROR_MAINTENANCE":
        raise ValueError("Drive durability must remain optional mirror maintenance")
    if policy.get("terminal_gate") is not False or policy.get("closure_authority") is not False:
        raise ValueError("Drive mirror maintenance cannot block terminal completion")
    legacy = _mapping(item.get("legacy_lane_cleanup"), "legacy lane cleanup")
    if legacy.get("status") != "RETIRED" or legacy.get("role") != "HISTORICAL_DATA_ONLY":
        raise ValueError("shared-zero lane cleanup must remain retired")
    if legacy.get("terminal_gate") is not False or legacy.get("closure_authority") is not False:
        raise ValueError("historical lane cleanup cannot own terminal state")
    if item.get("lane_delivery_receipt_schema") != HISTORICAL_LANE_RECEIPT_SCHEMA:
        raise ValueError("historical lane receipt marker mismatch")
    if list(item.get("lane_final_states") or ()) != []:
        raise ValueError("CURRENT durability must not expose shared-zero lane final states")
    if list(item.get("required_order") or ()) != [
        "FLOW_V2_DONE", "MERGE_READBACK_VERIFIED", "DURABLE_CLEANUP_COMPLETE"
    ]:
        raise ValueError("CURRENT durability order mismatch")
    forbidden = set(map(str, item.get("forbidden_current_authorities") or ()))
    if not {"SOURCE_SNAPSHOT", "CURRENT_SOURCE_MANIFEST", "WORK_ACTIVE_ARCHIVE"} <= forbidden:
        raise ValueError("legacy durability authorities must stay forbidden")
    return {str(k): v for k, v in item.items()}


def validate_terminal_execution(execution_record: object) -> dict[str, object]:
    record = _mapping(execution_record, "ExecutionRecord")
    if str(record.get("state") or "") != "DONE":
        raise ValueError("post-integration durability requires DONE ExecutionRecord")
    if record.get("lease") is not None:
        raise ValueError("post-integration durability requires lease=null")
    if record.get("next_action") is not None:
        raise ValueError("post-integration durability requires next_action=null")
    scope = _mapping(record.get("mutation_scope"), "ExecutionRecord mutation_scope")
    if scope.get("reservation_state") != "RELEASED":
        raise ValueError("post-integration durability requires RELEASED reservation")
    closure = _mapping(record.get("closure"), "ExecutionRecord closure")
    if closure.get("issue_closed") is not True:
        raise ValueError("post-integration durability requires issue_closed=true")
    merged_sha = _sha(closure.get("merged_sha") or record.get("target_sha"), "accepted merged_sha")
    return {
        "issue": _positive_int(record.get("issue"), "ExecutionRecord issue"),
        "generation": _positive_int(record.get("generation"), "ExecutionRecord generation"),
        "merged_sha": merged_sha,
    }


def sync_canonical_root_to_accepted_head(
    *,
    execution_record: object,
    accepted_tree_sha: str,
    root_path: str = DRIVE_MIRROR_ROOT,
    remote: str = "origin",
    production_branch: str = PRODUCTION_BRANCH,
) -> dict[str, object]:
    validate_terminal_execution(execution_record)
    _sha(accepted_tree_sha, "accepted_tree_sha")
    raise RootSyncError(RETIRED_ROOT_SYNC_ERROR)


def build_root_sync_receipt(
    *, accepted_sha: str, accepted_tree_sha: str, root_head_sha: str,
    root_tree_sha: str, root_path: str = DRIVE_MIRROR_ROOT,
) -> dict[str, object]:
    accepted_sha = _sha(accepted_sha, "accepted_sha")
    accepted_tree_sha = _sha(accepted_tree_sha, "accepted_tree_sha")
    root_head_sha = _sha(root_head_sha, "root_head_sha")
    root_tree_sha = _sha(root_tree_sha, "root_tree_sha")
    if str(root_path) != DRIVE_MIRROR_ROOT:
        raise ValueError("mirror receipt path mismatch")
    if root_head_sha != accepted_sha:
        raise ValueError("mirror HEAD does not match accepted merge")
    if root_tree_sha != accepted_tree_sha:
        raise ValueError("mirror tree does not match accepted tree")
    return {
        "schema": ROOT_SYNC_RECEIPT_SCHEMA,
        "status": "VERIFIED_NON_BLOCKING",
        "authority": False,
        "drive_role": "MIRROR_BACKUP_ONLY",
        "drive_mirror_root": DRIVE_MIRROR_ROOT,
        "accepted_sha": accepted_sha,
        "accepted_tree_sha": accepted_tree_sha,
        "root_head_sha": root_head_sha,
        "root_tree_sha": root_tree_sha,
    }


def validate_root_sync_receipt(receipt: object, *, expected_merged_sha: str) -> dict[str, object]:
    item = _mapping(receipt, "mirror receipt")
    if item.get("schema") != ROOT_SYNC_RECEIPT_SCHEMA:
        raise ValueError("mirror receipt schema mismatch")
    if item.get("status") != "VERIFIED_NON_BLOCKING" or item.get("authority") is not False:
        raise ValueError("mirror receipt must remain non-authoritative")
    if item.get("drive_role") != "MIRROR_BACKUP_ONLY" or item.get("drive_mirror_root") != DRIVE_MIRROR_ROOT:
        raise ValueError("mirror receipt Drive boundary mismatch")
    accepted = _sha(item.get("accepted_sha"), "mirror accepted_sha")
    if accepted != _sha(expected_merged_sha, "expected merged_sha"):
        raise ValueError("mirror receipt merged SHA mismatch")
    if _sha(item.get("root_head_sha"), "mirror root_head_sha") != accepted:
        raise ValueError("mirror receipt root HEAD mismatch")
    accepted_tree = _sha(item.get("accepted_tree_sha"), "mirror accepted_tree_sha")
    if _sha(item.get("root_tree_sha"), "mirror root_tree_sha") != accepted_tree:
        raise ValueError("mirror receipt tree mismatch")
    return {str(k): v for k, v in item.items()}


def historical_build_lane_delivery_receipt(
    *, lane: str, issue: int, generation: int, merged_sha: str,
    manifest_digest: str, delivered_paths, lane_state_after: str,
) -> dict[str, object]:
    paths = tuple(sorted(set(map(str, delivered_paths))))
    if not paths:
        raise ValueError("historical lane receipt requires delivered paths")
    return {
        "schema": HISTORICAL_LANE_RECEIPT_SCHEMA,
        "status": "HISTORICAL",
        "authority": False,
        "lane": str(lane),
        "issue": _positive_int(issue, "historical delivery issue"),
        "generation": _positive_int(generation, "historical delivery generation"),
        "merged_sha": _sha(merged_sha, "historical delivery merged_sha"),
        "manifest_digest": _sha256(manifest_digest, "historical delivery manifest_digest"),
        "delivered_paths": list(paths),
        "lane_state_after": str(lane_state_after),
    }


def build_lane_delivery_receipt(*args, **kwargs):
    raise ValueError(RETIRED_LANE_ERROR)


def validate_lane_delivery_receipt(*args, **kwargs):
    raise ValueError(RETIRED_LANE_ERROR)


def classify_post_integration_durability(
    *, execution_record: object, root_sync_receipt: object | None,
    lane_delivery_receipt: object | None,
    legacy_lane_cleanup_requested: bool = False,
) -> dict[str, object]:
    try:
        terminal = validate_terminal_execution(execution_record)
    except ValueError as exc:
        return {"state": "NOT_TERMINAL", "next_action": "WAIT_EXECUTION_DONE", "reason": str(exc)}

    mirror_status = "NOT_REQUESTED"
    mirror_reason = None
    if root_sync_receipt is not None:
        try:
            validate_root_sync_receipt(root_sync_receipt, expected_merged_sha=terminal["merged_sha"])
            mirror_status = "VERIFIED_NON_BLOCKING"
        except ValueError as exc:
            mirror_status = "INVALID_NON_BLOCKING"
            mirror_reason = str(exc)

    result = {
        "state": "DURABLE_CLEANUP_COMPLETE",
        "next_action": None,
        "issue": terminal["issue"],
        "root_sync_status": mirror_status,
        "shared_zero_lane_receipt": (
            "HISTORICAL_IGNORED"
            if lane_delivery_receipt is not None or legacy_lane_cleanup_requested
            else "NOT_REQUIRED"
        ),
    }
    if mirror_reason is not None:
        result["root_sync_reason"] = mirror_reason
    return result


def _load_json_file(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RootSyncError(f"failed to read execution record JSON: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Retired Drive-root sync compatibility entrypoint; use the mirror pipeline instead"
    )
    parser.add_argument("--execution-record", type=Path, required=True)
    parser.add_argument("--accepted-tree-sha", required=True)
    parser.add_argument("--root", default=DRIVE_MIRROR_ROOT)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--production-branch", default=PRODUCTION_BRANCH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        sync_canonical_root_to_accepted_head(
            execution_record=_load_json_file(args.execution_record),
            accepted_tree_sha=args.accepted_tree_sha,
            root_path=args.root,
            remote=args.remote,
            production_branch=args.production_branch,
        )
    except (RootSyncError, ValueError, OSError) as exc:
        rendered = json.dumps(
            {
                "schema": "WHD_CANONICAL_ROOT_SYNC_RESULT_V1",
                "status": "RETIRED",
                "authority": False,
                "reason": str(exc),
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 2
    raise AssertionError("retired root-sync entrypoint unexpectedly returned")


if __name__ == "__main__":
    raise SystemExit(main())
