"""Static regression checks for DC deny-by-default executor policy.

Repo checks do NOT intercept the external DC connector; that distinction is
intentional and must remain documented in AGENTS.md.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = (
    ".agents/skills/engineering/派工/SKILL.md",
    ".agents/skills/engineering/執行開發任務/SKILL.md",
    ".agents/skills/engineering/root-local-first/SKILL.md",
)

class DCDefaultDenyContractTest(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding="utf-8")

    def test_all_global_rules_present(self):
        s = self.read("AGENTS.md")
        for value in (
            "DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE",
            "DC_ACCESS_DENIED_BY_DEFAULT",
            "DC_AUTHORIZATION_REQUIRED",
            "list_devices",
            "ping",
            "/接手",
            "/派工",
            "LOCALX_INTEGRATION",
            "base=localX",
            "exact HEAD SHA",
            "SUCCESS",
            "使用者對本次特定目的明確指示允許 DC",
            "先向使用者說明",
            "等待使用者明確核准",
            "不得誤稱 GitHub CI 能直接攔截 ChatGPT",
        ):
            with self.subTest(token=value):
                self.assertIn(value, s)

    def test_execution_skills_inherit_default_deny(self):
        for path in SKILLS:
            s = self.read(path)
            with self.subTest(path=path):
                self.assertIn("DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE", s)
                self.assertIn("DC_AUTHORIZATION_REQUIRED", s)
                self.assertIn("list_devices", s)

    def test_product_publishing_remains_explicit(self):
        gate = self.read("tools/localx_publish_gate.py")
        self.assertIn("LOCALX_PUBLISH_REQUIRES_EXPLICIT_USER_SLASH_PUSH", gate)
        self.assertIn("head_sha", gate)

if __name__ == "__main__":
    unittest.main()
