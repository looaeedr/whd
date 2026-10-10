"""Ensure WHD public-delivery authorization is issue-scoped, not commit-scoped.

A policy regression test, NOT a substitute for an external platform's approval.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class IssueScopeApprovalContractTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_canonical_scope_boundaries(self):
        content = self.read("AGENTS.md")
        for phrase in (
            "ISSUE_SCOPE_AUTHORIZATION_REUSE",
            "不因 SHA 更新就要求重複核准公開上傳",
            "每個新 SHA 的 diff",
            "PUBLIC_UPLOAD_REVIEW_BLOCKED",
            "localX → cleanup/2d-3d-sync",
            "tools/localx_publish_gate.py",
            "未取得使用者本次對 DC／本機的明確授權",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_all_entry_skills_follow_contract(self):
        for path in (
            ".agents/skills/engineering/派工/SKILL.md",
            ".agents/skills/engineering/執行開發任務/SKILL.md",
            ".agents/skills/engineering/root-local-first/SKILL.md",
        ):
            content = self.read(path)
            with self.subTest(path=path):
                self.assertIn("ISSUE_SCOPE_AUTHORIZATION_REUSE", content)
                self.assertIn("SHA", content)
                self.assertIn("/推推", content)
                self.assertIn("DC", content)

    def test_production_publish_gate_keeps_exact_identity(self):
        gate = self.read("tools/localx_publish_gate.py")
        for phrase in ("PUBLISH_MARKER", "head_sha", "target_sha",
                       "LOCALX_PUBLISH_REQUIRES_EXPLICIT_USER_SLASH_PUSH"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, gate)

if __name__ == "__main__":
    unittest.main()
