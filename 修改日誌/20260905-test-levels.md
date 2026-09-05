# 2026-09-05 測試策略調整紀錄

### [22:00:00] 變更紀錄
- **變更檔案**：`.agents/skills/engineering/phase6-release-packaging/SKILL.md`
- **Git 備份點**：`backup/20260905-2200-test-levels`
- **Git Commit**：本次 Skill 修改完成後補記
- **修改摘要**：將每次小修改都執行完整回歸，調整為分級測試：小修改先做快速／對應測試並累積測試債；達到累積門檻或跨模組／核心高風險修改時，才執行完整 Headless + GUI Gate。完整 Gate 通過後清零累積測試債。出包流程仍維持正式完整回歸要求，且正常封包後不重跑完整 GUI。
