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
