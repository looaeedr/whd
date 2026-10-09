"""Guard DM8 published owner authority against stale pre-publish wording."""
import unittest
from pathlib import Path
R=Path(__file__).resolve().parents[2]
M=R/"個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
B=R/"個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md"
S=R/".agents/skills/engineering/phase6-assembly-view-boundaries/SKILL.md"
E=R/"docs/governance/DM8_LOCALX_COMBINED_ACCEPTANCE_STATUS_20261009.md"

class DM8PublishedWritebackTest(unittest.TestCase):
    def test_current_requires_published_exact_pr(self):
        t=M.read_text("utf-8")
        self.assertIn("DM8-C2 製造場景公開 access CURRENT",t)
        self.assertIn("DM8-B1/B2 Fold Designer Capability CURRENT",t)
        self.assertIn("ddfe789f54c865cca1a77ce143d79e0ef141ff29",t)
        self.assertNotIn("localX 候選（REFERENCE，尚未升格 X CURRENT）",t)
    def test_bridge_and_skill_no_old_candidate_wording(self):
        bridge = B.read_text("utf-8")
        self.assertIn("CURRENT composition owner", bridge)
        self.assertIn("second composition root", bridge)
        t=S.read_text("utf-8")
        self.assertIn("正式 scene access seam",t)
        self.assertNotIn("只在 localX",t)
    def test_evidence_keeps_reference_role(self):
        t=E.read_text("utf-8")
        self.assertIn("whd_doc_role: REFERENCE",t)
        self.assertIn("DM8_X_PUBLISH_ACCEPTED_V1",t)
        self.assertIn("37911058569",t)
        self.assertIn("98d42b1bef8c1b6077eacfaada183216cfe33967",t)

if __name__=="__main__":
    unittest.main()
