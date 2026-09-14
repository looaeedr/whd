# -*- coding: utf-8 -*-
"""Resolve incomplete WHD knowledge authority without mutating governed docs.

The frozen T1 matrix remains provenance.  This module may derive a reviewed T6
resolution only from explicit authority sources (for example skill_registry
routing), and otherwise reports unresolved debt fail-closed.
"""

import copy
import fnmatch
import json
from pathlib import Path
from typing import Mapping

T1_SCHEMA = "WHD_KNOWLEDGE_CLASSIFICATION_V1"
OVERLAY_SCHEMA = "WHD_KNOWLEDGE_T6_OVERLAY_V1"
EFFECTIVE_SCHEMA = "WHD_KNOWLEDGE_EFFECTIVE_AUTHORITY_V1"
VALID_ROLES = {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"}
SKIP_PARTS = {".git", ".scratch", "BACKUP", "__pycache__", ".pytest_cache"}


class AuthorityResolutionError(ValueError):
    """Explicit authority is insufficient, ambiguous, or structurally invalid."""


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
    result = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        rel = _norm(path.relative_to(root))
        if _is_governed_markdown(rel):
            result.append(rel)
    return tuple(sorted(result))


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorityResolutionError(f"cannot read JSON authority {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthorityResolutionError(f"JSON authority must be an object: {path}")
    return payload


def _skill_name_from_path(path: str) -> str:
    candidate = Path(path)
    if candidate.name != "SKILL.md" or len(candidate.parts) < 2:
        raise AuthorityResolutionError(f"not a Skill authority path: {path}")
    return candidate.parent.name


def _route_matches_skill(route: Mapping[str, object], *, path: str, skill_name: str) -> bool:
    route_id = route.get("id")
    globs = route.get("file_globs")
    required = route.get("required_skills")
    if not isinstance(route_id, str) or not route_id:
        return False
    if not isinstance(globs, list) or not isinstance(required, list):
        return False
    if skill_name not in required:
        return False
    return any(isinstance(pattern, str) and fnmatch.fnmatchcase(path, pattern) for pattern in globs)


def resolve_registry_current_skill(
    row: Mapping[str, object], registry: Mapping[str, object]
) -> dict[str, object]:
    """Resolve one CURRENT Skill contract from one unique explicit registry route."""
    path = row.get("path")
    if not isinstance(path, str) or not path:
        raise AuthorityResolutionError("row path is required")
    if row.get("target_role") != "CURRENT":
        raise AuthorityResolutionError(f"{path}: registry Skill resolver only accepts CURRENT rows")

    skill_name = _skill_name_from_path(path)
    routes = registry.get("routes")
    if not isinstance(routes, list):
        raise AuthorityResolutionError("skill registry routes must be a list")
    candidates = [
        route
        for route in routes
        if isinstance(route, dict) and _route_matches_skill(route, path=path, skill_name=skill_name)
    ]
    if len(candidates) != 1:
        ids = [str(route.get("id")) for route in candidates]
        raise AuthorityResolutionError(
            f"{path}: explicit registry route must be unique; candidates={ids!r}"
        )

    route_id = candidates[0]["id"]
    return {
        "path": path,
        "target_role": "CURRENT",
        "contract": route_id,
        "canonical_owner": None,
        "blocker": None,
        "evidence": {
            "type": "skill_registry_route",
            "source": ".agents/skills/skill_registry.json",
            "route_id": route_id,
            "required_skill": skill_name,
        },
        "resolves": {
            "target_role": row.get("target_role"),
            "contract": row.get("contract"),
            "blocker": row.get("blocker"),
        },
    }


def merge_effective_authority(t1: Mapping[str, object], overlay: Mapping[str, object]) -> dict:
    """Return a new effective authority; never mutate frozen T1 input."""
    if t1.get("schema") != T1_SCHEMA:
        raise AuthorityResolutionError(f"T1 schema must be {T1_SCHEMA}")
    if overlay.get("schema") != OVERLAY_SCHEMA:
        raise AuthorityResolutionError(f"overlay schema must be {OVERLAY_SCHEMA}")
    t1_rows = t1.get("rows")
    overlay_rows = overlay.get("rows")
    if not isinstance(t1_rows, list) or not isinstance(overlay_rows, list):
        raise AuthorityResolutionError("T1 and overlay rows must be lists")

    by_path: dict[str, dict] = {}
    order: list[str] = []
    for row in t1_rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise AuthorityResolutionError("T1 row missing path")
        path = _norm(row["path"])
        if path in by_path:
            raise AuthorityResolutionError(f"duplicate T1 path: {path}")
        by_path[path] = copy.deepcopy(row)
        order.append(path)

    overlay_seen: set[str] = set()
    for row in overlay_rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise AuthorityResolutionError("overlay row missing path")
        path = _norm(row["path"])
        if path in overlay_seen:
            raise AuthorityResolutionError(f"duplicate overlay path: {path}")
        overlay_seen.add(path)
        replacement = copy.deepcopy(row)
        if "evidence" not in replacement:
            raise AuthorityResolutionError(f"{path}: overlay row requires evidence")
        if path not in by_path:
            order.append(path)
        by_path[path] = replacement

    return {
        "schema": EFFECTIVE_SCHEMA,
        "rows": [by_path[path] for path in order],
        "provenance": {
            "base_schema": T1_SCHEMA,
            "overlay_schema": OVERLAY_SCHEMA,
            "precedence": "exact overlay path overrides frozen T1 row",
        },
    }


def build_resolution_census(root: Path, matrix_path: Path, registry_path: Path) -> dict[str, object]:
    """Read-only census: resolve only explicit registry-backed CURRENT Skill contracts."""
    root = root.resolve()
    matrix_path = matrix_path.resolve()
    registry_path = registry_path.resolve()
    before = matrix_path.read_bytes()
    matrix = _load_json(matrix_path)
    registry = _load_json(registry_path)
    if matrix.get("schema") != T1_SCHEMA:
        raise AuthorityResolutionError(f"matrix schema must be {T1_SCHEMA}")
    rows = matrix.get("rows")
    if not isinstance(rows, list):
        raise AuthorityResolutionError("matrix rows must be a list")

    by_path: dict[str, Mapping[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise AuthorityResolutionError("matrix row missing path")
        path = _norm(row["path"])
        if path in by_path:
            raise AuthorityResolutionError(f"duplicate matrix path: {path}")
        by_path[path] = row

    governed = _governed_paths(root)
    missing_from_t1 = sorted(set(governed) - set(by_path))
    registry_resolved: list[dict[str, object]] = []
    remaining: list[dict[str, object]] = []

    for path in governed:
        row = by_path.get(path)
        if row is None:
            continue
        role = row.get("target_role")
        contract = row.get("contract")
        blocker = row.get("blocker")
        if role == "CURRENT" and (not contract or blocker == "MISSING_STABLE_CONTRACT") and path.endswith("/SKILL.md"):
            try:
                registry_resolved.append(resolve_registry_current_skill(row, registry))
                continue
            except AuthorityResolutionError:
                pass
        if role not in VALID_ROLES or blocker or not isinstance(contract, str) or not contract:
            remaining.append(
                {
                    "path": path,
                    "target_role": role,
                    "contract": contract,
                    "blocker": blocker,
                }
            )

    after = matrix_path.read_bytes()
    return {
        "matrix_count": len(rows),
        "governed_count": len(governed),
        "missing_from_t1_count": len(missing_from_t1),
        "missing_from_t1": missing_from_t1,
        "registry_resolved_current_count": len(registry_resolved),
        "registry_resolved_current": registry_resolved,
        "remaining_unresolved_count": len(remaining),
        "remaining_unresolved": remaining,
        "frozen_t1_modified": before != after,
    }


def main() -> int:
    root = Path(".").resolve()
    census = build_resolution_census(
        root,
        root / "docs/superpowers/verification/knowledge_authority_classification_v1.json",
        root / ".agents/skills/skill_registry.json",
    )
    print(json.dumps(census, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
