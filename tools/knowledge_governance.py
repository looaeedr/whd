# -*- coding: utf-8 -*-
"""Executable governance helpers for WHD knowledge/documentation authority.

T0 scope is intentionally narrow:
- parse WHD_DOC_META_V1 frontmatter without a third-party YAML dependency;
- freeze a machine-readable inventory of governed knowledge documents;
- validate only changed governed Markdown in bootstrap mode so legacy debt
  can be migrated without allowing new documentation drift.

This module governs documentation metadata only. It is not a manufacturing,
geometry, UI, DXF, or runtime product authority.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, NamedTuple, Sequence


DOC_SCHEMA = "WHD_DOC_META_V1"
INVENTORY_SCHEMA = "WHD_KNOWLEDGE_INVENTORY_V1"
CLASSIFICATION_SCHEMA = "WHD_KNOWLEDGE_CLASSIFICATION_V1"
VALID_ROLES = {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"}
CONTRACT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
AUTHORITY_COMMENT_RE = re.compile(
    r"<!--\s+WHD_AUTHORITY(?:_ROW)?\s+(?P<attrs>.*?)\s*-->", re.DOTALL
)
LEGACY_ROLE_RE = re.compile(
    r"<!--\s+WHD_DOC_ROLE\s+(?P<attrs>.*?)\s*-->", re.DOTALL
)
ATTR_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>\"[^\"]*\"|'[^']*'|[^\s]+)")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".toml", ".txt"}
SKIP_PARTS = {".git", ".scratch", "BACKUP", "__pycache__", ".pytest_cache"}


class GovernanceError(ValueError):
    """Raised when governed documentation metadata is malformed."""


class DocMetadata(NamedTuple):
    role: str
    contract: str
    canonical: str | None
    schema: str


def _norm(value: str | Path) -> str:
    normalized = Path(value).as_posix()
    return normalized[2:] if normalized.startswith("./") else normalized


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "#" and index > 0 and value[index - 1].isspace():
            return value[:index].rstrip()
    return value.strip()


def _parse_scalar(raw: str) -> str | None:
    value = _strip_inline_comment(raw.strip())
    if value.lower() in {"null", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _frontmatter_mapping(text: str, *, path: str) -> Mapping[str, str | None]:
    source = text.lstrip("\ufeff")
    lines = source.splitlines()
    if not lines or lines[0].strip() != "---":
        raise GovernanceError(f"{path}: missing {DOC_SCHEMA} YAML frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise GovernanceError(f"{path}: unterminated YAML frontmatter") from exc

    values: dict[str, str | None] = {}
    for line_number, raw_line in enumerate(lines[1:end], start=2):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in raw_line:
            raise GovernanceError(f"{path}:{line_number}: frontmatter must be flat key: value")
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        if not key:
            raise GovernanceError(f"{path}:{line_number}: empty frontmatter key")
        if key in values:
            raise GovernanceError(f"{path}:{line_number}: duplicate frontmatter key {key}")
        values[key] = _parse_scalar(raw_value)
    return values


def parse_doc_metadata(text: str, *, path: str = "<memory>") -> DocMetadata:
    values = _frontmatter_mapping(text, path=path)
    required = {"whd_doc_role", "whd_contract", "whd_canonical", "whd_schema"}
    missing = sorted(required - set(values))
    if missing:
        raise GovernanceError(f"{path}: missing metadata fields: {', '.join(missing)}")

    schema = values["whd_schema"]
    if schema != DOC_SCHEMA:
        raise GovernanceError(f"{path}: whd_schema must be {DOC_SCHEMA}")

    role = values["whd_doc_role"]
    if role not in VALID_ROLES:
        raise GovernanceError(
            f"{path}: whd_doc_role must be one of {', '.join(sorted(VALID_ROLES))}"
        )

    contract = values["whd_contract"]
    if not isinstance(contract, str) or not CONTRACT_RE.fullmatch(contract):
        raise GovernanceError(f"{path}: whd_contract must be stable kebab-case")

    canonical = values["whd_canonical"]
    if role == "MIRROR":
        if not isinstance(canonical, str) or not canonical.strip():
            raise GovernanceError(f"{path}: MIRROR requires non-null whd_canonical")
        canonical = _norm(canonical)
        canonical_path = Path(canonical)
        if canonical_path.is_absolute() or ".." in canonical_path.parts:
            raise GovernanceError(f"{path}: whd_canonical must be repo-relative")
    elif canonical is not None:
        raise GovernanceError(f"{path}: non-MIRROR whd_canonical must be null")

    return DocMetadata(role=role, contract=contract, canonical=canonical, schema=schema)


def _generic_frontmatter_value(text: str, key: str) -> str | None:
    source = text.lstrip("\ufeff")
    lines = source.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for raw_line in lines[1:]:
        if raw_line.strip() == "---":
            break
        if ":" not in raw_line:
            continue
        current_key, raw_value = raw_line.split(":", 1)
        if current_key.strip() == key:
            value = _parse_scalar(raw_value)
            return value if isinstance(value, str) else None
    return None


def _attrs(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in ATTR_RE.finditer(raw):
        value = match.group("value")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[match.group("key")] = value
    return result


def _authority_rows(root: Path) -> list[dict[str, str]]:
    authority_map = root / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
    if not authority_map.is_file():
        return []
    text = authority_map.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []
    for match in AUTHORITY_COMMENT_RE.finditer(text):
        attrs = _attrs(match.group("attrs"))
        if {"contract", "role", "path"} <= set(attrs):
            rows.append(attrs)
    return rows


def _legacy_role(text: str) -> tuple[str | None, str | None]:
    match = LEGACY_ROLE_RE.search(text)
    if not match:
        return None, None
    attrs = _attrs(match.group("attrs"))
    role = attrs.get("role")
    contract = attrs.get("contract")
    if role not in VALID_ROLES:
        role = None
    return role, contract


def is_governed_markdown(path: str | Path) -> bool:
    rel = _norm(path)
    candidate = Path(rel)
    if candidate.suffix.lower() != ".md":
        return False
    if any(part in SKIP_PARTS for part in candidate.parts):
        return False
    if len(candidate.parts) == 1:
        return True
    return rel.startswith(
        (
            "個人AI檔案庫/",
            ".agents/skills/",
            "docs/",
            "handoff/",
        )
    )


def _iter_governed_markdown(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        rel = _norm(path.relative_to(root))
        if is_governed_markdown(rel):
            result.append(path)
    return sorted(result, key=lambda item: _norm(item.relative_to(root)))


def _iter_reference_texts(root: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel_path = path.relative_to(root)
        if any(part in SKIP_PARTS for part in rel_path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        result.append((_norm(rel_path), text))
    return result


def _routing_by_path(root: Path, governed: Sequence[Path]) -> dict[str, list[str]]:
    registry_path = root / ".agents/skills/skill_registry.json"
    if not registry_path.is_file():
        return {}
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    routes = registry.get("routes")
    if not isinstance(routes, list):
        return {}

    skill_name_to_path: dict[str, str] = {}
    for path in governed:
        rel = _norm(path.relative_to(root))
        if rel.startswith(".agents/skills/") and path.name == "SKILL.md":
            name = _generic_frontmatter_value(path.read_text(encoding="utf-8"), "name")
            if name:
                skill_name_to_path[name] = rel

    routing: dict[str, set[str]] = defaultdict(set)
    governed_rels = [_norm(path.relative_to(root)) for path in governed]
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("id") or "<unnamed-route>")
        for reference in route.get("required_references", ()) or ():
            routing[_norm(str(reference))].add(route_id)
        for skill in route.get("required_skills", ()) or ():
            skill_path = skill_name_to_path.get(str(skill))
            if skill_path:
                routing[skill_path].add(route_id)
        globs = tuple(str(item) for item in route.get("file_globs", ()) or ())
        for rel in governed_rels:
            if any(fnmatch.fnmatch(rel, pattern) for pattern in globs):
                routing[rel].add(route_id)
    return {path: sorted(route_ids) for path, route_ids in routing.items()}


def build_inventory(root: Path, *, source_head: str) -> dict[str, object]:
    root = root.resolve()
    governed = _iter_governed_markdown(root)
    authority_rows = _authority_rows(root)
    authority_by_path = {_norm(row["path"]): row for row in authority_rows}
    current_by_contract = {
        row["contract"]: _norm(row["path"])
        for row in authority_rows
        if row.get("role") == "CURRENT"
    }
    routing_by_path = _routing_by_path(root, governed)
    reference_texts = _iter_reference_texts(root)

    rows: list[dict[str, object]] = []
    for path in governed:
        rel = _norm(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        metadata: DocMetadata | None = None
        metadata_status = "legacy-or-unclassified"
        if "whd_schema:" in text or "whd_doc_role:" in text[:2000]:
            try:
                metadata = parse_doc_metadata(text, path=rel)
            except GovernanceError:
                metadata = None
                metadata_status = "invalid-v1"

        map_row = authority_by_path.get(rel)
        legacy_role, legacy_contract = _legacy_role(text)
        if metadata is not None:
            role = metadata.role
            contract = metadata.contract
            replacement = metadata.canonical
            metadata_status = "v1"
        elif map_row:
            role = map_row.get("role", "UNKNOWN")
            contract = map_row.get("contract")
            replacement = map_row.get("canonical")
        elif legacy_role:
            role = legacy_role
            contract = legacy_contract
            replacement = None
        else:
            role = "UNKNOWN"
            contract = None
            replacement = None

        canonical_owner = None
        if isinstance(contract, str):
            canonical_owner = current_by_contract.get(contract)
            if role == "CURRENT" and canonical_owner is None:
                canonical_owner = rel

        incoming = sorted(
            source_rel
            for source_rel, source_text in reference_texts
            if source_rel != rel and rel in source_text
        )
        action = "KEEP" if metadata_status == "v1" else "UPDATE"
        rows.append(
            {
                "path": rel,
                "role": role,
                "contract": contract,
                "canonical_owner": canonical_owner,
                "incoming_references": incoming,
                "machine_routing": routing_by_path.get(rel, []),
                "replacement": replacement,
                "action": action,
                "metadata_status": metadata_status,
                "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    return {
        "schema": INVENTORY_SCHEMA,
        "source_head": source_head,
        "governed_scope": [
            "/*.md",
            "個人AI檔案庫/**/*.md",
            ".agents/skills/**/*.md",
            "docs/**/*.md",
            "handoff/**/*.md",
        ],
        "rows": rows,
    }


def validate_bootstrap(
    root: Path,
    inventory: Mapping[str, object],
    *,
    changed_files: Iterable[str],
) -> tuple[str, ...]:
    root = root.resolve()
    if inventory.get("schema") != INVENTORY_SCHEMA:
        return (f"inventory schema must be {INVENTORY_SCHEMA}",)
    raw_rows = inventory.get("rows")
    if not isinstance(raw_rows, list):
        return ("inventory rows must be a list",)

    changed = tuple(dict.fromkeys(_norm(item) for item in changed_files))
    owners: dict[str, set[str]] = defaultdict(set)
    baseline_by_path: dict[str, dict[str, object]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        path = _norm(str(raw_row.get("path") or ""))
        baseline_by_path[path] = raw_row
        role = raw_row.get("role")
        contract = raw_row.get("contract")
        if role == "CURRENT" and isinstance(contract, str) and contract:
            owners[contract].add(path)

    # PR bases can predate the inventory freeze. A path listed by the PR diff
    # is not post-freeze drift when its current bytes still match the frozen
    # inventory snapshot. Only true post-freeze changes enter enforcement.
    effective_changed: list[str] = []
    for rel in changed:
        path = root / rel
        baseline = baseline_by_path.get(rel)
        frozen_hash = baseline.get("content_sha256") if baseline else None
        if (
            path.is_file()
            and isinstance(frozen_hash, str)
            and frozen_hash
            and hashlib.sha256(path.read_bytes()).hexdigest() == frozen_hash
        ):
            continue
        effective_changed.append(rel)
    changed = tuple(effective_changed)

    for rel in changed:
        baseline = baseline_by_path.get(rel)
        if baseline and baseline.get("role") == "CURRENT" and isinstance(baseline.get("contract"), str):
            owners[str(baseline["contract"])].discard(rel)

    errors: list[str] = []
    for rel in changed:
        path = root / rel
        if not path.exists():
            continue
        if not is_governed_markdown(rel):
            continue
        try:
            metadata = parse_doc_metadata(path.read_text(encoding="utf-8"), path=rel)
        except (GovernanceError, UnicodeDecodeError) as exc:
            errors.append(f"{rel}: missing/invalid {DOC_SCHEMA} metadata: {exc}")
            continue
        if metadata.role == "MIRROR":
            assert metadata.canonical is not None
            target = root / metadata.canonical
            if not target.is_file():
                errors.append(
                    f"{rel}: MIRROR canonical target does not exist: {metadata.canonical}"
                )
        if metadata.role == "CURRENT":
            owners[metadata.contract].add(rel)

    for contract, current_paths in sorted(owners.items()):
        active = sorted(path for path in current_paths if path)
        if len(active) > 1:
            errors.append(f"{contract}: multiple CURRENT owners after change: {active}")
    return tuple(sorted(errors))



def _body_after_frontmatter(text: str, *, path: str) -> list[str]:
    source = text.lstrip("\ufeff")
    lines = source.splitlines()
    if not lines or lines[0].strip() != "---":
        raise GovernanceError(f"{path}: missing {DOC_SCHEMA} YAML frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise GovernanceError(f"{path}: unterminated YAML frontmatter") from exc
    return [line.strip() for line in lines[end + 1 :] if line.strip()]


def _explicit_authority_routing_by_path(
    root: Path, governed: Sequence[Path]
) -> dict[str, list[str]]:
    """Return only explicit route dependencies, excluding trigger-only file globs."""
    registry_path = root / ".agents/skills/skill_registry.json"
    if not registry_path.is_file():
        return {}
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    routes = registry.get("routes")
    if not isinstance(routes, list):
        return {}

    skill_name_to_path: dict[str, str] = {}
    for path in governed:
        rel = _norm(path.relative_to(root))
        if rel.startswith(".agents/skills/") and path.name == "SKILL.md":
            name = _generic_frontmatter_value(path.read_text(encoding="utf-8"), "name")
            if name:
                skill_name_to_path[name] = rel

    routing: dict[str, set[str]] = defaultdict(set)
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("id") or "<unnamed-route>")
        for reference in route.get("required_references", ()) or ():
            routing[_norm(str(reference))].add(route_id)
        for skill in route.get("required_skills", ()) or ():
            skill_path = skill_name_to_path.get(str(skill))
            if skill_path:
                routing[skill_path].add(route_id)
    return {path: sorted(route_ids) for path, route_ids in routing.items()}


def validate_strict(root: Path) -> tuple[str, ...]:
    """Validate the complete governed Markdown tree after T6 migration."""
    root = root.resolve()
    governed = _iter_governed_markdown(root)
    explicit_routing = _explicit_authority_routing_by_path(root, governed)
    errors: list[str] = []
    current_owners: dict[str, set[str]] = defaultdict(set)

    for path in governed:
        rel = _norm(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
            metadata = parse_doc_metadata(text, path=rel)
        except (GovernanceError, UnicodeDecodeError, OSError) as exc:
            errors.append(f"{rel}: missing/invalid {DOC_SCHEMA} metadata: {exc}")
            continue

        if metadata.role == "CURRENT":
            current_owners[metadata.contract].add(rel)

        if metadata.role == "HISTORICAL" and explicit_routing.get(rel):
            errors.append(
                f"{rel}: HISTORICAL document must not participate in explicit authority routing: "
                f"{explicit_routing[rel]}"
            )

        if metadata.role == "MIRROR":
            assert metadata.canonical is not None
            target = root / metadata.canonical
            if not target.is_file():
                errors.append(
                    f"{rel}: MIRROR canonical target does not exist: {metadata.canonical}"
                )
            try:
                body = _body_after_frontmatter(text, path=rel)
            except GovernanceError as exc:
                errors.append(str(exc))
                continue
            joined = "\n".join(body)
            if not 3 <= len(body) <= 5:
                errors.append(
                    f"{rel}: MIRROR must use pointer-only 3-5 non-empty body lines; got {len(body)}"
                )
            if metadata.canonical not in joined:
                errors.append(
                    f"{rel}: MIRROR pointer-only body must name canonical target {metadata.canonical}"
                )
            if "不得新增或複製 normative 規則" not in joined:
                errors.append(
                    f"{rel}: MIRROR pointer-only body missing normative-copy prohibition"
                )

    for contract, owners in sorted(current_owners.items()):
        if len(owners) > 1:
            errors.append(f"{contract}: multiple CURRENT owners in strict mode: {sorted(owners)}")

    return tuple(sorted(errors))



def _safe_target_role(path: str) -> tuple[str, str | None]:
    rel = _norm(path)
    name = Path(rel).name
    if rel.startswith("docs/superpowers/plans/"):
        return "HISTORICAL", None
    if rel.startswith("docs/superpowers/verification/"):
        return "HISTORICAL", None
    if rel.startswith("docs/superpowers/checkpoints/"):
        return "HISTORICAL", None
    if rel.startswith("handoff/"):
        return "HISTORICAL", None
    if rel.startswith(".agents/skills/deprecated/"):
        return "HISTORICAL", None
    if rel.startswith(".agents/skills/") and name == "README.md":
        return "REFERENCE", None
    if rel.startswith(".agents/skills/") and name == "SKILL.md":
        return "CURRENT", "MISSING_STABLE_CONTRACT"
    if name == "README.md":
        return "REFERENCE", None
    if rel.startswith("個人AI檔案庫/踩坑庫/"):
        return "REFERENCE", None
    if rel == "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md":
        return "REFERENCE", None
    if name.startswith("CURRENT_"):
        return "HISTORICAL", None
    return "UNRESOLVED", "ROLE_REQUIRES_AUTHORITY_REVIEW"


def build_classification_matrix(
    root: Path,
    inventory: Mapping[str, object],
) -> dict[str, object]:
    if inventory.get("schema") != INVENTORY_SCHEMA:
        raise GovernanceError(f"inventory schema must be {INVENTORY_SCHEMA}")
    raw_rows = inventory.get("rows")
    if not isinstance(raw_rows, list):
        raise GovernanceError("inventory rows must be a list")

    authority_rows = _authority_rows(root.resolve())
    authority_by_path: dict[str, dict[str, str]] = {}
    authority_currents: dict[str, set[str]] = defaultdict(set)
    for authority in authority_rows:
        rel = _norm(authority["path"])
        authority_by_path[rel] = authority
        if authority.get("role") == "CURRENT":
            authority_currents[authority["contract"]].add(rel)

    classified_rows: list[dict[str, object]] = []
    by_contract: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        rel = _norm(str(row.get("path") or ""))
        observed_role = str(row.get("role") or "UNKNOWN")
        contract = row.get("contract")
        contract = contract if isinstance(contract, str) and contract else None
        authority = authority_by_path.get(rel)

        blocker: str | None = None
        if authority is not None:
            target_role = authority.get("role", observed_role)
            contract = authority.get("contract") or contract
            if target_role == "MIRROR":
                row["replacement"] = authority.get("canonical") or row.get("replacement")
        elif observed_role in VALID_ROLES:
            target_role = observed_role
        else:
            target_role, blocker = _safe_target_role(rel)

        if target_role == "CURRENT" and not contract:
            blocker = blocker or "MISSING_STABLE_CONTRACT"

        classified = {
            **row,
            "path": rel,
            "observed_role": observed_role,
            "target_role": target_role,
            "contract": contract,
            "blocker": blocker,
            "proposed_current_owner": None,
        }
        classified_rows.append(classified)
        if contract:
            by_contract[contract].append(classified)

    all_contracts = set(by_contract) | set(authority_currents)
    contract_rows: list[dict[str, object]] = []
    proposed_by_contract: dict[str, str | None] = {}
    conflicts: list[dict[str, object]] = []

    for contract in sorted(all_contracts):
        rows = by_contract.get(contract, [])
        candidates = {
            str(row["path"])
            for row in rows
            if row.get("target_role") == "CURRENT"
        }
        candidates.update(authority_currents.get(contract, set()))
        canonical_hints = {
            _norm(str(row.get("canonical_owner")))
            for row in rows
            if isinstance(row.get("canonical_owner"), str) and row.get("canonical_owner")
        }
        mapped = sorted(authority_currents.get(contract, set()))
        if len(mapped) == 1:
            proposed = mapped[0]
        elif len(canonical_hints) == 1:
            proposed = next(iter(canonical_hints))
        elif len(candidates) == 1:
            proposed = next(iter(candidates))
        else:
            proposed = None
        proposed_by_contract[contract] = proposed
        contract_rows.append(
            {
                "contract": contract,
                "current_candidates": sorted(candidates),
                "proposed_current_owner": proposed,
            }
        )
        if len(candidates) > 1:
            conflicts.append(
                {
                    "code": "DUAL_CURRENT",
                    "contract": contract,
                    "paths": sorted(candidates),
                    "proposed_current_owner": proposed,
                }
            )

    for row in classified_rows:
        contract = row.get("contract")
        if isinstance(contract, str):
            row["proposed_current_owner"] = proposed_by_contract.get(contract)
        target_role = row.get("target_role")
        rel = str(row.get("path") or "")
        routing = list(row.get("machine_routing") or [])
        incoming = list(row.get("incoming_references") or [])
        if target_role == "CURRENT" and not contract:
            conflicts.append(
                {
                    "code": "ORPHAN_CURRENT",
                    "contract": None,
                    "paths": [rel],
                    "proposed_current_owner": None,
                }
            )
        if target_role == "UNRESOLVED" and (routing or incoming):
            conflicts.append(
                {
                    "code": "UNKNOWN_ACTIVE",
                    "contract": contract,
                    "paths": [rel],
                    "proposed_current_owner": row.get("proposed_current_owner"),
                }
            )
        if target_role == "HISTORICAL" and routing:
            conflicts.append(
                {
                    "code": "STALE_ROUTE",
                    "contract": contract,
                    "paths": [rel],
                    "routes": sorted(str(item) for item in routing),
                    "proposed_current_owner": row.get("proposed_current_owner"),
                }
            )
        if target_role == "HISTORICAL" and "CURRENT" in Path(rel).name.upper():
            conflicts.append(
                {
                    "code": "MISLEADING_CURRENT_NAME",
                    "contract": contract,
                    "paths": [rel],
                    "proposed_current_owner": row.get("proposed_current_owner"),
                }
            )

    return {
        "schema": CLASSIFICATION_SCHEMA,
        "source_head": inventory.get("source_head"),
        "rows": sorted(classified_rows, key=lambda row: str(row.get("path") or "")),
        "contracts": contract_rows,
        "conflicts": sorted(
            conflicts,
            key=lambda item: (
                str(item.get("code") or ""),
                str(item.get("contract") or ""),
                tuple(item.get("paths") or []),
            ),
        ),
    }

def _git_changed_files(root: Path, base: str, head: str) -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", "-z", base, head],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return tuple(
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    )


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _load_inventory(path: Path) -> Mapping[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GovernanceError("inventory root must be an object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WHD knowledge/documentation governance")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory", help="build governed-document inventory")
    inventory_parser.add_argument("--root", default=".")
    inventory_parser.add_argument("--source-head", required=True)
    inventory_parser.add_argument("--output", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap", help="validate changed governed Markdown")
    bootstrap_parser.add_argument("--root", default=".")
    bootstrap_parser.add_argument("--inventory", required=True)
    bootstrap_parser.add_argument("--changed-file", action="append", default=[])
    bootstrap_parser.add_argument("--base")
    bootstrap_parser.add_argument("--head", default="HEAD")

    classify_parser = subparsers.add_parser("classify", help="classify governed-document authority")
    classify_parser.add_argument("--root", default=".")
    classify_parser.add_argument("--inventory", required=True)
    classify_parser.add_argument("--output", required=True)

    strict_parser = subparsers.add_parser("strict", help="validate all governed Markdown in strict mode")
    strict_parser.add_argument("--root", default=".")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "inventory":
        payload = build_inventory(root, source_head=args.source_head)
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        _write_json(output, payload)
        print(f"inventory rows={len(payload['rows'])} source_head={args.source_head}")
        return 0

    if args.command == "classify":
        inventory_path = Path(args.inventory)
        if not inventory_path.is_absolute():
            inventory_path = root / inventory_path
        inventory = _load_inventory(inventory_path)
        payload = build_classification_matrix(root, inventory)
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        _write_json(output, payload)
        print(f"classification rows={len(payload['rows'])} conflicts={len(payload['conflicts'])}")
        return 0

    if args.command == "strict":
        errors = validate_strict(root)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"strict governance GREEN governed={len(_iter_governed_markdown(root))}")
        return 0

    inventory_path = Path(args.inventory)
    if not inventory_path.is_absolute():
        inventory_path = root / inventory_path
    inventory = _load_inventory(inventory_path)
    changed_files = list(args.changed_file)
    if args.base:
        changed_files.extend(_git_changed_files(root, args.base, args.head))
    errors = validate_bootstrap(root, inventory, changed_files=changed_files)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"bootstrap governance GREEN changed={len(set(changed_files))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
