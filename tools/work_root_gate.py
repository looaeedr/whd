"""Machine validation for the WHD V2 full-repo Google Drive root."""
from __future__ import annotations

from typing import Mapping

GATE_SCHEMA = "WHD_WORK_ROOT_HARD_GATE_V2"
EVIDENCE_SCHEMA = "WHD_WORK_ROOT_GATE_EVIDENCE_V2"
DEFAULT_PROVIDER = "google_drive"
DEFAULT_LIBRARY_PATH = "/Google Drive/WHD"
DEFAULT_DRIVE_FOLDER_ID = "1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN"
REPO_CONTRACT_PATH = ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"
DRIVE_CONTRACT_PATH = f"{DEFAULT_LIBRARY_PATH}/{REPO_CONTRACT_PATH}"
UNPUSHED_ROOT = f"{DEFAULT_LIBRARY_PATH}/.unpushed"
REQUIRED_ROOT_ENTRIES = frozenset({
    ".git", ".agents", ".github", "AGENTS.md", "tools", "tests",
    "ae_engine", "gui_modules", ".unpushed",
})
READ_MODE_GOOGLE_DRIVE = "GOOGLE_DRIVE_CANONICAL"
READ_MODE_GITHUB_REPO = "GITHUB_REPO_CONTRACT"
REMOTE_MODES = frozenset({"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"})


def _mapping(value: Mapping[str, object] | object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def validate_gate_payload(payload: Mapping[str, object] | object) -> dict[str, object]:
    gate = _mapping(payload, "work-root gate")
    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != "CURRENT":
        raise ValueError("unexpected or non-current work-root gate")
    root = _mapping(gate.get("default_work_root"), "default_work_root")
    if root.get("provider") != DEFAULT_PROVIDER:
        raise ValueError("work-root provider mismatch")
    if root.get("library_path") != DEFAULT_LIBRARY_PATH:
        raise ValueError("work-root library path mismatch")
    if root.get("drive_folder_id") != DEFAULT_DRIVE_FOLDER_ID:
        raise ValueError("work-root folder identity mismatch")
    required = set(map(str, gate.get("required_root_entries") or ()))
    if required != set(REQUIRED_ROOT_ENTRIES):
        raise ValueError("full-repo root required entries mismatch")
    unpushed = _mapping(gate.get("unpushed"), "unpushed")
    if unpushed.get("root") != UNPUSHED_ROOT:
        raise ValueError("shared unpushed root mismatch")
    return {str(k): v for k, v in gate.items()}


def verify_root_entries(entries) -> tuple[str, ...]:
    actual = {str(x) for x in entries}
    missing = sorted(REQUIRED_ROOT_ENTRIES - actual)
    if missing:
        raise ValueError(f"FULL_REPO_ROOT_MISSING_ENTRIES:{missing}")
    legacy = {"source", "state", "work", "artifacts"} & actual
    if legacy:
        raise ValueError(f"LEGACY_CONTROL_ROOT_LAYOUT_FORBIDDEN:{sorted(legacy)}")
    return tuple(sorted(actual))


def unpushed_zero_path(lane: str) -> str:
    lane = str(lane).strip().lower()
    if lane not in {"body", "docs"}:
        raise ValueError(f"invalid unpushed lane: {lane}")
    return f"{UNPUSHED_ROOT}/{lane}/0"


def worker_candidate_path(*, lane: str, worker: str, issue: int) -> str:
    lane = str(lane).strip().lower()
    if lane not in {"body", "docs"}:
        raise ValueError(f"invalid unpushed lane: {lane}")
    if isinstance(issue, bool) or int(issue) <= 0:
        raise ValueError("issue must be positive")
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(worker)).strip("-")
    if not safe:
        raise ValueError("worker must contain a usable character")
    return f"{UNPUSHED_ROOT}/{lane}/workers/{safe}/issue-{int(issue)}"


def build_work_root_gate_evidence(*, gate_payload, read_mode: str, execution_mode: str, root_entries) -> dict[str, object]:
    validate_gate_payload(gate_payload)
    mode = str(execution_mode or "INTERACTIVE")
    if mode in REMOTE_MODES:
        if read_mode != READ_MODE_GITHUB_REPO:
            raise ValueError("remote mode must read the repository work-root contract")
        source = REPO_CONTRACT_PATH
    else:
        if read_mode != READ_MODE_GOOGLE_DRIVE:
            raise ValueError("interactive mode must read the Drive-root repository contract")
        source = DRIVE_CONTRACT_PATH
    verified = verify_root_entries(root_entries)
    return {
        "schema": EVIDENCE_SCHEMA,
        "gate_schema": GATE_SCHEMA,
        "execution_mode": mode,
        "read_mode": read_mode,
        "source": source,
        "provider": DEFAULT_PROVIDER,
        "library_path": DEFAULT_LIBRARY_PATH,
        "drive_folder_id": DEFAULT_DRIVE_FOLDER_ID,
        "root_entries": list(verified),
        "unpushed_root": UNPUSHED_ROOT,
        "status": "GREEN",
    }


def validate_work_root_gate_evidence(evidence, *, execution_mode: str) -> dict[str, object]:
    item = _mapping(evidence, "work-root gate evidence")
    if item.get("schema") != EVIDENCE_SCHEMA or item.get("gate_schema") != GATE_SCHEMA:
        raise ValueError("work-root gate evidence schema mismatch")
    if item.get("status") != "GREEN":
        raise ValueError("work-root gate evidence is not GREEN")
    if item.get("execution_mode") != str(execution_mode or "INTERACTIVE"):
        raise ValueError("work-root gate evidence execution_mode mismatch")
    if item.get("drive_folder_id") != DEFAULT_DRIVE_FOLDER_ID:
        raise ValueError("work-root gate evidence folder mismatch")
    verify_root_entries(item.get("root_entries") or ())
    if item.get("unpushed_root") != UNPUSHED_ROOT:
        raise ValueError("work-root gate evidence unpushed root mismatch")
    return {str(k): v for k, v in item.items()}
