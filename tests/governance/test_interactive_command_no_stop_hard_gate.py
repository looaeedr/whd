"""Regression: explicit user-command flow must directly continue, not pre-stop."""
import json
from pathlib import Path
import unittest
from tools.interactive_command_no_stop_gate import WorkObservation, next_action

ROOT = Path(__file__).resolve().parents[2]
SURFACES = [
    "AGENTS.md",
    ".agents/skills/engineering/派工/SKILL.md",
    ".agents/skills/engineering/新增功能/SKILL.md",
    ".agents/skills/engineering/diagnosing-bugs/SKILL.md",
    ".agents/skills/engineering/執行開發任務/SKILL.md",
]
CONTRACT = ROOT / ".agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json"

class InteractiveNoStopGate(unittest.TestCase):
    def test_all_active_command_surfaces_have_no_stop_gate(self):
        for path in SURFACES:
            with self.subTest(path=path):
                content = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("INTERACTIVE_COMMAND_NO_STOP_HARD_GATE_V1", content)
                self.assertIn("不得停止程序", content)
                self.assertNotIn("平台層級的 ChatGPT 回合攔截器", content)
                self.assertNotIn("ChatGPT 平台沒有可由此文件攔截", content)

    def test_blocker_never_becomes_predeclared_exit(self):
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
        gate = data["interactive_command_hard_gate"]
        self.assertFalse(gate["predeclared_stop_procedure_allowed"])
        self.assertTrue(gate["any_legal_action_available_means_continue"])
        for key in ("VERIFIED_EXTERNAL_BLOCKER", "REAL_RUNTIME_LIMIT"):
            self.assertFalse(data["decisions"][key]["may_end_turn_without_completion"])

    def test_real_next_steps_override_single_failed_operation(self):
        self.assertEqual(next_action(WorkObservation(
            authorized_actions=["REPAIR_OTHER_AUTHORIZED_FILE"], operation_rejected=True)),
            "REPAIR_OTHER_AUTHORIZED_FILE")
        self.assertEqual(next_action(WorkObservation(ci_status="in_progress",
            operation_rejected=True)), "CONTINUE_POLL")
        self.assertEqual(next_action(WorkObservation(ci_status="completed",
            ci_conclusion="failure")), "REPAIR_AND_RETEST")
        self.assertEqual(next_action(WorkObservation(ci_status="completed",
            ci_conclusion="success", pr_open=True)), "LOCALX_INTEGRATION_PENDING")
        self.assertEqual(next_action(WorkObservation(localx_merged=True,
            issue_closed=True)), "DISCOVER_NEXT_ISSUE")
        self.assertEqual(next_action(WorkObservation()), "READ_CURRENT_SOURCE_AND_CONTINUE")

if __name__ == "__main__":
    unittest.main()
