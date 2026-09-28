"""Machine validation for the WHD default Google Drive workspace-root hard gate."""

from __future__ import annotations

from typing import Mapping

import re

GATE_SCHEMA = "WHD_WORK_ROOT_HARD_GATE_V1"
EVIDENCE_SCHEMA = "WHD_WORK_ROOT_GATE_EVIDENCE_V1"

DEFAULT_PROVIDER = "google_drive"
DEFAULT_LIBRARY_PATH = "/Google Drive/WHD"
DEFAULT_DRIVE_FOLDER_ID = "1z-P-VXPd1xjK-PS3Jj7RreT2BLEmDvf_"
CANONICAL_GATE_LIBRARY_PATH = "/Google Drive/WHD/WHD_WORK_ROOT_HARD_GATE_V1.json"
CANONICAL_GATE_FILE_ID = "1eTePIN97fHAu-RPDtVRfqrAHP2zRTPmH"
CURRENT_SOURCE_MANIFEST_FILE_ID = "1NnUvzJGz7_SPpHvQ_IJvGR-3QgwbMfGCfgfj1hlpD9U"
REPO_MIRROR_PATH = ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json"
DEFAULT_WORK_PREFIX = f"{DEFAULT_LIBRARY_PATH}/work"

READ_MODE_GOOGLE_DRIVE = "GOOGLE_DRIVE_CANONICAL"
READ_MODE_GITHUB_MIRROR = "GITHUB_MIRROR"
_MIRROR_ALLOWED_EXECUTION_MODES = {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}


def build_interactive_work_path(*, issue: int | None = None, task_key: str | None = None, source_sha: str | None = None) -> str:
    """Build the canonical interactive work path below /Google Drive/WHD/work."""
    if issue is None and not str(task_key or "").strip():
        raise ValueError("issue or task_key is required")
    if issue is not None:
        if isinstance(issue, bool) or int(issue) <= 0:
            raise ValueError("issue must be a positive integer")
        owner = f"issue-{int(issue)}"
    else:
        raw = str(task_key).strip()
        owner = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in raw).strip("-")
        if not owner:
            raise ValueError("task_key must contain a usable character")

    path = f"{DEFAULT_WORK_PREFIX}/{owner}"
    if source_sha is not None:
        sha = str(source_sha).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("source_sha must be a 40-character hex commit SHA")
        path = f"{path}/{sha[:12]}"
    return path


def validate_interactive_workspace_path(path: str, *, execution_mode: str = "INTERACTIVE") -> str:
    """Reject implicit container/GitHub workspaces for normal interactive execution."""
    value = str(path).strip().rstrip("/")
    mode = str(execution_mode).strip() or "INTERACTIVE"
    if mode in _MIRROR_ALLOWED_EXECUTION_MODES:
        return value
    if value != DEFAULT_WORK_PREFIX and not value.startswith(DEFAULT_WORK_PREFIX + "/"):
        raise ValueError(
            f"interactive workspace must be under {DEFAULT_WORK_PREFIX}; got {path!r}"
        )
    return value

