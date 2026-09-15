from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
SKILL_POLICY = ROOT / "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md"
DIMENSION_ROOT = ROOT / "07_Phase6尺寸語意與標準截角母規則.md"
DIMENSION_CANONICAL = ROOT / "個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md"
LAYER_CANONICAL = ROOT / "加工層分類與定義.md"
MISNAMED_LAYER_ALIAS = ROOT / "標準基準檔格式.md"

AUTHORITY_RE = re.compile(
    r"<!-- WHD_AUTHORITY contract=(?P<contract>[^ ]+) role=(?P<role>CURRENT|REFERENCE|MIRROR|HISTORICAL) path=(?P<path>[^ ]+)(?: canonical=(?P<canonical>[^ ]+))? -->"
)


def _read(path: Path) -> str:
    assert path.is_file(), f"required authority artifact is missing: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def _assert_pointer_only(path: Path, canonical_path: str) -> None:
    text = _read(path)
    assert "WHD_AUTHORITY_ROLE: MIRROR" in text, f"{path.name} must declare MIRROR role"
    assert "WHD_MIRROR_MODE: POINTER_ONLY" in text, f"{path.name} must be pointer-only"
    assert canonical_path in text, f"{path.name} must point to {canonical_path}"
    assert len(text) < 2000, f"{path.name} is too large for a pointer-only mirror"


def test_authority_map_has_exactly_one_current_owner_per_contract() -> None:
    text = _read(AUTHORITY_MAP)
    assert "WHD_AUTHORITY_MAP_V1" in text
    rows = [match.groupdict() for match in AUTHORITY_RE.finditer(text)]
    assert rows, "authority map must contain machine-readable WHD_AUTHORITY rows"

    contracts = {row["contract"] for row in rows}
    for required in {"phase6-dimension-semantics", "manufacturing-layer-classification"}:
        assert required in contracts, f"missing authority contract: {required}"

    current_counts = Counter(row["contract"] for row in rows if row["role"] == "CURRENT")
    assert all(current_counts[contract] == 1 for contract in contracts), current_counts

    for row in rows:
        if row["role"] == "MIRROR":
            assert row["canonical"], f"MIRROR row must name canonical owner: {row}"


def test_dimension_semantics_root_is_pointer_to_ai_library_canonical() -> None:
    canonical = "個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md"
    assert DIMENSION_CANONICAL.is_file()
    _assert_pointer_only(DIMENSION_ROOT, canonical)
    root_text = _read(DIMENSION_ROOT)
    assert "## [CURRENT]" not in root_text
    assert "最高優先級機械語意規格" not in root_text


def test_misnamed_standard_baseline_format_is_pointer_to_layer_definition() -> None:
    assert LAYER_CANONICAL.is_file()
    _assert_pointer_only(MISNAMED_LAYER_ALIAS, "加工層分類與定義.md")
    assert _read(MISNAMED_LAYER_ALIAS) != _read(LAYER_CANONICAL)


def test_skill_policy_defines_authority_roles_and_forbids_dual_current() -> None:
    text = _read(SKILL_POLICY)
    for role in ("CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"):
        assert f"`{role}`" in text, f"missing authority role: {role}"
    assert "同一 contract" in text
    assert "只能有一個" in text
    assert "POINTER_ONLY" in text
