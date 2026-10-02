from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD_MATRIX = ROOT / "docs/superpowers/verification/combined_authority_guard_matrix_v1.json"

EXPECTED_GUARDS = {
    "R1": {
        "tests/knowledge/test_knowledge_authority_contract.py",
        "tests/knowledge/test_ae_engine_current_spec_contract.py",
        "tests/knowledge/test_current_history_authority_contract.py",
    },
    "R2": {
        "tests/test_issue175_dm7_navigation_authority_contract.py",
    },
    "R3": {
        "tests/knowledge/test_skill_catalog_classification_contract.py",
        "tests/knowledge/test_active_skill_runtime_contract.py",
    },
    "R4": {
        "tests/knowledge/test_skill_registry_domain_reference_contract.py",
        "tests/test_phase6_skill_preflight_gate.py",
    },
    "R5": {
        "tests/knowledge/test_current_history_authority_contract.py",
    },
}


def _load_matrix() -> dict:
    assert GUARD_MATRIX.is_file(), "Combined guard matrix must live in verification provenance, not Authority Map"
    return json.loads(GUARD_MATRIX.read_text(encoding="utf-8"))


def test_r1_to_r5_combined_guard_matrix_is_machine_readable_and_complete() -> None:
    matrix = _load_matrix()
    assert matrix["schema"] == "WHD_COMBINED_GUARD_MATRIX_V1"
    assert matrix["role"] == "VALIDATION_ONLY"
    assert matrix["authority"] == "none"

    rows: dict[str, set[str]] = defaultdict(set)
    for row in matrix["rows"]:
        rows[row["requirement"]].add(row["guard"])

    assert set(rows) == set(EXPECTED_GUARDS), rows
    for requirement, expected in EXPECTED_GUARDS.items():
        assert rows[requirement] == expected, (
            f"{requirement} guard matrix drift: expected {sorted(expected)}, got {sorted(rows[requirement])}"
        )


def test_every_combined_guard_path_exists_in_the_tree() -> None:
    for paths in EXPECTED_GUARDS.values():
        for relative in paths:
            path = ROOT / relative
            assert path.is_file(), f"Combined Acceptance guard missing: {relative}"


def test_combined_matrix_keeps_validation_as_guard_not_domain_authority() -> None:
    matrix = _load_matrix()
    note = matrix["note"]
    assert "validation-only" in note
    assert "不得成為 production manufacturing authority" in note
