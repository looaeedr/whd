# -*- coding: utf-8 -*-
"""Resolve T6 metadata authority gaps without mutating governed Markdown.

Authority precedence is deliberately one-way:
  frozen T1 matrix -> explicit T6 resolution overlay -> effective authority.

The overlay may only repair an incomplete frozen row or add an exact post-T1
path. It may not rewrite a complete frozen T1 decision. Resolution evidence is
stored on every overlay row so later migration never needs to infer authority
from validator output.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from pathlib import Path
from typing import Mapping, Sequence

FROZEN_SCHEMA = "WHD_KNOWLEDGE_CLASSIFICATION_V1"
OVERLAY_SCHEMA = "WHD_KNOWLEDGE_AUTHORITY_OVERLAY_V1"
VALID_ROLES = {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"}
CONTRACT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
AUTHORITY_RE = re.compile(r"<!--\s+WHD_AUTHORITY(?:_ROW)?\s+(?P<attrs>.*?)\s*-->", re.DOTALL)
ATTR_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>\"[^\"]*\"|'[^']*'|[^\s]+)")
SKIP_PARTS = {".git", ".scratch", "BACKUP", "__pycache__", ".pytest_cache"}


class AuthorityOverlayError(ValueError):
    pass


def _norm(value: str | Path) -> str:
    text = Path(value).as_posix()
    return text[2:] if text.startswith("./") else text


def _git_blob_sha(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _load_json(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorityOverlayError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthorityOverlayError(f"{path}: JSON root must be an object")
    return payload


def _rows(payload: Mapping[str, object], schema: str, *, label: str) -> list[dict[str, object]]:
    if payload.get("schema") != schema:
        raise AuthorityOverlayError(f"{label} schema must be {schema}")
    raw = payload.get("rows")
    if not isinstance(raw, list):
        raise AuthorityOverlayError(f"{label} rows must be a list")
    result: list[dict[str, object]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise AuthorityOverlayError(f"{label} row {index} must be an object")
        result.append(dict(item))
    return result


def is_governed_markdown(path: str | Path) -> bool:
    rel = _norm(path)
    candidate = Path(rel)
    if candidate.suffix.lower() != ".md":
        return False
    if any(part in SKIP_PARTS for part in candidate.parts):
        return False
    if len(candidate.parts) == 1:
        return True
    return rel.startswith(("個人AI檔案庫/", ".agents/skills/", "docs/", "handoff/"))


def governed_paths(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    return tuple(sorted(
        _norm(path.relative_to(root))
        for path in root.rglob("*.md")
        if path.is_file() and is_governed_markdown(path.relative_to(root))
    ))


def _valid_contract(value: object) -> bool:
    return isinstance(value, str) and CONTRACT_RE.fullmatch(value) is not None


def _canonical(row: Mapping[str, object]) -> str | None:
    value = row.get("replacement") or row.get("canonical") or row.get("canonical_owner")
    return _norm(value) if isinstance(value, str) and value.strip() else None


def _complete_frozen_row(row: Mapping[str, object]) -> bool:
    role = row.get("target_role")
    if row.get("blocker"):
        return False
    if role not in VALID_ROLES:
        return False
    if not _valid_contract(row.get("contract")):
        return False
    if role == "MIRROR" and _canonical(row) is None:
        return False
    return True


def merge_effective_authority(matrix_path: Path, overlay_path: Path) -> tuple[dict[str, object], ...]:
    frozen_payload = _load_json(matrix_path)
    overlay_payload = _load_json(overlay_path)
    frozen_rows = _rows(frozen_payload, FROZEN_SCHEMA, label="frozen matrix")
    overlay_rows = _rows(overlay_payload, OVERLAY_SCHEMA, label="authority overlay")

    frozen: dict[str, dict[str, object]] = {}
    for row in frozen_rows:
        path = row.get("path")
        if not isinstance(path, str) or not path.strip():
            raise AuthorityOverlayError("frozen matrix row missing path")
        rel = _norm(path)
        if rel in frozen:
            raise AuthorityOverlayError(f"duplicate frozen path: {rel}")
        frozen[rel] = row

    overlays: dict[str, dict[str, object]] = {}
    for row in overlay_rows:
        path = row.get("path")
        if not isinstance(path, str) or not path.strip():
            raise AuthorityOverlayError("overlay row missing path")
        rel = _norm(path)
        if rel in overlays:
            raise AuthorityOverlayError(f"duplicate overlay path: {rel}")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
            raise AuthorityOverlayError(f"{rel}: resolution requires explicit evidence")
        resolves = row.get("resolves")
        if not isinstance(resolves, str) or not resolves.strip():
            raise AuthorityOverlayError(f"{rel}: resolution requires provenance in resolves")
        if rel in frozen and _complete_frozen_row(frozen[rel]):
            raise AuthorityOverlayError(f"{rel}: overlay may not override an unblocked complete frozen row")
        role = row.get("target_role")
        if role not in VALID_ROLES:
            raise AuthorityOverlayError(f"{rel}: overlay role must be one of {sorted(VALID_ROLES)}")
        if not _valid_contract(row.get("contract")):
            raise AuthorityOverlayError(f"{rel}: overlay requires stable kebab-case contract")
        canonical = row.get("canonical")
        if role == "MIRROR":
            if not isinstance(canonical, str) or not canonical.strip():
                raise AuthorityOverlayError(f"{rel}: MIRROR overlay requires canonical")
            canonical = _norm(canonical)
        elif canonical is not None:
            raise AuthorityOverlayError(f"{rel}: non-MIRROR canonical must be null")
        normalized = dict(row)
        normalized["path"] = rel
        normalized["blocker"] = None
        normalized["replacement"] = canonical if role == "MIRROR" else None
        overlays[rel] = normalized

    effective: dict[str, dict[str, object]] = {path: dict(row) for path, row in frozen.items()}
    for path, row in overlays.items():
        base = effective.get(path, {})
        merged = dict(base)
        merged.update({
            "path": path,
            "target_role": row["target_role"],
            "contract": row["contract"],
            "blocker": None,
            "replacement": row.get("replacement"),
            "resolution_evidence": list(row["evidence"]),
            "resolution_provenance": row["resolves"],
        })
        effective[path] = merged
    return tuple(effective[path] for path in sorted(effective))


def _frontmatter_name(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").lstrip("\ufeff").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() == "name":
            result = value.strip().strip("'\"")
            return result or None
    return None


def _authority_by_path(root: Path) -> dict[str, dict[str, str]]:
    path = root / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
    text = path.read_text(encoding="utf-8")
    result: dict[str, dict[str, str]] = {}
    for match in AUTHORITY_RE.finditer(text):
        attrs: dict[str, str] = {}
        for attr in ATTR_RE.finditer(match.group("attrs")):
            value = attr.group("value")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            attrs[attr.group("key")] = value
        if {"path", "role", "contract"} <= set(attrs):
            result[_norm(attrs["path"])] = attrs
    return result


def _registry(root: Path) -> Mapping[str, object]:
    return _load_json(root / ".agents/skills/skill_registry.json")


def _catalog(root: Path) -> Mapping[str, object]:
    return _load_json(root / ".agents/skills/skill_catalog.json")


def _catalog_classification(path: str, catalog: Mapping[str, object]) -> str | None:
    rules = catalog.get("ordered_rules")
    if not isinstance(rules, list):
        return None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        glob = rule.get("glob")
        classification = rule.get("classification")
        if isinstance(glob, str) and isinstance(classification, str) and fnmatch.fnmatch(path, glob):
            return classification
    return None


def _skill_route_contract(name: str, registry: Mapping[str, object]) -> tuple[str | None, list[str]]:
    routes = registry.get("routes")
    if not isinstance(routes, list):
        return None, []
    matches: list[tuple[str, bool]] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = route.get("id")
        skills = route.get("required_skills")
        if not isinstance(route_id, str) or not isinstance(skills, list) or name not in skills:
            continue
        matches.append((route_id, bool(skills and skills[0] == name)))
    if CONTRACT_RE.fullmatch(name):
        return name, [route for route, _ in matches]
    primary = sorted({route for route, is_primary in matches if is_primary})
    if len(primary) == 1:
        return primary[0], [route for route, _ in matches]
    unique = sorted({route for route, _ in matches})
    if len(unique) == 1:
        return unique[0], unique
    return None, unique


def _skill_resolution(root: Path, rel: str, registry: Mapping[str, object], catalog: Mapping[str, object], authority: Mapping[str, Mapping[str, str]]) -> dict[str, object]:
    mapped = authority.get(rel)
    if mapped is not None:
        role = mapped.get("role")
        contract = mapped.get("contract")
        if role in VALID_ROLES and isinstance(contract, str) and CONTRACT_RE.fullmatch(contract):
            return {"role": role, "contract": contract, "canonical": mapped.get("canonical"), "evidence": [f"authority-map:{rel}"]}

    name = _frontmatter_name(root / rel)
    if not name:
        raise AuthorityOverlayError(f"{rel}: SKILL.md missing explicit frontmatter name")
    classification = _catalog_classification(rel, catalog)
    role_by_class = {
        "canonical": "CURRENT",
        "reference": "REFERENCE",
        "upstream-beta": "REFERENCE",
        "tool-specific": "REFERENCE",
        "retired": "HISTORICAL",
    }
    role = role_by_class.get(str(classification))
    if role is None:
        raise AuthorityOverlayError(f"{rel}: skill catalog has no supported classification")
    contract, routes = _skill_route_contract(name, registry)
    if contract is None:
        raise AuthorityOverlayError(f"{rel}: no unique stable contract from skill name/registry routes {routes}")
    evidence = [f"skill-catalog:{classification}", f"skill-frontmatter:name={name}"]
    if routes:
        evidence.append("skill-registry:" + ",".join(sorted(routes)))
    return {"role": role, "contract": contract, "canonical": None, "evidence": evidence}


def _category_resolution(rel: str, frozen: Mapping[str, object] | None) -> dict[str, object] | None:
    role = frozen.get("target_role") if frozen else None
    if rel == "docs/superpowers/CURRENT_API_INVENTORY_20260818.md":
        return {"role": "HISTORICAL", "contract": "api-inventory-snapshot", "canonical": None, "evidence": ["issue233:CURRENT_API_INVENTORY must be HISTORICAL", "approved-spec:T6 historical/current-named snapshot"]}
    if rel.startswith("docs/superpowers/plans/"):
        return {"role": "HISTORICAL", "contract": "implementation-plan-provenance", "canonical": None, "evidence": ["approved-spec:HISTORICAL preserves migration/implementation provenance", "path-scope:docs/superpowers/plans"]}
    if rel.startswith("docs/superpowers/verification/"):
        return {"role": "HISTORICAL", "contract": "verification-provenance", "canonical": None, "evidence": ["approved-spec:HISTORICAL preserves old acceptance/verification evidence", "path-scope:docs/superpowers/verification"]}
    if rel.startswith("docs/superpowers/checkpoints/"):
        return {"role": "HISTORICAL", "contract": "execution-checkpoint-provenance", "canonical": None, "evidence": ["approved-spec:HISTORICAL preserves migration/issue evidence", "path-scope:docs/superpowers/checkpoints"]}
    if rel.startswith("docs/superpowers/specs/"):
        return {"role": "HISTORICAL", "contract": "design-provenance", "canonical": None, "evidence": ["approved-spec:HISTORICAL preserves design provenance", "path-scope:docs/superpowers/specs"]}
    if rel.startswith("handoff/"):
        return {"role": "HISTORICAL", "contract": "handoff-provenance", "canonical": None, "evidence": ["approved-spec:HISTORICAL preserves old handoff architecture", "path-scope:handoff"]}
    if rel.startswith("個人AI檔案庫/踩坑庫/"):
        return {"role": "REFERENCE", "contract": "pitfall-ledger", "canonical": None, "evidence": ["authority-map:pitfall-ledger boundary", "authority-map:pitfall artifacts are REFERENCE incident evidence"]}
    if rel.startswith("個人AI檔案庫/"):
        return {"role": "REFERENCE", "contract": "ai-library-reference", "canonical": None, "evidence": ["approved-spec:REFERENCE background/explanation context", "authority-map:only mapped paths may act as CURRENT owners"]}
    if rel.startswith(".agents/skills/deprecated/"):
        return {"role": "HISTORICAL", "contract": "retired-skill-provenance", "canonical": None, "evidence": ["skill-catalog:deprecated retired", "approved-spec:HISTORICAL provenance"]}
    if rel.startswith(".agents/skills/") and Path(rel).name == "README.md":
        return {"role": "REFERENCE", "contract": "skill-navigation", "canonical": None, "evidence": ["approved-spec:Skill README is navigation, not machine authority", "path-scope:skill README"]}
    if rel == "README.md":
        return {"role": "REFERENCE", "contract": "repository-navigation", "canonical": None, "evidence": ["approved-spec:README/navigation must not become parallel CURRENT", "path-scope:root README"]}
    if rel.startswith("docs/"):
        final_role = role if role in VALID_ROLES and role != "CURRENT" else "REFERENCE"
        contract = "documentation-provenance" if final_role == "HISTORICAL" else "documentation-reference"
        return {"role": final_role, "contract": contract, "canonical": None, "evidence": ["approved-spec:documentation authority separation", "path-scope:docs"]}
    if len(Path(rel).parts) == 1:
        final_role = role if role in VALID_ROLES and role != "CURRENT" else "REFERENCE"
        contract = "project-provenance" if final_role == "HISTORICAL" else "project-reference"
        return {"role": final_role, "contract": contract, "canonical": None, "evidence": ["approved-spec:unmapped project prose cannot become parallel CURRENT", "authority-map:no CURRENT row for path"]}
    return None


def build_overlay(root: Path, matrix_path: Path) -> dict[str, object]:
    root = root.resolve()
    frozen_payload = _load_json(matrix_path)
    frozen_rows = _rows(frozen_payload, FROZEN_SCHEMA, label="frozen matrix")
    frozen_by_path: dict[str, dict[str, object]] = {}
    for row in frozen_rows:
        rel = _norm(str(row.get("path") or ""))
        if not rel or rel in frozen_by_path:
            raise AuthorityOverlayError(f"invalid/duplicate frozen path: {rel!r}")
        frozen_by_path[rel] = row

    governed = governed_paths(root)
    governed_set = set(governed)
    nonexistent = sorted(set(frozen_by_path) - governed_set)
    if nonexistent:
        raise AuthorityOverlayError(f"frozen matrix paths no longer governed: {nonexistent}")

    authority = _authority_by_path(root)
    registry = _registry(root)
    catalog = _catalog(root)
    resolved_cache: dict[str, dict[str, object]] = {}

    def resolve(rel: str) -> dict[str, object]:
        if rel in resolved_cache:
            return resolved_cache[rel]
        frozen = frozen_by_path.get(rel)
        mapped = authority.get(rel)
        if mapped is not None:
            role = mapped.get("role")
            contract = mapped.get("contract")
            canonical = mapped.get("canonical")
            if role in VALID_ROLES and isinstance(contract, str) and CONTRACT_RE.fullmatch(contract):
                result = {"role": role, "contract": contract, "canonical": canonical, "evidence": [f"authority-map:{rel}"]}
                resolved_cache[rel] = result
                return result
        if rel.startswith(".agents/skills/") and Path(rel).name == "SKILL.md":
            result = _skill_resolution(root, rel, registry, catalog, authority)
            resolved_cache[rel] = result
            return result
        if rel.startswith(".agents/skills/") and Path(rel).name != "README.md":
            parts = Path(rel).parts
            skill_index = None
            for index in range(len(parts) - 1, 1, -1):
                candidate = root.joinpath(*parts[:index], "SKILL.md")
                if candidate.is_file():
                    skill_index = index
                    break
            if skill_index is not None:
                parent_rel = Path(*parts[:skill_index], "SKILL.md").as_posix()
                parent = resolve(parent_rel)
                role = "HISTORICAL" if parent["role"] == "HISTORICAL" else "REFERENCE"
                result = {"role": role, "contract": parent["contract"], "canonical": None, "evidence": [f"parent-skill:{parent_rel}", *list(parent["evidence"])]}
                resolved_cache[rel] = result
                return result
        category = _category_resolution(rel, frozen)
        if category is None:
            raise AuthorityOverlayError(f"{rel}: no explicit resolution authority")
        resolved_cache[rel] = category
        return category

    overlay_rows: list[dict[str, object]] = []
    for rel in governed:
        frozen = frozen_by_path.get(rel)
        if frozen is not None and _complete_frozen_row(frozen):
            continue
        resolution = resolve(rel)
        role = resolution["role"]
        contract = resolution["contract"]
        canonical = resolution.get("canonical")
        if role == "MIRROR":
            canonical = _norm(str(canonical or _canonical(frozen or {}))) if (canonical or _canonical(frozen or {})) else None
            if canonical is None or canonical not in governed_set:
                raise AuthorityOverlayError(f"{rel}: resolved MIRROR canonical missing/nonexistent: {canonical}")
        else:
            canonical = None
        overlay_rows.append({
            "path": rel,
            "target_role": role,
            "contract": contract,
            "canonical": canonical,
            "evidence": list(resolution["evidence"]),
            "resolves": "post-t1-governed-path" if frozen is None else f"frozen-t1:{frozen.get('target_role')}:{frozen.get('blocker') or 'missing-stable-contract'}",
        })

    payload: dict[str, object] = {
        "schema": OVERLAY_SCHEMA,
        "frozen_matrix_path": _norm(matrix_path.relative_to(root)),
        "frozen_matrix_blob_sha1": _git_blob_sha(matrix_path.read_bytes()),
        "governed_count": len(governed),
        "resolution_count": len(overlay_rows),
        "rows": overlay_rows,
    }
    return payload


def validate_total(root: Path, matrix_path: Path, overlay_path: Path) -> tuple[str, ...]:
    errors: list[str] = []
    try:
        effective = merge_effective_authority(matrix_path, overlay_path)
    except AuthorityOverlayError as exc:
        return (str(exc),)
    by_path = {str(row.get("path")): row for row in effective}
    governed = set(governed_paths(root))
    if set(by_path) != governed:
        errors.append(f"effective/governed path mismatch missing={sorted(governed-set(by_path))} extra={sorted(set(by_path)-governed)}")
    for rel, row in sorted(by_path.items()):
        role = row.get("target_role")
        if role not in VALID_ROLES:
            errors.append(f"{rel}: unresolved/unknown role {role!r}")
        if row.get("blocker"):
            errors.append(f"{rel}: unresolved blocker {row.get('blocker')}")
        if not _valid_contract(row.get("contract")):
            errors.append(f"{rel}: missing/invalid stable contract")
        if role == "MIRROR":
            canonical = _canonical(row)
            if canonical is None or not (root / canonical).is_file():
                errors.append(f"{rel}: invalid MIRROR canonical {canonical!r}")
    return tuple(errors)


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WHD T6 authority resolution overlay")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--root", default=".")
    generate.add_argument("--matrix", required=True)
    generate.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--root", default=".")
    validate.add_argument("--matrix", required=True)
    validate.add_argument("--overlay", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    matrix = Path(args.matrix)
    if not matrix.is_absolute():
        matrix = root / matrix
    if args.command == "generate":
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        try:
            payload = build_overlay(root, matrix)
            _write_json(output, payload)
            errors = validate_total(root, matrix, output)
        except AuthorityOverlayError as exc:
            print(f"AUTHORITY_BLOCKED: {exc}")
            return 2
        if errors:
            for error in errors:
                print(f"AUTHORITY_BLOCKED: {error}")
            return 2
        print(f"authority overlay GREEN governed={payload['governed_count']} resolutions={payload['resolution_count']}")
        return 0
    overlay = Path(args.overlay)
    if not overlay.is_absolute():
        overlay = root / overlay
    errors = validate_total(root, matrix, overlay)
    if errors:
        for error in errors:
            print(f"AUTHORITY_BLOCKED: {error}")
        return 2
    print(f"effective authority GREEN governed={len(governed_paths(root))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
