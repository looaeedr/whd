from __future__ import annotations

from pathlib import Path

from tools.knowledge_governance import parse_doc_metadata


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP_REL = "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


ROLE_MARKERS = {
    "README.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=repo-overview -->",
    "AI_HANDOFF.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=handoff-ledger -->",
    "AGENTS.md": "<!-- WHD_DOC_ROLE role=CURRENT contract=agent-startup-process -->",
    "handoff/00_AI_HANDOFF_README.md": "<!-- WHD_DOC_ROLE role=MIRROR contract=agent-startup-process POINTER_ONLY -->",
    "handoff/01_ARCHITECTURE.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=architecture-snapshot -->",
    "handoff/05_NEXT_STEPS.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=roadmap-snapshot -->",
    "目前主要任務.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=task-roadmap-snapshot -->",
    "docs/superpowers/CURRENT_API_INVENTORY_20260818.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=api-inventory-snapshot snapshot=2026-08-18 -->",
    "docs/superpowers/README.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=superpowers-history-index -->",
    "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=global-ai-collaboration-reference -->",
    "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=pitfall-ledger -->",
}


def test_t7_documents_have_machine_readable_roles() -> None:
    # The current owner is WHD_DOC_META_V1 YAML; legacy HTML markers are optional.
    # Keep the older expected-role list as an independent regression oracle.
    for path, marker in ROLE_MARKERS.items():
        metadata = parse_doc_metadata(read(path), path=path)
        assert f"role={metadata.role} contract={metadata.contract}" in marker, path



def test_current_entrypoints_point_to_current_authorities() -> None:
    # Navigation mirrors name domain owners; AGENTS.md itself owns the workflow
    # contract and is not required to self-reference the entire authority map.
    for rel in ("README.md", "AI_HANDOFF.md", "handoff/00_AI_HANDOFF_README.md"):
        text = read(rel)[:5000]
        assert AUTHORITY_MAP_REL in text, rel
        assert "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md" in text, rel

    entry = read("AGENTS.md")[:5000]
    assert "cleanup/2d-3d-sync" in entry
    assert "NON_PRODUCT_GOVERNANCE_DIRECT_X" in entry
    assert "main" in entry


def test_stale_roadmaps_and_dated_api_inventory_are_explicitly_historical() -> None:
    for rel in (
        "handoff/01_ARCHITECTURE.md",
        "handoff/05_NEXT_STEPS.md",
        "目前主要任務.md",
        "docs/superpowers/CURRENT_API_INVENTORY_20260818.md",
    ):
        prefix = read(rel)[:1200]
        assert "role=HISTORICAL" in prefix, rel
        assert "不參與 current routing" in prefix, rel

    dated = read("docs/superpowers/CURRENT_API_INVENTORY_20260818.md")[:1200]
    assert "2026-08-18" in dated
    assert "HISTORICAL SNAPSHOT" in dated


def test_ai_handoff_does_not_keep_2026_09_02_as_current_authority() -> None:
    text = read("AI_HANDOFF.md")
    assert "## [CURRENT] 2026-09-02 Runtime semantic guard" not in text
    assert "## [HISTORICAL/SUPERSEDED] 2026-09-02 Runtime semantic guard" in text


def test_global_pitfall_file_is_reference_index_not_parallel_domain_ssot() -> None:
    text = read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    prefix = text[:2200]
    assert "role=REFERENCE" in prefix
    assert "不是 CURRENT domain authority" in prefix
    assert AUTHORITY_MAP_REL in prefix

    collision = text.index("### 50. 先用截角公式猜 Assembly Relief")
    collision_window = text[max(0, collision - 400):collision + 650]
    assert "SUPERSEDED_BY_CERTIFIED_RELIEF_REGISTRY" in collision_window

    divider = text.index("## 2026-09-07 — Receiving Divider / 多件式箱身 / Dynamic 2D 單源規則")
    divider_window = text[max(0, divider - 250):divider + 1100]
    assert "HISTORICAL/SUPERSEDED" in divider_window
    assert "CURRENT Requirement Authority" not in divider_window


def test_global_ai_collaboration_rules_do_not_make_giant_06_the_domain_owner() -> None:
    text = read("個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md")
    assert "06_踩坑記錄與防錯經驗庫.md` 是 REFERENCE / incident ledger" in text
    assert "09_WHD_Canonical_Authority_Map.md" in text
    assert "04_WHD鈑金展開幾何引擎規範.md" in text


def test_authority_map_records_permanent_current_history_roles() -> None:
    text = read(AUTHORITY_MAP_REL)
    required_rows = (
        "WHD_AUTHORITY contract=agent-startup-process role=CURRENT path=AGENTS.md",
        "WHD_AUTHORITY contract=manufacturing-architecture role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md",
        "WHD_AUTHORITY contract=manufacturing-architecture role=HISTORICAL path=handoff/01_ARCHITECTURE.md",
        f"WHD_AUTHORITY contract=pitfall-ledger role=CURRENT path={AUTHORITY_MAP_REL}",
        "WHD_AUTHORITY contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
    )
    for row in required_rows:
        assert row in text
    assert "contract=api-inventory role=HISTORICAL" not in text


