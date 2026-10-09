---
name: 執行開發任務
description: 直接執行 WHD 開發任務，在 localX 整合測試，不使用舊治理狀態機。
whd_doc_role: CURRENT
whd_contract: development-task-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 執行開發任務

使用使用者指定的 Issue 或明確開發任務，讀取 GitHub Git 與相關產品規格，在合法工作分支或本地 /workspace/whd 修改、測試、提交，再將成果整合至本地 localX。

使用者下達 /接手 時優先透過 Remote Desktop Commander → CoreELEC whd-dev → /workspace/whd 執行。不因缺少另一個 Agent、工作槽、狀態交易或工單接取紀錄而停止。

保留必要的產品測試、程式碼 review、現場 DXF 驗收，實際交付狀態以 Git HEAD 與 Issue/PR 反讀為準。

產品或混合檔案仍須 localX 與使用者當次 /推推 才可正式發布 X。純非產品文檔、治理、技能及其專用測試，改由 tools/change_lane_gate.py 判定後直接本地治理分支 → X PR/merge，不走一般產品流程。

## 工作結束前的交付驗證

產品 PR 建立後不表示任務完成。尚在 queued/in_progress/pending 的 CI 只能續查，不可最終回報「已派工」就離開；成功時在同一可執行回合繼續合併 localX、驗證 HEAD、工單留言、結案回讀，失敗時主動查 log 修復並重測。只有不可執行的外部 blocker／回合工具限制才可停止，須明確揭露，不得冒充背景執行；`/推推` 仍是正式 X 發布唯一授權。
`localX` 成功合併並完成 GitHub SHA 回讀之後立刻 `NEXT_ISSUE_DISCOVERY_REQUIRED`：在原 Issue 結案前／同時查下一張符合依賴、無重複施工、目前 OPEN 的工單，直接切入派工與實作；不能把原 Issue close 當下一張搜尋的先決條件。沒有可執行工單則記錄真實 `NO_ELIGIBLE_ISSUE`。
