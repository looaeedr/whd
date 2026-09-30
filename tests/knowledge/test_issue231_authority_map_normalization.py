from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"

ROW_RE = re.compile(
    r"<!-- WHD_AUTHORITY contract=(?P<contract>[^ ]+) "
    r"role=(?P<role>CURRENT|REFERENCE|MIRROR|HISTORICAL) "
    r"path=(?P<path>[^ ]+)"
    r"(?: canonical=(?P<canonical>[^ ]+))? -->"
)

REQUIRED_CURRENT = {
    "flow-v2-execution": ".agents/skills/engineering/flow-v2-execution/SKILL.md",
    "root-local-first-workflow": ".agents/skills/engineering/root-local-first/SKILL.md",
    "skill-routing": ".agents/skills/skill_registry.json",
    "skill-classification": ".agents/skills/skill_catalog.json",
    "pitfall-ledger": "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md",
}


def _text() -> str:
    return AUTHORITY_MAP.read_text(encoding="utf-8")


def _rows() -> list[dict[str, str | None]]:
    return [match.groupdict() for match in ROW_RE.finditer(_text())]


def test_authority_map_has_current_structured_metadata_and_no_legacy_row_format() -> None:
    text = _text()
    assert text.startswith("---\n")
    assert "whd_doc_role: CURRENT" in text
    assert "whd_contract: canonical-authority-map" in text
    assert "WHD_AUTHORITY_MAP_V1" in text
    assert "WHD_AUTHORITY_ROW" not in text


def test_core_current_contracts_resolve_to_flow_v2_era_owners() -> None:
    rows = _rows()
    currents = {row["contract"]: row["path"] for row in rows if row["role"] == "CURRENT"}
    for contract, owner in REQUIRED_CURRENT.items():
        assert currents.get(contract) == owner


def test_current_owner_is_unique_and_mirror_canonical_points_to_a_current_path() -> None:
    rows = _rows()
    counts = Counter(row["contract"] for row in rows if row["role"] == "CURRENT")
    assert all(count == 1 for count in counts.values()), counts
    current_paths = {row["path"] for row in rows if row["role"] == "CURRENT"}
    for row in rows:
        if row["role"] == "MIRROR":
            assert row["canonical"], row
            assert row["canonical"] in current_paths, row


def test_legacy_continuity_and_entrypoint_bridges_are_not_current_owners() -> None:
    rows = _rows()
    forbidden_current = {
        "tools/continuity_controller.py",
        ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
        ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
        ".agents/skills/engineering/issue-closure-gate/SKILL.md",
    }
    assert not any(row["role"] == "CURRENT" and row["path"] in forbidden_current for row in rows)
    assert any(
        row["role"] == "HISTORICAL" and row["path"] == "tools/continuity_controller.py"
        for row in rows
    )


def test_pitfall_references_are_not_parallel_current_owners() -> None:
    for row in _rows():
        if row["role"] == "CURRENT":
            assert "/踩坑庫/" not in str(row["path"])
            assert "pitfall" not in str(row["path"]).lower()
