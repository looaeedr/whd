# -*- coding: utf-8 -*-
"""Phase6 Knowledge Preflight gate.

Skills 決定 AI 怎麼改；required references 提供踩坑、規格與 Source of Truth。
本工具只檢查 AI 開發流程 evidence，不參與 runtime 製造公式。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
ROUTE_STATUS_ACTIVE = "ACTIVE"
ROUTE_STATUS_RETIRED = "RETIRED"
ROUTE_STATUS_VALUES = frozenset({ROUTE_STATUS_ACTIVE, ROUTE_STATUS_RETIRED})

GLOBAL_REQUIRED_REFERENCES = (
    "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
)


def _force_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict")


def _norm(value: str | Path) -> str:
    text = Path(value).as_posix()
    return text[2:] if text.startswith("./") else text


def _keyword_matches_task(keyword: str, task_text: str) -> bool:
    keyword_text = keyword.lower()
    is_short_ascii_acronym = (
        len(keyword) <= 3
        and keyword.isascii()
        and keyword.isalnum()
        and any(char.isupper() or char.isdigit() for char in keyword)
    )
    if is_short_ascii_acronym:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(keyword_text)}(?![A-Za-z0-9_])"
        return re.search(pattern, task_text) is not None
    return keyword_text in task_text


def _route_status(route: Mapping[str, object]) -> str:
    status = str(route.get("routing_status") or ROUTE_STATUS_ACTIVE).strip().upper()
    if status not in ROUTE_STATUS_VALUES:
        raise ValueError(f"unsupported skill_registry routing_status: {status}")
    return status


def _route_index(data: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for raw in data["routes"]:  # type: ignore[index]
        if not isinstance(raw, Mapping):
            raise ValueError("skill_registry route must be an object")
        route_id = str(raw.get("id") or "").strip()
        if not route_id:
            raise ValueError("skill_registry route id must be nonblank")
        if route_id in result:
            raise ValueError(f"duplicate skill_registry route id: {route_id}")
        result[route_id] = raw
    return result


def _effective_route(route: Mapping[str, object], data: Mapping[str, object]) -> Mapping[str, object]:
    if _route_status(route) == ROUTE_STATUS_ACTIVE:
        return route
    replacement = str(route.get("replacement_route_id") or "").strip()
    if not replacement:
        raise ValueError(f"retired route {route.get('id')} missing replacement_route_id")
    indexed = _route_index(data)
    target = indexed.get(replacement)
    if target is None:
        raise ValueError(f"retired route replacement missing: {replacement}")
    if _route_status(target) != ROUTE_STATUS_ACTIVE:
        raise ValueError(f"retired route replacement must be ACTIVE: {replacement}")
    retired_identity = str(route.get("id") or "").strip()
    if retired_identity in set(map(str, route.get("required_skills", ()) or ())):
        raise ValueError(f"retired route must not require retired skill identity: {retired_identity}")
    return target


def load_skill_registry(path: Path = REGISTRY) -> Mapping[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported skill_registry schema_version")
    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("skill_registry routes must be a non-empty list")
    indexed = _route_index(data)
    for route in indexed.values():
        status = _route_status(route)
        if status == ROUTE_STATUS_RETIRED:
            _effective_route(route, data)
    return data


def required_skills_for(
    *,
    task: str = "",
    changed_files: Iterable[str] = (),
    registry: Mapping[str, object] | None = None,
) -> tuple[str, ...]:
    data = registry or load_skill_registry()
    task_text = str(task or "").lower()
    files = tuple(_norm(path) for path in changed_files)
    required: list[str] = []

    for route in data["routes"]:  # type: ignore[index]
        if not isinstance(route, dict):
            raise ValueError("skill_registry route must be an object")
        keywords = tuple(str(item) for item in route.get("keywords", ()) or ())
        globs = tuple(_norm(str(item)) for item in route.get("file_globs", ()) or ())
        matched_keyword = any(_keyword_matches_task(keyword, task_text) for keyword in keywords)
        matched_file = any(fnmatch.fnmatch(path, pattern) for path in files for pattern in globs)
        if not (matched_keyword or matched_file):
            continue
        effective = _effective_route(route, data)
        for skill in tuple(effective.get("required_skills", ()) or ()):
            skill_name = str(skill)
            if skill_name not in required:
                required.append(skill_name)
    return tuple(required)


def required_references_for(
    *,
    task: str = "",
    changed_files: Iterable[str] = (),
    registry: Mapping[str, object] | None = None,
) -> tuple[str, ...]:
    data = registry or load_skill_registry()
    task_text = str(task or "").lower()
    files = tuple(_norm(path) for path in changed_files)
    required: list[str] = list(GLOBAL_REQUIRED_REFERENCES)

    for route in data["routes"]:  # type: ignore[index]
        if not isinstance(route, dict):
            raise ValueError("skill_registry route must be an object")
        keywords = tuple(str(item) for item in route.get("keywords", ()) or ())
        globs = tuple(_norm(str(item)) for item in route.get("file_globs", ()) or ())
        matched_keyword = any(_keyword_matches_task(keyword, task_text) for keyword in keywords)
        matched_file = any(fnmatch.fnmatch(path, pattern) for path in files for pattern in globs)
        if not (matched_keyword or matched_file):
            continue
        effective = _effective_route(route, data)
        for reference in tuple(effective.get("required_references", ()) or ()):
            rel = _norm(str(reference))
            if rel not in required:
                required.append(rel)
    return tuple(required)


def completed_skills_from_evidence(paths: Iterable[str]) -> set[str]:
    completed: set[str] = set()
    data = load_skill_registry()
    skill_names = {
        str(skill)
        for route in data["routes"]  # type: ignore[index]
        for skill in tuple(_effective_route(route, data).get("required_skills", ()) or ())
    }
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for skill_name in skill_names:
            if skill_name in text:
                completed.add(skill_name)
    return completed


def completed_references_from_evidence(
    paths: Iterable[str], required_references: Iterable[str]
) -> set[str]:
    required = tuple(_norm(item) for item in required_references)
    completed: set[str] = set()
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for reference in required:
            marker = f"READ_REFERENCE: {reference}"
            if marker in text and (ROOT / reference).is_file():
                completed.add(reference)
    return completed


def format_reference_report(required: Sequence[str], completed: set[str]) -> str:
    lines = ["REQUIRED REFERENCES"]
    if not required:
        lines.append("✓ no required references matched")
        return "\n".join(lines)
    for reference in required:
        mark = "✓" if reference in completed else "✗"
        lines.append(f"{mark} {reference}")
    return "\n".join(lines)


def format_report(required: Sequence[str], completed: set[str]) -> str:
    lines = ["REQUIRED SKILLS"]
    if not required:
        lines.append("✓ no required skills matched")
        return "\n".join(lines)
    for skill in required:
        mark = "✓" if skill in completed else "✗"
        lines.append(f"{mark} {skill}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase6 machine-readable Knowledge Preflight gate")
    parser.add_argument("--task", default="", help="任務描述或任務類型")
    parser.add_argument("--changed-file", action="append", default=[], help="本次修改檔案，可重複")
    parser.add_argument("--evidence", action="append", default=[], help="Skill/reference verification evidence 檔案，可重複")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _force_utf8_stdio()
    args = build_parser().parse_args(argv)
    required = required_skills_for(task=args.task, changed_files=args.changed_file)
    required_references = required_references_for(task=args.task, changed_files=args.changed_file)
    completed = completed_skills_from_evidence(args.evidence)
    completed_references = completed_references_from_evidence(args.evidence, required_references)
    print(format_report(required, completed))
    print(format_reference_report(required_references, completed_references))
    missing_skills = [skill for skill in required if skill not in completed]
    missing_references = [ref for ref in required_references if ref not in completed_references]
    return 1 if (missing_skills or missing_references) else 0


if __name__ == "__main__":
    raise SystemExit(main())