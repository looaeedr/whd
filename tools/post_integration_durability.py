"""Post-integration durability gate for WHD root-local-first work.

This module owns only the cleanup tail *after* Flow v2 execution is durably DONE.
It does not own execution state, lease, mutation authority, merge, or issue closure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

CONTRACT_SCHEMA = "WHD_POST_INTEGRATION_DURABILITY_V1"
EXPORT_SCHEMA = "WHD_DRIVE_SOURCE_EXPORT_V1"
SOURCE_EXPORT_REQUEST_SCHEMA = "WHD_SOURCE_EXPORT_REQUEST_V1"
SOURCE_EXPORT_REQUEST_BRANCH = "coord/source-export-requests"
SOURCE_EXPORT_REQUEST_PATH = ".dispatch/source-export-request.json"
SOURCE_EXPORT_BRANCH = "cleanup/2d-3d-sync"
SNAPSHOT_RECEIPT_SCHEMA = "WHD_SOURCE_SNAPSHOT_WRITEBACK_RECEIPT_V1"
WORKSPACE_ARCHIVE_RECEIPT_SCHEMA = "WHD_WORKSPACE_ARCHIVE_RECEIPT_V1"
ACTIVE_PREFIX = "/Google Drive/WHD/work/active"
DONE_PREFIX = "/Google Drive/WHD/work/done"
SNAPSHOT_PREFIX = "/Google Drive/WHD/source/snapshots"
ROOT_LOCAL_GATE_PATH = "/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
ROOT_LOCAL_GATE_FILE_ID = "1qOMBtDwNGK5yxq_iyfISKYYDkBITXFuV"


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sha(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError(f"{label} must be a 40-character hex SHA")
    return text


def _sha256(value: object, label: str, *, prefixed: bool = False) -> str:
    text = str(value or "").strip().lower()
    pattern = r"sha256:[0-9a-f]{64}" if prefixed else r"[0-9a-f]{64}"
    if not re.fullmatch(pattern, text):
        raise ValueError(f"{label} must be {'sha256:<64hex>' if prefixed else 'SHA256'}")
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
        raise ValueError("post-integration durability contract is not CURRENT")
    if item.get("owner") != "tools/post_integration_durability.py":
        raise ValueError("post-integration durability owner mismatch")
    if item.get("execution_state_owner") != "WHD_EXECUTION_RECORD_V2":
        raise ValueError("execution state owner must remain WHD_EXECUTION_RECORD_V2")
    if item.get("active_workspace_prefix") != ACTIVE_PREFIX:
        raise ValueError("active workspace prefix mismatch")
    if item.get("done_workspace_prefix") != DONE_PREFIX:
        raise ValueError("done workspace prefix mismatch")
    if item.get("snapshot_prefix") != SNAPSHOT_PREFIX:
        raise ValueError("snapshot prefix mismatch")
    pointer = _mapping(item.get("root_local_gate_pointer"), "root_local_gate_pointer")
    if pointer.get("path") != ROOT_LOCAL_GATE_PATH or pointer.get("file_id") != ROOT_LOCAL_GATE_FILE_ID:
        raise ValueError("root-local gate pointer mismatch")
    if item.get("physical_cycle_completion_guard") != "tools/execution_invocation_exit.py::assert_repository_content_cycle_complete":
        raise ValueError("physical cycle completion guard mismatch")
    if item.get("artifact_source_identity_policy") != "TRUSTED_EXPORT_MANIFEST_SOURCE_SHA_PLUS_EXACT_ARTIFACT_NAME; WORKFLOW_RUN_HEAD_SHA_IS_TRANSPORT_TRIGGER_IDENTITY":
        raise ValueError("artifact source identity policy mismatch")
    if item.get("source_export_request_schema") != SOURCE_EXPORT_REQUEST_SCHEMA:
        raise ValueError("source export request schema mismatch")
    if item.get("source_export_request_branch") != SOURCE_EXPORT_REQUEST_BRANCH:
        raise ValueError("source export request branch mismatch")
    if item.get("source_export_request_path") != SOURCE_EXPORT_REQUEST_PATH:
        raise ValueError("source export request path mismatch")
    if item.get("source_export_request_source_branch") != SOURCE_EXPORT_BRANCH:
        raise ValueError("source export request source branch mismatch")
    return {str(k): v for k, v in item.items()}


def build_source_export_request(*, source_sha: str) -> dict[str, object]:
    return {
        "schema": SOURCE_EXPORT_REQUEST_SCHEMA,
        "version": 1,
        "source_branch": SOURCE_EXPORT_BRANCH,
        "source_sha": _sha(source_sha, "source export request source_sha"),
    }


def validate_source_export_request(payload: object) -> dict[str, object]:
    item = _mapping(payload, "source export request")
    if item.get("schema") != SOURCE_EXPORT_REQUEST_SCHEMA:
        raise ValueError("unexpected source export request schema")
    if item.get("version") != 1:
        raise ValueError("source export request version must be 1")
    if str(item.get("source_branch") or "").strip() != SOURCE_EXPORT_BRANCH:
        raise ValueError("source export request source_branch must be cleanup/2d-3d-sync")
    source_sha = _sha(item.get("source_sha"), "source export request source_sha")
    return {
        "schema": SOURCE_EXPORT_REQUEST_SCHEMA,
        "version": 1,
        "source_branch": SOURCE_EXPORT_BRANCH,
        "source_sha": source_sha,
    }


def source_export_request_transport() -> dict[str, str]:
    return {
        "schema": SOURCE_EXPORT_REQUEST_SCHEMA,
        "branch": SOURCE_EXPORT_REQUEST_BRANCH,
        "path": SOURCE_EXPORT_REQUEST_PATH,
        "source_branch": SOURCE_EXPORT_BRANCH,
    }


def build_snapshot_writeback_receipt(
    *,
    export_manifest: object,
    artifact: object,
    drive_snapshot: object,
) -> dict[str, object]:
    export = _mapping(export_manifest, "source export manifest")
    if export.get("schema") != EXPORT_SCHEMA:
        raise ValueError("unexpected source export manifest schema")
    source_sha = _sha(export.get("source_sha"), "source export source_sha")
    tree_sha = _sha(export.get("tree_sha"), "source export tree_sha")
    run_id = _positive_int(export.get("github_run_id"), "github_run_id")
    snapshot_name = str(export.get("snapshot_name") or "").strip()
    if not snapshot_name:
        raise ValueError("snapshot_name must be nonblank")
    snapshot_sha256 = _sha256(export.get("snapshot_sha256"), "snapshot_sha256")
    artifact_name = str(export.get("artifact_name") or "").strip()
    if artifact_name != f"whd-drive-source-{source_sha}":
        raise ValueError("artifact_name is not exact-source bound")

    art = _mapping(artifact, "GitHub artifact readback")
    artifact_id = _positive_int(art.get("id"), "artifact_id")
    if str(art.get("name") or "").strip() != artifact_name:
        raise ValueError("artifact name mismatch")
    artifact_digest = _sha256(art.get("digest"), "artifact digest", prefixed=True)
    run = _mapping(art.get("workflow_run"), "artifact workflow_run")
    if _positive_int(run.get("id"), "artifact workflow run id") != run_id:
        raise ValueError("artifact workflow run mismatch")
    trigger_head_sha = _sha(run.get("head_sha"), "artifact head_sha")

    drive = _mapping(drive_snapshot, "Drive snapshot readback")
    drive_file_id = str(drive.get("file_id") or "").strip()
    if not drive_file_id:
        raise ValueError("Drive snapshot file_id must be nonblank")
    if str(drive.get("name") or "").strip() != snapshot_name:
        raise ValueError("Drive snapshot name mismatch")
    if _sha256(drive.get("sha256"), "Drive snapshot sha256") != snapshot_sha256:
        raise ValueError("Drive snapshot digest mismatch")
    size = _positive_int(drive.get("size"), "Drive snapshot size")

    return {
        "schema": SNAPSHOT_RECEIPT_SCHEMA,
        "status": "VERIFIED",
        "source_sha": source_sha,
        "tree_sha": tree_sha,
        "github_run_id": run_id,
        "trigger_head_sha": trigger_head_sha,
        "artifact_id": artifact_id,
        "artifact_name": artifact_name,
        "artifact_digest": artifact_digest,
        "snapshot_name": snapshot_name,
        "snapshot_sha256": snapshot_sha256,
        "drive_file_id": drive_file_id,
        "drive_size": size,
    }


def build_manifest_complete_patch(receipt: object) -> dict[str, object]:
    item = _mapping(receipt, "snapshot writeback receipt")
    if item.get("schema") != SNAPSHOT_RECEIPT_SCHEMA or item.get("status") != "VERIFIED":
        raise ValueError("snapshot writeback receipt is not VERIFIED")
    source_sha = _sha(item.get("source_sha"), "receipt source_sha")
    tree_sha = _sha(item.get("tree_sha"), "receipt tree_sha")
    snapshot_sha256 = _sha256(item.get("snapshot_sha256"), "receipt snapshot_sha256")
    artifact_digest = _sha256(item.get("artifact_digest"), "receipt artifact_digest", prefixed=True)
    return {
        "durable_snapshot_base_sha": source_sha,
        "durable_snapshot_base_tree_sha": tree_sha,
        "durable_snapshot_file_id": str(item.get("drive_file_id") or ""),
        "durable_snapshot_name": str(item.get("snapshot_name") or ""),
        "durable_snapshot_status": "CURRENT_EXACT_HEAD",
        "export_writeback_status": "COMPLETE",
        "post_integration_export_run_id": _positive_int(item.get("github_run_id"), "receipt github_run_id"),
        "post_integration_export_trigger_head_sha": _sha(item.get("trigger_head_sha"), "receipt trigger_head_sha"),
        "post_integration_export_artifact_id": _positive_int(item.get("artifact_id"), "receipt artifact_id"),
        "post_integration_export_artifact_digest": artifact_digest,
        "durable_snapshot_sha256": snapshot_sha256,
        "durable_snapshot_readback": "VERIFIED",
        "root_local_gate_json_path": ROOT_LOCAL_GATE_PATH,
        "root_local_gate_json_file_id": ROOT_LOCAL_GATE_FILE_ID,
    }


def validate_workspace_archive_eligibility(execution_record: object) -> dict[str, object]:
    record = _mapping(execution_record, "ExecutionRecord")
    if str(record.get("state") or "") != "DONE":
        raise ValueError("workspace archival requires DONE ExecutionRecord")
    if record.get("lease") is not None:
        raise ValueError("workspace archival requires lease=null")
    if record.get("next_action") is not None:
        raise ValueError("workspace archival requires next_action=null")
    scope = _mapping(record.get("mutation_scope"), "ExecutionRecord mutation_scope")
    if scope.get("reservation_state") != "RELEASED":
        raise ValueError("workspace archival requires RELEASED reservation")
    closure = _mapping(record.get("closure"), "ExecutionRecord closure")
    if closure.get("issue_closed") is not True:
        raise ValueError("workspace archival requires issue_closed=true")
    issue = _positive_int(record.get("issue"), "ExecutionRecord issue")
    generation = _positive_int(record.get("generation"), "ExecutionRecord generation")
    return {
        "schema": WORKSPACE_ARCHIVE_RECEIPT_SCHEMA,
        "eligible": True,
        "issue": issue,
        "generation": generation,
        "required_destination": DONE_PREFIX,
    }


def validate_completed_source_manifest(manifest: object) -> dict[str, object]:
    item = _mapping(manifest, "Current Source Manifest")
    source_sha = _sha(item.get("source_sha"), "manifest source_sha")
    tree_sha = _sha(item.get("tree_sha"), "manifest tree_sha")
    if str(item.get("export_writeback_status") or "") != "COMPLETE":
        raise ValueError("source export writeback is not COMPLETE")
    if str(item.get("durable_snapshot_status") or "") != "CURRENT_EXACT_HEAD":
        raise ValueError("durable snapshot is not CURRENT_EXACT_HEAD")
    if _sha(item.get("durable_snapshot_base_sha"), "snapshot base sha") != source_sha:
        raise ValueError("snapshot base sha does not match source_sha")
    if _sha(item.get("durable_snapshot_base_tree_sha"), "snapshot base tree") != tree_sha:
        raise ValueError("snapshot tree does not match tree_sha")
    if str(item.get("durable_snapshot_readback") or "") != "VERIFIED":
        raise ValueError("snapshot Drive readback is not VERIFIED")
    _sha256(item.get("durable_snapshot_sha256"), "manifest snapshot sha256")
    _sha256(item.get("post_integration_export_artifact_digest"), "manifest artifact digest", prefixed=True)
    _positive_int(item.get("post_integration_export_run_id"), "manifest export run id")
    _sha(item.get("post_integration_export_trigger_head_sha"), "manifest export trigger head sha")
    _positive_int(item.get("post_integration_export_artifact_id"), "manifest artifact id")
    if not str(item.get("durable_snapshot_file_id") or "").strip():
        raise ValueError("manifest durable snapshot file_id missing")
    if not str(item.get("durable_snapshot_name") or "").strip():
        raise ValueError("manifest durable snapshot name missing")
    if str(item.get("root_local_gate_json_path") or "").strip() != ROOT_LOCAL_GATE_PATH:
        raise ValueError("manifest root-local gate path is stale")
    if str(item.get("root_local_gate_json_file_id") or "").strip() != ROOT_LOCAL_GATE_FILE_ID:
        raise ValueError("manifest root-local gate file id is stale")
    return {str(k): v for k, v in item.items()}


def classify_post_integration_durability(
    *,
    execution_record: object,
    source_manifest: object,
    workspace_location: str,
) -> dict[str, object]:
    """Return the only legal cleanup action after a ticket reaches durable DONE."""
    try:
        archive = validate_workspace_archive_eligibility(execution_record)
    except ValueError as exc:
        return {"state": "NOT_TERMINAL", "next_action": "WAIT_EXECUTION_DONE", "reason": str(exc)}

    try:
        completed_manifest = validate_completed_source_manifest(source_manifest)
    except ValueError as exc:
        return {
            "state": "SOURCE_EXPORT_PENDING",
            "next_action": "CONSUME_SOURCE_EXPORT",
            "reason": str(exc),
            "issue": archive["issue"],
            "request_transport": source_export_request_transport(),
        }

    location = str(workspace_location or "").strip().upper()
    if location == "ACTIVE":
        record = _mapping(execution_record, "ExecutionRecord")
        target_sha = _sha(record.get("target_sha"), "ExecutionRecord target_sha")
        manifest_sha = _sha(completed_manifest.get("source_sha"), "manifest source_sha")
        if manifest_sha != target_sha:
            return {
                "state": "SOURCE_EXPORT_PENDING",
                "next_action": "CONSUME_SOURCE_EXPORT",
                "reason": "Current Source Manifest does not cover this terminal target_sha",
                "issue": archive["issue"],
                "request_transport": source_export_request_transport(),
            }
        return {
            "state": "WORKSPACE_ARCHIVE_PENDING",
            "next_action": "ARCHIVE_WORKSPACE_TO_DONE",
            "issue": archive["issue"],
            "destination": DONE_PREFIX,
        }
    if location not in {"DONE", "ABSENT"}:
        raise ValueError("workspace_location must be ACTIVE, DONE, or ABSENT")
    return {
        "state": "DURABLE_CLEANUP_COMPLETE",
        "next_action": None,
        "issue": archive["issue"],
    }