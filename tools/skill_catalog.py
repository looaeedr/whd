from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents/skills"
CATALOG_PATH = SKILLS_ROOT / "skill_catalog.json"


@dataclass(frozen=True)
class SkillRecord:
    path: str
    classification: str
    active: bool


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_path(path: Path | str, catalog: dict | None = None) -> str | None:
    catalog = load_catalog() if catalog is None else catalog
    rel = Path(path).as_posix()
    if rel.startswith(str(ROOT).replace("\\", "/")):
        rel = Path(rel).relative_to(ROOT).as_posix()
    for rule in catalog["ordered_rules"]:
        if fnmatch.fnmatchcase(rel, rule["glob"]):
            return rule["classification"]
    return None


def discover_skill_files(root: Path = SKILLS_ROOT) -> list[Path]:
    return sorted(root.rglob("SKILL.md"))


def inventory(root: Path = SKILLS_ROOT, catalog: dict | None = None) -> list[SkillRecord]:
    catalog = load_catalog() if catalog is None else catalog
    active = set(catalog["active_classifications"])
    records: list[SkillRecord] = []
    for path in discover_skill_files(root):
        classification = classify_path(path.relative_to(ROOT), catalog)
        if classification is None:
            raise ValueError(f"unclassified Skill: {path.relative_to(ROOT).as_posix()}")
        records.append(
            SkillRecord(
                path=path.relative_to(ROOT).as_posix(),
                classification=classification,
                active=classification in active,
            )
        )
    return records


def active_canonical(records: Iterable[SkillRecord] | None = None) -> list[SkillRecord]:
    rows = inventory() if records is None else list(records)
    return [row for row in rows if row.active and row.classification == "canonical"]


def main() -> int:
    rows = inventory()
    payload = {
        "inventory_count": len(rows),
        "active_canonical_count": len(active_canonical(rows)),
        "skills": [row.__dict__ for row in rows],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
