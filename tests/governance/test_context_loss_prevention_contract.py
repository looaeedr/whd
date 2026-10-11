"""WHD: reduce context-loss risk rather than build handoff machinery.

Static checks do not and cannot measure ChatGPT's remaining context tokens.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
LOG = ROOT / ".agents/skills/engineering/long-log-context-safe-execution/SKILL.md"
CI = ROOT / ".github/workflows/knowledge-governance-bootstrap.yml"
HANDOFF = ROOT / ".agents/skills/productivity/handoff/SKILL.md"


class ContextLossPreventionContract(unittest.TestCase):
    def test_no_fabricated_capacity_and_no_new_handoff_process(self):
        agents = AGENTS.read_text("utf-8")
        section = agents.split("## WHD 長對話上下文損耗防護", 1)[1].split("## `/推推`", 1)[0]
        for word in ("WHD_CONTEXT_LOSS_PREVENTION_V1", "剩餘 Token", "無法保證",
                     "不建立新交接文件", "不建立", "定時檢查",
                     "已確認的使用者決策", "不中斷", "未核實"):
            with self.subTest(word=word):
                self.assertIn(word, section)
        self.assertNotIn("WHD_CONTEXT_CHECKPOINT_V1", section)
        self.assertNotIn("NORMAL / WATCH / HIGH", section)

    def test_bounded_output_and_targeted_rereads(self):
        agents = AGENTS.read_text("utf-8")
        skill = LOG.read_text("utf-8")
        for content in (agents, skill):
            for marker in ("WHD_CONTEXT_LOSS_PREVENTION_V1", "80", "truncated",
                           "run_id", "HEAD", "GitHub"):
                with self.subTest(marker=marker):
                    self.assertIn(marker, content)
        self.assertIn("start_line/end_line", skill)
        self.assertIn("不重新問已提供的答案", agents)
        self.assertIn("不中斷既有施工", skill)

    def test_handoff_skill_is_not_extended_for_this_feature(self):
        handoff = HANDOFF.read_text("utf-8")
        self.assertNotIn("WHD_CONTEXT_LOSS_PREVENTION_V1", handoff)
        self.assertNotIn("WHD_CONTEXT_CHECKPOINT_V1", handoff)

    def test_governance_only_and_ci_protection(self):
        workflow = CI.read_text("utf-8")
        self.assertIn("test_context_loss_prevention_contract.py", workflow)
        from tools.change_lane_gate import classify_changes
        changes = ["AGENTS.md",
                   ".agents/skills/engineering/long-log-context-safe-execution/SKILL.md",
                   "tests/governance/test_context_loss_prevention_contract.py",
                   ".github/workflows/knowledge-governance-bootstrap.yml"]
        self.assertEqual(classify_changes(changes), "GOVERNANCE_DIRECT_X")
        self.assertEqual(classify_changes(changes + ["gui.py"]), "PRODUCT_LOCALX_ONLY")


if __name__ == "__main__":
    unittest.main()
