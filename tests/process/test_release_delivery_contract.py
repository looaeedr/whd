"""Release /推推 must deliver an actual Windows EXE + zh-TW notes, not only a tag.

These tests verify the pure release-notes generator and the existing workflow
wiring. A unit test alone does not claim PyInstaller or GitHub upload passed.
"""
from pathlib import Path
import hashlib
import tempfile
import unittest
import zipfile

from tools.release_notes_zh_tw import build_guide, build_notes, validate_notes
from tools.repack_existing_release_notes import read_release_body, repack

ROOT = Path(__file__).resolve().parents[2]


class ZhTWReleaseNotesTest(unittest.TestCase):
    SHA = "a" * 40
    BEFORE = "b" * 40
    TAG = "v2026.10.30-x-aaaaaaaaaaaa"
    PREV = "v2026.10.29-x-bbbbbbbbbbbb"

    def test_real_changes_become_short_chinese_highlights_not_raw_titles(self):
        subjects = [
            "feat(#2379): accept original source PROFILE contour",
            "fix(#2380): durable DXF rollback refuses wrong file",
            "feat(#2378): WHD small-door prepare Frame",
            "fix(release): require Windows EXE and zh-TW notes",
            "test: Windows GUI persistence",
        ]
        notes = build_notes(
            tag=self.TAG, sha=self.SHA, previous_tag=self.PREV,
            previous_sha=self.BEFORE, titles=subjects,
        )
        for token in ("正式版更新重點", "本次主要更新", "門板開孔與幾何",
                      "多份 DXF 的資料保護", "小門與外部工具串接",
                      "Windows 交付", "尚非全面開放", self.TAG, self.SHA,
                      self.PREV, f"WHD_Windows_x64_{self.TAG}.zip"):
            with self.subTest(token=token):
                self.assertIn(token, notes)
        for source_title in subjects:
            self.assertNotIn(source_title, notes)
        self.assertNotIn("## 逐項變更", notes)
        self.assertNotIn("## What's Changed", notes)
        self.assertLessEqual(len(notes), 2000)
        validate_notes(notes)

    def test_hundreds_of_raw_english_commits_still_produce_short_zh_tw(self):
        notes = build_notes(
            tag=self.TAG, sha=self.SHA, previous_tag=self.PREV,
            previous_sha=self.BEFORE,
            titles=["fix(#2380): prevent DXF rollback error"] * 300
                   + ["test: CI shard stability"] * 70,
        )
        self.assertEqual(notes.count("- **"), 1)
        self.assertNotIn("fix(#2380):", notes)
        self.assertLessEqual(len(notes), 2000)

    def test_release_generator_rejects_english_commit_dumps(self):
        notes = build_notes(
            tag=self.TAG, sha=self.SHA, previous_tag=self.PREV,
            previous_sha=self.BEFORE, titles=["fix(#2379): DXF source edge"],
        )
        with self.assertRaisesRegex(ValueError, "RAW_COMMIT_DUMP"):
            validate_notes(notes + "\n- fix: copy English commit again\n")
        with self.assertRaisesRegex(ValueError, "MUST_BE_CONCISE"):
            validate_notes(notes + "\n" + "追加內容" * 1000)

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


class PreviousPublishedReleaseBackfillTest(unittest.TestCase):
    TAG = "v2026.10.30-x-9b7519164dd0"
    SHA = "9b7519164dd08916deff42f3ff0790707f10d371"

    def test_previous_release_reference_is_short_and_pinned(self):
        document = ROOT / "docs/releases/WHD_v2026.10.30_更新紀錄_精簡.md"
        body = read_release_body(document, tag=self.TAG, sha=self.SHA)
        self.assertIn("本次主要更新", body)
        self.assertIn("門板開孔與幾何", body)
        self.assertNotIn("## 逐項變更", body)
        self.assertLessEqual(len(body), 2000)

    def test_repacked_zip_only_changes_bundled_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old = base / f"WHD_Windows_x64_{self.TAG}.zip"
            original_exe = b"WHDEXE" + bytes(range(60))
            with zipfile.ZipFile(old, "w") as archive:
                archive.writestr("WHD/WHD.exe", original_exe)
                archive.writestr("WHD/BUILD_SOURCE.txt", f"X={self.SHA}\n")
                archive.writestr("WHD/本次更新.md", "Old English commit dump")
                archive.writestr("WHD/config.ini", "[General]\n")
            body = read_release_body(
                ROOT / "docs/releases/WHD_v2026.10.30_更新紀錄_精簡.md",
                tag=self.TAG, sha=self.SHA,
            )
            new_zip, notes = repack(old, base / "new", tag=self.TAG, sha=self.SHA, body=body)
            with zipfile.ZipFile(old) as initial, zipfile.ZipFile(new_zip) as updated:
                self.assertEqual(updated.read("WHD/WHD.exe"), original_exe)
                self.assertEqual(updated.read("WHD/config.ini"), initial.read("WHD/config.ini"))
                self.assertEqual(updated.read("WHD/BUILD_SOURCE.txt"), initial.read("WHD/BUILD_SOURCE.txt"))
                self.assertEqual(updated.read("WHD/本次更新.md").decode("utf-8"), body)
            self.assertEqual(notes.read_text(encoding="utf-8"), body)
            self.assertIn(hashlib.sha256(new_zip.read_bytes()).hexdigest(),
                          (base / "new/SHA256.txt").read_text(encoding="ascii"))
            with self.assertRaisesRegex(ValueError, "WRONG_NOTES_SOURCE"):
                repack(old, base / "wrong", tag=self.TAG, sha=self.SHA, body=body.replace(self.SHA, "f" * 40))



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
