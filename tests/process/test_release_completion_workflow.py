"""Guard the one-time official release completion for approved X fast-forward."""
from pathlib import Path
import unittest
from tools.localx_publish_gate import official_release_tag

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/whd-official-release-completion.yml"
APPROVED = "7c1d6f59e3582bdff10af1c3d432d375341c0bea"
TAG = "v2026.10.15-x-7c1d6f59e358"


class ReleaseCompletionContract(unittest.TestCase):
    def test_expected_version_is_derived_from_original_publish(self):
        self.assertEqual(official_release_tag(APPROVED, "2026-10-15T04:04:10Z"), TAG)

    def test_release_is_scoped_to_exact_accepted_product(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        for required in (
            "APPROVED_SHA: " + APPROVED,
            "APPROVED_TAG: " + TAG,
            'branches: [cleanup/2d-3d-sync]',
            'git merge-base --is-ancestor "$APPROVED_SHA" "$GITHUB_SHA"',
            '"git", "diff", "--name-only", approved, head',
            'gh api "repos/$GITHUB_REPOSITORY/pulls/1764"',
            '.merge_commit_sha == $sha',
            'if [ "$x" != "$GITHUB_SHA" ] || [ "$localx" != "$x" ]',
        ):
            with self.subTest(required=required):
                self.assertIn(required, src)

    def test_idempotent_tag_and_release_are_verified(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        for required in (
            'existing_sha', 'OFFICIAL_TAG_WRONG_SHA',
            'gh release create "$APPROVED_TAG"',
            '--target "$APPROVED_SHA"',
            'isDraft,isPrerelease,targetCommitish,url',
            'RELEASE_READBACK_FAILED',
            '"tests/process/test_release_completion_workflow.py"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, src)
        self.assertNotIn("WINDOWS_LOCALX_UAT_V1", src)
        self.assertNotIn("--force", src)


if __name__ == "__main__":
    unittest.main()
