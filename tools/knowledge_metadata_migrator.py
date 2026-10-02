# -*- coding: utf-8 -*-
"""Deterministic WHD_DOC_META_V1 migrator driven by effective authority.

Authority flows one way only:
    frozen T1 matrix + reviewed T6 overlay -> effective authority -> migration plan -> files

Validation may reject the result. It must never feed roles, contracts, or canonical
paths back into this migrator.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import NamedTuple, Sequence

try:
    from tools.knowledge_authority_overlay import governed_paths, merge_effective_authority
except ModuleNotFoundError:  # direct execution: python tools/knowledge_metadata_migrator.py
    from knowledge_authority_overlay import governed_paths, merge_effective_authority

DOC_SCHEMA = "WHD_DOC_META_V1"
VALID_ROLES = {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"}
CONTRACT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WHD_KEYS = ("whd_doc_role", "whd_contract", "whd_canonical", "whd_schema")


class MigrationPlanError(ValueError):
    """Raised when reviewed authority cannot produce one total migration plan."""


class MigrationOperation(NamedTuple):
    path: str
    role: str
    contract: str
    canonical: str | None


def _norm(value: str | Path) -> str:
    text = Path(value).as_posix()
    return text[2:] if text.startswith("./") else text


def _canonical_from_row(row: dict[str, object], *, path: str, role: str) -> str | None:
    if role != "MIRROR":
        return None
    raw = row.get("replacement") or row.get("canonical") or row.get("canonical_owner")
    if not isinstance(raw, str) or not raw.strip():
        raise MigrationPlanError(f"{path}: MIRROR missing canonical target")
    canonical = _norm(raw)
    candidate = Path(canonical)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise MigrationPlanError(f"{path}: MIRROR canonical target must be repo-relative")
    return canonical


def build_plan(root: Path, matrix_path: Path, overlay_path: Path) -> tuple[MigrationOperation, ...]:
    """Build the complete deterministic plan without mutating repository files."""
    root = root.resolve()
    matrix_path = matrix_path.resolve()
    overlay_path = overlay_path.resolve()

    try:
        effective_rows = merge_effective_authority(matrix_path, overlay_path)
    except Exception as exc:
        raise MigrationPlanError(f"effective authority invalid: {exc}") from exc

    by_path: dict[str, dict[str, object]] = {}
    for raw_row in effective_rows:
        row = dict(raw_row)
        raw_path = row.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise MigrationPlanError("effective authority row missing path")
        rel = _norm(raw_path)
        if rel in by_path:
            raise MigrationPlanError(f"duplicate mapping: {rel}")
        by_path[rel] = row

    governed = governed_paths(root)
    governed_set = set(governed)
    authority_set = set(by_path)
    missing = sorted(governed_set - authority_set)
    nonexistent = sorted(authority_set - governed_set)
    if missing:
        raise MigrationPlanError(f"missing mapping: {missing}")
    if nonexistent:
        raise MigrationPlanError(f"nonexistent target: {nonexistent}")

    operations: list[MigrationOperation] = []
    for rel in governed:
        row = by_path[rel]
        blocker = row.get("blocker")
        if blocker:
            raise MigrationPlanError(f"{rel}: unresolved blocker {blocker}")
        role = row.get("target_role")
        if role not in VALID_ROLES:
            raise MigrationPlanError(f"{rel}: unknown role {role!r}")
        contract = row.get("contract")
        if not isinstance(contract, str) or CONTRACT_RE.fullmatch(contract) is None:
            raise MigrationPlanError(f"{rel}: missing/invalid stable contract")
        canonical = _canonical_from_row(row, path=rel, role=str(role))
        if canonical is not None and canonical not in governed_set:
            raise MigrationPlanError(f"{rel}: nonexistent target {canonical}")
        operations.append(
            MigrationOperation(
                path=rel,
                role=str(role),
                contract=contract,
                canonical=canonical,
            )
        )

    result = tuple(sorted(operations, key=lambda item: item.path))
    if len(result) != len(governed):
        raise MigrationPlanError(
            f"mapping count mismatch: governed={len(governed)} planned={len(result)}"
        )
    return result


def _metadata_lines(operation: MigrationOperation) -> list[str]:
    canonical = "null" if operation.canonical is None else operation.canonical
    return [
        f"whd_doc_role: {operation.role}",
        f"whd_contract: {operation.contract}",
        f"whd_canonical: {canonical}",
        f"whd_schema: {DOC_SCHEMA}",
    ]


def _split_frontmatter(text: str) -> tuple[str, list[str], str]:
    """Return BOM, non-WHD frontmatter lines, and body without changing body bytes."""
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    source = text[len(bom) :]
    if not source.startswith("---\n"):
        return bom, [], source
    end = source.find("\n---\n", 4)
    if end == -1:
        raise MigrationPlanError("unterminated YAML frontmatter")
    raw_header = source[4:end]
    body = source[end + 5 :]
    retained: list[str] = []
    for line in raw_header.split("\n"):
        stripped = line.lstrip()
        if any(stripped.startswith(f"{key}:") for key in WHD_KEYS):
            continue
        retained.append(line)
    while retained and retained[-1] == "":
        retained.pop()
    return bom, retained, body


def _render_document(original: str, operation: MigrationOperation) -> str:
    bom, retained, body = _split_frontmatter(original)
    header = retained + _metadata_lines(operation)
    if operation.role == "MIRROR":
        assert operation.canonical is not None
        body = (
            "# MIRROR pointer\n\n"
            f"Canonical: `{operation.canonical}`\n\n"
            "此檔僅為 MIRROR 指標；規則與 authoritative 內容以 canonical 為準。\n"
            "不得新增或複製 normative 規則。\n"
        )
    return bom + "---\n" + "\n".join(header) + "\n---\n" + body


def apply_plan(root: Path, plan: Sequence[MigrationOperation]) -> tuple[str, ...]:
    """Apply only the supplied reviewed plan and return the exact changed-file set."""
    root = root.resolve()
    seen: set[str] = set()
    changed: list[str] = []
    for operation in sorted(plan, key=lambda item: item.path):
        rel = _norm(operation.path)
        if rel in seen:
            raise MigrationPlanError(f"duplicate operation: {rel}")
        seen.add(rel)
        path = root / rel
        if not path.is_file():
            raise MigrationPlanError(f"missing governed document: {rel}")
        if operation.role == "MIRROR":
            if operation.canonical is None:
                raise MigrationPlanError(f"{rel}: MIRROR missing canonical target")
            canonical_path = root / operation.canonical
            if not canonical_path.is_file():
                raise MigrationPlanError(f"{rel}: nonexistent target {operation.canonical}")
        original = path.read_text(encoding="utf-8")
        rendered = _render_document(original, operation)
        if rendered != original:
            path.write_text(rendered, encoding="utf-8")
            changed.append(rel)
    return tuple(changed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic WHD_DOC_META_V1 migration")
    parser.add_argument("--root", default=".")
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--apply", action="store_true", default=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    matrix = Path(args.matrix)
    overlay = Path(args.overlay)
    if not matrix.is_absolute():
        matrix = root / matrix
    if not overlay.is_absolute():
        overlay = root / overlay
    try:
        plan = build_plan(root, matrix, overlay)
        print(f"MIGRATION_PLAN_GREEN governed={len(plan)} mapped={len(plan)}")
        if not args.apply:
            return 0
        changed = apply_plan(root, plan)
    except MigrationPlanError as exc:
        print(f"MIGRATION_BLOCKED: {exc}")
        return 2
    print(f"MIGRATION_CHANGED_COUNT={len(changed)}")
    for rel in changed:
        print(f"MIGRATION_CHANGED:{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
