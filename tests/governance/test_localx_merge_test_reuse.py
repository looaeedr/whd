"""Merge validation uses tested Git tree equivalence, not an extra GUI pass."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.change_test_profile import evaluate_merge_test_reuse


class LocalXMergeTestReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

        def run(*args):
            proc = subprocess.run(
                ["git", "-C", str(self.root), *args],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return proc.stdout.decode("utf-8").strip()

        self.run_git = run
        run("init", "-q")
        run("config", "user.name", "Test")
        run("config", "user.email", "test@example.invalid")
        (self.root / "gui.py").write_text("value = 1\n", encoding="utf-8")
        run("add", "gui.py")
        run("commit", "-qm", "already tested")
        self.tested = run("rev-parse", "HEAD")
        run("commit", "--allow-empty", "-qm", "merge metadata only")
        self.same_tree = run("rev-parse", "HEAD")
        (self.root / "gui.py").write_text("value = 2\n", encoding="utf-8")
        run("commit", "-qam", "new gui code")
        self.changed_tree = run("rev-parse", "HEAD")

    def decision(self, integrated, **overrides):
        args = dict(repo_root=self.root, tested_commit=self.tested,
                    integrated_commit=integrated, ci_head_sha=self.tested,
                    ci_conclusion="SUCCESS", required_tests_complete=True)
        args.update(overrides)
        return evaluate_merge_test_reuse(**args)

    def test_new_commit_with_identical_tested_tree_reuses_results(self):
        out = self.decision(self.same_tree)
        self.assertEqual(out["decision"], "REUSE_VERIFIED")
        self.assertEqual(out["extra_test_runs"], 0)
        self.assertEqual(out["tested_tree"], out["integrated_tree"])

    def test_real_gui_change_requires_impact_analysis_not_blind_full_rerun(self):
        out = self.decision(self.changed_tree)
        self.assertEqual(out["decision"], "IMPACT_TEST_REQUIRED")
        self.assertEqual(out["changed_paths"], ["gui.py"])
        self.assertFalse(out["full_regression_default"])

    def test_missing_green_evidence_must_not_skip_tests(self):
        for updates in (
            {"ci_conclusion": "IN_PROGRESS"},
            {"ci_head_sha": self.changed_tree},
            {"required_tests_complete": False},
            {"tested_commit": "not-a-git-hash"},
        ):
            with self.subTest(updates=updates):
                out = self.decision(self.same_tree, **updates)
                self.assertEqual(out["decision"], "EVIDENCE_INCOMPLETE")

    def test_nonexistent_merged_commit_must_not_reuse(self):
        out = self.decision("f" * 40)
        self.assertEqual(out["decision"], "EVIDENCE_INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
