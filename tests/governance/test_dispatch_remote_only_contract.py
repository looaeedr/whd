"""Enforce /派工 cloud-only BUILD and Desktop Commander final localX integration."""
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
        for path in (AGENTS, DISPATCH):
            text = path.read_text("utf-8")
            for marker in (
                "DISPATCH_CLOUD_BUILD_DC_LOCALX_ONLY",
                "execution_location=GITHUB|SCHEDULER|REMOTE_ACTION",
                "DISPATCH_LOCAL_EXECUTION_DENIED",
                "REMOTE_EXECUTOR_UNAVAILABLE",
            ):
                with self.subTest(path=path.name, marker=marker):
                    self.assertIn(marker, text)
        dispatch = DISPATCH.read_text("utf-8")
        self.assertIn("絕不能在使用者本機施工", dispatch)
        self.assertNotIn("能直接完成時直接修改、測試", dispatch)
        self.assertNotIn("本機測試與 commit", dispatch)

    def test_dc_allowed_only_during_final_localx_integration(self):
        for path in (AGENTS, DISPATCH, QA):
            text = path.read_text("utf-8")
            with self.subTest(path=path.name):
                self.assertIn("LOCALX_INTEGRATION", text)
                self.assertIn("CI", text)
                self.assertIn("DC", text)
                self.assertIn("本機", text)
                self.assertIn("localX", text)
        dispatch = DISPATCH.read_text("utf-8")
        self.assertIn("CI SUCCESS 之前禁止用 DC", dispatch)
        self.assertIn("只在", dispatch)
        self.assertIn("不得在這個階段直接改產品程式", dispatch)
        self.assertIn("非強制同步 GitHub", dispatch)

    def test_dc_unreachable_is_the_only_remote_merge_fallback(self):
        for path in (AGENTS, DISPATCH, QA):
            text = path.read_text("utf-8")
            for marker in ("DC_UNREACHABLE", "LOCALX_SYNC_PENDING"):
                with self.subTest(path=path.name, marker=marker):
                    self.assertIn(marker, text)
            self.assertIn("無法連線", text)
        dispatch = DISPATCH.read_text("utf-8")
        self.assertIn("衝突", dispatch)
        self.assertIn("不能", dispatch)
        self.assertIn("不得宣稱本機", dispatch)
        self.assertIn("實際不可連線或逾時", dispatch)

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
        self.assertIn("本機已整合", dispatch)
        self.assertIn("回讀", dispatch)
        self.assertIn("NEXT_ISSUE_DISCOVERY_REQUIRED", dispatch)

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