def _mapping(value: Mapping[str, object] | object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def validate_gate_payload(
    payload: Mapping[str, object] | object,
    *,
    read_mode: str,
) -> dict[str, object]:
    """Validate canonical Drive gate or its pointer-only GitHub mirror."""
    gate = _mapping(payload, "work-root gate")
    if gate.get("schema") != GATE_SCHEMA:
        raise ValueError("unexpected work-root gate schema")
    if gate.get("status") != "CURRENT":
        raise ValueError("work-root gate is not CURRENT")
    if "current_synced_source" in gate:
        raise ValueError("work-root gate must not duplicate mutable current source state")

    root = _mapping(gate.get("default_work_root"), "default_work_root")
    if root.get("provider") != DEFAULT_PROVIDER:
        raise ValueError("work-root provider mismatch")
    if root.get("library_path") != DEFAULT_LIBRARY_PATH:
        raise ValueError("work-root library path mismatch")
    if root.get("drive_folder_id") != DEFAULT_DRIVE_FOLDER_ID:
        raise ValueError("work-root folder identity mismatch")

    identity = _mapping(gate.get("identity_checks"), "identity_checks")
    if identity.get("required_provider") != DEFAULT_PROVIDER:
        raise ValueError("work-root required provider mismatch")
    if identity.get("required_library_path") != DEFAULT_LIBRARY_PATH:
        raise ValueError("work-root required library path mismatch")
    if identity.get("required_drive_folder_id") != DEFAULT_DRIVE_FOLDER_ID:
        raise ValueError("work-root required folder identity mismatch")
    if identity.get("current_source_manifest_file_id") != CURRENT_SOURCE_MANIFEST_FILE_ID:
        raise ValueError("work-root source manifest identity mismatch")

    forbidden = gate.get("forbidden_default_roots")
    if not isinstance(forbidden, list):
        raise ValueError("forbidden_default_roots must be a list")
    required_forbidden = {"/", "/mnt/data", "/WHD", "GitHub repository checkout"}
    if not required_forbidden.issubset({str(value) for value in forbidden}):
        raise ValueError("work-root forbidden defaults are incomplete")

    if read_mode == READ_MODE_GOOGLE_DRIVE:
        if gate.get("role") == "MIRROR":
            raise ValueError("interactive canonical read cannot use repository mirror payload")
    elif read_mode == READ_MODE_GITHUB_MIRROR:
        if gate.get("role") != "MIRROR" or gate.get("mirror_policy") != "POINTER_ONLY":
            raise ValueError("GitHub-only startup requires pointer-only work-root mirror")
        canonical = _mapping(gate.get("canonical_source"), "canonical_source")
        if canonical.get("provider") != DEFAULT_PROVIDER:
            raise ValueError("work-root mirror canonical provider mismatch")
        if canonical.get("library_path") != CANONICAL_GATE_LIBRARY_PATH:
            raise ValueError("work-root mirror canonical path mismatch")
        if canonical.get("drive_file_id") != CANONICAL_GATE_FILE_ID:
            raise ValueError("work-root mirror canonical file identity mismatch")
    else:
        raise ValueError("unsupported work-root gate read mode")

    return {str(k): v for k, v in gate.items()}


def build_work_root_gate_evidence(
    *,
    gate_payload: Mapping[str, object],
    read_mode: str,
    execution_mode: str,
) -> dict[str, object]:
    """Build machine evidence that one runtime read the correct root-gate surface."""
    execution_mode = str(execution_mode).strip() or "INTERACTIVE"
    gate = validate_gate_payload(gate_payload, read_mode=read_mode)

    if execution_mode in _MIRROR_ALLOWED_EXECUTION_MODES:
        if read_mode != READ_MODE_GITHUB_MIRROR:
            raise ValueError(f"{execution_mode} must use GitHub work-root mirror")
        source = REPO_MIRROR_PATH
    else:
        if read_mode != READ_MODE_GOOGLE_DRIVE:
            raise ValueError("interactive startup must read canonical Google Drive work-root gate")
        source = CANONICAL_GATE_LIBRARY_PATH

    return {
        "schema": EVIDENCE_SCHEMA,
        "gate_schema": GATE_SCHEMA,
        "gate_status": "CURRENT",
        "read_mode": read_mode,
        "execution_mode": execution_mode,
        "source": source,
        "provider": DEFAULT_PROVIDER,
        "library_path": DEFAULT_LIBRARY_PATH,
        "drive_folder_id": DEFAULT_DRIVE_FOLDER_ID,
        "current_source_manifest_file_id": CURRENT_SOURCE_MANIFEST_FILE_ID,
    }


def validate_work_root_gate_evidence(
    evidence: Mapping[str, object] | object,
    *,
    execution_mode: str,
) -> dict[str, object]:
    """Fail closed unless startup evidence proves the fixed WHD work-root gate was read."""
    item = _mapping(evidence, "work-root gate evidence")
    required = {
        "schema",
        "gate_schema",
        "gate_status",
        "read_mode",
        "execution_mode",
        "source",
        "provider",
        "library_path",
        "drive_folder_id",
        "current_source_manifest_file_id",
    }
    missing = sorted(required - set(item))
    if missing:
        raise ValueError(f"work-root gate evidence missing fields: {missing}")
    if item.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError("unexpected work-root gate evidence schema")
    if item.get("gate_schema") != GATE_SCHEMA or item.get("gate_status") != "CURRENT":
        raise ValueError("work-root gate evidence contract mismatch")

    expected_mode = str(execution_mode).strip() or "INTERACTIVE"
    if item.get("execution_mode") != expected_mode:
        raise ValueError("work-root gate evidence execution_mode mismatch")

    read_mode = str(item.get("read_mode"))
    if expected_mode in _MIRROR_ALLOWED_EXECUTION_MODES:
        if read_mode != READ_MODE_GITHUB_MIRROR or item.get("source") != REPO_MIRROR_PATH:
            raise ValueError("GitHub-only execution requires repository root-gate mirror evidence")
    else:
        if read_mode != READ_MODE_GOOGLE_DRIVE or item.get("source") != CANONICAL_GATE_LIBRARY_PATH:
            raise ValueError("interactive execution requires canonical Google Drive root-gate evidence")

    if item.get("provider") != DEFAULT_PROVIDER:
        raise ValueError("work-root gate evidence provider mismatch")
    if item.get("library_path") != DEFAULT_LIBRARY_PATH:
        raise ValueError("work-root gate evidence library path mismatch")
    if item.get("drive_folder_id") != DEFAULT_DRIVE_FOLDER_ID:
        raise ValueError("work-root gate evidence folder identity mismatch")
    if item.get("current_source_manifest_file_id") != CURRENT_SOURCE_MANIFEST_FILE_ID:
        raise ValueError("work-root gate evidence manifest identity mismatch")

    return {str(k): v for k, v in item.items()}
