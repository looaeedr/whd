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
- **原清查時狀態（HISTORICAL）**：`PENDING_PRODUCT_LOCALX_ROUTE`；指 PR #1548 當時四份文件的修訂尚未發布 X，不代表正式 X 目前仍待修。以文末 fresh readback 為準。
- 機器驗證：`WHD Change Lane Gate` 對同時修改以下四個路徑的治理 PR 回傳 `PRODUCT_OR_MIXED_REQUIRES_LOCALX`。因此已在候選治理分支恢復四份文件原文，禁止放寬白名單或宣稱已修復。
- `main` 是不管理的歷史分支，**不清理、不修改、不鏡像、不合併**；本清查不以它為前置。

## 原清查時已確認的殘留（HISTORICAL；不是現行待辦）

下表保存當時診斷及原先的合法施工路由；不得直接把「後續處理」當作當前尚未完成的工單，也不得照表覆蓋已修正的正式 X 原文。

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


## 補充清查：入口導覽文件（2026-10-11）

下列兩份**在原清查當時**的 X 入口／導覽文件原文尚未修改；這些路徑同樣不在目前受信任 `change_lane_gate.py` 的治理直送白名單，不能因為內容是 Markdown 就繞過產品通道：

| 路徑 | 角色／殘留 | 後續 |
|---|---|---|
| `README.md` | REFERENCE，Current authority pointers 把 `AGENTS.md` 描述為「Agent 啟動、Preflight、派工與驗收流程入口」 | 舊 Preflight 已非 CURRENT 必經門檻；需由合法產品／混合通道修正導覽文字 |
| `handoff/00_AI_HANDOFF_README.md` | MIRROR／POINTER_ONLY，Current entry 把 `AGENTS.md` 描述為「Agent 啟動與 Preflight process」 | 保留指向 `AGENTS.md` 的相容路徑，但不能恢復舊 Preflight；按路徑分類處置 |

本輪也已針對正式 X 的 Catalog 規則下 **47 份 canonical 候選 `SKILL.md`** 逐份掃描退役交易關鍵字。完成之修復：[#1555](https://github.com/looaeedr/whd/pull/1555) 的問答／技能發現／MCP／架構掃描入口，以及 [#1556](https://github.com/looaeedr/whd/pull/1556) 的正式出包施工分流。其餘命中包含**明確標示退役的歷史說明**，不能只因字串存在就當成 ACTIVE 舊門檻；這是關鍵字清查而非所有技能語意／產品驗收通過證明。

- 原清查待修範圍：當時上述 2 份導覽文件 + 前節 4 份域 SOP，共 6 份；其最新狀態以文末 X 原文回讀為準。
- `main`：維持 `HISTORICAL_UNMANAGED_DO_NOT_MUTATE`，不清理、不同步、不提交修改。
- 不因清查發現問題就自行擴大治理白名單、觸碰 DC／本機或發布產品 X。

## 2026-10-11 後續正式 X 回讀（取代上方待修狀態，不抹除原始證據）

- 已重新讀取正式 X 上述六份文件的現行內容：`README.md` 與 `handoff/00_AI_HANDOFF_README.md` 已註明舊 Preflight 退役；`12_WHD_FoldDesignerBridgeOwnership規則.md` 改用 `/派工` 雲端、當次 `/接手` RC、產品 `localX`／`/推推`；`08_WHD截角資料與2D入口收斂規則.md` 明示舊寫入憑證非前置；`12_WHD規格書Skill前置與Grounding規則.md` 已標 REFERENCE／歷史；`06_踩坑記錄與防錯經驗庫.md` 已註明舊交易規則 HISTORICAL / SUPERSEDED。
- 因此**不得再把原表六份當作尚未修正而重新施工**；保留原表僅為 PR #1548 事故證據。六份文件仍需依其 CURRENT／REFERENCE 邊界判讀，這不是全篇產品語意驗收通過的宣告。
- 本次另發現 `09_WHD_Canonical_Authority_Map.md` 正文仍將已不存在的 interactive runtime／execution control plane 模組寫成 CURRENT owner；治理修復將這兩段改為 HISTORICAL 導覽，保留原版於 `WHD_20261010_retired_process_provenance.md`，不刪任何歷史檔、產品幾何、HA／Node-RED 安全契約。
- `tests/knowledge/test_current_history_authority_contract.py` 的舊驗證對 `AGENTS.md` 仍強制 HTML marker 與全文自我引用；修復為驗證正式 `WHD_DOC_META_V1` metadata 及入口執行分流，不放鬆 CURRENT owner 的有效性。
- 此處僅記錄本 PR 提案與已回讀的六份原文；**merge／CI 實際狀態以 GitHub PR 和 Actions 為準**，不可在驗收前宣稱本次治理修訂已合併。
