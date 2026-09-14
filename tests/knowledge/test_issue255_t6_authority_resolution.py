from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESOLVER = ROOT / "tools/knowledge_authority_resolution.py"
T1_MATRIX = ROOT / "docs/superpowers/verification/knowledge_authority_classification_v1.json"
REGISTRY = ROOT / ".agents/skills/skill_registry.json"


def _load_resolver():
    assert RESOLVER.is_file(), "#255 requires tools/knowledge_authority_resolution.py"
    spec = importlib.util.spec_from_file_location("knowledge_authority_resolution_issue255", RESOLVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_backed_current_skill_contract_is_resolved_from_explicit_route() -> None:
    resolver = _load_resolver()
    matrix = json.loads(T1_MATRIX.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    row = next(
        row for row in matrix["rows"]
        if row["path"] == ".agents/skills/engineering/Python測試實務/SKILL.md"
    )

    resolution = resolver.resolve_registry_current_skill(row, registry)
    assert resolution["target_role"] == "CURRENT"
    assert resolution["contract"] == "python-testing-practices"
    assert resolution["blocker"] is None
    assert resolution["evidence"]["type"] == "skill_registry_route"
    assert resolution["evidence"]["route_id"] == "python-testing-practices"


def test_registry_resolution_fails_closed_when_route_is_not_unique() -> None:
    resolver = _load_resolver()
    row = {
        "path": ".agents/skills/engineering/Demo/SKILL.md",
        "target_role": "CURRENT",
        "contract": None,
        "blocker": "MISSING_STABLE_CONTRACT",
    }
    registry = {
        "routes": [
            {
                "id": "one",
                "file_globs": [".agents/skills/engineering/Demo/**"],
                "required_skills": ["Demo"],
            },
            {
                "id": "two",
                "file_globs": [".agents/skills/engineering/Demo/**"],
                "required_skills": ["Demo"],
            },
        ]
    }

    with pytest.raises(resolver.AuthorityResolutionError, match="unique|ambiguous"):
        resolver.resolve_registry_current_skill(row, registry)


def test_effective_authority_never_mutates_frozen_t1_rows_in_place(tmp_path: Path) -> None:
    resolver = _load_resolver()
    t1 = {
        "schema": "WHD_KNOWLEDGE_CLASSIFICATION_V1",
        "rows": [
            {
                "path": "doc.md",
                "target_role": "UNRESOLVED",
                "contract": None,
                "blocker": "ROLE_REQUIRES_AUTHORITY_REVIEW",
            }
        ],
    }
    original = json.dumps(t1, sort_keys=True)
    overlay = {
        "schema": "WHD_KNOWLEDGE_T6_OVERLAY_V1",
        "rows": [
            {
                "path": "doc.md",
                "target_role": "HISTORICAL",
                "contract": "demo-history",
                "canonical_owner": None,
                "blocker": None,
                "evidence": {"type": "reviewed_authority", "source": "issue255"},
            }
        ],
    }

    effective = resolver.merge_effective_authority(t1, overlay)
    assert json.dumps(t1, sort_keys=True) == original
    assert effective["rows"][0]["target_role"] == "HISTORICAL"
    assert effective["rows"][0]["contract"] == "demo-history"


def test_repo_resolution_census_is_explicit_about_remaining_authority_debt() -> None:
    resolver = _load_resolver()
    census = resolver.build_resolution_census(ROOT, T1_MATRIX, REGISTRY)
    assert census["governed_count"] >= 396
    assert census["matrix_count"] == 396
    assert census["registry_resolved_current_count"] > 0
    assert census["remaining_unresolved_count"] >= 0
    assert census["missing_from_t1_count"] >= 2
    assert census["frozen_t1_modified"] is False
