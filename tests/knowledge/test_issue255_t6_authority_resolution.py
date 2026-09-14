from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESOLVER = ROOT / "tools/knowledge_authority_resolution.py"
T1_MATRIX = ROOT / "docs/superpowers/verification/knowledge_authority_classification_v1.json"
REGISTRY = ROOT / ".agents/skills/skill_registry.json"
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"


def _load_resolver():
    assert RESOLVER.is_file(), "#255 requires tools/knowledge_authority_resolution.py"
    spec = importlib.util.spec_from_file_location("knowledge_authority_resolution_issue255", RESOLVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _matrix_row(path: str) -> dict:
    matrix = json.loads(T1_MATRIX.read_text(encoding="utf-8"))
    return next(row for row in matrix["rows"] if row["path"] == path)


def test_registry_backed_current_skill_contract_is_resolved_from_explicit_route() -> None:
    resolver = _load_resolver()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    row = _matrix_row(".agents/skills/engineering/Python測試實務/SKILL.md")

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


def test_unique_t1_machine_route_can_resolve_current_contract_without_guessing() -> None:
    resolver = _load_resolver()
    row = {
        "path": ".agents/skills/engineering/Demo/SKILL.md",
        "target_role": "CURRENT",
        "contract": None,
        "blocker": "MISSING_STABLE_CONTRACT",
        "machine_routing": ["demo-contract"],
    }
    resolution = resolver.resolve_unique_machine_route_current(row)
    assert resolution["contract"] == "demo-contract"
    assert resolution["evidence"] == {
        "type": "t1_unique_machine_routing",
        "source": "docs/superpowers/verification/knowledge_authority_classification_v1.json",
        "route_id": "demo-contract",
    }


def test_unique_t1_machine_route_fails_closed_on_ambiguity() -> None:
    resolver = _load_resolver()
    row = {
        "path": ".agents/skills/engineering/Demo/SKILL.md",
        "target_role": "CURRENT",
        "contract": None,
        "blocker": "MISSING_STABLE_CONTRACT",
        "machine_routing": ["one", "two"],
    }
    with pytest.raises(resolver.AuthorityResolutionError, match="unique|ambiguous"):
        resolver.resolve_unique_machine_route_current(row)


def test_t5_authority_map_rows_support_multiple_contracts_per_path() -> None:
    resolver = _load_resolver()
    rows = resolver.parse_authority_map(AUTHORITY_MAP)
    monitoring = rows[".agents/skills/engineering/monitoring-remote-qa/SKILL.md"]
    assert len(monitoring) == 1
    assert monitoring[0]["role"] == "CURRENT"
    assert monitoring[0]["contract"] == "remote-qa-monitoring"
    assert monitoring[0]["evidence"]["type"] == "canonical_authority_map"
    assert {row["contract"] for row in rows["AGENTS.md"]} == {
        "agent-startup-process",
        "knowledge-preflight",
    }


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


def test_repo_resolution_census_splits_role_debt_from_contract_debt() -> None:
    resolver = _load_resolver()
    census = resolver.build_resolution_census(ROOT, T1_MATRIX, REGISTRY, AUTHORITY_MAP)
    assert census["governed_count"] >= 396
    assert census["matrix_count"] == 396
    assert census["authority_map_resolved_count"] > 0
    assert census["registry_resolved_current_count"] > 0
    assert census["unresolved_role_count"] > 0
    assert census["missing_contract_by_role"]["HISTORICAL"] > 0
    assert census["missing_contract_by_role"]["REFERENCE"] > 0
    assert census["missing_from_t1_count"] >= 2
    assert census["frozen_t1_modified"] is False
