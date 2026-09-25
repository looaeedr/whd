from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md"
PUBLIC_API = ROOT / "ae_engine/__init__.py"
CURRENT_MARKER = "## [CURRENT] ae_engine Manufacturing / Certified Registry Contract"
HISTORICAL_MARKER = "## [HISTORICAL/SUPERSEDED] Legacy ae_engine notes"


def _spec_sections() -> tuple[str, str]:
    text = SPEC.read_text(encoding="utf-8")
    assert CURRENT_MARKER in text, "04 must begin with an explicit current manufacturing contract"
    assert HISTORICAL_MARKER in text, "legacy 04 prose must be explicitly historical/superseded"
    current_start = text.index(CURRENT_MARKER)
    history_start = text.index(HISTORICAL_MARKER)
    assert current_start < history_start
    return text[current_start:history_start], text[history_start:]


def test_current_section_is_explicit_current_authority_and_repo_relative() -> None:
    current, _ = _spec_sections()
    assert "WHD_AUTHORITY_ROLE: CURRENT" in current
    assert "`ae_engine/`" in current
    assert "Z:" not in current


def test_current_section_tracks_exported_registry_public_api() -> None:
    current, _ = _spec_sections()
    public_api = PUBLIC_API.read_text(encoding="utf-8")
    required_exports = (
        "CertifiedReliefStatus",
        "CertifiedReliefRule",
        "CertifiedReliefResult",
        "CertifiedCornerPolicyRule",
        "CertifiedReliefRegistryError",
        "CertifiedReliefRegistryAmbiguityError",
        "registered_certified_relief_rules",
        "registered_certified_corner_policy_rules",
        "lookup_certified_endcap_relief",
        "lookup_certified_corner_state",
        "certified_corner_policy_for_part",
        "certified_rule_revision_exists",
        "build_relief_promotion_candidate",
    )
    for name in required_exports:
        assert name in public_api, f"public API no longer exports {name}"
        assert name in current, f"04 current contract does not document exported API {name}"


def test_current_registry_hit_miss_and_ambiguity_contract_is_explicit() -> None:
    current, _ = _spec_sections()
    required_phrases = (
        "Registry HIT",
        "canonical manufacturing answer",
        "3D shadow validation",
        "不得覆蓋",
        "Registry MISS",
        "discovery",
        "REGISTRY_AMBIGUOUS",
        "fail closed",
        "PROVISIONAL_3D",
        "CERTIFIED_FROM_3D",
    )
    for phrase in required_phrases:
        assert phrase in current, f"missing current Registry contract phrase: {phrase}"


def test_current_contract_states_family_topology_and_canonical_parameter_ownership() -> None:
    current, _ = _spec_sections()
    for phrase in (
        "Cabinet Family",
        "Topology",
        "canonical parameters",
        "rule_id",
        "revision",
        "trust_level",
        "standard_ref",
        "dimension_space",
    ):
        assert phrase in current, f"missing current manufacturing ownership concept: {phrase}"


def test_validation_is_strictly_one_way() -> None:
    current, _ = _spec_sections()
    for phrase in (
        "Validation is one-way",
        "expected value",
        "fixture",
        "probe",
        "tolerance",
        "不得回灌 production",
    ):
        assert phrase in current, f"missing validation boundary phrase: {phrase}"


def test_stale_local_paths_and_collision_first_legacy_are_history_only() -> None:
    current, historical = _spec_sections()
    assert "Z:" not in current
    assert "Z:\\Ollama-整合whd" in historical
    assert "先形成名義板件與折後實體，再由實際干涉反推 2D CUTTING" in historical
    assert "Registry HIT" in current
