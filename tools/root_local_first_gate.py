"""Machine contract for WHD root-local-first entry execution.

The canonical workspace remains Google Drive `/Google Drive/WHD`.  A runtime may
materialize that workspace onto a local filesystem for editing/testing, but Git
writes remain locked until the exact root-local diff is tested GREEN and frozen.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

GATE_SCHEMA = "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1"
ENTRY_EVIDENCE_SCHEMA = "WHD_ROOT_LOCAL_FIRST_ENTRY_EVIDENCE_V1"
COMPLETION_EVIDENCE_SCHEMA = "WHD_ROOT_LOCAL_FIRST_COMPLETION_EVIDENCE_V1"

READ_MODE_GOOGLE_DRIVE = "GOOGLE_DRIVE_CANONICAL"
READ_MODE_GITHUB_MIRROR = "GITHUB_MIRROR"

CANONICAL_LIBRARY_PATH = "/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
DEFAULT_LIBRARY_PATH = "/Google Drive/WHD"
DEFAULT_DRIVE_FOLDER_ID = "1z-P-VXPd1xjK-PS3Jj7RreT2BLEmDvf_"
ROOT_WORK_SURFACE = "/Google Drive/WHD/work"

ENTRY_MODE = "ROOT_LOCAL_FIRST"
LOCKED_STATE = "LOCKED_UNTIL_ROOT_TESTS_GREEN"
UNLOCKED_STATE = "GIT_WRITE_UNLOCKED"
PUSH_PAYLOAD_POLICY = "EXACT_TESTED_DIFF_ONLY"
TARGET_DRIFT_POLICY = "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE"
REMOTE_CI_ROLE = "POST_PUSH_VERIFICATION_NOT_FIRST_TEST_SURFACE"
RUNTIME_MATERIALIZATION_POLICY = (
    "MAY_MATERIALIZE_CANONICAL_ROOT_LOCALLY_IF_IDENTITY_AND_SOURCE_PROVENANCE_ARE_PRESERVED"
)

_PRE_GIT_ACCESS = ("READ", "FETCH", "COMPARE")
_FORBIDDEN_BEFORE_GREEN = (
    "CREATE_OR_UPDATE_FILE",
    "CREATE_COMMIT",
    "UPDATE_REF",
    "PUSH",
    "MERGE",
)
_REQUIRED_BEFORE_GIT_WRITE = (
    "ROOT_SOURCE_CURRENT",
    "ROOT_MUTATIONS_COMPLETE",
    "ROOT_TEST_CLASSIFIED",
    "ROOT_TESTS_GREEN",
    "ROOT_DIFF_FROZEN",
)
_TEST_CLASSIFICATIONS = {
    "GOVERNANCE_OR_SKILL",
    "BUGFIX",
    "UPDATE_OR_FEATURE",
    "CORE_OR_HIGH_RISK",
}


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _as_string_list(value: Any, field: str) -> list[str]:
    _expect(isinstance(value, list) and all(isinstance(item, str) for item in value), f"{field} must be a string list")
    return list(value)


def validate_entry_gate_payload(
    payload: Mapping[str, Any], *, read_mode: str
) -> dict[str, Any]:
    """Validate canonical or pointer-mirror entry-gate payload."""

    data = deepcopy(dict(payload))
    _expect(data.get("schema") == GATE_SCHEMA, "root-local entry gate schema mismatch")
    _expect(data.get("version") == 1, "root-local entry gate version mismatch")
    _expect(data.get("status") == "CURRENT", "root-local entry gate is not CURRENT")

    canonical_root = data.get("canonical_root")
    _expect(isinstance(canonical_root, dict), "canonical root block missing")
    _expect(canonical_root.get("provider") == "google_drive", "canonical root provider mismatch")
    _expect(canonical_root.get("library_path") == DEFAULT_LIBRARY_PATH, "canonical root path mismatch")
    _expect(canonical_root.get("drive_folder_id") == DEFAULT_DRIVE_FOLDER_ID, "canonical root folder id mismatch")

    policy = data.get("execution_policy")
    _expect(isinstance(policy, dict), "execution policy missing")
    _expect(policy.get("mode") == ENTRY_MODE, "root-local entry mode mismatch")
    _expect(policy.get("treat_root_as_local_workspace") is True, "canonical root must be treated as local workspace")
    _expect(policy.get("root_work_surface") == ROOT_WORK_SURFACE, "root work surface mismatch")
    _expect(policy.get("runtime_materialization_policy") == RUNTIME_MATERIALIZATION_POLICY, "runtime materialization policy mismatch")
    _expect(policy.get("source_bootstrap") == "CURRENT_SOURCE_MANIFEST", "source bootstrap must use current source manifest")

    pre_git = _as_string_list(policy.get("pre_git_write_git_access"), "pre-Git-write access")
    _expect(pre_git == list(_PRE_GIT_ACCESS), "pre-Git-write access must be READ/FETCH/COMPARE only")
    forbidden = _as_string_list(policy.get("forbidden_before_root_green"), "forbidden-before-green")
    _expect(forbidden == list(_FORBIDDEN_BEFORE_GREEN), "forbidden-before-green contract mismatch")
    required = _as_string_list(policy.get("required_before_git_write"), "required-before-Git-write")
    _expect(required == list(_REQUIRED_BEFORE_GIT_WRITE), "required-before-Git-write contract mismatch")
    _expect(policy.get("git_write_unlock_state") == UNLOCKED_STATE, "Git-write unlock state mismatch")
    _expect(policy.get("push_payload_policy") == PUSH_PAYLOAD_POLICY, "push payload policy mismatch")
    _expect(policy.get("on_target_drift") == TARGET_DRIFT_POLICY, "target drift must resync root and retest")
    _expect(policy.get("remote_ci_role") == REMOTE_CI_ROLE, "remote CI role mismatch")

    classifications = data.get("test_classification")
    _expect(isinstance(classifications, dict), "test classification map missing")
    _expect(set(classifications) == _TEST_CLASSIFICATIONS, "test classification map mismatch")

    if read_mode == READ_MODE_GOOGLE_DRIVE:
        _expect("role" not in data, "canonical Drive gate must not carry mirror role")
        _expect("canonical_source" not in data, "canonical Drive gate must not point to itself")
    elif read_mode == READ_MODE_GITHUB_MIRROR:
        _expect(data.get("role") == "MIRROR", "GitHub entry gate must be a MIRROR")
        _expect(data.get("mirror_policy") == "POINTER_ONLY", "GitHub entry gate mirror must be POINTER_ONLY")
        source = data.get("canonical_source")
        _expect(isinstance(source, dict), "canonical source pointer missing")
        _expect(source.get("provider") == "google_drive", "canonical source provider mismatch")
        _expect(source.get("library_path") == CANONICAL_LIBRARY_PATH, "canonical source library path mismatch")
        _expect(bool(source.get("drive_file_id")), "canonical source Drive file id missing")
        digest = source.get("canonical_payload_sha256")
        _expect(isinstance(digest, str) and len(digest) == 64, "canonical source sha256 missing")
    else:
        raise ValueError(f"unsupported root-local entry gate read mode: {read_mode}")

    return data


def build_root_local_first_entry_evidence(
    *, gate_payload: Mapping[str, Any], read_mode: str, execution_mode: str
) -> dict[str, Any]:
    validate_entry_gate_payload(gate_payload, read_mode=read_mode)
    if execution_mode == "INTERACTIVE" and read_mode != READ_MODE_GOOGLE_DRIVE:
        raise ValueError("interactive startup requires Google Drive canonical entry gate")
    return {
        "schema": ENTRY_EVIDENCE_SCHEMA,
        "status": "VALID",
        "read_mode": read_mode,
        "execution_mode": execution_mode,
        "execution_policy": ENTRY_MODE,
        "canonical_root": DEFAULT_LIBRARY_PATH,
        "root_work_surface": ROOT_WORK_SURFACE,
        "git_write_state": LOCKED_STATE,
        "push_payload_policy": PUSH_PAYLOAD_POLICY,
        "target_drift_policy": TARGET_DRIFT_POLICY,
    }


def validate_root_local_first_entry_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    data = deepcopy(dict(evidence))
    required = {
        "schema": ENTRY_EVIDENCE_SCHEMA,
        "status": "VALID",
        "execution_policy": ENTRY_MODE,
        "canonical_root": DEFAULT_LIBRARY_PATH,
        "root_work_surface": ROOT_WORK_SURFACE,
        "git_write_state": LOCKED_STATE,
        "push_payload_policy": PUSH_PAYLOAD_POLICY,
        "target_drift_policy": TARGET_DRIFT_POLICY,
    }
    for field, expected in required.items():
        _expect(data.get(field) == expected, f"entry evidence {field} mismatch")
    return data


def build_root_local_completion_evidence(
    *,
    source_sha: str,
    root_diff_sha256: str,
    changed_files: Sequence[str],
    test_classification: str,
    completed_states: Iterable[str],
) -> dict[str, Any]:
    states = list(completed_states)
    missing = [state for state in _REQUIRED_BEFORE_GIT_WRITE if state not in states]
    if missing:
        raise ValueError(f"root-local completion missing required state: {missing[0]}")
    _expect(len(source_sha) == 40, "source_sha must be a 40-character Git SHA")
    _expect(len(root_diff_sha256) == 64, "root_diff_sha256 must be a sha256 digest")
    _expect(bool(changed_files) and all(isinstance(path, str) and path for path in changed_files), "changed_files must be non-empty")
    _expect(test_classification in _TEST_CLASSIFICATIONS, "unsupported test classification")
    return {
        "schema": COMPLETION_EVIDENCE_SCHEMA,
        "status": "VALID",
        "source_sha": source_sha,
        "root_diff_sha256": root_diff_sha256,
        "changed_files": list(changed_files),
        "test_classification": test_classification,
        "completed_states": states,
        "git_write_state": UNLOCKED_STATE,
        "push_payload_policy": PUSH_PAYLOAD_POLICY,
        "target_drift_policy": TARGET_DRIFT_POLICY,
    }


def validate_root_local_completion_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    data = deepcopy(dict(evidence))
    _expect(data.get("schema") == COMPLETION_EVIDENCE_SCHEMA, "completion evidence schema mismatch")
    _expect(data.get("status") == "VALID", "completion evidence is not VALID")
    _expect(data.get("git_write_state") == UNLOCKED_STATE, "completion evidence does not unlock Git writes")
    _expect(data.get("push_payload_policy") == PUSH_PAYLOAD_POLICY, "completion push payload policy mismatch")
    _expect(data.get("target_drift_policy") == TARGET_DRIFT_POLICY, "completion target drift policy mismatch")
    states = _as_string_list(data.get("completed_states"), "completion states")
    for state in _REQUIRED_BEFORE_GIT_WRITE:
        _expect(state in states, f"completion evidence missing {state}")
    return data
