"""Entry-point isolation: /派工 may never use a user's machine as executor."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
DISPATCH = ROOT / ".agents/skills/engineering/派工/SKILL.md"
TAKEOVER = ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md"
LOCAL = ROOT / ".agents/skills/engineering/root-local-first/SKILL.md"


class DispatchRemoteOnlyContract(unittest.TestCase):
    def test_dispatch_requires_truly_remote_execution(self):
        text = DISPATCH.read_text(encoding="utf-8")
        for marker in (
            "DISPATCH_REMOTE_ONLY",
            "execution_location=GITHUB|SCHEDULER|REMOTE_ACTION",
            "DISPATCH_LOCAL_EXECUTION_DENIED",
            "REMOTE_EXECUTOR_UNAVAILABLE",
            "GitHub 遠端",
            "本機 `localX` 已更新",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn("能直接完成時直接修改、測試", text)
        self.assertNotIn("本機測試與 commit", text)

    def test_no_implicit_rc_or_local_fallback(self):
        text = DISPATCH.read_text(encoding="utf-8")
        for marker in (
            "絕不能在使用者本機施工",
            "Remote Desktop Commander",
            "/workspace/whd",
            "禁止把 `/派工` 隱性改成 `/接手`",
            "只有使用者明確下 `/接手`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertIn("不能用", AGENTS.read_text("utf-8"))

    def test_takeover_alone_owns_rc_local_path(self):
        text = TAKEOVER.read_text(encoding="utf-8")
        root_local = LOCAL.read_text(encoding="utf-8")
        for surface in (text, root_local):
            with self.subTest(surface=surface[:45]):
                self.assertIn("/接手", surface)
                self.assertIn("Remote Desktop Commander", surface)
                self.assertIn("/workspace/whd", surface)
                self.assertIn("/派工", surface)
                self.assertIn("不得", surface)

    def test_agency_and_release_separation(self):
        text = AGENTS.read_text(encoding="utf-8")
        for marker in (
            "DISPATCH_REMOTE_ONLY",
            "DISPATCH_LOCAL_EXECUTION_DENIED",
            "REMOTE_EXECUTOR_UNAVAILABLE",
            "工作位置完全分流",
            "本機 `localX` 已同步",
            "/推推",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_only_governance_files_are_changed(self):
        from tools.change_lane_gate import classify_changes
        paths = [
            "AGENTS.md",
            ".agents/skills/engineering/派工/SKILL.md",
            ".agents/skills/engineering/執行開發任務/SKILL.md",
            ".agents/skills/engineering/root-local-first/SKILL.md",
            "tests/governance/test_dispatch_remote_only_contract.py",
            ".github/workflows/knowledge-governance-bootstrap.yml",
        ]
        self.assertEqual(classify_changes(paths), "GOVERNANCE_DIRECT_X")
        self.assertEqual(
            classify_changes(paths + ["phase6_manufacturing_adapter.py"]),
            "PRODUCT_LOCALX_ONLY",
        )


if __name__ == "__main__":
    unittest.main()
