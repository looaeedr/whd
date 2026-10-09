"""Protect DM8 draft writeback from pre-authorizing unpublished product code."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
SKILL = ROOT / ".agents/skills/engineering/phase6-assembly-view-boundaries/SKILL.md"
EVIDENCE = ROOT / "docs/governance/DM8_LOCALX_COMBINED_ACCEPTANCE_STATUS_20261009.md"


class PendingWritebackTest(unittest.TestCase):
    def test_candidate_not_promoted_before_push_command(self):
        s=MAP.read_text(encoding="utf-8")
        self.assertIn("DM8-C2/B1/B2 localX 候選（REFERENCE，尚未升格 X CURRENT）",s)
        self.assertIn("不能冒充 X 現行實作",s)
        self.assertIn("正式發布後才可",s)

    def test_skill_does_not_call_unreleased_api_as_production(self):
        s=SKILL.read_text(encoding="utf-8")
        self.assertIn("只在 localX",s)
        self.assertIn("不得假設 X 已提供新 API",s)

    def test_date_scoped_evidence_is_reference_not_authority(self):
        s=EVIDENCE.read_text(encoding="utf-8")
        self.assertIn("whd_doc_role: REFERENCE",s)
        self.assertIn("未完成的正式驗收",s)
        self.assertIn("/推推",s)


if __name__=="__main__":
    unittest.main()
