"""Fast lane is fail-closed for product and mixed repository changes."""
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

from tools.change_lane_gate import (
    ChangeLaneDenied,
    classify_changes,
    evaluate_pr,
    is_governance_file,
    is_safe_product_ci_scheduling_edit,
    classify_verified_pr_changes,
    PROTECTED_PRODUCT_CI_WORKFLOW,
    parse_name_status_zero,
    require_x_only_governance_history,
)


BASE = "a" * 40
HEAD = "b" * 40


def pr_event(*, branch="governance/direct-x", sha=HEAD):
    repo = {"full_name": "looaeedr/whd"}
    return {
        "repository": repo,
        "pull_request": {
            "number": 42,
            "base": {"ref": "cleanup/2d-3d-sync", "sha": BASE, "repo": repo},
            "head": {"ref": branch, "sha": sha, "repo": repo},
        },
    }


def publish_comment():
    return [{
        "user": {"login": "looaeedr", "type": "User"},
        "body": "\n".join([
            "/推推", "WHD_LOCALX_PUBLISH_AUTH_V1",
            "repo=looaeedr/whd", "pr=42", "source=localX",
            "head=" + HEAD, "target=cleanup/2d-3d-sync", "base=" + BASE,
        ]),
    }]


class ChangeLaneTests(unittest.TestCase):
    def test_explicit_nonproduct_paths_are_allowed(self):
        for path in (
            "AGENTS.md",
            ".agents/skills/engineering/推推/SKILL.md",
            ".agents/contracts/safety.json",
            ".github/workflows/whd-change-lane-hard-gate.yml",
            "docs/governance/policy.md",
            "個人AI檔案庫/踩坑庫/issue.md",
            "tools/change_lane_gate.py",
            "tests/process/test_change_lane_gate.py",
            "tests/governance/test_rules.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_governance_file(path))
        self.assertEqual(classify_changes([
            "AGENTS.md", "docs/governance/policy.md",
            "tests/process/test_change_lane_gate.py",
        ]), "GOVERNANCE_DIRECT_X")

    def test_product_and_unknown_are_denied_fast_lane(self):
        for path in (
            "gui.py",
            "ae_engine/certified_relief_registry.py",
            "gui_modules/editor.py",
            "tests/test_dxf_acceptance.py",
            "tests/process/test_unknown.py",
            "docs/specs/product-dimensions.md",
            "基準檔/截角資料庫/certified_relief_rules.json",
            "requirements.txt",
            "foo.dat",
            "../AGENTS.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(classify_changes(["AGENTS.md", path]),
                                 "PRODUCT_LOCALX_ONLY")

    def test_ci_scheduling_is_governance_only_when_trusted_diff_proves_safe(self):
        workflow = PROTECTED_PRODUCT_CI_WORKFLOW
        original = (
            "name: WHD Product Regression\n"
            "on:\n  pull_request:\n    branches: [localX]\n"
            "jobs:\n  product-regression:\n"
            "    name: Canonical Product Regression\n"
            "    runs-on: ubuntu-latest\n    timeout-minutes: 50\n"
            "    steps:\n      - run: python tools/product_ci_regression.py\n"
        )
        adjusted = original.replace("timeout-minutes: 50", "timeout-minutes: 45")
        adjusted = adjusted.replace("runs-on: ubuntu-latest", "runs-on: ubuntu-24.04")
        self.assertFalse(is_governance_file(workflow))
        self.assertEqual(classify_changes([workflow]), "PRODUCT_LOCALX_ONLY")
        self.assertTrue(is_safe_product_ci_scheduling_edit(original, adjusted))
        self.assertEqual(classify_changes(
            [workflow, "AGENTS.md"], verified_ci_scheduling=True,
        ), "GOVERNANCE_DIRECT_X")
        proc = [
            subprocess.CompletedProcess([], 0, original.encode()),
            subprocess.CompletedProcess([], 0, adjusted.encode()),
        ]
        with patch("tools.change_lane_gate.subprocess.run", side_effect=proc):
            self.assertEqual(classify_verified_pr_changes(
                Path("."), BASE, HEAD, [workflow, "AGENTS.md"],
            ), "GOVERNANCE_DIRECT_X")

    def test_ci_scheduling_fast_lane_rejects_acceptance_mutations(self):
        workflow = PROTECTED_PRODUCT_CI_WORKFLOW
        original = (
            "on:\n  pull_request:\n    branches: [localX]\n"
            "jobs:\n  product-regression:\n"
            "    name: Canonical Product Regression\n"
            "    runs-on: ubuntu-latest\n    timeout-minutes: 50\n"
            "    strategy:\n      max-parallel: 3\n"
            "    steps:\n      - run: python tools/product_ci_regression.py\n"
        )
        unsafe = (
            original.replace("run: python tools/product_ci_regression.py", "run: echo GREEN"),
            original.replace("branches: [localX]", "branches: [main]"),
            original.replace("name: Canonical Product Regression", "name: Always Green"),
            original.replace("timeout-minutes: 50", "timeout-minutes: 1"),
            original.replace("max-parallel: 3", "max-parallel: 0"),
            original.replace("timeout-minutes: 50", "if: always()"),
            original.replace("    steps:", "    if: false\n    steps:"),
            original.replace("timeout-minutes: 50", "timeout-minutes: 50\n    if: false"),
            original.replace("    steps:\n", ""),
            original.replace("runs-on: ubuntu-latest", "runs-on: windows-latest"),
            original.replace("      - run:", "      - name: skip tests\n      - run:"),
            original + "\n    retention-days: 7\n",
            "",
        )
        for changed in unsafe:
            with self.subTest(changed=changed[-90:]):
                self.assertFalse(is_safe_product_ci_scheduling_edit(original, changed))
                proc = [
                    subprocess.CompletedProcess([], 0, original.encode()),
                    subprocess.CompletedProcess([], 0, changed.encode()),
                ]
                with patch("tools.change_lane_gate.subprocess.run", side_effect=proc):
                    self.assertEqual(classify_verified_pr_changes(
                        Path("."), BASE, HEAD, [workflow],
                    ), "PRODUCT_LOCALX_ONLY")
        self.assertFalse(is_safe_product_ci_scheduling_edit(original, original))

    def test_acceptance_authority_code_never_becomes_direct_x(self):
        for file in (
            "tools/product_ci_regression.py",
            "tools/product_ci_green_reuse.py",
            "tools/whd_v15_acceptance_evidence.py",
            "tests/process/test_product_ci_sharding.py",
            "tests/test_issue1469_v15_acceptance.py",
            "docs/superpowers/verification/issue1469-v15-acceptance-matrix.json",
        ):
            with self.subTest(file=file):
                self.assertEqual(classify_changes([file]), "PRODUCT_LOCALX_ONLY")
                self.assertEqual(
                    classify_changes([file, "AGENTS.md"], verified_ci_scheduling=True),
                    "PRODUCT_LOCALX_ONLY",
                )

    def test_protected_workflow_missing_git_evidence_fails_closed(self):
        with patch("tools.change_lane_gate.subprocess.run", side_effect=OSError("no git")):
            self.assertEqual(classify_verified_pr_changes(
                Path("."), BASE, HEAD, [PROTECTED_PRODUCT_CI_WORKFLOW],
            ), "PRODUCT_LOCALX_ONLY")
        with self.assertRaisesRegex(ChangeLaneDenied, "INVALID_COMMIT_SHA"):
            classify_verified_pr_changes(
                Path("."), "bad", HEAD, [PROTECTED_PRODUCT_CI_WORKFLOW],
            )

    def test_protected_acceptance_workflow_requires_localx_and_slash_push(self):
        with self.assertRaisesRegex(ChangeLaneDenied, "REQUIRES_LOCALX"):
            evaluate_pr(event=pr_event(), changed_paths=[PROTECTED_PRODUCT_CI_WORKFLOW])
        with self.assertRaisesRegex(ChangeLaneDenied, "EXACT_USER_SLASH_PUSH"):
            evaluate_pr(event=pr_event(branch="localX"),
                        changed_paths=[PROTECTED_PRODUCT_CI_WORKFLOW])
        passed = evaluate_pr(event=pr_event(),
                             changed_paths=[PROTECTED_PRODUCT_CI_WORKFLOW],
                             verified_ci_scheduling=True)
        self.assertEqual(passed["lane"], "GOVERNANCE_DIRECT_X")

    def test_empty_pr_is_rejected(self):
        with self.assertRaisesRegex(ChangeLaneDenied, "EMPTY_PR_DIFF"):
            classify_changes([])

    def test_governance_direct_x_branch_passes_without_slash_push(self):
        r = evaluate_pr(event=pr_event(), changed_paths=[
            "AGENTS.md", ".agents/skills/engineering/派工/SKILL.md",
        ])
        self.assertEqual(r["lane"], "GOVERNANCE_DIRECT_X")

    def test_governance_requires_named_fast_lane_branch(self):
        with self.assertRaisesRegex(ChangeLaneDenied, "DEDICATED_BRANCH"):
            evaluate_pr(event=pr_event(branch="work/issue-1"), changed_paths=["AGENTS.md"])

    def test_product_and_mixed_require_localx(self):
        for paths in (["gui.py"], ["AGENTS.md", "gui.py"], ["some_unknown.txt"]):
            with self.subTest(paths=paths):
                with self.assertRaisesRegex(ChangeLaneDenied, "REQUIRES_LOCALX"):
                    evaluate_pr(event=pr_event(), changed_paths=paths)

    def test_localx_product_requires_owner_slash_push(self):
        event = pr_event(branch="localX")
        with self.assertRaisesRegex(ChangeLaneDenied, "EXACT_USER_SLASH_PUSH"):
            evaluate_pr(event=event, changed_paths=["gui.py"], comments=[])
        r = evaluate_pr(event=event, changed_paths=["gui.py"], comments=publish_comment())
        self.assertEqual(r["lane"], "PRODUCT_LOCALX_ONLY")

    def test_invalid_or_stale_owner_approval_is_denied(self):
        event = pr_event(branch="localX")
        comments = publish_comment()
        comments[0]["user"]["login"] = "github-actions[bot]"
        with self.assertRaises(ChangeLaneDenied):
            evaluate_pr(event=event, changed_paths=["gui.py"], comments=comments)
        event["pull_request"]["head"]["sha"] = "c" * 40
        with self.assertRaises(ChangeLaneDenied):
            evaluate_pr(event=event, changed_paths=["gui.py"], comments=publish_comment())

    def test_wrong_target_and_fork_are_denied(self):
        event = pr_event()
        event["pull_request"]["base"]["ref"] = "main"
        with self.assertRaisesRegex(ChangeLaneDenied, "INVALID_EXACT_X"):
            evaluate_pr(event=event, changed_paths=["AGENTS.md"])
        event = pr_event()
        event["pull_request"]["head"]["repo"] = {"full_name": "another/whd"}
        with self.assertRaisesRegex(ChangeLaneDenied, "FORK_NOT_SUPPORTED"):
            evaluate_pr(event=event, changed_paths=["AGENTS.md"])

    def test_rename_checks_both_old_and_new_paths(self):
        paths = parse_name_status_zero(
            b"R100\x00gui.py\x00docs/governance/gui.md\x00"
        )
        self.assertEqual(paths, ["gui.py", "docs/governance/gui.md"])
        self.assertEqual(classify_changes(paths), "PRODUCT_LOCALX_ONLY")

    def test_x_ahead_governance_history_allows_docs_without_presync(self):
        commit = "c" * 40
        responses = [
            subprocess.CompletedProcess([], 0, (commit + "\n").encode()),
            subprocess.CompletedProcess([], 0, ("d" * 40 + "\n").encode()),
            subprocess.CompletedProcess([], 0, b"M\0AGENTS.md\0"),
        ]
        with patch("tools.change_lane_gate.subprocess.run", side_effect=responses) as run:
            self.assertEqual(
                require_x_only_governance_history(Path("."), BASE, HEAD), 1
            )
            self.assertEqual(run.call_count, 3)
            self.assertEqual(run.call_args_list[0].args[0][1], "rev-list")

    def test_x_ahead_product_or_unknown_is_blocked(self):
        for changed in (b"M\0gui.py\0", b"M\0docs/specs/unknown.md\0"):
            commit = "c" * 40
            responses = [
                subprocess.CompletedProcess([], 0, (commit + "\n").encode()),
                subprocess.CompletedProcess([], 0, ("d" * 40 + "\n").encode()),
                subprocess.CompletedProcess([], 0, changed),
            ]
            with self.subTest(changed=changed):
                with patch("tools.change_lane_gate.subprocess.run", side_effect=responses):
                    with self.assertRaisesRegex(
                        ChangeLaneDenied, "X_AHEAD_NON_GOVERNANCE_BLOCKED"
                    ):
                        require_x_only_governance_history(Path("."), BASE, HEAD)

    def test_x_ahead_unverifiable_history_is_blocked(self):
        with patch("tools.change_lane_gate.subprocess.run", side_effect=OSError("missing git")):
            with self.assertRaisesRegex(ChangeLaneDenied, "X_AHEAD_HISTORY_UNVERIFIABLE"):
                require_x_only_governance_history(Path("."), BASE, HEAD)

    def test_x_already_contained_in_localx_is_no_op(self):
        with patch("tools.change_lane_gate.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, b"")):
            self.assertEqual(require_x_only_governance_history(Path("."), BASE, HEAD), 0)

    def test_unrecognized_status_or_malformed_path_fails(self):
        for blob in (b"Z\x00AGENTS.md\x00", b"M\x00../AGENTS.md\x00",
                     b"R100\x00AGENTS.md\x00"):
            with self.subTest(blob=blob):
                with self.assertRaises(ChangeLaneDenied):
                    parse_name_status_zero(blob)


if __name__ == "__main__":
    unittest.main()
