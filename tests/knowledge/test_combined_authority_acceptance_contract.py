from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"

GUARD_RE = re.compile(
    r"<!-- WHD_COMBINED_GUARD requirement=(?P<requirement>R[1-5]) guard=(?P<guard>[^ ]+) -->"
)

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


def _read(path: Path) -> str:
    assert path.is_file(), f"required durable artifact is missing: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def test_r1_to_r5_combined_guard_matrix_is_machine_readable_and_complete() -> None:
    text = _read(AUTHORITY_MAP)
    assert "WHD_COMBINED_GUARD_MATRIX_V1" in text

    rows: dict[str, set[str]] = defaultdict(set)
    for match in GUARD_RE.finditer(text):
        rows[match.group("requirement")].add(match.group("guard"))

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
    text = _read(AUTHORITY_MAP)
    section = text.split("WHD_COMBINED_GUARD_MATRIX_V1", 1)[-1]
    assert "validation-only" in section
    assert "不得成為 production manufacturing authority" in section
