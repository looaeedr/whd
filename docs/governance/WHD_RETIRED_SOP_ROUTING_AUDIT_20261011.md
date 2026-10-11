---
whd_doc_role: REFERENCE
whd_contract: retired-sop-routing-audit-20261011
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 退役流程引用待修清查（2026-10-11）

> **REFERENCE／清查紀錄，並非 CURRENT 執行權威或修改授權。** 現行施工與治理分流一律依正式 X 的 `AGENTS.md`、CURRENT Skills 及受信任 `tools/change_lane_gate.py`。本文件不恢復 Flow v2、Preflight receipt、`GIT_WRITE_UNLOCKED`、工作槽、lease 或根目錄本機施工門檻。

## 狀態與來源

- 基準分支：`cleanup/2d-3d-sync`（正式 X）。
- 清查 PR：[#1548](https://github.com/looaeedr/whd/pull/1548)。
- 狀態：**PENDING_PRODUCT_LOCALX_ROUTE**；以下四份文件的建議修訂**尚未發布 X**。
- 機器驗證：`WHD Change Lane Gate` 對同時修改以下四個路徑的治理 PR 回傳 `PRODUCT_OR_MIXED_REQUIRES_LOCALX`。因此已在候選治理分支恢復四份文件原文，禁止放寬白名單或宣稱已修復。
- `main` 是不管理的歷史分支，**不清理、不修改、不鏡像、不合併**；本清查不以它為前置。

## 已確認的殘留

| 位置 | 內容 | 目前權威角色 | 後續處理 |
|---|---|---|---|
| `個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md` | Integration/future change 第 3 項仍要求 `root-local-first`、`GIT_WRITE_UNLOCKED`、single execution claim | CURRENT，包含產品／組裝權責 | 保留製造域契約，只更正執行路由；產品通道驗證後經 `localX`，正式 X 須當次 `/推推` |
| `個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md` | 開發驗收段落仍要求 `ROOT_SOURCE_CURRENT → PATHS_RESERVED`、`GIT_WRITE_UNLOCKED`、Phase6 Preflight | REFERENCE，仍含截角域產品規則 | 區分歷史與 domain grounding；不按舊門檻執行；經產品通道處理 |
| `個人AI檔案庫/第二層_專案與SOP/12_WHD規格書Skill前置與Grounding規則.md` | 仍把 Skill 首行公告、Phase6 Preflight、`READ_REFERENCE` 憑證及舊 Git-phase 排序當「永久」流程 | REFERENCE；不具備獨立執行權威，但路徑不在治理白名單 | 依現行 `寫成規格書` CURRENT Skill 更新參考敘述；須按機器分類處置，不能越過 X gate |
| `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md` | 2026-09-10 與 2026-10-04/05 事故段落仍把舊 `WORKSPACE_DEFAULT`、`ACQUIRE`、`FINALIZE` 標為 CURRENT | REFERENCE／事故庫，跨產品領域 | 保留事故證據，在原位置標 HISTORICAL/SUPERSEDED；路徑不在治理直送白名單 |

## 不可跳過的處置邊界

1. **不因為檔名是 Markdown 就當作純治理。** 這四個路徑目前不符合可信 X 的 `GOVERNANCE_DIRECT_X` 白名單；依機器回傳必須視為 `PRODUCT_LOCALX_ONLY`，不得加入治理 PR 直送 X。
2. 需要實際修改時，從正式 X 重新檢查來源、相關產品權威與 exact diff；依使用者指定的合法 `/派工` 雲端施工或當次明確 `/接手` RC 施工，完成產品測試、PR／CI、`localX` 整合，再由使用者當次 `/推推` 發布 X。
3. **禁止自行讀寫 DC／CoreELEC／本機**、不重啟 Flow v2、不修改 `main`、不擴大 `change_lane_gate.py` 白名單規避產品通道。
4. 這份清查紀錄和機器分類測試可經治理通道直送 X；它們**不構成上述四份文件已修復的驗收證據**。
