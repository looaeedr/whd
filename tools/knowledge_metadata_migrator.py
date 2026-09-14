# -*- coding: utf-8 -*-
"""Deterministic WHD_DOC_META_V1 migration planner/applicator.

Authority flows one way: explicit classification matrix -> migration plan -> files.
Validation may reject the result but must never invent roles/contracts/canonical paths.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

CLASSIFICATION_SCHEMA = "WHD_KNOWLEDGE_CLASSIFICATION_V1"
DOC_SCHEMA = "WHD_DOC_META_V1"
VALID_ROLES = {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"}
CONTRACT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKIP_PARTS = {".git", ".scratch", "BACKUP", "__pycache__", ".pytest_cache"}


class MigrationPlanError(ValueError):
    """Raised when authority cannot produce one total deterministic mapping."""


@dataclass(frozen=True, order=True)
class MigrationOperation:
    path: str
    role: str
    contract: str
    canonical: str | None


def _norm(value: str | Path) -> str:
    normalized = Path(value).as_posix()
    return normalized[2:] if normalized.startswith("./") else normalized


def _is_governed_markdown(path: str | Path) -> bool:
    rel = _norm(path)
    candidate = Path(rel)
    if candidate.suffix.lower() != ".md":
        return False
    if any(part in SKIP_PARTS for part in candidate.parts):
        return False
    if len(candidate.parts) == 1:
        return True
    return rel.startswith(("個人AI檔案庫/", ".agents/skills/", "docs/", "handoff/"))


def _governed_paths(root: Path) -> tuple[str, ...]:
    paths = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        rel = _norm(path.relative_to(root))
        if _is_governed_markdown(rel):
            paths.append(rel)
    return tuple(sorted(paths))


def _load_matrix(path: Path) -> list[Mapping[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationPlanError(f"cannot read authority matrix: {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CLASSIFICATION_SCHEMA:
        raise MigrationPlanError(f"authority schema must be {CLASSIFICATION_SCHEMA}")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise MigrationPlanError("authority rows must be a list")
    normalized: list[Mapping[str, object]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise MigrationPlanError(f"authority row {index} must be an object")
        normalized.append(row)
    return normalized


def _canonical_for(row: Mapping[str, object], *, path: str, role: str) -> str | None:
    if role != "MIRROR":
        return None
    raw = row.get("replacement")
    if not isinstance(raw, str) or not raw.strip():
        raw = row.get("canonical_owner")
    if not isinstance(raw, str) or not raw.strip():
        raise MigrationPlanError(f"{path}: MIRROR missing canonical target")
    canonical = _norm(raw)
    canonical_path = Path(canonical)
    if canonical_path.is_absolute() or ".." in canonical_path.parts:
        raise MigrationPlanError(f"{path}: MIRROR canonical target must be repo-relative")
    return canonical


def build_plan(root: Path, matrix_path: Path) -> tuple[MigrationOperation, ...]:
    """Build a total migration plan without mutating repository files."""
    root = root.resolve()
    matrix_path = matrix_path.resolve()
    rows = _load_matrix(matrix_path)

    by_path: dict[str, Mapping[str, object]] = {}
    for row in rows:
        raw_path = row.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise MigrationPlanError("authority row missing path")
        rel = _norm(raw_path)
        if rel in by_path:
            raise MigrationPlanError(f"duplicate mapping: {rel}")
        by_path[rel] = row

    governed = _governed_paths(root)
    governed_set = set(governed)
    matrix_set = set(by_path)
    missing = sorted(governed_set - matrix_set)
    nonexistent = sorted(matrix_set - governed_set)
    if missing:
        raise MigrationPlanError(f"missing mapping: {missing}")
    if nonexistent:
        raise MigrationPlanError(f"nonexistent target: {nonexistent}")

    operations: list[MigrationOperation] = []
    blocked: list[str] = []
    for rel in governed:
        row = by_path[rel]
        role = row.get("target_role")
        blocker = row.get("blocker")
        if blocker:
            blocked.append(f"{rel}: {role} blocker={blocker}")
            continue
        if role not in VALID_ROLES:
            blocked.append(f"{rel}: unknown role {role!r}")
            continue

        contract = row.get("contract")
        if not isinstance(contract, str) or not CONTRACT_RE.fullmatch(contract):
            blocked.append(f"{rel}: {role} missing/invalid stable contract")
            continue

        canonical = _canonical_for(row, path=rel, role=str(role))
        if canonical is not None and canonical not in governed_set:
            blocked.append(f"{rel}: nonexistent target {canonical}")
            continue
        operations.append(
            MigrationOperation(path=rel, role=str(role), contract=contract, canonical=canonical)
        )

    if blocked:
        preview = "; ".join(blocked[:20])
        suffix = "" if len(blocked) <= 20 else f"; ... +{len(blocked) - 20} more"
        raise MigrationPlanError(f"authority incomplete: {preview}{suffix}")

    if len(operations) != len(governed):
        raise MigrationPlanError(
            f"mapping count mismatch: governed={len(governed)} planned={len(operations)}"
        )
    return tuple(sorted(operations))


def render_frontmatter(operation: MigrationOperation) -> str:
    canonical = "null" if operation.canonical is None else operation.canonical
    return (
        "---\n"
        f"whd_doc_role: {operation.role}\n"
        f"whd_contract: {operation.contract}\n"
        f"whd_canonical: {canonical}\n"
        f"whd_schema: {DOC_SCHEMA}\n"
        "---\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic WHD metadata migration")
    parser.add_argument("--root", default=".")
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--plan-only", action="store_true", default=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    matrix = Path(args.matrix)
    if not matrix.is_absolute():
        matrix = root / matrix
    try:
        plan = build_plan(root, matrix)
    except MigrationPlanError as exc:
        print(f"MIGRATION_BLOCKED: {exc}")
        return 2
    print(f"migration plan GREEN governed={len(plan)}")
    if not args.plan_only:
        print("MIGRATION_BLOCKED: apply phase intentionally unavailable until authority plan is complete")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
