from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
SK=ROOT/'.agents'/'skills'
class RemoteContractTests(unittest.TestCase):
    def test_no_retired_remote_gates_in_active_skills(self):
        markers=('WHD_REMOTE_CONNECTION_AUTHORITY_V1','GIT_WRITE_UNLOCKED','root_local_first_gate.py','WHD_TEST_EXECUTION_RECEIPT_V1')
        for f in SK.rglob('SKILL.md'):
            content=f.read_text('utf-8')
            for marker in markers:
                with self.subTest(file=str(f), marker=marker):
                    self.assertNotIn(marker,content)
    def test_both_dispatch_and_takeover_scope(self):
        for p in ('派工/SKILL.md','執行開發任務/SKILL.md'):
            s=(SK/'engineering'/p).read_text('utf-8')
            for token in ('/接手','/派工','looaeedr/whd','localX','/推推','CI','平台'):
                with self.subTest(skill=p, token=token): self.assertIn(token,s)
    def test_fallback_respects_platform_and_local_commit(self):
        s=(SK/'misc/git-remote-sync-fallback/SKILL.md').read_text('utf-8')
        for token in ('平台','安全審查','exact tested diff','force=false','正式 X'):
            with self.subTest(token=token): self.assertIn(token,s)
    def test_governance_lane_excludes_product(self):
        from tools.change_lane_gate import classify_changes
        paths=['AGENTS.md','.agents/skills/engineering/派工/SKILL.md',
               '.agents/skills/engineering/執行開發任務/SKILL.md',
               'tests/governance/test_issue1464_dispatch_takeover_remote_contract.py']
        self.assertEqual(classify_changes(paths),'GOVERNANCE_DIRECT_X')
        self.assertEqual(classify_changes(paths+['gui.py']),'PRODUCT_LOCALX_ONLY')
    def test_reference_pitfalls_do_not_reactivate_retired_execution(self):
        git_pitfall=(ROOT/'個人AI檔案庫/踩坑庫/git_connector_target_write_pitfall.md').read_text('utf-8')
        root_pitfall=(ROOT/'個人AI檔案庫/踩坑庫/root_local_first_entry_gate_pitfall.md').read_text('utf-8')
        continuity=(ROOT/'個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md').read_text('utf-8')
        closure=(ROOT/'個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md').read_text('utf-8')
        for doc in (git_pitfall,root_pitfall,continuity,closure):
            self.assertIn("whd_doc_role: REFERENCE", doc[:200])
            self.assertIn("AGENTS.md", doc)
        self.assertNotIn("所有 repository-content 修改先走 CURRENT root-local-first router",git_pitfall)
        self.assertIn("Contents API 永遠不得直接寫 authoritative production target",git_pitfall)
        self.assertNotIn("## CURRENT workspace-first 覆寫規則",root_pitfall)
        self.assertIn("HISTORICAL/SUPERSEDED",root_pitfall)
        self.assertNotIn("CURRENT durable state、transition、resume",continuity)
        self.assertIn("當時 V2 規則（HISTORICAL",continuity)
        self.assertNotIn("都必須讓 Preflight 命中此 Skill",closure)
        self.assertIn("現在不再要求 Preflight receipt",closure)

if __name__=='__main__':unittest.main()
