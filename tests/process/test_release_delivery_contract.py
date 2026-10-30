"""Release /推推 must deliver an actual Windows EXE + zh-TW notes, not only a tag.

These tests verify the pure release-notes generator and the existing workflow
wiring. A unit test alone does not claim PyInstaller or GitHub upload passed.
"""
from pathlib import Path
import unittest

from tools.release_notes_zh_tw import build_guide, build_notes

ROOT = Path(__file__).resolve().parents[2]


class ZhTWReleaseNotesTest(unittest.TestCase):
    SHA = "a" * 40
    BEFORE = "b" * 40
    TAG = "v2026.10.30-x-aaaaaaaaaaaa"
    PREV = "v2026.10.29-x-bbbbbbbbbbbb"

    def test_real_changes_have_chinese_summary_and_exact_identity(self):
        notes = build_notes(
            tag=self.TAG, sha=self.SHA, previous_tag=self.PREV,
            previous_sha=self.BEFORE,
            titles=["feat(receiving): add NFB parts",
                    "fix(dxf): reject invalid holes",
                    "test: Windows GUI persistence"],
        )
        for token in ("正式版更新說明", "本次主要更新", "新增與改善",
                      "錯誤修正", "測試與驗證", self.TAG, self.SHA,
                      self.PREV, self.BEFORE,
                      f"WHD_Windows_x64_{self.TAG}.zip"):
            with self.subTest(token=token):
                self.assertIn(token, notes)
        self.assertNotIn("## What's Changed", notes)
        self.assertIn("Source code (zip)", notes)

    def test_no_fabricated_changelog_for_wrong_or_missing_data(self):
        common = dict(tag=self.TAG, sha=self.SHA, previous_tag=self.PREV,
                      previous_sha=self.BEFORE, titles=["fix: enough detail"])
        for kw in (
            {"sha": self.BEFORE},
            {"sha": "not-a-sha"},
            {"previous_sha": "not-a-sha"},
            {"tag": "not-a-version"},
            {"titles": []},
            {"titles": ["Merge pull request #5"]},
        ):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                build_notes(**dict(common, **kw))

    def test_guide_is_traditional_chinese_and_not_hardcoded_old_version(self):
        guide = build_guide(tag=self.TAG, sha=self.SHA)
        for text in ("使用說明", "如何下載", self.TAG, self.SHA, "WHD.exe",
                     "SHA256.txt", "完整解壓", "備份"):
            self.assertIn(text, guide)
        self.assertNotIn("v2026.10.20-x-3da51e25a324", guide)


class AuthorizedExeWorkflowContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official = (
            ROOT / ".github/workflows/whd-official-release.yml"
        ).read_text(encoding="utf-8")
        cls.windows = (
            ROOT / ".github/workflows/whd-windows-exe.yml"
        ).read_text(encoding="utf-8")

    def test_official_publish_waits_for_exact_windows_packaging(self):
        for expected in (
            "authorize-release:", "windows-package:", "official-release:",
            "needs: [authorize-release, windows-package]",
            "uses: ./.github/workflows/whd-windows-exe.yml",
            "release_sha: ${{ github.sha }}",
            "needs.authorize-release.outputs.eligible == 'true'",
            "WHD_Release_Notes_zh-TW.md", "WHD_Windows_Guide_zh-TW.md",
            "WHD/WHD.exe", "sha256sum --check SHA256.txt",
            "--draft=false", "OFFICIAL_WINDOWS_EXE_RELEASED",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.official)
        self.assertNotIn("--generate-notes", self.official)

    def test_windows_package_is_current_x_sha_not_old_pinned_version(self):
        for expected in (
            "workflow_call:", "pull_request:", "PRODUCT_SHA:",
            "inputs.release_sha", "actions/checkout@v4",
            "ref: ${{ env.PRODUCT_SHA }}",
            "python -m PyInstaller", "Smoke-test actual WHD.exe",
            "python product/tools/release_notes_zh_tw.py",
            "WHD_Windows_x64_$env:RELEASE_TAG.zip",
            "WHD_Release_Notes_zh-TW.md",
            "WHD_Windows_Guide_zh-TW.md",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.windows)
        self.assertNotIn("ref: 3da51e25a32491b58867a0ea1eec56087c03bad2", self.windows)
        self.assertNotIn("RELEASE_TAG: v2026.10.20-x-3da51e25a324", self.windows)


if __name__ == "__main__":
    unittest.main()
