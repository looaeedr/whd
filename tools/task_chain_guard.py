"""Fail-closed task-chain identity guard.

T1 establishes two immutable identities for an in-flight WHD task chain:
- X is always ``cleanup/2d-3d-sync``.
- the chain's frozen base is the SHA captured when the chain was created.

The current X head may advance while a chain is in flight. That observation is status
only and must never refresh or replace ``frozen_base_sha``.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


X_TARGET = "cleanup/2d-3d-sync"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class TaskChainContractError(RuntimeError):
    """Raised when task-chain identity cannot be proven exactly."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise TaskChainContractError(
                f"ambiguous task-chain contract: duplicate JSON key {key!r}"
            )
        payload[key] = value
    return payload


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TaskChainContractError(f"missing required contract field: {key}")
    return value.strip()


def _validate_sha(value: str, label: str) -> str:
    value = str(value).strip()
    if not _SHA_RE.fullmatch(value):
        raise TaskChainContractError(f"malformed {label}: expected 40-char lowercase SHA")
    return value


@dataclass(frozen=True)
class TaskChainContract:
    task_id: str
    target: str
    frozen_base_sha: str
    base_frozen: bool
    observed_target_head_sha: str
    target_advanced: bool


def load_task_chain_contract(path: Path) -> tuple[str, str, str, bool]:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise TaskChainContractError(f"task-chain contract not found: {path}") from exc
    except TaskChainContractError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskChainContractError(f"malformed task-chain contract {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise TaskChainContractError("malformed task-chain contract: root must be an object")

    task_id = _require_text(payload, "task_id")
    target = _require_text(payload, "target")
    frozen_base_sha = _validate_sha(
        _require_text(payload, "frozen_base_sha"), "contract frozen base SHA"
    )
    base_frozen = payload.get("base_frozen")
    if base_frozen is not True:
        raise TaskChainContractError("task-chain base is not frozen/locked")
    return task_id, target, frozen_base_sha, base_frozen


def assert_frozen_base_contract(
    path: Path,
    *,
    expected_task_id: str,
    expected_target: str,
    expected_base_sha: str,
    observed_target_head_sha: str,
) -> TaskChainContract:
    expected_task_id = str(expected_task_id).strip()
    expected_target = str(expected_target).strip()
    expected_base_sha = _validate_sha(expected_base_sha, "expected frozen base SHA")
    observed_target_head_sha = _validate_sha(
        observed_target_head_sha, "current target head SHA"
    )

    if not expected_task_id:
        raise TaskChainContractError("expected task_id must be nonblank")
    if expected_target != X_TARGET:
        raise TaskChainContractError(
            f"X target identity is immutable: expected caller target {X_TARGET!r}, "
            f"got {expected_target!r}"
        )

    task_id, target, frozen_base_sha, base_frozen = load_task_chain_contract(path)
    if task_id != expected_task_id:
        raise TaskChainContractError(
            f"task identity mismatch: expected={expected_task_id!r}, contract={task_id!r}"
        )
    if target != X_TARGET:
        raise TaskChainContractError(
            f"X target identity mismatch: expected={X_TARGET!r}, contract={target!r}"
        )
    if frozen_base_sha != expected_base_sha:
        raise TaskChainContractError(
            "frozen base SHA mismatch: "
            f"expected={expected_base_sha}, contract={frozen_base_sha}; "
            "an in-flight chain must not refresh its base to current X"
        )

    return TaskChainContract(
        task_id=task_id,
        target=target,
        frozen_base_sha=frozen_base_sha,
        base_frozen=base_frozen,
        observed_target_head_sha=observed_target_head_sha,
        target_advanced=observed_target_head_sha != frozen_base_sha,
    )


@dataclass(frozen=True)
class ParentContractCheck:
    task_id: str
    stage_id: str
    expected_parent_sha: str
    actual_parent_sha: str
    current_target_head_sha: str
    expected_parent_issue: int
    work_branch: str


def _load_parent_contract(path: Path) -> tuple[str, str, str, int, str]:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise TaskChainContractError(f"parent contract not found: {path}") from exc
    except TaskChainContractError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskChainContractError(f"malformed parent contract {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise TaskChainContractError("malformed parent contract: root must be an object")

    task_id = _require_text(payload, "task_id")
    stage_id = _require_text(payload, "stage_id")
    expected_parent_sha = _validate_sha(
        _require_text(payload, "expected_parent_sha"), "contract expected parent SHA"
    )
    expected_parent_issue = payload.get("expected_parent_issue")
    if (
        isinstance(expected_parent_issue, bool)
        or not isinstance(expected_parent_issue, int)
        or expected_parent_issue <= 0
    ):
        raise TaskChainContractError("missing required parent contract field: expected_parent_issue")
    work_branch = _require_text(payload, "work_branch")
    return task_id, stage_id, expected_parent_sha, expected_parent_issue, work_branch


def assert_parent_contract(
    path: Path,
    *,
    expected_task_id: str,
    expected_stage_id: str,
    expected_parent_sha: str,
    actual_parent_sha: str,
    current_target_head_sha: str,
) -> ParentContractCheck:
    expected_task_id = str(expected_task_id).strip()
    expected_stage_id = str(expected_stage_id).strip()
    expected_parent_sha = _validate_sha(expected_parent_sha, "authoritative expected parent SHA")
    actual_parent_sha = _validate_sha(actual_parent_sha, "actual branch parent SHA")
    current_target_head_sha = _validate_sha(current_target_head_sha, "current X head SHA")

    if not expected_task_id:
        raise TaskChainContractError("expected task_id must be nonblank")
    if not expected_stage_id:
        raise TaskChainContractError("expected stage_id must be nonblank")

    task_id, stage_id, contract_parent_sha, parent_issue, work_branch = _load_parent_contract(path)
    if task_id != expected_task_id:
        raise TaskChainContractError(
            f"task identity mismatch: expected={expected_task_id!r}, contract={task_id!r}"
        )
    if stage_id != expected_stage_id:
        raise TaskChainContractError(
            f"stage identity mismatch: expected={expected_stage_id!r}, contract={stage_id!r}"
        )
    if contract_parent_sha != expected_parent_sha:
        raise TaskChainContractError(
            "expected parent contract mismatch: "
            f"authoritative={expected_parent_sha}, contract={contract_parent_sha}"
        )
    if actual_parent_sha != expected_parent_sha:
        if actual_parent_sha == current_target_head_sha:
            raise TaskChainContractError(
                "actual parent is current X head, not the previous accepted task-chain HEAD"
            )
        raise TaskChainContractError(
            "actual parent mismatch: "
            f"expected previous accepted HEAD={expected_parent_sha}, actual={actual_parent_sha}"
        )

    return ParentContractCheck(
        task_id=task_id,
        stage_id=stage_id,
        expected_parent_sha=expected_parent_sha,
        actual_parent_sha=actual_parent_sha,
        current_target_head_sha=current_target_head_sha,
        expected_parent_issue=parent_issue,
        work_branch=work_branch,
    )

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail closed unless WHD X identity and frozen task-chain base are preserved"
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--task-id", required=True, dest="expected_task_id")
    parser.add_argument("--target", required=True, dest="expected_target")
    parser.add_argument("--base-sha", required=True, dest="expected_base_sha")
    parser.add_argument(
        "--current-target-sha", required=True, dest="observed_target_head_sha"
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        contract = assert_frozen_base_contract(
            args.contract,
            expected_task_id=args.expected_task_id,
            expected_target=args.expected_target,
            expected_base_sha=args.expected_base_sha,
            observed_target_head_sha=args.observed_target_head_sha,
        )
    except TaskChainContractError as exc:
        print(f"TASK_CHAIN_FROZEN_BASE_ERROR: {exc}")
        return 2

    print(
        "TASK_CHAIN_FROZEN_BASE_GREEN "
        f"task_id={contract.task_id} target={contract.target} "
        f"frozen_base_sha={contract.frozen_base_sha} "
        f"current_target_sha={contract.observed_target_head_sha} "
        f"target_advanced={'true' if contract.target_advanced else 'false'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
