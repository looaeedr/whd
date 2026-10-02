"""Post-integration durability for the full-repo/shared-unpushed WHD workflow.

After Flow v2 reaches durable DONE, physical completion means two things only:
1. the canonical full repo root is synced to the accepted merged commit/tree; and
2. the selected shared-unpushed lane has a delivery receipt and no longer
   exposes the delivered generation as pending work.

Legacy snapshot/manifests and per-Issue workspace archival are
SUPERSEDED and must not participate in CURRENT completion decisions.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

CONTRACT_SCHEMA = "WHD_POST_INTEGRATION_DURABILITY_V2"
ROOT_SYNC_RECEIPT_SCHEMA = "WHD_CANONICAL_ROOT_SYNC_RECEIPT_V1"
LANE_DELIVERY_RECEIPT_SCHEMA = "WHD_UNPUSHED_LANE_DELIVERY_RECEIPT_V1"
CANONICAL_ROOT = "/Google Drive/WHD"
LANES = frozenset({"body", "docs"})
LANE_FINAL_STATES = frozenset({"EMPTY", "ROLLED_FORWARD"})


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
    if item.get("canonical_root") != CANONICAL_ROOT:
        raise ValueError("canonical root mismatch")
    if item.get("root_sync_receipt_schema") != ROOT_SYNC_RECEIPT_SCHEMA:
        raise ValueError("root sync receipt schema mismatch")
    if item.get("lane_delivery_receipt_schema") != LANE_DELIVERY_RECEIPT_SCHEMA:
        raise ValueError("lane delivery receipt schema mismatch")
    forbidden = set(map(str, item.get("forbidden_current_authorities") or ()))
    expected = {"SOURCE_SNAPSHOT", "CURRENT_SOURCE_MANIFEST", "WORK_ACTIVE_ARCHIVE"}
    if not expected <= forbidden:
        raise ValueError("legacy durability authorities must be explicitly forbidden")
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


def build_root_sync_receipt(
    *, accepted_sha: str, accepted_tree_sha: str, root_head_sha: str,
    root_tree_sha: str, root_path: str = CANONICAL_ROOT,
) -> dict[str, object]:
    accepted_sha = _sha(accepted_sha, "accepted_sha")
    accepted_tree_sha = _sha(accepted_tree_sha, "accepted_tree_sha")
    root_head_sha = _sha(root_head_sha, "root_head_sha")
    root_tree_sha = _sha(root_tree_sha, "root_tree_sha")
    if str(root_path) != CANONICAL_ROOT:
        raise ValueError("root sync receipt canonical root mismatch")
    if root_head_sha != accepted_sha:
        raise ValueError("canonical root HEAD does not match accepted merge")
    if root_tree_sha != accepted_tree_sha:
        raise ValueError("canonical root tree does not match accepted tree")
    return {
        "schema": ROOT_SYNC_RECEIPT_SCHEMA,
        "status": "VERIFIED",
        "canonical_root": CANONICAL_ROOT,
        "accepted_sha": accepted_sha,
        "accepted_tree_sha": accepted_tree_sha,
        "root_head_sha": root_head_sha,
        "root_tree_sha": root_tree_sha,
    }


def validate_root_sync_receipt(receipt: object, *, expected_merged_sha: str) -> dict[str, object]:
    item = _mapping(receipt, "root sync receipt")
    if item.get("schema") != ROOT_SYNC_RECEIPT_SCHEMA or item.get("status") != "VERIFIED":
        raise ValueError("root sync receipt is not VERIFIED")
    if item.get("canonical_root") != CANONICAL_ROOT:
        raise ValueError("root sync receipt canonical root mismatch")
    accepted = _sha(item.get("accepted_sha"), "root sync accepted_sha")
    if accepted != _sha(expected_merged_sha, "expected merged_sha"):
        raise ValueError("root sync receipt merged SHA mismatch")
    if _sha(item.get("root_head_sha"), "root sync root_head_sha") != accepted:
        raise ValueError("root sync receipt root HEAD mismatch")
    accepted_tree = _sha(item.get("accepted_tree_sha"), "root sync accepted_tree_sha")
    if _sha(item.get("root_tree_sha"), "root sync root_tree_sha") != accepted_tree:
        raise ValueError("root sync receipt tree mismatch")
    return {str(k): v for k, v in item.items()}


def build_lane_delivery_receipt(
    *, lane: str, issue: int, generation: int, merged_sha: str,
    manifest_digest: str, delivered_paths: Iterable[str], lane_state_after: str,
) -> dict[str, object]:
    lane = str(lane).strip().lower()
    if lane not in LANES:
        raise ValueError("invalid delivered lane")
    state = str(lane_state_after).strip().upper()
    if state not in LANE_FINAL_STATES:
        raise ValueError("lane_state_after must be EMPTY or ROLLED_FORWARD")
    paths = tuple(sorted(set(map(str, delivered_paths))))
    if not paths:
        raise ValueError("delivery receipt requires delivered paths")
    return {
        "schema": LANE_DELIVERY_RECEIPT_SCHEMA,
        "status": "VERIFIED",
        "lane": lane,
        "issue": _positive_int(issue, "delivery issue"),
        "generation": _positive_int(generation, "delivery generation"),
        "merged_sha": _sha(merged_sha, "delivery merged_sha"),
        "manifest_digest": _sha256(manifest_digest, "delivery manifest_digest"),
        "delivered_paths": list(paths),
        "lane_state_after": state,
    }


def validate_lane_delivery_receipt(receipt: object, *, expected_issue: int, expected_merged_sha: str) -> dict[str, object]:
    item = _mapping(receipt, "lane delivery receipt")
    if item.get("schema") != LANE_DELIVERY_RECEIPT_SCHEMA or item.get("status") != "VERIFIED":
        raise ValueError("lane delivery receipt is not VERIFIED")
    if str(item.get("lane") or "") not in LANES:
        raise ValueError("lane delivery receipt lane invalid")
    if _positive_int(item.get("issue"), "delivery issue") != _positive_int(expected_issue, "expected issue"):
        raise ValueError("lane delivery receipt issue mismatch")
    if _sha(item.get("merged_sha"), "delivery merged_sha") != _sha(expected_merged_sha, "expected merged_sha"):
        raise ValueError("lane delivery receipt merged SHA mismatch")
    _positive_int(item.get("generation"), "delivery generation")
    _sha256(item.get("manifest_digest"), "delivery manifest_digest")
    paths = item.get("delivered_paths")
    if not isinstance(paths, list) or not paths:
        raise ValueError("lane delivery receipt delivered_paths missing")
    if str(item.get("lane_state_after") or "") not in LANE_FINAL_STATES:
        raise ValueError("delivered lane still exposes pending generation")
    return {str(k): v for k, v in item.items()}


def classify_post_integration_durability(
    *, execution_record: object, root_sync_receipt: object | None,
    lane_delivery_receipt: object | None,
) -> dict[str, object]:
    try:
        terminal = validate_terminal_execution(execution_record)
    except ValueError as exc:
        return {"state": "NOT_TERMINAL", "next_action": "WAIT_EXECUTION_DONE", "reason": str(exc)}

    if root_sync_receipt is None:
        return {
            "state": "ROOT_SYNC_PENDING",
            "next_action": "SYNC_CANONICAL_ROOT_TO_ACCEPTED_HEAD",
            "issue": terminal["issue"],
        }
    try:
        validate_root_sync_receipt(root_sync_receipt, expected_merged_sha=terminal["merged_sha"])
    except ValueError as exc:
        return {
            "state": "ROOT_SYNC_PENDING",
            "next_action": "SYNC_CANONICAL_ROOT_TO_ACCEPTED_HEAD",
            "issue": terminal["issue"],
            "reason": str(exc),
        }

    if lane_delivery_receipt is None:
        return {
            "state": "LANE_CLEANUP_PENDING",
            "next_action": "FINALIZE_DELIVERED_LANE_ZERO",
            "issue": terminal["issue"],
        }
    try:
        validate_lane_delivery_receipt(
            lane_delivery_receipt,
            expected_issue=terminal["issue"],
            expected_merged_sha=terminal["merged_sha"],
        )
    except ValueError as exc:
        return {
            "state": "LANE_CLEANUP_PENDING",
            "next_action": "FINALIZE_DELIVERED_LANE_ZERO",
            "issue": terminal["issue"],
            "reason": str(exc),
        }

    return {"state": "DURABLE_CLEANUP_COMPLETE", "next_action": None, "issue": terminal["issue"]}
