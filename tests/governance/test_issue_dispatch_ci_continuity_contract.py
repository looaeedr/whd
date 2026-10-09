"""Regression: a dispatched product PR cannot be described as done at CI pending.

Checks all active instruction surfaces so continuity text cannot silently
disappear in a future governance-only cleanup.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SURFACES = {
    "AGENTS.md": ["CONTINUE_POLL", "合併至 localX", "close + readback", "背景輪詢", "/推推"],
    ".agents/skills/engineering/派工/SKILL.md": ["CONTINUE_POLL", "CI_SUCCESS", "CI_FAILURE", "close Issue", "/推推"],
    ".agents/skills/engineering/monitoring-remote-qa/SKILL.md": ["CONTINUE_POLL", "success", "failure", "merged", "沒有檢查結果"],
    ".agents/skills/engineering/執行開發任務/SKILL.md": ["pending", "localX", "HEAD", "結案回讀"],
}

class ContinuityContractTests(unittest.TestCase):
    def test_every_active_delivery_surface_requires_ci_continuation(self):
        for path, requirements in SURFACES.items():
            text=(ROOT/path).read_text(encoding="utf-8")
            for marker in requirements:
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker,text)

    def test_rules_do_not_imply_background_autonomy_or_reenable_flow_v2(self):
        for path in SURFACES:
            text=(ROOT/path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("回合",text)
                self.assertIn("/推推",text)


if __name__ == "__main__":
    unittest.main()
