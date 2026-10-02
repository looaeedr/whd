# -*- coding: utf-8 -*-
"""Permanent WHD knowledge-governance guards for #234 / T7.

Consumes the accepted T6 WHD_DOC_META_V1 state. It never reclassifies documents
and never treats validator output as authority.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

from tools.knowledge_governance import (
    GovernanceError,
    _authority_rows,
    _iter_governed_markdown,
    _norm,
    parse_doc_metadata,
    validate_strict,
)


NAVIGATION_NAMES = {"README.md"}
OBSOLETE_NORMATIVE_PATTERNS = (
    re.compile(r"\buse\s+BACKUP/.*\b(?:authority|source of truth)\b", re.I),
    re.compile(r"(?:使用|採用)\s*`?BACKUP/`?.{0,40}(?:authority|權威|真值)"),
)
NEGATION_MARKERS = ("不得", "不要", "禁止", "removed", "legacy", "historical", "old ", "not ")


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GovernanceError(f"{path}: root must be object")
    return payload


def _skill_name(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for raw in lines[1:]:
        if raw.strip() == "---":
            break
        if raw.startswith("name:"):
            value = raw.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


def _classification_for(path: str, catalog: dict[str, object]) -> str | None:
    explicit = catalog.get("skills")
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, dict) and _norm(str(item.get("path") or "")) == path:
                value = item.get("classification", "canonical")
                return str(value)
    rules = catalog.get("ordered_rules")
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            pattern = str(rule.get("glob") or "")
            if pattern and fnmatch.fnmatch(path, pattern):
                value = rule.get("classification")
                return str(value) if value else None
    return None


def _registry_catalog_errors(root: Path) -> list[str]:
    registry_path = root / ".agents/skills/skill_registry.json"
    catalog_path = root / ".agents/skills/skill_catalog.json"
    if not registry_path.is_file() or not catalog_path.is_file():
        return ["registry/catalog/filesystem coherence: registry or catalog missing"]
    try:
        registry = _load_json(registry_path)
        catalog = _load_json(catalog_path)
    except GovernanceError as exc:
        return [f"registry/catalog/filesystem coherence: {exc}"]

    active = set(str(item) for item in (catalog.get("active_classifications") or ["canonical"]))
    skill_paths: dict[str, str] = {}
    for path in root.glob(".agents/skills/**/SKILL.md"):
        if not path.is_file():
            continue
        name = _skill_name(path)
        if name:
            skill_paths[name] = _norm(path.relative_to(root))

    errors: list[str] = []
    routes = registry.get("routes")
    if not isinstance(routes, list):
        return ["registry/catalog/filesystem coherence: registry routes must be list"]
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("id") or "<unnamed-route>")
        for skill in route.get("required_skills", ()) or ():
            skill_name = str(skill)
            rel = skill_paths.get(skill_name)
            if not rel:
                errors.append(
                    f"registry/catalog/filesystem coherence: route {route_id} requires missing skill {skill_name}"
                )
                continue
            classification = _classification_for(rel, catalog)
            if classification not in active:
                errors.append(
                    f"registry/catalog/filesystem coherence: route {route_id} requires inactive/unclassified skill {skill_name} ({classification})"
                )
        for reference in route.get("required_references", ()) or ():
            rel = _norm(str(reference))
            if not (root / rel).is_file():
                errors.append(
                    f"registry/catalog/filesystem coherence: route {route_id} reference missing: {rel}"
                )

    explicit = catalog.get("skills")
    if isinstance(explicit, list):
        for item in explicit:
            if not isinstance(item, dict):
                continue
            rel = _norm(str(item.get("path") or ""))
            if rel and not (root / rel).is_file():
                errors.append(
                    f"registry/catalog/filesystem coherence: catalog path missing: {rel}"
                )
    return errors


def validate_permanent_governance(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    errors = list(validate_strict(root))

    # R4: navigation artifacts can point, but cannot own CURRENT contracts.
    for path in _iter_governed_markdown(root):
        rel = _norm(path.relative_to(root))
        if path.name not in NAVIGATION_NAMES:
            continue
        try:
            metadata = parse_doc_metadata(path.read_text(encoding="utf-8"), path=rel)
        except (GovernanceError, OSError, UnicodeDecodeError):
            continue  # strict validator already reports malformed metadata
        if metadata.role == "CURRENT":
            errors.append(f"{rel}: README/navigation cannot own domain CURRENT contract {metadata.contract}")

    # R5: continuous execution must have a real executable machine owner.
    machine_rows = [
        row for row in _authority_rows(root)
        if row.get("contract") == "continuous-execution-machine" and row.get("role") == "CURRENT"
    ]
    if len(machine_rows) != 1:
        errors.append(
            f"continuous-execution-machine executable authority requires exactly one CURRENT row; got {len(machine_rows)}"
        )
    else:
        owner = _norm(machine_rows[0]["path"])
        target = root / owner
        if not target.is_file() or target.suffix.lower() != ".py":
            errors.append(
                f"continuous-execution-machine executable authority missing/non-executable source: {owner}"
            )

    # R6: routed skills/references must agree with catalog classification and filesystem.
    errors.extend(_registry_catalog_errors(root))

    # R7: obsolete wording is allowed in REFERENCE/HISTORICAL or negated discussion,
    # but not as positive normative instruction in CURRENT documents.
    for path in _iter_governed_markdown(root):
        rel = _norm(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
            metadata = parse_doc_metadata(text, path=rel)
        except (GovernanceError, OSError, UnicodeDecodeError):
            continue
        if metadata.role != "CURRENT":
            continue
        lowered = text.lower()
        if any(marker.lower() in lowered for marker in NEGATION_MARKERS):
            continue
        if any(pattern.search(text) for pattern in OBSOLETE_NORMATIVE_PATTERNS):
            errors.append(f"{rel}: obsolete wording used normatively in CURRENT authority")

    return tuple(sorted(set(errors)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Permanent WHD knowledge governance guard")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    errors = validate_permanent_governance(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"permanent knowledge governance GREEN governed={len(_iter_governed_markdown(root))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
