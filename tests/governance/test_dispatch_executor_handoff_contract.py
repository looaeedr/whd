"""A dispatch registration must not be represented as an executor handoff.

This contract checks the instruction surfaces rather than claiming GitHub CI
can create or observe independent coding agents outside its own runtime.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
SKILL = ROOT / ".agents/skills/engineering/派工/SKILL.md"


class DispatchExecutorHandoffContract(unittest.TestCase):
    def test_self_execution_first_before_external_agent_discovery(self):
        for path in (AGENTS, SKILL):
            content = path.read_text(encoding="utf-8")
            self.assertIn("DISPATCH_SELF_EXECUTION_FIRST", content)
            self.assertIn("Codex", content)
            self.assertIn("本體", content)
            self.assertIn("REMOTE_EXECUTOR_UNAVAILABLE", content)
            self.assertIn("EXECUTOR_START_CONFIRMED", content)
            self.assertLess(content.index("DISPATCH_SELF_EXECUTION_FIRST"),
                            content.index("## 真實執行者接取：" if path == SKILL
                                          else "## /派工真實啟動證據"))
        skill = SKILL.read_text(encoding="utf-8")
        start = skill.split("## 本體直接施工優先", 1)[1].split("## 真實執行者接取", 1)[0]
        for item in ("本體直接接取", "execution_location=GITHUB",
                     "commit SHA", "CI", "無能力才找外部代理",
                     "localX", "治理"):
            self.assertIn(item, start)
        self.assertLess(start.index("沿用既有工作"), start.index("無能力才找外部代理"))

    def test_non_product_governance_uses_localx_but_skips_product_qa(self):
        agents = AGENTS.read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")
        for text in (agents, skill):
            self.assertIn("NON_PRODUCT_GOVERNANCE_DIRECT_X", text)
            self.assertIn("治理", text)
            self.assertIn("localX", text)
            self.assertIn("/推推", text)
        self.assertIn("治理與產品測試分流、施工來源一致", skill)
        self.assertIn("治理專項 CI", skill)
        self.assertIn("PR 合回 `localX`", skill)
        self.assertNotIn("不走 `localX`、一般產品派工或 `/推推`", skill)
        from tools.change_lane_gate import classify_changes
        self.assertEqual(classify_changes([
            "AGENTS.md", ".agents/skills/engineering/派工/SKILL.md",
            "tests/governance/test_dispatch_executor_handoff_contract.py",
        ]), "GOVERNANCE_DIRECT_X")  # Legacy path classification, not X authorization
        self.assertEqual(classify_changes(["AGENTS.md", "gui.py"]),
                         "PRODUCT_LOCALX_ONLY")

    def test_handoff_is_not_registration(self):
        for path in (AGENTS, SKILL):
            content = path.read_text(encoding="utf-8")
            for expected in (
                "DISPATCH_EXECUTOR_HANDOFF_REQUIRED",
                "EXECUTOR_START_CONFIRMED",
                "DISPATCH_REGISTERED_ONLY",
                "REMOTE_EXECUTOR_UNAVAILABLE",
                "DISPATCH_START_UNCONFIRMED",
            ):
                with self.subTest(path=str(path), marker=expected):
                    self.assertIn(expected, content)
            self.assertIn("Issue", content)
            self.assertIn("PR", content)
            self.assertIn("執行者", content)
            self.assertIn("接取", content)
            self.assertIn("不得", content)

    def test_execution_evidence_and_failure_remain_separate(self):
        skill = SKILL.read_text(encoding="utf-8")
        section = skill.split("## 真實執行者接取：", 1)[1].split("### 唯一可使用 DC", 1)[0]
        self.assertLess(section.index("能力核對與啟動"), section.index("回讀接取證據"))
        self.assertLess(section.index("回讀接取證據"), section.index("失敗即真實回報"))
        for rule in ("task/run ID", "Issue", "分支", "首個真實施工動作", "代貼", "背景"):
            self.assertIn(rule, section)
        self.assertIn("同一合法雲端執行者直接施工", section)
        self.assertIn("不得轉用 DC／本機", section)

    def test_only_governance_files_changed(self):
        from tools.change_lane_gate import classify_changes
        self.assertEqual(classify_changes([
            "AGENTS.md",
            ".agents/skills/engineering/派工/SKILL.md",
            "tests/governance/test_dispatch_executor_handoff_contract.py",
        ]), "GOVERNANCE_DIRECT_X")


if __name__ == "__main__":
    unittest.main()
