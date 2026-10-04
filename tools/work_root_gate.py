"""Machine validation for the WHD V2 full-repo Google Drive root."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
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
PRODUCTION_BRANCH = "cleanup/2d-3d-sync"
ROOT_RECOVERY_RECEIPT_SCHEMA = "WHD_WORK_ROOT_RECOVERY_RECEIPT_V1"
ROOT_RECOVERY_RESULT_SCHEMA = "WHD_WORK_ROOT_RECOVERY_RESULT_V1"


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
    recovery = _mapping(gate.get("root_identity_recovery"), "root_identity_recovery")
    if recovery.get("owner") != "tools/work_root_gate.py::recover_canonical_root_to_current_production":
        raise ValueError("work-root recovery owner mismatch")
    if recovery.get("success_schema") != ROOT_RECOVERY_RECEIPT_SCHEMA:
        raise ValueError("work-root recovery success schema mismatch")
    if recovery.get("failure_schema") != ROOT_RECOVERY_RESULT_SCHEMA:
        raise ValueError("work-root recovery failure schema mismatch")
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

class WorkRootRecoveryError(RuntimeError):
    """Raised when canonical work-root catch-up cannot be proven safe."""


def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise WorkRootRecoveryError(
            f"canonical root git command failed: {' '.join(args)}: {str(detail).strip()}"
        ) from exc


def recover_canonical_root_to_current_production(
    *,
    root_path: str = DEFAULT_LIBRARY_PATH,
    remote: str = "origin",
    production_branch: str = PRODUCTION_BRANCH,
) -> dict[str, object]:
    """Fast-forward a clean canonical root to the current production ref.

    This is startup/root-identity recovery only. It does not create or mutate
    ExecutionRecords, does not close Issues, and does not emit a
    post-integration durability receipt.
    """
    root = Path(str(root_path))
    if str(root) != DEFAULT_LIBRARY_PATH:
        raise WorkRootRecoveryError("canonical root path mismatch")
    if not root.is_dir():
        raise WorkRootRecoveryError("canonical root directory is unavailable")

    branch = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if branch != str(production_branch):
        raise WorkRootRecoveryError(
            f"canonical root branch mismatch: expected {production_branch}, observed {branch}"
        )

    tracked_status = _run_git(
        root, "status", "--porcelain", "--untracked-files=no"
    ).stdout.strip()
    if tracked_status:
        raise WorkRootRecoveryError("canonical root has tracked worktree/index changes")

    remote = str(remote or "").strip()
    if not remote:
        raise WorkRootRecoveryError("canonical root remote must be nonblank")
    production_branch = str(production_branch or "").strip()
    if not production_branch:
        raise WorkRootRecoveryError("canonical production branch must be nonblank")

    previous_head = _run_git(root, "rev-parse", "HEAD").stdout.strip().lower()
    remote_ref = f"refs/remotes/{remote}/{production_branch}"
    fetch_refspec = f"refs/heads/{production_branch}:{remote_ref}"
    _run_git(root, "fetch", "--no-tags", remote, fetch_refspec)
    remote_head = _run_git(root, "rev-parse", remote_ref).stdout.strip().lower()

    ancestry = _run_git(
        root, "merge-base", "--is-ancestor", previous_head, remote_head, check=False
    )
    if ancestry.returncode != 0:
        raise WorkRootRecoveryError(
            "canonical root history diverged from current production; automatic catch-up refused"
        )

    if previous_head != remote_head:
        _run_git(root, "reset", "--hard", remote_head)

    root_head = _run_git(root, "rev-parse", "HEAD").stdout.strip().lower()
    root_tree = _run_git(root, "rev-parse", "HEAD^{tree}").stdout.strip().lower()
    if root_head != remote_head:
        raise WorkRootRecoveryError(
            f"canonical root HEAD readback mismatch: expected {remote_head}, observed {root_head}"
        )

    return {
        "schema": ROOT_RECOVERY_RECEIPT_SCHEMA,
        "status": "VERIFIED",
        "canonical_root": DEFAULT_LIBRARY_PATH,
        "production_branch": production_branch,
        "remote": remote,
        "previous_head_sha": previous_head,
        "remote_head_sha": remote_head,
        "root_head_sha": root_head,
        "root_tree_sha": root_tree,
        "recovery_mode": "FAST_FORWARD_CATCH_UP",
        "execution_record_mutated": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WHD canonical work-root gate and recovery")
    sub = parser.add_subparsers(dest="command", required=True)
    recover = sub.add_parser(
        "recover-current-production",
        help="fast-forward a clean canonical root to current production",
    )
    recover.add_argument("--root", default=DEFAULT_LIBRARY_PATH)
    recover.add_argument("--remote", default="origin")
    recover.add_argument("--production-branch", default=PRODUCTION_BRANCH)
    recover.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        receipt = recover_canonical_root_to_current_production(
            root_path=args.root,
            remote=args.remote,
            production_branch=args.production_branch,
        )
        rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except (WorkRootRecoveryError, OSError, ValueError) as exc:
        result = {
            "schema": ROOT_RECOVERY_RESULT_SCHEMA,
            "status": "FAILED",
            "reason": str(exc),
        }
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if getattr(args, "output", None):
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

