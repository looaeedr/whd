from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

ALLOWED_CONTEXT_SUFFIXES = {".md", ".json"}
ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_context_text(path: Path | str) -> str:
    """Read only explicit UTF-8 Markdown/JSON context; reject binary payloads fail-closed."""
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix not in ALLOWED_CONTEXT_SUFFIXES:
        raise ValueError(
            f"context text loader only accepts .md/.json; got {target.name!r}"
        )
    raw = target.read_bytes()
    prefix = raw[:4096]
    if any(raw.startswith(magic) for magic in ZIP_MAGIC) or b"\x00" in prefix:
        raise ValueError(f"binary content is forbidden in context loader: {target}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"context text must be valid UTF-8: {target}") from exc


def trailing_whitespace_paths(root: Path | str) -> tuple[str, ...]:
    base = Path(root)
    offenders: list[str] = []
    for path in base.rglob("*"):
        rel = path.relative_to(base)
        if any(part != part.strip() for part in rel.parts):
            offenders.append(rel.as_posix())
    return tuple(sorted(set(offenders)))


def assert_clean_skill_paths(skills_root: Path | str) -> None:
    root = Path(skills_root)
    offenders = trailing_whitespace_paths(root)
    if offenders:
        raise ValueError(
            "skill paths contain leading/trailing whitespace: " + ", ".join(offenders)
        )


def _frontmatter_name(path: Path) -> str | None:
    text = read_context_text(path)
    match = re.search(r'^name:\\s*["\\']?(.+?)["\\']?\\s*$', text, re.MULTILINE)
    return match.group(1).strip() if match else None


def validate_registry_targets(
    *,
    repo_root: Path | str,
    registry: Mapping[str, object] | None = None,
    catalog: Mapping[str, object] | None = None,
) -> None:
    """Fail closed if Registry routes to missing or non-canonical/inactive Skills."""
    root = Path(repo_root)
    skills_root = root / ".agents" / "skills"
    assert_clean_skill_paths(skills_root)

    if registry is None:
        registry = json.loads(read_context_text(skills_root / "skill_registry.json"))
    if catalog is None:
        catalog = json.loads(read_context_text(skills_root / "skill_catalog.json"))

    active = set(str(v) for v in catalog.get("active_classifications", ()))
    rules = list(catalog.get("ordered_rules", ()))

    import fnmatch

    skill_by_name: dict[str, tuple[str, str]] = {}
    for path in sorted(skills_root.rglob("SKILL.md")):
        rel = path.relative_to(root).as_posix()
        classification = None
        for rule in rules:
            if fnmatch.fnmatchcase(rel, str(rule.get("glob", ""))):
                classification = str(rule.get("classification", ""))
                break
        name = _frontmatter_name(path)
        if name:
            skill_by_name[name] = (rel, classification or "")

    errors: list[str] = []
    for route in registry.get("routes", ()):  # type: ignore[union-attr]
        if not isinstance(route, Mapping):
            errors.append("registry route must be an object")
            continue
        route_id = str(route.get("id") or "<unnamed>")
        for skill_name in route.get("required_skills", ()) or ():
            name = str(skill_name)
            row = skill_by_name.get(name)
            if row is None:
                errors.append(f"{route_id}: missing required skill {name}")
                continue
            rel, classification = row
            if classification not in active or classification != "canonical":
                errors.append(
                    f"{route_id}: inactive required skill {name} -> {rel} ({classification})"
                )
            if "/in-progress/" in f"/{rel}" or "/deprecated/" in f"/{rel}":
                errors.append(f"{route_id}: forbidden inactive bucket target {rel}")
    if errors:
        raise ValueError("skill registry/catalog conflict: " + "; ".join(errors))
