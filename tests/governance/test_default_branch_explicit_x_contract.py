"""Keep GitHub's default main branch historical and require explicit WHD X refs."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_DEFAULT_BRANCH_FAIL_CLOSED_V1.json"
AGENTS = ROOT / "AGENTS.md"


class DefaultBranchExplicitXContract(unittest.TestCase):
    def test_main_is_unmanaged_history_not_tombstone_target(self):
        doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "CURRENT")
        self.assertEqual(doc["production_branch"], "cleanup/2d-3d-sync")
        self.assertEqual(doc["default_branch"], "main")
        self.assertEqual(doc["policy"], "MAIN_HISTORICAL_UNMANAGED_EXPLICIT_X_ONLY")
        self.assertEqual(doc["main_disposition"], "HISTORICAL_UNMANAGED_DO_NOT_MUTATE")
        self.assertNotIn("required_main_stub_paths", doc)
        self.assertEqual(doc["retired_main_tree_policy"]["status"], "RETIRED")
        for op in ("cleanup", "delete", "rewrite_as_stub", "governance_mirror",
                   "synchronize", "merge", "rebase", "force_push"):
            with self.subTest(op=op):
                self.assertIn(op, doc["main_automatic_mutations_forbidden"])

    def test_canonical_reads_fail_closed_when_ref_unspecified(self):
        doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(doc["canonical_read_ref"], doc["production_branch"])
        self.assertEqual(doc["unspecified_ref_policy"], "FAIL_CLOSED_REQUIRE_EXPLICIT_X")
        self.assertEqual(doc["main_read_policy"], "HISTORICAL_CONTEXT_ONLY_NO_EXECUTION_AUTHORITY")
        agents = AGENTS.read_text(encoding="utf-8")
        for required in ("MAIN_HISTORICAL_UNMANAGED_EXPLICIT_X_ONLY",
                         "ref=cleanup/2d-3d-sync", "不清理", "不得再次啟動 `main` 清理"):
            with self.subTest(required=required):
                self.assertIn(required, agents)


if __name__ == "__main__":
    unittest.main()
