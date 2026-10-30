"""Guard the CURRENT issue-closure skill against blanket UAT blockers.

This checks policy text; it does not claim to execute GitHub closure,
override human approval, or convert a failing end-to-end test into GREEN.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents/skills/engineering/issue-closure-gate/SKILL.md"


class IssueClosureEvidencePolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")

    def test_existing_owner_and_no_retired_receipt_gate(self):
        self.assertIn("whd_doc_role: CURRENT", self.skill)
        self.assertIn("whd_contract: issue-closure-gate-independent", self.skill)
        self.assertIn("不得依賴額外 execution record or transaction", self.skill.replace(
            "execution record 或 transaction", "execution record or transaction"
        ))
        self.assertIn("重新讀取狀態以確認", self.skill)

    def test_no_generic_manual_uat_blocker_and_no_hard_gate_bypass(self):
        for required in (
            "不以籠統人工 UAT 卡單",
            "不得事後用沒有指出具體操作",
            "使用者當次明確驗收決定",
            "明示不可替代的人工、安全、製造、CI 驗收",
            "不能自行以自動化冒充",
            "不得僅因其他分段 PASS 就關單",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.skill)

    def test_stage_evidence_never_claimed_as_single_green_e2e(self):
        for required in (
            "分段 PASS 不等於",
            "同輪端到端 E2E PASS",
            "失敗、偶發失敗、未執行",
            "不得改寫成 GREEN",
            "實際判準",
            "#1959",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.skill)

    def test_issue_closed_readback_is_not_x_release(self):
        for required in (
            "closed / completed",
            "反讀 Issue",
            "結案不等於產品已發布正式",
            "/推推",
            "不得觸碰 X",
            "DC/RC",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.skill)


if __name__ == "__main__":
    unittest.main()
