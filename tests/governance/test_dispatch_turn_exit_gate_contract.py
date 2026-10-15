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
                       next_issue_checked=False, next_issue_found=False,
                       next_issue_start_evidence=None, no_eligible_evidence=None,
                       blocker=None, limit_evidence=None):
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
    # Discovery starts at localX merge readback, not at Issue close.
    if not next_issue_checked:
        return "NEXT_ISSUE_DISCOVERY_REQUIRED"
    if not issue_closed:
        return "CI_EXACT_SUCCESS_REMAINING_DELIVERY"
    if next_issue_found:
        if next_issue_start_evidence:
            return "NEXT_ISSUE_ALREADY_STARTED"
        return "NEXT_ISSUE_START_REQUIRED"
    if no_eligible_evidence:
        return "FULL_DELIVERY_READBACK"
    return "NEXT_ISSUE_DISCOVERY_REQUIRED"


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
            ({"localx_integrated": True}, "DISCOVER_NEXT_ISSUE"),
            ({"localx_integrated": True, "issue_closed": True},
             "DISCOVER_NEXT_ISSUE"),
            ({"localx_integrated": True, "next_issue_checked": True},
             "CONTINUE_FINALIZATION"),
            ({"localx_integrated": True, "issue_closed": True,
              "next_issue_checked": True}, "DISCOVER_NEXT_ISSUE"),
            ({"localx_integrated": True, "issue_closed": True,
              "next_issue_checked": True, "next_issue_found": True},
             "START_NEXT_ISSUE"),
            ({"localx_integrated": True, "issue_closed": True,
              "next_issue_checked": True, "next_issue_found": True,
              "next_issue_start_evidence": "#1800 / branch / real first action"},
             "CONTINUE_NEXT_ISSUE"),
            ({"localx_integrated": True, "issue_closed": True,
              "next_issue_checked": True,
              "no_eligible_evidence": "OPEN issue list checked; none eligible"},
             "RELEASED"),
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
        common_markers = (
            "DISPATCH_TURN_EXIT_GATE_V1", "CONTINUE_POLL",
            "RECONCILE_ONLY", "REPAIR_AND_RETEST",
            "BLOCKED_WITH_EVIDENCE", "RUNTIME_LIMIT_UNRESOLVED",
        )
        for path in (AGENTS, DISPATCH, MONITOR):
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path)):
                for marker in common_markers:
                    self.assertIn(marker, content)
                self.assertIn("SHA", content)
                self.assertIn("GITHUB_LOCALX_FIRST", content)
        # Orchestration/Issue close belongs to the dispatch contract; QA
        # observes exact SHA CI and must not create a second routing policy.
        for path in (AGENTS, DISPATCH):
            content = path.read_text(encoding="utf-8")
            for marker in ("LOCALX_INTEGRATION_PENDING", "CONTINUE_FINALIZATION", "run_id"):
                self.assertIn(marker, content)
        self.assertIn("不會在回合結束後自行喚醒", AGENTS.read_text(encoding="utf-8"))
        self.assertIn("沒有可由此文件攔截", DISPATCH.read_text(encoding="utf-8"))
        self.assertIn("未建立排程的聊天不具背景輪詢能力", MONITOR.read_text("utf-8"))

    def test_github_first_integration_and_explicit_dc_are_scoped(self):
        modes = POLICY["integration_routes"]
        self.assertEqual(set(modes), {"GITHUB_LOCALX_FIRST", "EXPLICIT_DC_LOCALX"})
        self.assertEqual(POLICY["default_integration_route"], "GITHUB_LOCALX_FIRST")
        github = modes["GITHUB_LOCALX_FIRST"]
        for requirement in (
            "same_issue_execution_authorization", "exact_ci_success",
            "pr_base_localX", "mergeable_pr", "base_change_impact_checked",
            "expected_head_sha",
        ):
            self.assertIn(requirement, github["requires"])
        self.assertIn("GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING",
                      github["on_success"])
        for forbidden in (
            "unapproved_dc_probe", "pretending_windows_is_synced",
            "publishing_product_x", "force_reset",
        ):
            self.assertIn(forbidden, github["forbids"])
        explicit = modes["EXPLICIT_DC_LOCALX"]
        self.assertIn("explicit_current_dc_device_and_operation_authorization",
                      explicit["requires"])
        self.assertIn("external_dc_approval", explicit["requires"])
        self.assertEqual(POLICY["route_selection_order"][0].startswith("Use EXPLICIT_DC_LOCALX only"), True)
        for path in (AGENTS, DISPATCH, MONITOR):
            content = path.read_text(encoding="utf-8")
            self.assertIn("GITHUB_LOCALX_FIRST", content)
            self.assertNotIn("DC_LOCALX_FIRST", content)
            self.assertNotIn("DC_UNREACHABLE_FALLBACK", content)

    def test_machine_contract_and_governance_scope(self):
        self.assertEqual(POLICY["contract"], "WHD_DISPATCH_TURN_EXIT_GATE_V1")
        self.assertEqual(set(POLICY["decisions"]), set(POLICY["ordering"]))
        self.assertEqual([key for key, spec in POLICY["decisions"].items()
                          if spec["normal_completion"]],
                         ["FULL_DELIVERY_READBACK"])
        self.assertIn("verified_no_eligible_issue_evidence",
                      POLICY["decisions"]["FULL_DELIVERY_READBACK"]["requires"])
        for key in ("NEXT_ISSUE_DISCOVERY_REQUIRED",
                    "NEXT_ISSUE_START_REQUIRED", "NEXT_ISSUE_ALREADY_STARTED"):
            self.assertFalse(POLICY["decisions"][key]["normal_completion"])
            self.assertFalse(POLICY["decisions"][key]["may_end_turn_without_completion"])
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
