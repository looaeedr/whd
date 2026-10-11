"""WHD context risk handoff must be useful without fake token telemetry or scheduling."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
HANDOFF = ROOT / ".agents/skills/productivity/handoff/SKILL.md"
LONG_LOG = ROOT / ".agents/skills/engineering/long-log-context-safe-execution/SKILL.md"
WORKFLOW = ROOT / ".github/workflows/knowledge-governance-bootstrap.yml"


class ContextRiskHandoffContract(unittest.TestCase):
    def test_one_authority_and_three_risk_levels(self):
        rule = AGENTS.read_text(encoding="utf-8")
        self.assertIn("WHD_CONTEXT_RISK_CHECKPOINT_V1", rule)
        section = rule.split("## WHD 對話上下文風險與交接", 1)[1].split("## `/推推`", 1)[0]
        for marker in ("NORMAL", "WATCH", "HIGH", "上下文", "Token",
                       "可觀察", "不新增定時輪詢", "不新增", "未核實"):
            with self.subTest(marker=marker):
                self.assertIn(marker, section)
        self.assertIn("不能控制平台自動壓縮", section)

    def test_checkpoint_fields_and_persistence(self):
        agents = AGENTS.read_text(encoding="utf-8")
        handoff = HANDOFF.read_text(encoding="utf-8")
        for content in (agents, handoff):
            for marker in ("WHD_CONTEXT_CHECKPOINT_V1", "Issue", "PR", "run_id",
                           "head_sha", "Asia/Taipei", "/推推", "下一個", "未核實"):
                with self.subTest(marker=marker):
                    self.assertIn(marker, content)
        for marker in ("repo", "執行者", "來源分支", "目標分支", "阻塞",
                       "下一個精確動作", "權限", "GitHub"):
            self.assertIn(marker, handoff)
        self.assertIn("fresh-read", agents)
        self.assertIn("不為每次消息重寫", agents)

    def test_no_fake_background_monitor_and_no_dc_expansion(self):
        rule = AGENTS.read_text(encoding="utf-8")
        handoff = HANDOFF.read_text(encoding="utf-8")
        log_skill = LONG_LOG.read_text(encoding="utf-8")
        for text in (rule, handoff, log_skill):
            self.assertIn("WHD_CONTEXT_RISK_CHECKPOINT_V1", text)
        self.assertIn("不是平台自動註冊的工具／排程", handoff)
        self.assertIn("不得增加新門檻", handoff)
        self.assertIn("未獲授權不得轉走 DC／本機", log_skill)
        self.assertIn("last_read_offset/cursor", log_skill)

    def test_ci_runs_contract(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("test_context_risk_handoff_contract.py", workflow)
        self.assertIn("python -m unittest discover", workflow)
        from tools.change_lane_gate import classify_changes
        paths = ["AGENTS.md", ".agents/skills/productivity/handoff/SKILL.md",
                 ".agents/skills/engineering/long-log-context-safe-execution/SKILL.md",
                 ".github/workflows/knowledge-governance-bootstrap.yml",
                 "tests/governance/test_context_risk_handoff_contract.py"]
        self.assertEqual(classify_changes(paths), "GOVERNANCE_DIRECT_X")
        self.assertEqual(classify_changes(paths + ["gui.py"]), "PRODUCT_LOCALX_ONLY")


if __name__ == "__main__":
    unittest.main()
