"""Machine validation for the WHD V2 executor-local repository workspace."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Mapping

GATE_SCHEMA = "WHD_WORK_ROOT_HARD_GATE_V2"
EVIDENCE_SCHEMA = "WHD_WORK_ROOT_GATE_EVIDENCE_V2"
DEFAULT_PROVIDER = "executor_local_workspace"
DEFAULT_WORKSPACE_POLICY = "EXECUTOR_LOCAL_REPO_WORKSPACE"
DRIVE_MIRROR_ROOT = "/Google Drive/WHD/WHD_MIRROR/CURRENT"
REPO_CONTRACT_PATH = ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"
RETIRED_DRIVE_WORK_ROOT = "RETIRED_DRIVE_WORK_ROOT"
RETIRED_SHARED_ZERO_ROOT = "RETIRED_SHARED_ZERO_ROOT"
REQUIRED_ROOT_ENTRIES = frozenset({
    ".git", ".agents", ".github", "AGENTS.md", "tools", "tests",
    "ae_engine", "gui_modules",
})
READ_MODE_WORKSPACE = "WORKSPACE_GIT_BASELINE"
READ_MODE_GOOGLE_DRIVE = "GOOGLE_DRIVE_CANONICAL"  # retired input; always rejected
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
    if root.get("path_policy") != DEFAULT_WORKSPACE_POLICY:
        raise ValueError("work-root path policy mismatch")
    if root.get("production_branch") != PRODUCTION_BRANCH:
        raise ValueError("work-root production branch mismatch")
    if root.get("authority") is not False:
        raise ValueError("executor workspace must not become authority")
    mirror = _mapping(gate.get("drive_mirror"), "drive_mirror")
    if mirror.get("library_path") != "/Google Drive/WHD/WHD_MIRROR/CURRENT":
        raise ValueError("Drive mirror path mismatch")
    if mirror.get("role") != "MIRROR_BACKUP_ONLY" or mirror.get("authority") is not False:
        raise ValueError("Drive must remain mirror/backup only")
    if mirror.get("ordinary_startup_required") is not False or mirror.get("routing_forbidden") is not True:
        raise ValueError("Drive mirror must not participate in startup routing")
    recovery = _mapping(gate.get("root_identity_recovery"), "root_identity_recovery")
    if recovery.get("owner") != "tools/work_root_gate.py::recover_canonical_root_to_current_production":
        raise ValueError("work-root recovery owner mismatch")
    if recovery.get("success_schema") != ROOT_RECOVERY_RECEIPT_SCHEMA:
        raise ValueError("work-root recovery success schema mismatch")
    if recovery.get("failure_schema") != ROOT_RECOVERY_RESULT_SCHEMA:
        raise ValueError("work-root recovery failure schema mismatch")
    if recovery.get("terminal_gate") is not False:
        raise ValueError("work-root recovery must not be a terminal gate")
    if recovery.get("closure_authority") is not False:
        raise ValueError("work-root recovery must not own Issue closure")
    if recovery.get("purpose") != "OPTIONAL_WORKSPACE_BASELINE_CATCHUP":
        raise ValueError("work-root recovery purpose must be optional workspace maintenance")
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
    raise ValueError("SHARED_ZERO_ROUTING_RETIRED")


def worker_candidate_path(*, lane: str, worker: str, issue: int) -> str:
    raise ValueError("SHARED_ZERO_ROUTING_RETIRED")


def build_work_root_gate_evidence(
    *,
    gate_payload,
    read_mode: str,
    execution_mode: str,
    root_entries,
    workspace_root: str | None = None,
    production_head_sha: str | None = None,
) -> dict[str, object]:
    validate_gate_payload(gate_payload)
    mode = str(execution_mode or "INTERACTIVE")
    if mode in REMOTE_MODES:
        if read_mode != READ_MODE_GITHUB_REPO:
            raise ValueError("remote mode must read the repository work-root contract")
        source = REPO_CONTRACT_PATH
        resolved_workspace = str(workspace_root or "REMOTE_RUNTIME_WORKSPACE").strip()
    else:
        if read_mode == READ_MODE_WORKSPACE:
            source = REPO_CONTRACT_PATH
            resolved_workspace = str(workspace_root or "").strip()
            if not resolved_workspace:
                raise ValueError("interactive executor workspace_root must be nonblank")
        elif read_mode == READ_MODE_GOOGLE_DRIVE:
            raise ValueError("DRIVE_WORK_ROOT_RETIRED_USE_EXECUTOR_LOCAL_WORKSPACE")
        else:
            raise ValueError("interactive mode must use executor-local workspace Git baseline")
    verified = verify_root_entries(root_entries)
    head = str(production_head_sha or "").strip().lower()
    if head and (len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head)):
        raise ValueError("production_head_sha must be a Git SHA")
    return {
        "schema": EVIDENCE_SCHEMA,
        "gate_schema": GATE_SCHEMA,
        "execution_mode": mode,
        "read_mode": read_mode,
        "source": source,
        "provider": DEFAULT_PROVIDER,
        "workspace_policy": DEFAULT_WORKSPACE_POLICY,
        "workspace_root": resolved_workspace,
        "production_branch": PRODUCTION_BRANCH,
        "production_head_sha": head or None,
        "drive_role": "MIRROR_BACKUP_ONLY",
        "drive_mirror_root": DRIVE_MIRROR_ROOT,
        "root_entries": list(verified),
        "shared_zero_required": False,
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
    if item.get("provider") != DEFAULT_PROVIDER:
        raise ValueError("work-root gate evidence provider mismatch")
    if item.get("workspace_policy") != DEFAULT_WORKSPACE_POLICY:
        raise ValueError("work-root gate evidence workspace policy mismatch")
    if not str(item.get("workspace_root") or "").strip():
        raise ValueError("work-root gate evidence workspace_root missing")
    if item.get("production_branch") != PRODUCTION_BRANCH:
        raise ValueError("work-root gate evidence production branch mismatch")
    if item.get("drive_role") != "MIRROR_BACKUP_ONLY" or item.get("drive_mirror_root") != DRIVE_MIRROR_ROOT:
        raise ValueError("work-root gate evidence Drive mirror boundary mismatch")
    verify_root_entries(item.get("root_entries") or ())
    if item.get("shared_zero_required") is not False:
        raise ValueError("ordinary work-root evidence must not require shared-zero")
    return {str(k): v for k, v in item.items()}

class WorkRootRecoveryError(RuntimeError):
    """Raised when workspace baseline catch-up cannot be proven safe."""


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
    root_path: str = ".",
    remote: str = "origin",
    production_branch: str = PRODUCTION_BRANCH,
) -> dict[str, object]:
    """Fast-forward a clean persistent workspace mirror to the current production ref.

    This is startup/root-identity recovery only. It does not create or mutate
    ExecutionRecords, does not close Issues, and does not emit a
    post-integration durability receipt.
    """
    root = Path(str(root_path)).resolve()
    if not root.is_dir():
        raise WorkRootRecoveryError("workspace root directory is unavailable")

    branch = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if branch != str(production_branch):
        raise WorkRootRecoveryError(
            f"workspace branch mismatch: expected {production_branch}, observed {branch}"
        )

    tracked_status = _run_git(
        root, "status", "--porcelain", "--untracked-files=no"
    ).stdout.strip()
    if tracked_status:
        raise WorkRootRecoveryError("canonical root has tracked worktree/index changes")

    remote = str(remote or "").strip()
    if not remote:
        raise WorkRootRecoveryError("workspace remote must be nonblank")
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
            "workspace history diverged from current production; automatic catch-up refused"
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
        "workspace_root": str(root),
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
    parser = argparse.ArgumentParser(description="WHD executor-local work-root gate and recovery")
    sub = parser.add_subparsers(dest="command", required=True)
    recover = sub.add_parser(
        "recover-current-production",
        help="fast-forward a clean canonical root to current production",
    )
    recover.add_argument("--root", default=".")
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

