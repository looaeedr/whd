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

使用者下達 `/接手` 時，優先透過 Remote Desktop Commander → CoreELEC `whd-dev` → `/workspace/whd` 執行。不因缺少另一個 Agent、工作槽、狀態交易或工單接取紀錄而停止。

## `/接手` 的遠端 Git 交付授權（產品通道）

`/接手` 對已明確指定、或當輪已確認接手的 **同一張 Issue／工作分支**，包含從施工到 `localX` 的完整交付授權：本機修改、測試、`git commit` → 推送本次工作分支提交到使用者的 `looaeedr/whd` GitHub → 建立／更新 **base=`localX`** 的產品 PR → 驗收該 PR exact HEAD 的 CI → 合併至 `localX` → 回讀實際 PR、Git HEAD 與 Issue，留言、結案，並依前置及衝突檢查續作下一張可執行工單。

**這些遠端推送及 PR／localX 合併不是「發布正式 X」**；已存在有效 `/接手` 指令及明確 Issue 時，不得只因沒有另外一句「授權遠端推送」便自行中斷或重問。只有目標是 `cleanup/2d-3d-sync`（正式 X）的**產品**發布才必須取得使用者當次 `/推推`。

授權嚴格限於 `looaeedr/whd`、指定工作分支及 `localX`；禁止變更正式 X、跨專案推送、擴大變更範圍或對未驗證提交宣稱 CI GREEN。不得捏造已核准的工具操作：若 GitHub／Remote Desktop／自動批准系統在工具層拒絕實際 push／merge，必須回報**哪個實際工具操作**被拒及具體阻塞，不能用技能文字繞過平台權限，亦不得將本地 commit 說成已遠端交付。

**入口分流硬閘門**：本 Skill 是使用者明確下達 `/接手` 的 RC 施工入口，才可用 Remote Desktop Commander → CoreELEC `whd-dev` → `/workspace/whd`。**`/派工` 不是本機施工授權，也不可自行接到本 Skill／RC。** 兩個入口共用指定倉庫 `looaeedr/whd`、base=`localX` PR、exact CI、合併與回讀的交付邊界；`/派工` 的施工／測試仍只能在雲端／GitHub executor，**唯一 DC 例外是 CI 通過後最後合併本機 `localX` 的 `LOCALX_INTEGRATION`**（DC 不通才遠端 `localX` 備援，標記 `LOCALX_SYNC_PENDING`），不能用例外做本機施工。`/接手` 經使用者明確指示才允許在本機施工。不得要求退役的 remote token／receipt／unlock 或第二次專案內部批准。**平台安全審查仍有效**：公開推送若需更明確確認或工具拒絕，保留本地提交並回報實際拒絕，不得換工具繞過。

## `/接手` 同工單授權與新 SHA

依 `AGENTS.md` 的 `ISSUE_SCOPE_AUTHORIZATION_REUSE`，同一個已明確授權的 Issue，沿原工作分支將範圍內的 CI 修復或測試修復做成新 commit SHA，仍屬原本 push → PR → exact CI → `localX` 整合許可。**SHA 是追蹤版本及驗收的依據，不應每更新一次 SHA 就重問原核准**；但如果原授權明示僅限固定 SHA，則不得擴張。每次更新均需檢查 diff 沒有跨出工單、repo、分支、base，並對新 SHA 重測。

此規則不能用於別張 Issue、無關功能或正式 X 產品發布（須當次 `/推推`）。若平台推送安全審查拒絕，保留本地提交並報明 `PUBLIC_UPLOAD_REVIEW_BLOCKED` 的實際拒絕點，不換工具繞過、不假稱成功、不無限重問相同核准。純治理工作優先 GitHub 遠端直送 X，**未經另外明確授權不得用 DC**。

保留必要的產品測試、程式碼 review、現場 DXF 驗收，實際交付狀態以 Git HEAD 與 Issue/PR 反讀為準。

產品或混合檔案仍須 localX 與使用者當次 /推推 才可正式發布 X。純非產品文檔、治理、技能及其專用測試，由 tools/change_lane_gate.py 判定後優先直接 GitHub／雲端治理分支 → X PR/merge，不走一般產品流程；未明確授權不得使用 DC／本機。

## 工作結束前的交付驗證

產品 PR 建立後不表示任務完成。尚在 queued/in_progress/pending 的 CI 只能續查，不可最終回報「已派工」就離開；成功時在同一可執行回合繼續合併 localX、驗證 HEAD、工單留言、結案回讀，失敗時主動查 log 修復並重測。只有不可執行的外部 blocker／回合工具限制才可停止，須明確揭露，不得冒充背景執行；`/推推` 仍是正式 X 發布唯一授權。
`localX` 成功合併並完成 GitHub SHA 回讀之後立刻 `NEXT_ISSUE_DISCOVERY_REQUIRED`：在原 Issue 結案前／同時查下一張符合依賴、無重複施工、目前 OPEN 的工單，直接切入派工與實作；不能把原 Issue close 當下一張搜尋的先決條件。沒有可執行工單則記錄真實 `NO_ELIGIBLE_ISSUE`。