def test_historical_evidence_is_preserved_instead_of_deleted() -> None:
    assert "下一個真正階段：第二箱型" in read("handoff/05_NEXT_STEPS.md")
    assert "第一階段：先新增一個穩定 API" in read("目前主要任務.md")
    assert "generate_part()" in read("docs/superpowers/CURRENT_API_INVENTORY_20260818.md")

def test_retired_execution_references_are_not_current_map_owners() -> None:
    authority = read(AUTHORITY_MAP_REL)
    historical = read("docs/governance/WHD_20261010_retired_process_provenance.md")
    for former_owner in (
        "tools/interactive_runtime_liveness.py",
        "tools/scheduler_runtime_liveness.py",
        "tools/execution_record.py",
        "tools/execution_work_slot_view.py",
    ):
        assert former_owner not in authority
        assert former_owner in historical

    for active_owner in (
        "tools/local_durability_gate.py",
        "tools/workstation_poweroff_gate.py",
        "tools/whd_poweroff_ha_bridge.py",
    ):
        assert active_owner in authority
    assert "退役 scheduled-resume / execution control plane" in authority


def test_current_skill_authority_rows_match_frontmatter() -> None:
    """Map must not advertise a different contract from a CURRENT skill."""
    for line in read(AUTHORITY_MAP_REL).splitlines():
        if not line.startswith("<!-- WHD_AUTHORITY "):
            continue
        fields = dict(
            item.split("=", 1)
            for item in line.removeprefix("<!-- WHD_AUTHORITY ").removesuffix(" -->").split()
            if "=" in item
        )
        if fields.get("role") != "CURRENT":
            continue
        path = fields.get("path", "")
        if not path.startswith(".agents/skills/"):
            continue
        metadata = parse_doc_metadata(read(path), path=path)
        assert metadata.role == "CURRENT", path
        assert metadata.contract == fields["contract"], path


def test_dm7_current_skill_does_not_restore_retired_preflight_gate() -> None:
    path = ".agents/skills/engineering/截角資料入口收斂/SKILL.md"
    skill = read(path)
    metadata = parse_doc_metadata(skill, path=path)
    assert metadata.role == "CURRENT"
    assert metadata.contract == "dm7-part-navigation"
    assert "## 現行施工入口與來源查核" in skill
    assert "由 GitHub／排程／雲端執行器施工" in skill
    assert "只有使用者當次明確 `/接手`" in skill
    assert "不得要求已退役的 preflight 重跑" in skill
    assert "先跑 `tools/phase6_skill_preflight.py" not in skill
    assert "並留下 `READ_REFERENCE:` evidence" not in skill
    assert "再以全部 changed files 重跑 preflight" not in skill
    assert "## DM7 canonical navigation authority" in skill
    assert "STALE_PHYSICAL_CHILD" in skill


def test_legacy_knowledge_preflight_has_no_current_authority_row() -> None:
    """The retired receipt transaction cannot be reintroduced as CURRENT."""
    authority = read(AUTHORITY_MAP_REL)
    assert "WHD_AUTHORITY contract=knowledge-preflight role=CURRENT" not in authority
    assert "退役入口註記（HISTORICAL）" in authority
    agents = read("AGENTS.md")
    assert "舊工單交易、工作槽與 lease 控制系統已退役" in agents
    assert "Preflight receipt" in agents


def test_registered_mirrors_match_canonical_metadata() -> None:
    """Registered pointer-only mirrors must not invent another contract."""
    import re

    paths = []
    for line in read(AUTHORITY_MAP_REL).splitlines():
        if "WHD_AUTHORITY " not in line or "role=MIRROR" not in line:
            continue
        match = re.search(r"\bpath=([^\s]+)", line)
        assert match is not None
        paths.append(match.group(1))
    paths.append("docs/governance/WHD_規格書Skill前置與Grounding規則.md")
    for path in sorted(set(paths)):
        metadata = parse_doc_metadata(read(path), path=path)
        assert metadata.role == "MIRROR", path
        assert metadata.canonical, path
        target = metadata.canonical
        target_meta = parse_doc_metadata(read(target), path=target)
        assert target_meta.role == "CURRENT", (path, target)
        assert metadata.contract == target_meta.contract, (path, target)


def test_governance_and_spec_authorities_are_registered() -> None:
    """Stable active policies and compatibility mirror must remain discoverable."""
    text = read(AUTHORITY_MAP_REL)
    rows = (
        ("grounded-spec-authoring", "CURRENT", ".agents/skills/engineering/寫成規格書/SKILL.md"),
        ("grounded-spec-authoring", "MIRROR", "docs/governance/WHD_規格書Skill前置與Grounding規則.md"),
        ("direct-governance-publish", "CURRENT", "docs/governance/WHD_DIRECT_GOVERNANCE_PUBLISH_POLICY.md"),
    )
    for contract, role, path in rows:
        exact = f"WHD_AUTHORITY contract={contract} role={role} path={path}"
        assert text.count(exact) == 1, exact
        meta = parse_doc_metadata(read(path), path=path)
        assert meta.contract == contract, path
        assert meta.role == role, path
