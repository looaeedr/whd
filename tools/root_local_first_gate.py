"""Machine gate for WHD interactive root-local-first repository content work."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping

SCHEMA = "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1"
EVIDENCE_SCHEMA = "WHD_ROOT_LOCAL_FIRST_GATE_EVIDENCE_V1"
DEFAULT_ROOT = "/Google Drive/WHD"
DEFAULT_WORK_PREFIX = "/Google Drive/WHD/work/active"
TEST_PROFILE_SCHEMA = "WHD_CHANGE_TEST_PROFILE_V1"
TEST_PROFILE_OWNER = "tools/change_test_profile.py"
REQUIRED_ORDER = (
    "ROOT_SOURCE_CURRENT",
    "ROOT_MUTATIONS_COMPLETE",
    "ROOT_TEST_CLASSIFIED",
    "ROOT_TESTS_GREEN",
    "ROOT_DIFF_FROZEN",
    "GIT_WRITE_UNLOCKED",
)
INTERACTIVE_MODES = {"INTERACTIVE", "CHAT", "DEFAULT"}
REMOTE_MODES = {"SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"}
READ_ONLY_GIT_ACTIONS = {"READ", "FETCH", "COMPARE"}


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sha(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError(f"{label} must be a 40-character hex SHA")
    return text


def validate_contract(payload: object) -> dict[str, object]:
    contract = _mapping(payload, "root-local-first contract")
    if contract.get("schema") != SCHEMA:
        raise ValueError("unexpected root-local-first schema")
    if contract.get("status") != "CURRENT":
        raise ValueError("root-local-first contract is not CURRENT")
    root = _mapping(contract.get("canonical_root"), "canonical_root")
    if root.get("library_path") != DEFAULT_ROOT:
        raise ValueError("canonical root path mismatch")
    if root.get("interactive_work_prefix") != DEFAULT_WORK_PREFIX:
        raise ValueError("interactive work prefix mismatch")
    if tuple(contract.get("required_order") or ()) != REQUIRED_ORDER:
        raise ValueError("root-local-first required order mismatch")
    if contract.get("test_profile_schema") != TEST_PROFILE_SCHEMA:
        raise ValueError("test-profile schema mismatch")
    if contract.get("test_profile_owner") != TEST_PROFILE_OWNER:
        raise ValueError("test-profile owner mismatch")
    if set(contract.get("git_before_unlock") or ()) != READ_ONLY_GIT_ACTIONS:
        raise ValueError("pre-unlock Git action policy mismatch")
    if contract.get("git_write_mode") != "EXACT_TESTED_DIFF_ONLY":
        raise ValueError("Git write mode must be EXACT_TESTED_DIFF_ONLY")
    if contract.get("target_drift_action") != "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE":
        raise ValueError("target drift action mismatch")
    modes = _mapping(contract.get("execution_modes"), "execution_modes")
    if modes.get("INTERACTIVE") != "ROOT_LOCAL_FIRST_REQUIRED":
        raise ValueError("interactive execution mode must require root-local-first")
    for mode in REMOTE_MODES:
        if mode not in modes:
            raise ValueError(f"missing execution mode policy: {mode}")
    return {str(k): v for k, v in contract.items()}


def validate_source_current(*, manifest: object, live_source_sha: str, live_tree_sha: str, touched_path_proofs: Iterable[Mapping[str, object]] = ()) -> dict[str, object]:
    item = _mapping(manifest, "source manifest")
    live_sha = _sha(live_source_sha, "live_source_sha")
    live_tree = _sha(live_tree_sha, "live_tree_sha")
    manifest_sha = _sha(item.get("source_sha"), "manifest source_sha")
    manifest_tree = _sha(item.get("tree_sha"), "manifest tree_sha")
    if manifest_sha == live_sha and manifest_tree == live_tree:
        return {"status": "EXACT_SOURCE_CURRENT", "source_sha": live_sha, "tree_sha": live_tree, "snapshot_status": str(item.get("durable_snapshot_status") or "UNKNOWN")}
    proofs = list(touched_path_proofs)
    if not proofs:
        raise ValueError("ROOT_SOURCE_CURRENT_FAILED: manifest stale and no touched-path proof")
    for proof in proofs:
        path = str(proof.get("path") or "").strip()
        expected = str(proof.get("live_blob_sha") or "").strip().lower()
        observed = str(proof.get("workspace_blob_sha") or "").strip().lower()
        if not path or not re.fullmatch(r"[0-9a-f]{40}", expected) or expected != observed:
            raise ValueError(f"ROOT_SOURCE_CURRENT_FAILED: invalid touched-path proof for {path!r}")
    return {"status": "SCOPED_CURRENT_RECOVERY", "source_sha": live_sha, "tree_sha": live_tree, "verified_paths": sorted(str(p["path"]) for p in proofs)}


def frozen_diff_digest(entries: Iterable[Mapping[str, object]]) -> str:
    normalized = []
    for entry in entries:
        path = str(entry.get("path") or "").strip()
        sha256 = str(entry.get("sha256") or "").strip().lower()
        if not path or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("frozen diff entries require path + sha256")
        normalized.append({"path": path, "sha256": sha256})
    if not normalized:
        raise ValueError("frozen diff must contain at least one entry")
    body = json.dumps(sorted(normalized, key=lambda x: x["path"]), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_gate_evidence(*, execution_mode: str, source_evidence: Mapping[str, object] | None = None, root_mutations_complete: bool = False, test_classified: bool = False, tests_green: bool = False, diff_digest: str | None = None, target_drift: bool = False) -> dict[str, object]:
    mode = str(execution_mode or "INTERACTIVE").strip().upper()
    if mode in REMOTE_MODES:
        return {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "scope": "REMOTE_CONTROL_PLANE_EXCEPTION", "applicable": False, "git_write_unlocked": False, "next_action": "FOLLOW_FLOW_V2_REMOTE_AUTHORITY"}
    if mode not in INTERACTIVE_MODES:
        raise ValueError(f"unsupported execution mode: {mode}")
    completed: list[str] = []
    if not source_evidence:
        next_action = "ROOT_SOURCE_CURRENT"
    else:
        status = str(source_evidence.get("status") or "")
        if status not in {"EXACT_SOURCE_CURRENT", "SCOPED_CURRENT_RECOVERY"}:
            raise ValueError("invalid ROOT_SOURCE_CURRENT evidence")
        completed.append("ROOT_SOURCE_CURRENT")
        if not root_mutations_complete:
            next_action = "ROOT_MUTATIONS_COMPLETE"
        else:
            completed.append("ROOT_MUTATIONS_COMPLETE")
            if not test_classified:
                next_action = "ROOT_TEST_CLASSIFIED"
            else:
                completed.append("ROOT_TEST_CLASSIFIED")
                if not tests_green:
                    next_action = "ROOT_TESTS_GREEN"
                else:
                    completed.append("ROOT_TESTS_GREEN")
                    if not diff_digest:
                        next_action = "ROOT_DIFF_FROZEN"
                    else:
                        if not re.fullmatch(r"[0-9a-f]{64}", diff_digest):
                            raise ValueError("diff_digest must be SHA256")
                        completed.append("ROOT_DIFF_FROZEN")
                        if target_drift:
                            return {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "applicable": True, "completed": completed, "git_write_unlocked": False, "next_action": "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE", "diff_digest": diff_digest}
                        completed.append("GIT_WRITE_UNLOCKED")
                        next_action = "EXACT_TESTED_DIFF_ONLY"
    return {"schema": EVIDENCE_SCHEMA, "execution_mode": mode, "applicable": True, "completed": completed, "git_write_unlocked": "GIT_WRITE_UNLOCKED" in completed, "next_action": next_action, **({"diff_digest": diff_digest} if diff_digest else {})}


def assert_git_content_write_allowed(evidence: object, *, action: str) -> None:
    item = _mapping(evidence, "root-local-first evidence")
    action_name = str(action or "").strip().upper()
    if action_name in READ_ONLY_GIT_ACTIONS:
        return
    if item.get("applicable") is False:
        raise ValueError("root-local-first does not authorize remote control-plane Git content writes")
    if not item.get("git_write_unlocked"):
        raise ValueError("GIT_WRITE_LOCKED_UNTIL_ROOT_DIFF_FROZEN")
    if item.get("next_action") != "EXACT_TESTED_DIFF_ONLY":
        raise ValueError("Git content write is not bound to exact tested diff")
