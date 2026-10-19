from __future__ import annotations

import json
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
    "handoff/01_ARCHITECTURE.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=manufacturing-architecture -->",
    "handoff/05_NEXT_STEPS.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=roadmap-snapshot -->",
    "目前主要任務.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=task-roadmap-snapshot -->",
    "docs/superpowers/CURRENT_API_INVENTORY_20260818.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=api-inventory-snapshot snapshot=2026-08-18 -->",
    "docs/superpowers/README.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=superpowers-history-index -->",
    "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=global-ai-collaboration-reference -->",
    "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=pitfall-ledger -->",
}


def test_t7_documents_have_machine_readable_roles() -> None:
    # The current owner is WHD_DOC_META_V1 YAML; legacy HTML markers are optional.
    # Preserve role expectations, but follow the canonical YAML contract for the
    # historical architecture snapshot rather than its old HTML label.
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
        if path.endswith(".json"):
            # The registry/catalog are machine-readable CURRENT owners, but
            # JSON must not be parsed as Markdown YAML frontmatter.
            expected_lists = {
                ".agents/skills/skill_registry.json": "routes",
                ".agents/skills/skill_catalog.json": "ordered_rules",
            }
            assert path in expected_lists, path
            payload = json.loads(read(path))
            assert payload["schema_version"] == 1, path
            rows = payload[expected_lists[path]]
            assert isinstance(rows, list) and rows, path
            continue
        assert path.endswith("/SKILL.md"), path
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
    assert "**不得**要求已退役的 preflight 重跑" in skill
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


def test_github_only_publish_is_explicit_scoped_exception_not_default() -> None:
    agents = read("AGENTS.md")
    skill = read(".agents/skills/engineering/推推/SKILL.md")
    policy = read("docs/governance/WHD_DIRECT_GOVERNANCE_PUBLISH_POLICY.md")
    for name, text in (("AGENTS", agents), ("publish skill", skill), ("governance policy", policy)):
        assert "GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1" in text, name
        assert "LOCAL_SYNC_PENDING" in text, name
        assert "GitHub-only" in text, name
        assert "本機" in text, name
    assert "必要 CI" in agents
    assert "owner" in skill
    assert "不豁免產品測試" in policy
    assert "當次明確" in agents and "當次明確" in skill and "當次明確" in policy
    assert "不 reset" in agents
    assert "非強制 fast-forward" in skill and "非強制 fast-forward" in policy
    assert "PUBLISHED_AND_SYNCED" in agents and "PUBLISHED_AND_SYNCED" in skill


def test_beta_skill_navigation_does_not_resurrect_retired_preflight() -> None:
    text = read(".agents/skills/in-progress/README.md")
    assert "upstream-beta" in text
    assert "skill_catalog.json" in text
    assert "Phase6 Preflight receipt" in text
    assert "not** a promotion prerequisite" in text
    assert "Skill governance, Preflight and regression checks" not in text
    assert "no local-machine permission" in text


