"""Regression for /派工 exit decisions. Static policy/fixture tests, NOT a ChatGPT turn hook."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json"
AGENTS = ROOT / "AGENTS.md"
DISPATCH = ROOT / ".agents/skills/engineering/派工/SKILL.md"
MONITOR = ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"
WORKFLOW = ROOT / ".github/workflows/knowledge-governance-bootstrap.yml"

POLICY = json.loads(CONTRACT.read_text(encoding="utf-8"))


def turn_exit_decision(*, pr_head="a" * 40, run_head="a" * 40,
                       run_status="completed", conclusion="success",
                       localx_integrated=False, issue_closed=False,
                       next_issue_checked=False, blocker=None,
                       limit_evidence=None):
    """Executable contract fixture, not a production ChatGPT runtime interceptor."""
    if limit_evidence:
        return "REAL_RUNTIME_LIMIT"
    if blocker:
        return "VERIFIED_EXTERNAL_BLOCKER"
    if not pr_head or not run_head or pr_head != run_head:
        return "RUN_OR_HEAD_MISSING_OR_MISMATCH"
    if run_status in POLICY["nonterminal_statuses"]:
        return "CI_NONTERMINAL"
    if run_status != "completed":
        return "RUN_OR_HEAD_MISSING_OR_MISMATCH"
    if conclusion in POLICY["red_conclusions"]:
        return "CI_TERMINAL_RED"
    if conclusion != "success":
        return "RUN_OR_HEAD_MISSING_OR_MISMATCH"
    if not localx_integrated:
        return "CI_EXACT_SUCCESS_LOCALX_PENDING"
    if not issue_closed or not next_issue_checked:
        return "CI_EXACT_SUCCESS_REMAINING_DELIVERY"
    return "FULL_DELIVERY_READBACK"


class DispatchTurnExitContract(unittest.TestCase):
    def test_pending_never_looks_like_delivery(self):
        for status in POLICY["nonterminal_statuses"]:
            with self.subTest(status=status):
                key = turn_exit_decision(run_status=status, conclusion=None)
                self.assertEqual(key, "CI_NONTERMINAL")
                result = POLICY["decisions"][key]
                self.assertEqual(result["action"], "CONTINUE_POLL")
                self.assertFalse(result["normal_completion"])
                self.assertFalse(result["may_end_turn_without_completion"])

    def test_head_mismatch_and_no_run_deny_green(self):
        for head in (None, "", "b" * 40):
            with self.subTest(head=head):
                key = turn_exit_decision(run_head=head)
                self.assertEqual(key, "RUN_OR_HEAD_MISSING_OR_MISMATCH")
                self.assertEqual(POLICY["decisions"][key]["action"], "RECONCILE_ONLY")

    def test_terminal_failure_must_be_repaired(self):
        for conclusion in POLICY["red_conclusions"]:
            with self.subTest(conclusion=conclusion):
                key = turn_exit_decision(conclusion=conclusion)
                self.assertEqual(POLICY["decisions"][key]["action"], "REPAIR_AND_RETEST")
                self.assertFalse(POLICY["decisions"][key]["normal_completion"])

    def test_ci_success_does_not_allow_exit_before_delivery(self):
        cases = [
            ({}, "LOCALX_INTEGRATION_PENDING"),
            ({"localx_integrated": True}, "CONTINUE_FINALIZATION"),
            ({"localx_integrated": True, "issue_closed": True},
             "CONTINUE_FINALIZATION"),
            ({"localx_integrated": True, "issue_closed": True,
              "next_issue_checked": True}, "RELEASED"),
        ]
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                key = turn_exit_decision(**kwargs)
                self.assertEqual(POLICY["decisions"][key]["action"], expected)
                self.assertEqual(POLICY["decisions"][key]["normal_completion"],
                                 expected == "RELEASED")

    def test_blocked_turn_exit_cannot_claim_done(self):
        for kwargs, expected in [
            ({"blocker": "HTTP 403 and run link"}, "BLOCKED_WITH_EVIDENCE"),
            ({"limit_evidence": "runtime stopped tools"}, "RUNTIME_LIMIT_UNRESOLVED"),
        ]:
            key = turn_exit_decision(**kwargs)
            result = POLICY["decisions"][key]
            self.assertEqual(result["action"], expected)
            self.assertTrue(result["may_end_turn_without_completion"])
            self.assertFalse(result["normal_completion"])
            self.assertIn("next_exact_action", result["requires"])

    def test_contract_applies_to_all_active_instruction_surfaces(self):
        for path in (AGENTS, DISPATCH, MONITOR):
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path)):
                for marker in (
                    "DISPATCH_TURN_EXIT_GATE_V1",
                    "CONTINUE_POLL",
                    "RECONCILE_ONLY",
                    "REPAIR_AND_RETEST",
                    "LOCALX_INTEGRATION_PENDING",
                    "CONTINUE_FINALIZATION",
                    "BLOCKED_WITH_EVIDENCE",
                    "RUNTIME_LIMIT_UNRESOLVED",
                ):
                    self.assertIn(marker, content)
                self.assertIn("run_id", content)
                self.assertIn("SHA", content)
        self.assertIn("不會在回合結束後自行喚醒", AGENTS.read_text(encoding="utf-8"))
        self.assertIn("沒有可由此文件攔截", DISPATCH.read_text(encoding="utf-8"))

    def test_github_only_integration_requires_scope_and_does_not_claim_dc_failure(self):
        modes = POLICY["integration_routes"]
        self.assertEqual(set(modes), {
            "DC_LOCALX_FIRST", "DC_UNREACHABLE_FALLBACK", "GITHUB_ONLY_EXPLICIT_SCOPE"
        })
        github = modes["GITHUB_ONLY_EXPLICIT_SCOPE"]
        self.assertIn("user_explicit_remote_localX_merge_authorization_for_same_issue_pr",
                      github["requires"])
        self.assertIn("expected_head_sha", github["requires"])
        self.assertIn("GITHUB_ONLY_LOCALX_MERGED + LOCALX_SYNC_PENDING",
                      github["on_success"])
        self.assertIn("fabricated_dc_disconnection", github["forbids"])
        self.assertIn("assuming_local_localX_head", github["forbids"])
        self.assertIn("verified_dc_connection_failure",
                      modes["DC_UNREACHABLE_FALLBACK"]["requires"])
        for path in (AGENTS, DISPATCH, MONITOR):
            text = path.read_text(encoding="utf-8")
            self.assertIn("GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1", text)
            self.assertIn("LOCALX_SYNC_PENDING", text)
            self.assertIn("DC_UNREACHABLE", text)
        self.assertIn("執行者自己在 PR 寫的", MONITOR.read_text("utf-8"))

    def test_machine_contract_and_governance_scope(self):
        self.assertEqual(POLICY["contract"], "WHD_DISPATCH_TURN_EXIT_GATE_V1")
        self.assertEqual(set(POLICY["decisions"]), set(POLICY["ordering"]))
        self.assertEqual([key for key, spec in POLICY["decisions"].items()
                          if spec["normal_completion"]],
                         ["FULL_DELIVERY_READBACK"])
        self.assertIn("test_dispatch_turn_exit_gate_contract.py",
                      WORKFLOW.read_text(encoding="utf-8"))
        from tools.change_lane_gate import classify_changes
        paths = [
            "AGENTS.md", ".agents/skills/engineering/派工/SKILL.md",
            ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
            ".agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json",
            "tests/governance/test_dispatch_turn_exit_gate_contract.py",
            ".github/workflows/knowledge-governance-bootstrap.yml",
        ]
        self.assertEqual(classify_changes(paths), "GOVERNANCE_DIRECT_X")
        self.assertEqual(classify_changes(paths + ["gui.py"]), "PRODUCT_LOCALX_ONLY")


if __name__ == "__main__":
    unittest.main()
