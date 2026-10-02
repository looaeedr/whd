"""Fail-closed current-X Integration Readiness gate for #262 / T6.

This verifier never mutates X and never performs Integration Acceptance. It proves only
that one frozen Task-Accepted chain head is eligible to proceed to a later integration
acceptance step against one frozen current-X head.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ELIGIBLE_CODE = "INTEGRATION_READINESS_ELIGIBLE"
_NOT_PERFORMED = "NOT_PERFORMED"

_TOP_LEVEL_FIELDS = {
    "schema_version",
    "master_task_id",
    "master_base_sha",
    "target",
    "target_branch",
    "task_final_sha",
    "current_x_before",
    "current_x_after",
    "task_acceptance",
    "base_to_task",
    "base_to_x",
    "task_to_x",
    "conflict_audit",
}
_TASK_ACCEPTANCE_FIELDS = {"status", "code", "evidence"}
_BASE_COMPARE_FIELDS = {
    "status",
    "merge_base_sha",
    "ahead_by",
    "behind_by",
    "changed_paths",
}
_TASK_X_COMPARE_FIELDS = {
    "status",
    "merge_base_sha",
    "task_only_commits",
    "x_only_commits",
}
_CONFLICT_FIELDS = {"status", "method", "evidence"}


class IntegrationReadinessError(RuntimeError):
    """Raised when integration readiness cannot be proven exactly."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise IntegrationReadinessError(f"ambiguous JSON: duplicate key {key!r}")
        payload[key] = value
    return payload


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise IntegrationReadinessError(f"{label} not found: {path}") from exc
    except IntegrationReadinessError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationReadinessError(f"malformed {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IntegrationReadinessError(f"malformed {label}: root must be an object")
    return payload


def _require_exact_fields(payload: dict[str, object], expected: set[str], *, label: str) -> None:
    observed = set(payload)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise IntegrationReadinessError(
            f"{label} schema mismatch: missing={missing} extra={extra}"
        )


def _require_text(payload: dict[str, object], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IntegrationReadinessError(f"{label} {key} must be nonblank text")
    return value.strip()


def _require_sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise IntegrationReadinessError(
            f"{label} must be a 40-character lowercase SHA"
        )
    return value


def _require_nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IntegrationReadinessError(f"{label} must be a nonnegative integer")
    return value


def _require_path_list(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise IntegrationReadinessError(f"{label} must be a nonempty path list")
    paths: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise IntegrationReadinessError(f"{label} contains a blank/non-text path")
        path = item.strip().replace("\\", "/")
        if path.startswith("/") or posixpath.normpath(path) != path or path in {".", ".."}:
            raise IntegrationReadinessError(f"{label} contains non-canonical path {item!r}")
        if any(part == ".." for part in path.split("/")):
            raise IntegrationReadinessError(f"{label} contains parent traversal {item!r}")
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise IntegrationReadinessError(f"{label} contains duplicate paths")
    return tuple(paths)


def _has_prefix_collision(left: str, right: str) -> bool:
    return left.startswith(right + "/") or right.startswith(left + "/")


@dataclass(frozen=True)
class ReadinessContract:
    schema_version: int
    master_task_id: str
    master_base_sha: str
    target: str
    target_branch: str
    task_final_sha: str
    current_x_sha: str
    required_task_acceptance_code: str
    required_conflict_method: str


@dataclass(frozen=True)
class IntegrationReadinessDecision:
    eligible: bool
    code: str
    task_acceptance: str
    integration_acceptance: str
    current_x_sha: str


def load_contract(path: Path) -> ReadinessContract:
    payload = _read_json(path, label="integration-readiness contract")
    expected = {
        "schema_version",
        "master_task_id",
        "master_base_sha",
        "target",
        "target_branch",
        "task_final_sha",
        "current_x_sha",
        "required_task_acceptance_code",
        "required_conflict_method",
    }
    _require_exact_fields(payload, expected, label="integration-readiness contract")

    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise IntegrationReadinessError("contract schema_version must be 1")

    target = _require_text(payload, "target", label="contract")
    if target != "X":
        raise IntegrationReadinessError(f"contract TARGET identity must be 'X', got {target!r}")

    return ReadinessContract(
        schema_version=1,
        master_task_id=_require_text(payload, "master_task_id", label="contract"),
        master_base_sha=_require_sha(payload.get("master_base_sha"), label="contract master_base_sha"),
        target=target,
        target_branch=_require_text(payload, "target_branch", label="contract"),
        task_final_sha=_require_sha(payload.get("task_final_sha"), label="contract task_final_sha"),
        current_x_sha=_require_sha(payload.get("current_x_sha"), label="contract current_x_sha"),
        required_task_acceptance_code=_require_text(
            payload, "required_task_acceptance_code", label="contract"
        ),
        required_conflict_method=_require_text(
            payload, "required_conflict_method", label="contract"
        ),
    )


def _validate_identity(payload: dict[str, object], contract: ReadinessContract) -> None:
    _require_exact_fields(payload, _TOP_LEVEL_FIELDS, label="readiness manifest")

    if payload.get("schema_version") != contract.schema_version or isinstance(
        payload.get("schema_version"), bool
    ):
        raise IntegrationReadinessError("manifest identity schema_version mismatch")

    master_task_id = _require_text(payload, "master_task_id", label="manifest")
    if master_task_id != contract.master_task_id:
        raise IntegrationReadinessError(
            f"manifest master identity mismatch: expected={contract.master_task_id!r} observed={master_task_id!r}"
        )

    master_base_sha = _require_sha(payload.get("master_base_sha"), label="manifest master_base_sha")
    if master_base_sha != contract.master_base_sha:
        raise IntegrationReadinessError(
            f"manifest frozen base mismatch: expected={contract.master_base_sha} observed={master_base_sha}"
        )

    target = _require_text(payload, "target", label="manifest")
    if target != contract.target:
        raise IntegrationReadinessError(
            f"manifest TARGET identity mismatch: expected={contract.target!r} observed={target!r}"
        )

    target_branch = _require_text(payload, "target_branch", label="manifest")
    if target_branch != contract.target_branch:
        raise IntegrationReadinessError(
            f"manifest target branch identity mismatch: expected={contract.target_branch!r} observed={target_branch!r}"
        )

    task_final_sha = _require_sha(payload.get("task_final_sha"), label="manifest task_final_sha")
    if task_final_sha != contract.task_final_sha:
        raise IntegrationReadinessError(
            f"manifest task-final identity mismatch: expected={contract.task_final_sha} observed={task_final_sha}"
        )

    current_x_before = _require_sha(payload.get("current_x_before"), label="manifest current_x_before")
    current_x_after = _require_sha(payload.get("current_x_after"), label="manifest current_x_after")
    if current_x_before != current_x_after:
        raise IntegrationReadinessError(
            f"current-X drift during audit: before={current_x_before} after={current_x_after}"
        )
    if current_x_before != contract.current_x_sha:
        raise IntegrationReadinessError(
            f"current-X identity mismatch: expected={contract.current_x_sha} observed={current_x_before}"
        )


def _validate_task_acceptance(payload: object, contract: ReadinessContract) -> None:
    if not isinstance(payload, dict):
        raise IntegrationReadinessError("Task Acceptance evidence must be an object")
    _require_exact_fields(payload, _TASK_ACCEPTANCE_FIELDS, label="Task Acceptance")

    status = _require_text(payload, "status", label="Task Acceptance")
    if status != "ACCEPTED":
        raise IntegrationReadinessError(
            f"Task Acceptance must be ACCEPTED before integration readiness, got {status!r}"
        )
    code = _require_text(payload, "code", label="Task Acceptance")
    if code != contract.required_task_acceptance_code:
        raise IntegrationReadinessError(
            "Task Acceptance code mismatch: "
            f"expected={contract.required_task_acceptance_code!r} observed={code!r}"
        )
    _require_text(payload, "evidence", label="Task Acceptance")


def _validate_base_compare(
    payload: object,
    *,
    label: str,
    frozen_base: str,
) -> tuple[int, tuple[str, ...]]:
    if not isinstance(payload, dict):
        raise IntegrationReadinessError(f"{label} must be an object")
    _require_exact_fields(payload, _BASE_COMPARE_FIELDS, label=label)

    status = _require_text(payload, "status", label=label)
    if status != "ahead":
        raise IntegrationReadinessError(f"{label} status must be 'ahead', got {status!r}")

    merge_base = _require_sha(payload.get("merge_base_sha"), label=f"{label} merge_base_sha")
    if merge_base != frozen_base:
        raise IntegrationReadinessError(
            f"{label} merge-base must equal frozen base {frozen_base}, got {merge_base}"
        )

    ahead_by = _require_nonnegative_int(payload.get("ahead_by"), label=f"{label} ahead_by")
    behind_by = _require_nonnegative_int(payload.get("behind_by"), label=f"{label} behind_by")
    if ahead_by <= 0 or behind_by != 0:
        raise IntegrationReadinessError(
            f"{label} must prove direct advancement from frozen base: ahead={ahead_by} behind={behind_by}"
        )

    paths = _require_path_list(payload.get("changed_paths"), label=f"{label} changed_paths")
    return ahead_by, paths


def _validate_task_to_x(
    payload: object,
    *,
    frozen_base: str,
    expected_task_commits: int,
    expected_x_commits: int,
) -> None:
    if not isinstance(payload, dict):
        raise IntegrationReadinessError("task_to_x must be an object")
    _require_exact_fields(payload, _TASK_X_COMPARE_FIELDS, label="task_to_x")

    status = _require_text(payload, "status", label="task_to_x")
    if status != "diverged":
        raise IntegrationReadinessError(
            f"task_to_x must prove real divergence, got status={status!r}"
        )
    merge_base = _require_sha(payload.get("merge_base_sha"), label="task_to_x merge_base_sha")
    if merge_base != frozen_base:
        raise IntegrationReadinessError(
            f"task_to_x merge-base must equal frozen base {frozen_base}, got {merge_base}"
        )

    task_only = _require_nonnegative_int(
        payload.get("task_only_commits"), label="task_to_x task_only_commits"
    )
    x_only = _require_nonnegative_int(
        payload.get("x_only_commits"), label="task_to_x x_only_commits"
    )
    if task_only <= 0 or x_only <= 0:
        raise IntegrationReadinessError(
            f"task_to_x must prove divergence on both sides: task_only={task_only} x_only={x_only}"
        )
    if task_only != expected_task_commits or x_only != expected_x_commits:
        raise IntegrationReadinessError(
            "task_to_x commit counts do not reconcile with frozen-base comparisons: "
            f"task={task_only}/{expected_task_commits} x={x_only}/{expected_x_commits}"
        )


def _validate_disjoint_paths(task_paths: tuple[str, ...], x_paths: tuple[str, ...]) -> None:
    task_set = set(task_paths)
    x_set = set(x_paths)
    overlap = sorted(task_set & x_set)
    if overlap:
        raise IntegrationReadinessError(f"changed path overlap blocks readiness: {overlap}")

    prefix_collisions: list[tuple[str, str]] = []
    for task_path in task_paths:
        for x_path in x_paths:
            if _has_prefix_collision(task_path, x_path):
                prefix_collisions.append((task_path, x_path))
    if prefix_collisions:
        raise IntegrationReadinessError(
            f"changed path structural overlap blocks readiness: {prefix_collisions}"
        )


def _validate_conflict_audit(payload: object, contract: ReadinessContract) -> None:
    if not isinstance(payload, dict):
        raise IntegrationReadinessError("conflict_audit must be an object")
    _require_exact_fields(payload, _CONFLICT_FIELDS, label="conflict_audit")

    status = _require_text(payload, "status", label="conflict_audit")
    if status != "CLEAN":
        raise IntegrationReadinessError(
            f"conflict audit must be CLEAN, got {status!r}"
        )
    method = _require_text(payload, "method", label="conflict_audit")
    if method != contract.required_conflict_method:
        raise IntegrationReadinessError(
            "conflict audit method mismatch: "
            f"expected={contract.required_conflict_method!r} observed={method!r}"
        )
    _require_text(payload, "evidence", label="conflict_audit")


def evaluate_readiness(manifest_path: Path, contract_path: Path) -> IntegrationReadinessDecision:
    contract = load_contract(contract_path)
    payload = _read_json(manifest_path, label="integration-readiness manifest")
    _validate_identity(payload, contract)
    _validate_task_acceptance(payload.get("task_acceptance"), contract)

    task_commits, task_paths = _validate_base_compare(
        payload.get("base_to_task"),
        label="base_to_task",
        frozen_base=contract.master_base_sha,
    )
    x_commits, x_paths = _validate_base_compare(
        payload.get("base_to_x"),
        label="base_to_x",
        frozen_base=contract.master_base_sha,
    )
    _validate_task_to_x(
        payload.get("task_to_x"),
        frozen_base=contract.master_base_sha,
        expected_task_commits=task_commits,
        expected_x_commits=x_commits,
    )
    _validate_disjoint_paths(task_paths, x_paths)
    _validate_conflict_audit(payload.get("conflict_audit"), contract)

    return IntegrationReadinessDecision(
        eligible=True,
        code=_ELIGIBLE_CODE,
        task_acceptance="ACCEPTED",
        integration_acceptance=_NOT_PERFORMED,
        current_x_sha=contract.current_x_sha,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed frozen current-X integration-readiness verifier"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        decision = evaluate_readiness(args.manifest, args.contract)
    except IntegrationReadinessError as exc:
        print(f"INTEGRATION_READINESS_DENY reason={exc}")
        return 2

    print(
        "INTEGRATION_READINESS_GREEN "
        f"code={decision.code} "
        f"task_acceptance={decision.task_acceptance} "
        f"integration_acceptance={decision.integration_acceptance} "
        f"current_x={decision.current_x_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
