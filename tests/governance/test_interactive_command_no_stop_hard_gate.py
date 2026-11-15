"""Regression: explicit user-command flow must directly continue, not pre-stop."""
import json
from pathlib import Path
import unittest
from tools.interactive_command_no_stop_gate import (
    WorkObservation, next_action, ordered_command_skills, execute_authorized_step,
)
from tools.phase6_skill_preflight import required_skills_for

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
            self.assertTrue(data["decisions"][key]["may_end_turn_without_completion"])
            self.assertFalse(data["decisions"][key]["normal_completion"])

    def test_actual_skill_router_calls_combined_command_route(self):
        expected = ("新增功能", "diagnosing-bugs", "tdd", "派工", "issue-closure-gate")
        self.assertEqual(ordered_command_skills("/功能 /DEBUG /派工 #1933"), expected)
        selected = required_skills_for(task="/功能 /DEBUG /派工 #1933")
        self.assertEqual(selected[:len(expected)], expected)
        self.assertNotIn("root-local-first", selected)
        takeover = required_skills_for(task="/接手 #1933")
        self.assertIn("root-local-first", takeover)
        self.assertIn("執行開發任務", takeover)
        self.assertNotIn("root-local-first", required_skills_for(task="/派工 #1933"))

    def test_negated_slash_commands_do_not_select_local_or_dispatch_execution(self):
        cases = (
            ("不要 /接手，改用 /派工 #42",
             ("派工",), ("root-local-first", "執行開發任務")),
            ("不要執行 `/接手`，改用 `/派工`",
             ("派工",), ("root-local-first", "執行開發任務")),
            ("don't /接手; use /派工 #42",
             ("派工",), ("root-local-first", "執行開發任務")),
            ("不用 /派工，改用 /debug #42",
             ("diagnosing-bugs", "tdd"), ("派工", "issue-closure-gate")),
            ("禁止 /debug，改用 /功能 #42",
             ("新增功能",), ("diagnosing-bugs", "tdd")),
            ("not /功能; run /debug #42",
             ("diagnosing-bugs", "tdd"), ("新增功能",)),
        )
        for task, present, absent in cases:
            with self.subTest(task=task):
                ordered = set(ordered_command_skills(task))
                selected = set(required_skills_for(task=task))
                for skill in present:
                    self.assertIn(skill, ordered)
                    self.assertIn(skill, selected)
                for skill in absent:
                    self.assertNotIn(skill, ordered)
                    self.assertNotIn(skill, selected)

        for task in ("不要 /接手", "不准 /派工", "不用 /debug", "不要 /功能"):
            with self.subTest(task=task):
                self.assertEqual(ordered_command_skills(task), ())
                self.assertEqual(required_skills_for(task=task), ())

        self.assertEqual(
            ordered_command_skills("/功能 /DEBUG /派工 #1933"),
            ("新增功能", "diagnosing-bugs", "tdd", "派工", "issue-closure-gate"),
        )
        self.assertEqual(
            ordered_command_skills("/接手 #42"), ("root-local-first", "執行開發任務")
        )

    def test_real_executor_invokes_other_authorized_work_after_refusal(self):
        calls = []
        def denied():
            calls.append("denied")
            raise PermissionError("explicit permission denied")
        def do_work():
            calls.append("implemented")
        result = execute_authorized_step(
            WorkObservation(authorized_actions=("denied", "implemented")),
            {"denied": denied, "implemented": do_work},
        )
        self.assertEqual(calls, ["denied", "implemented"])
        self.assertEqual(result.completed_action, "implemented")
        self.assertEqual(result.blocked, ("denied",))
        self.assertEqual(result.attempted, ("denied", "implemented"))

    def test_refused_operation_does_not_fabricate_success_or_unapproved_route(self):
        def denied():
            raise PermissionError("denied")
        result = execute_authorized_step(
            WorkObservation(authorized_actions=("denied", "absent")),
            {"denied": denied},
        )
        self.assertIsNone(result.completed_action)
        self.assertEqual(result.attempted, ("denied",))
        self.assertEqual(result.blocked, ("denied",))

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


    def test_denied_tool_skips_only_that_action_without_escalating_permission(self):
        self.assertEqual(next_action(WorkObservation(
            authorized_actions=("DENIED_DC", "READ_GITHUB_SOURCE"),
            rejected_actions=("DENIED_DC",),
            operation_rejected=True,
        )), "READ_GITHUB_SOURCE")
        self.assertEqual(next_action(WorkObservation(
            authorized_actions=("DENIED_DC",),
            rejected_actions=("DENIED_DC",),
            ci_status="in_progress",
            operation_rejected=True,
        )), "CONTINUE_POLL")
        self.assertEqual(next_action(WorkObservation(
            authorized_actions=("DENIED_DC",),
            rejected_actions=("DENIED_DC",),
            operation_rejected=True,
        )), "READ_CURRENT_SOURCE_AND_CONTINUE")

    def test_unknown_ci_outcome_reconciles_instead_of_inventing_red(self):
        for outcome in ("", "neutral", "skipped"):
            with self.subTest(outcome=outcome):
                self.assertEqual(next_action(WorkObservation(
                    ci_status="completed", ci_conclusion=outcome,
                )), "RECONCILE_ONLY")
        self.assertEqual(next_action(WorkObservation(
            ci_status="completed", ci_conclusion="failure",
        )), "REPAIR_AND_RETEST")

    def test_next_issue_requires_independent_authorization(self):
        base = dict(localx_merged=True, issue_closed=True,
                    next_issue_checked=True, next_issue_eligible=True)
        self.assertEqual(next_action(WorkObservation(**base)),
                         "NEXT_ISSUE_AUTHORIZATION_REQUIRED")
        self.assertEqual(next_action(WorkObservation(
            **base, next_issue_authorized=True)), "START_NEXT_ISSUE")
        self.assertEqual(next_action(WorkObservation(
            localx_merged=True, issue_closed=True, next_issue_checked=True,
            no_eligible_issue_evidence="OPEN issue list checked; none eligible")),
            "RELEASED")
        self.assertEqual(next_action(WorkObservation(
            localx_merged=True, issue_closed=True, next_issue_checked=True)),
            "RECONCILE_ONLY")
        calls = []
        result = execute_authorized_step(WorkObservation(
            authorized_actions=("START_NEXT_ISSUE", "READ_SOURCE"), **base),
            {"START_NEXT_ISSUE": lambda: calls.append("wrong-issue"),
             "READ_SOURCE": lambda: calls.append("READ_SOURCE")})
        self.assertEqual(calls, ["READ_SOURCE"])
        self.assertEqual(result.completed_action, "READ_SOURCE")
        self.assertIn("START_NEXT_ISSUE", result.blocked)
        self.assertEqual(next_action(WorkObservation(
            authorized_actions=("START_NEXT_ISSUE",), **base)),
            "NEXT_ISSUE_AUTHORIZATION_REQUIRED")

    def test_localx_merge_triggers_discovery_before_closure(self):
        self.assertEqual(next_action(WorkObservation(
            localx_merged=True, issue_closed=False,
        )), "DISCOVER_NEXT_ISSUE")
        self.assertEqual(next_action(WorkObservation(
            localx_merged=True, issue_closed=False, next_issue_checked=True,
        )), "CONTINUE_FINALIZATION")
        self.assertEqual(next_action(WorkObservation(
            localx_merged=True, issue_closed=True, next_issue_started=True,
            next_issue_checked=True, next_issue_eligible=True,
            next_issue_authorized=True,
        )), "CONTINUE_NEXT_ISSUE")

if __name__ == "__main__":
    unittest.main()
