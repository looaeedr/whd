from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
AUTHORITY_MAP_REL = "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"

ROW_RE = re.compile(
    r"<!-- WHD_AUTHORITY contract=(?P<contract>[^ ]+) "
    r"role=(?P<role>CURRENT|REFERENCE|MIRROR|HISTORICAL) "
    r"path=(?P<path>[^ ]+)"
    r"(?: canonical=(?P<canonical>[^ ]+))? -->"
)

EXPECTED_PROCESS_CURRENT = {
    "continuous-execution-machine": "tools/continuity_controller.py",
    "continuous-execution-operations": ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
    "remote-qa-monitoring": ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
    "issue-closure": ".agents/skills/engineering/issue-closure-gate/SKILL.md",
    "skill-routing": ".agents/skills/skill_registry.json",
    "skill-classification": ".agents/skills/skill_catalog.json",
    "knowledge-preflight": "AGENTS.md",
    # Pitfall documents are accepted as REFERENCE only.  The permanent map owns
    # the routing contract that says where those references sit in authority.
    "pitfall-ledger": AUTHORITY_MAP_REL,
}


def _text() -> str:
    return AUTHORITY_MAP.read_text(encoding="utf-8")


def _rows(text: str) -> list[dict[str, str | None]]:
    return [match.groupdict() for match in ROW_RE.finditer(text)]


def test_authority_map_has_current_structured_metadata_and_no_legacy_row_format() -> None:
    text = _text()
    assert text.startswith("---\n")
    for marker in (
        "whd_doc_role: CURRENT",
        "whd_contract: pitfall-ledger",
        "whd_canonical: null",
        "whd_schema: WHD_DOC_META_V1",
        "WHD_AUTHORITY_MAP_V1",
    ):
        assert marker in text
    assert "WHD_AUTHORITY_ROW" not in text


def test_authority_map_contains_only_permanent_normative_body() -> None:
    text = _text()
    for forbidden in (
        "T7 Current / History entrypoint roles",
        "T1 scope boundary",
        "T8 Combined Acceptance guard matrix",
        "WHD_COMBINED_GUARD_MATRIX_V1",
        "WHD_COMBINED_GUARD requirement=",
        "本輪",
        "#180",
    ):
        assert forbidden not in text


def test_process_contracts_resolve_to_approved_unique_current_owners() -> None:
    rows = _rows(_text())
    assert rows
    currents: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["role"] == "CURRENT":
            currents[str(row["contract"])].append(str(row["path"]))
    for contract, owner in EXPECTED_PROCESS_CURRENT.items():
        assert currents[contract] == [owner], (contract, currents[contract])


def test_every_mapped_contract_has_exactly_one_current_and_mirrors_are_pointer_only() -> None:
    rows = _rows(_text())
    contracts = {str(row["contract"]) for row in rows}
    current_counts = Counter(str(row["contract"]) for row in rows if row["role"] == "CURRENT")
    assert contracts
    assert all(current_counts[contract] == 1 for contract in contracts), current_counts
    for row in rows:
        if row["role"] == "MIRROR":
            assert row["canonical"], row


def test_reference_and_historical_rows_are_attached_to_a_current_contract() -> None:
    rows = _rows(_text())
    currents = {str(row["contract"]) for row in rows if row["role"] == "CURRENT"}
    for row in rows:
        if row["role"] in {"REFERENCE", "HISTORICAL", "MIRROR"}:
            assert str(row["contract"]) in currents, row


def test_readme_and_pitfall_artifacts_are_not_parallel_current_owners() -> None:
    for row in _rows(_text()):
        if row["role"] != "CURRENT":
            continue
        path = str(row["path"])
        assert not path.endswith("README.md"), row
        assert "/踩坑庫/" not in path, row
        assert "pitfall" not in path.lower(), row
    pitfall_refs = [
        row for row in _rows(_text())
        if row["contract"] == "pitfall-ledger" and row["role"] == "REFERENCE"
    ]
    assert pitfall_refs, "pitfall-ledger must keep reference evidence without promoting it to CURRENT"


def test_historical_acceptance_provenance_remains_outside_normative_map_body() -> None:
    assert (ROOT / "docs/superpowers/verification/knowledge_authority_classification_v1.json").is_file()
    assert (ROOT / "docs/superpowers/checkpoints/issue230-t4-preflight-evidence.txt").is_file()
