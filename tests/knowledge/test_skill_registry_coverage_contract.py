from __future__ import annotations

import json
from pathlib import Path

from tools.phase6_skill_preflight import REGISTRY, required_skills_for
from tools.skill_catalog import inventory


ROOT = Path(__file__).resolve().parents[2]


def _active_canonical_rows():
    return [row for row in inventory() if row.active and row.classification == "canonical"]


def _skill_name(path: str) -> str:
    return Path(path).parent.name


def test_every_active_canonical_skill_is_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registered = {
        str(skill)
        for route in registry["routes"]
        for skill in route.get("required_skills", [])
    }
    active = {_skill_name(row.path) for row in _active_canonical_rows()}
    assert active - registered == set()


def test_every_active_canonical_skill_is_explicitly_routable() -> None:
    failures: list[str] = []
    for row in _active_canonical_rows():
        name = _skill_name(row.path)
        by_name = set(required_skills_for(task=name))
        by_file = set(required_skills_for(changed_files=[row.path]))
        if name not in by_name:
            failures.append(f"{name}: task-name route missing")
        if name not in by_file:
            failures.append(f"{name}: skill-file route missing")
    assert failures == []
