"""Keep GitHub's default main branch historical and require explicit WHD X refs."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_DEFAULT_BRANCH_FAIL_CLOSED_V1.json"
AGENTS = ROOT / "AGENTS.md"


class DefaultBranchExplicitXContract(unittest.TestCase):
    def test_main_is_unmanaged_history_not_tombstone_target(self):
        doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "CURRENT")
        self.assertEqual(doc["production_branch"], "cleanup/2d-3d-sync")
        self.assertEqual(doc["default_branch"], "main")
        self.assertEqual(doc["policy"], "MAIN_HISTORICAL_UNMANAGED_EXPLICIT_X_ONLY")
        self.assertEqual(doc["main_disposition"], "HISTORICAL_UNMANAGED_DO_NOT_MUTATE")
        self.assertNotIn("required_main_stub_paths", doc)
        self.assertEqual(doc["retired_main_tree_policy"]["status"], "RETIRED")
        for op in ("cleanup", "delete", "rewrite_as_stub", "governance_mirror",
                   "synchronize", "merge", "rebase", "force_push"):
            with self.subTest(op=op):
                self.assertIn(op, doc["main_automatic_mutations_forbidden"])

    def test_20260928_main_sync_manifest_is_history_not_a_live_requirement(self):
        path = ROOT / "docs/governance/main_cleanup_governance_sync_20260928.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["schema"], "WHD_MAIN_CLEANUP_GOVERNANCE_SYNC_V1")
        self.assertEqual(record["target_ref"], "main")
        self.assertEqual(record["status"], "HISTORICAL")
        self.assertIs(record["execution_authority"], False)
        self.assertEqual(
            record["current_main_policy"], "MAIN_HISTORICAL_UNMANAGED_EXPLICIT_X_ONLY"
        )
        self.assertIn("Do not run mirroring", record["usage_note"])
        self.assertIn("invariant", record)  # Retained only as historical evidence.

    def test_canonical_reads_fail_closed_when_ref_unspecified(self):
        doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(doc["canonical_read_ref"], doc["production_branch"])
        self.assertEqual(doc["unspecified_ref_policy"], "FAIL_CLOSED_REQUIRE_EXPLICIT_X")
        self.assertEqual(doc["main_read_policy"], "HISTORICAL_CONTEXT_ONLY_NO_EXECUTION_AUTHORITY")
        agents = AGENTS.read_text(encoding="utf-8")
        for required in ("MAIN_HISTORICAL_UNMANAGED_EXPLICIT_X_ONLY",
                         "ref=cleanup/2d-3d-sync", "不清理", "不得再次啟動 `main` 清理"):
            with self.subTest(required=required):
                self.assertIn(required, agents)


    def test_localx_development_and_x_release_are_separate_explicit_refs(self):
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn("唯一日常施工與治理修改基準是 GitHub `localX`", agents)
        self.assertIn("ref=localX", agents)
        self.assertIn("只有正式發布查核才使用精確 `ref=cleanup/2d-3d-sync`", agents)
        self.assertIn("不得作為日常產品／治理施工基準", agents)

    def test_slash_push_remote_default_has_no_extra_local_approval(self):
        """A user /推推 is acceptance + GitHub release authority, not a DC request."""
        agents = AGENTS.read_text(encoding="utf-8")
        push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(
            encoding="utf-8"
        )
        packaging = (
            ROOT / ".agents/skills/engineering/phase6-release-packaging/SKILL.md"
        ).read_text(encoding="utf-8")
        policy = agents.split(
            "## `/推推` 發布先行、X 回同步硬閘門", 1,
        )[1].split("## 全域台灣時區硬閘門", 1)[0]

        self.assertIn("`/推推` 預設 GitHub-only", policy)
        self.assertIn("不讀本機、不另問「GitHub-only」授權", policy)
        self.assertIn("本機未同步不阻擋遠端發布", policy)
        self.assertIn("owner exact `/推推` 留言", policy)
        self.assertIn("非強制 fast-forward", policy)
        self.assertIn("本機同步待辦不影響 GitHub 發布", policy)
        self.assertIn("LOCAL_SYNC_PENDING", policy)
        self.assertIn("GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1", policy)
        for retired_gate in (
            "預設本機優先",
            "只有完成 Windows UAT",
            "未取得 GitHub-only 明確授權時",
            "一般 `/推推` 繼續遵守上方本機優先",
        ):
            with self.subTest(retired_gate=retired_gate):
                self.assertNotIn(retired_gate, policy)

        self.assertIn("唯一預設路線：GitHub-only", push)
        self.assertIn("最後一步是正式 GitHub Release", push)
        self.assertIn("不再具有執行權威", push)
        self.assertIn("由使用者當次 `/推推`", packaging)
        self.assertIn("不允許治理直送 X", packaging)
        self.assertNotIn("直接 PR／CI 合併 X，不經 `localX`", packaging)

    def test_open_pr_head_and_base_refs_fail_closed(self):
        """An OPEN PR protects its head AND base refs from cleanup."""
        from tools.branch_cleanup_ref_guard import (
            BranchCleanupGuardError,
            assert_delete_candidates_safe,
            protected_open_pr_refs,
        )

        pulls = [
            {"head": {"ref": "feature/test"}, "base": {"ref": "cleanup/2d-3d-sync"}},
            {"head": {"ref": "refs/heads/docs/clean"}, "base": {"ref": "localX"}},
        ]
        self.assertEqual(
            protected_open_pr_refs(pulls),
            {"feature/test", "docs/clean", "cleanup/2d-3d-sync", "localX"},
        )
        for protected in (
            "feature/test", "docs/clean", "cleanup/2d-3d-sync",
            "refs/heads/localX",
        ):
            with self.subTest(protected=protected):
                with self.assertRaisesRegex(BranchCleanupGuardError, "protected ref"):
                    assert_delete_candidates_safe([protected], pulls)
        assert_delete_candidates_safe(["feature/unrelated"], pulls)
        for malformed in (
            [{"head": {"ref": "feature/test"}}],
            [{"head": {"ref": "feature/test"}, "base": {"ref": ""}}],
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(BranchCleanupGuardError):
                    assert_delete_candidates_safe(["feature/unrelated"], malformed)


    def test_knowledge_authority_suite_is_wired_to_bootstrap(self):
        workflow = (
            ROOT / ".github/workflows/knowledge-governance-bootstrap.yml"
        ).read_text(encoding="utf-8")
        suite = "tests/knowledge/test_current_history_authority_contract.py"
        self.assertIn("- '" + suite + "'", workflow)
        self.assertIn("python -m pytest -q " + suite, workflow)



if __name__ == "__main__":
    unittest.main()
