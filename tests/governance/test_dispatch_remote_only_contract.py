"""Enforce /派工 GitHub-first development, CI and localX delivery without implicit DC."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
DISPATCH = ROOT / ".agents/skills/engineering/派工/SKILL.md"
TAKEOVER = ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md"
LOCAL = ROOT / ".agents/skills/engineering/root-local-first/SKILL.md"
QA = ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"


class DispatchRemoteOnlyContract(unittest.TestCase):
    def test_cloud_only_build_and_ci(self):
        agents = AGENTS.read_text("utf-8")
        dispatch = DISPATCH.read_text("utf-8")
        for text in (agents, dispatch):
            self.assertIn("DISPATCH_CLOUD_BUILD_GITHUB_LOCALX_ONLY", text)
            self.assertIn("GITHUB_LOCALX_FIRST", text)
            self.assertIn("/派工", text)
            self.assertNotIn("DC_LOCALX_FIRST", text)
        self.assertIn("execution_location=GITHUB|SCHEDULER|REMOTE_ACTION", dispatch)
        self.assertIn("不因此自動授權 DC", dispatch)
        self.assertIn("ref=localX", agents)
        self.assertIn("只有正式發布查核才使用精確 `ref=cleanup/2d-3d-sync`", agents)

    def test_github_localx_is_default_after_ci_without_dc(self):
        agents = AGENTS.read_text("utf-8")
        dispatch = DISPATCH.read_text("utf-8")
        qa = QA.read_text("utf-8")
        for text in (agents, dispatch, qa):
            self.assertIn("GITHUB_LOCALX_FIRST", text)
            self.assertIn("WINDOWS_LOCALX_SYNC_PENDING", text)
            self.assertNotIn("DC_LOCALX_FIRST", text)
            self.assertIn("DC", text)
        self.assertIn("expected_head_sha", dispatch)
        self.assertIn("不先用 DC", qa)
        self.assertIn("不需要 DC", dispatch)

    def test_dc_fallback_is_not_a_default_requirement(self):
        agents = AGENTS.read_text("utf-8")
        dispatch = DISPATCH.read_text("utf-8")
        qa = QA.read_text("utf-8")
        self.assertIn("不要求 DC 斷線證據", agents)
        self.assertIn("不需要 DC", dispatch)
        self.assertIn("不先用 DC", qa)
        self.assertIn("GITHUB_LOCALX_FIRST", dispatch)
        self.assertNotIn("用 DC 僅安全整合本機", qa)
        self.assertNotIn("DC_UNREACHABLE", qa)

    def test_slash_takeover_remains_distinct_from_dispatch_dc_exception(self):
        for path in (TAKEOVER, LOCAL):
            text = path.read_text("utf-8")
            with self.subTest(path=path.name):
                self.assertIn("/接手", text)
                self.assertIn("/派工", text)
                self.assertIn("Remote Desktop Commander", text)
                self.assertIn("/workspace/whd", text)
                self.assertIn("LOCALX_INTEGRATION", text)
                self.assertIn("施工", text)

    def test_no_premature_x_publish_or_localx_success_claim(self):
        agents = AGENTS.read_text("utf-8")
        dispatch = DISPATCH.read_text("utf-8")
        self.assertIn("/推推", agents)
        self.assertIn("/推推", dispatch)
        self.assertIn("WINDOWS_LOCALX_SYNC_PENDING", dispatch)
        self.assertIn("GITHUB_LOCALX_FIRST", dispatch)
        self.assertIn("回讀", dispatch)
        self.assertIn("NEXT_ISSUE_DISCOVERY_REQUIRED", dispatch)

    def test_registry_cannot_convert_dispatch_or_generic_edit_into_local_takeover(self):
        from tools.phase6_skill_preflight import required_skills_for

        generic = set(required_skills_for(task="一般產品錯誤修正", changed_files=["gui.py"]))
        self.assertNotIn("root-local-first", generic)
        dispatch = set(required_skills_for(task="/派工 #999", changed_files=["gui.py"]))
        self.assertIn("派工", dispatch)
        self.assertNotIn("root-local-first", dispatch)
        takeover = set(required_skills_for(task="/接手 #999", changed_files=["gui.py"]))
        self.assertIn("root-local-first", takeover)
        self.assertIn("執行開發任務", takeover)
        self.assertNotIn("派工", takeover)
        migration = set(required_skills_for(
            task="deterministic repo migration",
            changed_files=[".agents/skills/engineering/deterministic-repo-migration/SKILL.md"],
        ))
        self.assertIn("deterministic-repo-migration", migration)
        self.assertNotIn("root-local-first", migration)

    def test_current_authority_map_and_skill_reference_respect_execution_split(self):
        authority = (
            ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
        ).read_text("utf-8")
        reference = (
            ROOT / "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md"
        ).read_text("utf-8")
        for marker in ("/派工", "/接手", "LOCALX_INTEGRATION", "/推推", "GitHub／雲端"):
            with self.subTest(marker=marker):
                self.assertIn(marker, authority)
        self.assertNotIn("Repository work is made and validated locally", authority)
        self.assertIn("REFERENCE／非執行權威", reference)
        self.assertIn("HISTORICAL／不可執行", reference)
        self.assertNotIn("## 已核准規格拆工單 fast path — CURRENT", reference)

    def test_retired_scheduler_simulation_is_not_an_active_skill_route(self):
        import json
        from tools.phase6_skill_preflight import required_skills_for

        registry = json.loads(
            (ROOT / ".agents/skills/skill_registry.json").read_text("utf-8")
        )
        self.assertFalse(any(r["id"] == "scheduler-simulation" for r in registry["routes"]))
        matches = [r for r in registry["routes"] if r["id"] == "scheduler-command-reference"]
        self.assertEqual(len(matches), 1)
        route = matches[0]
        self.assertEqual(route["file_globs"], [])
        self.assertEqual(route["required_skills"], [])
        self.assertEqual(route["keywords"], ["/排程A", "/排程B", "排程A", "排程B"])
        for task in ("/排程A", "/排程B"):
            selected = set(required_skills_for(task=task))
            self.assertNotIn("排程模擬", selected)
            self.assertNotIn("寫排程", selected)
            self.assertNotIn("root-local-first", selected)

    def test_git_fallback_and_ui_skill_keep_current_execution_authority(self):
        fallback = (
            ROOT / ".agents/skills/misc/git-remote-sync-fallback/SKILL.md"
        ).read_text("utf-8")
        ui = (
            ROOT / ".agents/skills/engineering/UI設計與去AI味/SKILL.md"
        ).read_text("utf-8")
        for marker in ("/派工", "/接手", "LOCALX_INTEGRATION", "/推推", "GitHub／雲端"):
            with self.subTest(marker=marker):
                self.assertIn(marker, fallback)
        self.assertIn("不自行授權施工或 DC 存取", fallback)
        self.assertNotIn("施工、測試和 commit 仍由指定本地工作區擁有", fallback)
        self.assertNotIn("AGENTS.md`、Phase6 Preflight、project Skills", ui)
        self.assertIn("已退役的 Phase6 Preflight receipt", ui)

    def test_navigation_docs_do_not_reintroduce_local_dispatch_or_preflight(self):
        nav = (
            ROOT / ".agents/skills/engineering/README.md"
        ).read_text("utf-8")
        handoff = (ROOT / "AI_HANDOFF.md").read_text("utf-8")
        for marker in ("/派工", "/接手", "GITHUB_LOCALX_FIRST", "WINDOWS_LOCALX_SYNC_PENDING"):
            with self.subTest(marker=marker):
                self.assertIn(marker, nav)
        self.assertNotIn("派工與本地施工", nav)
        self.assertNotIn("預設 repository content work", nav)
        self.assertIn("APPROVED_REQUIREMENT_FAST_PATH", nav)
        self.assertIn("舊 Phase6 Preflight receipt 已退役", handoff)

    def test_non_whitelisted_sop_remediation_stays_out_of_governance_lane(self):
        from tools.change_lane_gate import classify_changes

        paths = [
            "個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md",
            "個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md",
            "個人AI檔案庫/第二層_專案與SOP/12_WHD規格書Skill前置與Grounding規則.md",
            "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
        ]
        self.assertEqual(classify_changes(paths), "PRODUCT_LOCALX_ONLY")
        report = (ROOT / "docs/governance/WHD_RETIRED_SOP_ROUTING_AUDIT_20261011.md").read_text("utf-8")
        self.assertIn("PENDING_PRODUCT_LOCALX_ROUTE", report)
        self.assertIn("PRODUCT_OR_MIXED_REQUIRES_LOCALX", report)
        self.assertIn("不得加入治理 PR 直送 X", report)
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(path, report)

    def test_ask_matt_router_does_not_reenable_retired_execution(self):
        router = (
            ROOT / ".agents/skills/engineering/ask-matt/SKILL.md"
        ).read_text(encoding="utf-8")
        for marker in ("APPROVED_REQUIREMENT_FAST_PATH", "/派工", "/接手",
                       "/推推", "ref=cleanup/2d-3d-sync"):
            with self.subTest(marker=marker):
                self.assertIn(marker, router)
        self.assertNotIn("Requirement RED-first + 使用者核准後拆 tickets", router)
        self.assertNotIn("跨回合的 execution authority 必須落在 `WHD_EXECUTION_RECORD_V2`", router)
        self.assertNotIn("仍服從專案 Preflight/branch/QA 規則", router)
        self.assertIn("已退役", router)
        self.assertIn("不得假裝會背景續作", router)

    def test_legacy_preflight_router_is_not_execution_authority(self):
        import json
        from tools import phase6_skill_preflight

        registry = json.loads(
            (ROOT / ".agents/skills/skill_registry.json").read_text("utf-8")
        )
        self.assertIn("NOT current execution/CI/DC authorization", registry["description"])
        self.assertIn("not an execution gate", phase6_skill_preflight.__doc__)
        self.assertNotIn("Phase6 Knowledge Preflight gate.", phase6_skill_preflight.__doc__)
        self.assertIn("NOT a CURRENT execution gate",
                      phase6_skill_preflight.build_parser().description)
        self.assertTrue(callable(phase6_skill_preflight.required_skills_for))
        self.assertTrue(callable(phase6_skill_preflight.required_references_for))

    def test_skill_discovery_and_questioning_respect_current_x_lanes(self):
        paths = {
            "questioning": ".agents/skills/engineering/拷問邊建立文件/SKILL.md",
            "discovery": ".agents/skills/productivity/找技能/SKILL.md",
            "mcp": ".agents/skills/productivity/MCP工具操作/SKILL.md",
            "scanner": ".agents/skills/engineering/掃描深模組/SKILL.md",
        }
        docs = {name: (ROOT / path).read_text("utf-8")
                for name, path in paths.items()}
        for name in ("questioning", "discovery", "mcp"):
            with self.subTest(skill=name):
                self.assertIn("/派工", docs[name])
                self.assertIn("/接手", docs[name])
                self.assertIn("GitHub／雲端", docs[name])
        self.assertNotIn("先遵守 `AGENTS.md` / root-local-first / Knowledge Preflight", docs["questioning"])
        self.assertNotIn("Phase6 **Preflight**、root-local-first、Git-phase branch", docs["discovery"])
        self.assertNotIn("若任務本身另有專案級 root-local-first", docs["mcp"])
        self.assertIn("ref=cleanup/2d-3d-sync", docs["mcp"])
        self.assertIn("APPROVED_REQUIREMENT_FAST_PATH", docs["scanner"])
        self.assertNotIn("的 RED-first、AI Library、Issue、remote QA 流程", docs["scanner"])

    def test_release_packaging_does_not_override_cloud_dispatch_execution(self):
        skill = (
            ROOT / ".agents/skills/engineering/phase6-release-packaging/SKILL.md"
        ).read_text(encoding="utf-8")
        for marker in ("/派工", "/接手", "LOCALX_INTEGRATION", "/推推",
                       "GitHub／排程／雲端", "pristine", "exact HEAD CI"):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        self.assertNotIn("WHD interactive/default changes enter release only after root-local qualification", skill)
        self.assertNotIn("after unlock, create a fresh work branch", skill)
        self.assertNotIn("A work branch is still mandatory in Git phase, but it does not precede root development/testing", skill)
        self.assertIn("不得為治理修改探測使用者本機", skill)

    def test_nonwhitelisted_readme_handoff_are_tracked_without_bypass(self):
        from tools.change_lane_gate import classify_changes

        paths = ["README.md", "handoff/00_AI_HANDOFF_README.md"]
        self.assertEqual(classify_changes(paths), "PRODUCT_LOCALX_ONLY")
        audit = (
            ROOT / "docs/governance/WHD_RETIRED_SOP_ROUTING_AUDIT_20261011.md"
        ).read_text("utf-8")
        self.assertIn("47 份 canonical 候選", audit)
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(path, audit)
        self.assertIn("共 6 份", audit)
        self.assertIn("HISTORICAL_UNMANAGED_DO_NOT_MUTATE", audit)

    def test_changes_are_governance_only(self):
        from tools.change_lane_gate import classify_changes
        paths = [
            "AGENTS.md",
            ".agents/skills/engineering/派工/SKILL.md",
            ".agents/skills/engineering/執行開發任務/SKILL.md",
            ".agents/skills/engineering/root-local-first/SKILL.md",
            ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
            "tests/governance/test_dispatch_remote_only_contract.py",
        ]
        self.assertEqual(classify_changes(paths), "GOVERNANCE_DIRECT_X")
        self.assertEqual(classify_changes(paths + ["phase6_manufacturing_adapter.py"]), "PRODUCT_LOCALX_ONLY")


if __name__ == "__main__":
    unittest.main()
