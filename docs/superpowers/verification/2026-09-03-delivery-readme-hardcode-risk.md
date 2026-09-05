# 2026-09-03 DELIVERY_README 檔名硬編碼風險處理證據

## Knowledge Preflight

- READ_SKILL: phase6-release-packaging
- READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
- READ_REFERENCE: release_required_artifacts.json

## 判斷

- `DELIVERY_README.md` 不應作為 release policy、runtime oracle 或固定檔名契約。
- 交付語意的正式來源應維持在 `release_required_artifacts.json`、`AI_HANDOFF.md`、`CONTEXT.md`、專項 spec / verification 與踩坑庫。
- 測試若需要檢查交付文件語意，應檢查「目前存在的文件內容」與 canonical source，而不是讓歷史檔名成為必須存在的硬依賴。