def test_remote_qa_route_is_github_localx_first_and_does_not_grant_dc() -> None:
    qa = read(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
    dispatch = read(".agents/skills/engineering/派工/SKILL.md")
    assert "GITHUB_LOCALX_FIRST" in qa and "GITHUB_LOCALX_FIRST" in dispatch
    assert "expected_head_sha" in qa
    assert "不呼叫 DC" in dispatch
    assert "WINDOWS_LOCALX_SYNC_PENDING" in qa
    assert "不要求每張 PR 重複授權" in qa

def test_ci_qa_reference_does_not_resurrect_legacy_merge_or_fresh_branch_rule() -> None:
    contract = read(".agents/skills/engineering/monitoring-remote-qa/CI_SHARDING_ACCEPTANCE_CONTRACT.md")
    nav = read(".agents/skills/engineering/README.md")
    assert "whd_doc_role: REFERENCE" in contract[:250]
    assert "Historical #303/T8 routing only" in contract
    assert "Every modification starts on a fresh branch" in contract
    assert "explicit `合`" in contract
    assert "Neither sentence is a current WHD" in contract
    assert "Product PRs target `localX`" in contract
    assert "requires a fresh `/推推`" in contract
    assert "specific user approval for that Issue/PR" not in contract
    assert "FULL_COLLECTION == UNIQUE_SHARD_UNION" in contract
    assert "FLAKY-WARNING" in contract
    assert "GITHUB_LOCALX_FIRST" in nav
    assert "WINDOWS_LOCALX_SYNC_PENDING" in nav
    assert "不能先探測 DC" in nav

def test_dispatch_default_localx_integration_is_continuation_not_extra_user_approval() -> None:
    import json
    agents = read("AGENTS.md")
    dispatch = read(".agents/skills/engineering/派工/SKILL.md")
    qa = read(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
    nav = read(".agents/skills/engineering/README.md")
    gate = json.loads(read(".agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json"))
    assert "DISPATCH_DEFAULT_LOCALX_CONTINUATION_V1" in agents
    assert "DISPATCH_DEFAULT_LOCALX_CONTINUATION_V1" in dispatch
    assert "不需要另下一張 PR 合併口令" in dispatch
    assert "不要求每張 PR 重複授權" in qa
    assert "GITHUB_LOCALX_FIRST" in nav
    assert gate["default_integration_route"] == "GITHUB_LOCALX_FIRST"
    assert "WINDOWS_LOCALX_SYNC_PENDING" in gate["integration_routes"]["GITHUB_LOCALX_FIRST"]["on_success"]
    assert "external_dc_approval" in gate["integration_routes"]["EXPLICIT_DC_LOCALX"]["requires"]
    assert "DC_LOCALX_FIRST" not in agents
    assert "DC_LOCALX_FIRST" not in dispatch
    assert "DC_LOCALX_FIRST" not in qa
    assert "不豁免" in agents


def test_localx_is_development_authority_and_x_is_release_only() -> None:
    """Never let the stale production branch become the next development baseline."""
    agents = read("AGENTS.md")
    source_block = agents.split("## 所有產品修改前先讀程式與文檔硬閘門", 1)[1].split("\n## ", 1)[0]
    assert "LOCALX_DEVELOPMENT_SOURCE_AUTHORITY_V1" in agents
    assert "唯一日常施工與治理修改基準是 GitHub `localX`" in agents
    assert "新工作分支從此 HEAD 建立" in agents
    assert "fresh-read GitHub `localX` 最新 HEAD 的 `AGENTS.md`" in source_block
    assert "fresh-read 正式 `X=cleanup/2d-3d-sync`" not in source_block
    assert "正式執行／治理唯一權威是 `X=cleanup/2d-3d-sync`" not in agents
    assert "X-only 提交不得默默 merge" in agents
    assert "不是因為 `localX` 需要本機 checkout" in agents
    assert "預設由 GitHub／雲端將已測試成果直接合回" in agents


def test_no_active_governance_route_can_bypass_localx() -> None:
    agents = read("AGENTS.md")
    dispatch = read(".agents/skills/engineering/派工/SKILL.md")
    for obsolete in (
        "直接走治理 PR 至正式 X",
        "治理變更走既有 governance 直送 X 通道",
        "照既有 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 直送 X",
    ):
        assert obsolete not in agents
    for obsolete in (
        "照治理通道直接由 GitHub PR 合併 X",
        "純治理文件必須優先 GitHub 直送 X",
    ):
        assert obsolete not in dispatch
    assert "治理與產品測試分流、施工來源一致" in dispatch
    assert "非本體治理修訂從 GitHub `localX` 開分支" in agents


def test_localx_qa_and_execution_skills_cannot_fallback_to_coreelec() -> None:
    """Check the actual QA success path, not just the presence of a green keyword."""
    qa = read(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
    diagnosis = read(".agents/skills/engineering/diagnosing-bugs/SKILL.md")
    execution = read(".agents/skills/engineering/執行開發任務/SKILL.md")
    root = read(".agents/skills/engineering/root-local-first/SKILL.md")
    assert qa.count("## QA 輪詢與交付閘門") == 1
    success = qa.split("`completed / success` →", 1)[1].split("\n- ", 1)[0]
    assert "`GITHUB_LOCALX_FIRST`" in success
    assert "`expected_head_sha`" in success
    assert "不先用 DC" in success
    assert "用 DC 僅安全整合本機" not in qa
    assert "DC_UNREACHABLE" not in qa
    assert "正式 X `AGENTS.md` 判斷" not in diagnosis
    assert "以最新 `localX` 建工作分支" in diagnosis
    assert "不因 `LOCALX_INTEGRATION` 或 CI GREEN 自動啟動 DC" in execution
    assert "CI GREEN／`LOCALX_INTEGRATION`" in root
    for body in (diagnosis, execution, root):
        assert "治理分支直接 PR／CI 合併 X" not in body
        assert "治理分支 → X PR/merge" not in body

def test_retired_continuity_pitfalls_do_not_present_removed_machine_guards_as_current() -> None:
    """Archived failure evidence must not offer removed control-plane executables."""
    continuous = read("個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md")
    closure = read("個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md")
    assert "whd_doc_role: REFERENCE" in continuous[:250]
    assert "whd_doc_role: REFERENCE" in closure[:250]
    assert "現在是**反向 anti-regrowth tests**" not in continuous
    assert "CURRENT fix 是 `tools/execution_invocation_exit.py" not in continuous
    assert "已不存在" in continuous and "HISTORICAL" in continuous
    assert "### 當時的 fail-closed 規則（HISTORICAL／已退役）" in closure
    assert "**當時的 semantic owners（HISTORICAL）**" in closure
    assert "Canonical semantic owners remain single-source" not in closure
    assert "當時的 finalization 規則（HISTORICAL／已退役）" in closure
    assert "AGENTS.md" in continuous and "AGENTS.md" in closure
    entry = read("個人AI檔案庫/踩坑庫/root_local_first_entry_gate_pitfall.md")
    assert "現行糾偏（不恢復歷史入口）" in entry
    assert "不得因讀到本段就呼叫 root-local-first 或 DC／RC" in entry


def test_reference_pitfalls_cannot_reactivate_workspace_or_phase6_preflight() -> None:
    """Optional legacy diagnostics and historical migration notes are not work gates."""
    migration = read("個人AI檔案庫/踩坑庫/deterministic_repo_migration_pitfalls.md")
    keyword = read("個人AI檔案庫/踩坑庫/preflight_keyword_boundary_pitfall.md")
    for text in (migration, keyword):
        assert "whd_doc_role: REFERENCE" in text[:200]
        assert "AGENTS.md" in text
    assert "當時的工作區規則（HISTORICAL／SUPERSEDED）" in migration
    assert "不得把舊 `WORKSPACE_DEFAULT` 當作每件 WHD 任務的強制入口" in migration
    assert "不能作為 Git／施工／PR／DC／CI 前置授權或阻擋門檻" in keyword
    assert "相容診斷工具的字詞比對正確性規則" in keyword
    assert "## 永久規則" not in keyword


def test_retired_pitfall_subsections_do_not_advertise_active_owners() -> None:
    """History-only subheadings must not masquerade as CURRENT routing."""
    closure = read("個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md")
    continuity = read("個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md")
    assert "當時的 Canonical Skill（HISTORICAL／已退役）" in closure
    assert "當時的 Machine guards（HISTORICAL；不可作今日必經驗收）" in closure
    assert "當時的 Registry route（HISTORICAL；不代表現行啟用）" in closure
    assert continuity.count("當時的事故防錯規則（HISTORICAL；今日依 CURRENT Skill／GitHub 回讀）") == 3
    assert "\n永久規則：\n" not in continuity


def test_issue1796_partial_gui_acceptance_checkpoint_stays_historical_and_blocked() -> None:
    """A dated GUI checkpoint cannot silently become release or CURRENT authority."""
    body = read("docs/superpowers/verification/2026-10-16-issue1796-gui-integrity-checkpoint.md")
    assert "whd_doc_role: HISTORICAL" in body[:250]
    assert "whd_contract: verification-provenance" in body[:250]
    assert "部分驗收" in body
    assert "CURRENT" in body and "phase6-gui-performance-integrity" in body
    for required in (
        "#1794", "#1796", "#1805", "#1806",
        "WINDOWS_LOCALX_SYNC_PENDING",
        "WINDOWS_UAT_PENDING",
        "AI_LIBRARY_WRITEBACK_PENDING",
        "正式 X",
    ):
        assert required in body, required


def test_release_1997_legacy_docs_have_consistent_nonduplicated_metadata() -> None:
    docs = (
        "docs/integrations/cadcraft-2d-preview-poc.md",
        "docs/performance/issue1816-baseline.md",
        "docs/performance/issue1816-cloud-baseline-20261016.md",
        "docs/performance/issue1816-private-nfb-source-preview-20261016.md",
        "docs/performance/issue1817-paired-bay-preview.md",
        "docs/performance/issue1818-navigation-sync.md",
        "docs/performance/issue1819-long-gui-memory.md",
        "docs/performance/issue1819-three-bay-ab.md",
        "docs/performance/issue1819-windows-uat.md",
        "docs/performance/issue1820-cadcraft-evaluation.md",
        "docs/performance/issue1820-cadcraft-native-gui.md",
        "docs/performance/issue1820-cadcraft-v080-windows-r5.md",
        "docs/performance/issue1820-same-runner-gui.md",
        "docs/performance/issue1820-whd-real-gui.md",
        "docs/releases/WHD_Windows_使用說明.md",
        "docs/releases/WHD_v2026.10.15_更新紀錄.md",
    )
    contracts = set()
    for rel in docs:
        metadata = parse_doc_metadata(read(rel), path=rel)
        assert metadata.role == "REFERENCE", rel
        assert metadata.canonical is None, rel
        assert metadata.contract.startswith("reference-"), rel
        assert metadata.contract not in contracts, rel
        contracts.add(metadata.contract)
    current = "docs/manufacturing/receiving-fixed-plate-source-20261018.md"
    owner = parse_doc_metadata(read(current), path=current)
    assert owner.role == "CURRENT"
    assert owner.contract == "receiving-fixed-plate-canonical-bend-20261018"
    assert owner.canonical is None


def test_release_1997_cadcraft_is_ignored_without_root_dotfile_diff() -> None:
    import subprocess

    root_ignore = read(".gitignore")
    nested = read("cadcraft/.gitignore")
    assert "/cadcraft/" not in root_ignore
    assert "*" in nested.splitlines()
    assert "!.gitignore" in nested.splitlines()
    for candidate in ("cadcraft/third-party.dll", "cadcraft/internal/config.json", "cadcraft/subdir/module.so"):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", candidate],
            cwd=ROOT, capture_output=True, check=False,
        )
        assert result.returncode == 0, (candidate, result.stderr)
    self_result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "cadcraft/.gitignore"],
        cwd=ROOT, capture_output=True, check=False,
    )
    assert self_result.returncode == 1, self_result.stderr.decode(errors="replace")
