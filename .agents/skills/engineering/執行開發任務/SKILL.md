---
name: 執行開發任務
description: 直接執行 WHD 開發任務，在 localX 整合測試，不使用舊治理狀態機。
whd_doc_role: CURRENT
whd_contract: development-task-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 執行開發任務

## 不得停止程序 `INTERACTIVE_COMMAND_NO_STOP_HARD_GATE_V1`

使用者明確下達施工、`/功能`、`/DEBUG`、`/派工` 或 `/接手` 後，在原有授權範圍內直接施工，不得預先設停止程序；能讀真實來源就讀、能修改就提交、能查 CI 就查、GREEN 就依現行授權合併 `localX` 並接下一張。單一操作遭拒只處理該操作，改做其他合法可行工作；不得以狀態報告、建立工單、PR 或單一 blocker 宣稱完成。維持 `SOURCE_READ_BEFORE_MUTATION_V1`、DC/RC 明確授權及正式 X `/推推` 閘門。


**改程式前的必做條件**：執行 `AGENTS.md` 的 `SOURCE_READ_BEFORE_MUTATION_V1`；先實際讀受影響程式完整函式／呼叫鏈、CURRENT 規格與資料檔及既有測試，交代 `SOURCE_READ_EVIDENCE` 後才可寫產品程式或測試。若來源或正確判準缺失，回報 `SOURCE_READ_PRECONDITION_FAILED`，繼續只讀查證，**不可看檔名就直接改、不得憑測試輸出猜幾何公式**。此條不擴大 RC/DC 權限。

使用使用者指定的 Issue 或明確開發任務，先讀 GitHub `localX` 精確 HEAD 的 `AGENTS.md`，再依入口分流：一般修復、`/派工` 與治理修改從最新 `localX` 建工作分支，在 GitHub／排程／雲端施工並通過 CI 後 PR 合回遠端 `localX`。僅使用者當次明確 `/接手` 選用 RC 的任務可以使用 CoreELEC；不因 `LOCALX_INTEGRATION` 或 CI GREEN 自動啟動 DC。正式 X 只在 Windows 人工驗收及當次 `/推推` 後發布。

使用者下達 `/接手` 時，優先透過 Remote Desktop Commander → CoreELEC `whd-dev` → `/workspace/whd` 執行。不因缺少另一個 Agent、工作槽、狀態交易或工單接取紀錄而停止。

## 全域 DC 硬閘門

依 `AGENTS.md` 的 `DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE`，只有使用者當次明確 `/接手` 選用 RC，或明確允許指定 DC 裝置／路徑／操作時才能調用 DC，且外部平台審查仍須核准；一般 `/派工` 的 CI GREEN 與 `localX` 整合都不是 DC 授權。**單純要求改程式、修改治理、檢查 GitHub、核准 push 或「繼續」均不授予 DC 存取**；不論 `list_devices`、`ping`、讀取檔案或執行命令，未先滿足豁免都禁止。若別的任務確有需求，回報原因、裝置／路徑、操作及影響，標記 `DC_AUTHORIZATION_REQUIRED`，先取得明確核准。任何 CI 或外部工具拒絕都不能繞過。

## `/接手` 的遠端 Git 交付授權（產品通道）

`/接手` 對已明確指定、或當輪已確認接手的 **同一張 Issue／工作分支**，包含從施工到 `localX` 的完整交付授權：本機修改、測試、`git commit` → 推送本次工作分支提交到使用者的 `looaeedr/whd` GitHub → 建立／更新 **base=`localX`** 的產品 PR → 驗收該 PR exact HEAD 的 CI → 合併至 `localX` → 回讀實際 PR、Git HEAD 與 Issue，留言、結案，並依前置及衝突檢查續作下一張可執行工單。

**這些遠端推送及 PR／localX 合併不是「發布正式 X」**；已存在有效 `/接手` 指令及明確 Issue 時，不得只因沒有另外一句「授權遠端推送」便自行中斷或重問。只有目標是 `cleanup/2d-3d-sync`（正式 X）的**產品**發布才必須取得使用者當次 `/推推`。

授權嚴格限於 `looaeedr/whd`、指定工作分支及 `localX`；禁止變更正式 X、跨專案推送、擴大變更範圍或對未驗證提交宣稱 CI GREEN。不得捏造已核准的工具操作：若 GitHub／Remote Desktop／自動批准系統在工具層拒絕實際 push／merge，必須回報**哪個實際工具操作**被拒及具體阻塞，不能用技能文字繞過平台權限，亦不得將本地 commit 說成已遠端交付。

**入口分流硬閘門**：本 Skill 是使用者明確下達 `/接手` 的 RC 施工入口，才可用 Remote Desktop Commander → CoreELEC `whd-dev` → `/workspace/whd`。**`/派工` 不是本機施工授權，也不可自行接到本 Skill／RC。** 兩個入口共用指定倉庫 `looaeedr/whd`、base=`localX` PR、exact CI、合併與回讀的交付邊界；`/派工` 的施工／測試仍只能在雲端／GitHub executor，**預設 CI 成功後直接在 GitHub 合併遠端 `localX`，不要求 DC 連線或斷線證據**，不能用例外做本機施工。`/接手` 經使用者明確指示才允許在本機施工。不得要求退役的 remote token／receipt／unlock 或第二次專案內部批准。**平台安全審查仍有效**：公開推送若需更明確確認或工具拒絕，保留本地提交並回報實際拒絕，不得換工具繞過。

## `/接手` 同工單授權與新 SHA

依 `AGENTS.md` 的 `ISSUE_SCOPE_AUTHORIZATION_REUSE`，同一個已明確授權的 Issue，沿原工作分支將範圍內的 CI 修復或測試修復做成新 commit SHA，仍屬原本 push → PR → exact CI → `localX` 整合許可。**SHA 是追蹤版本及驗收的依據，不應每更新一次 SHA 就重問原核准**；但如果原授權明示僅限固定 SHA，則不得擴張。每次更新均需檢查 diff 沒有跨出工單、repo、分支、base，並對新 SHA 重測。

此規則不能用於別張 Issue、無關功能或正式 X 產品發布（須當次 `/推推`）。若平台推送安全審查拒絕，保留本地提交並報明 `PUBLIC_UPLOAD_REVIEW_BLOCKED` 的實際拒絕點，不換工具繞過、不假稱成功、不無限重問相同核准。純治理工作優先 GitHub `localX` 工作分支與治理 CI，先合 `localX`，**未經另外明確授權不得用 DC**。

保留必要的產品測試、程式碼 review、現場 DXF 驗收，實際交付狀態以 Git HEAD 與 Issue/PR 反讀為準。

產品或混合檔案仍須 localX 與使用者當次 /推推 才可正式發布 X。純非產品文檔、治理、技能及其專用測試，由現行治理專項 CI 判定後先走 GitHub／雲端工作分支 → `localX` PR/merge，不走一般產品 QA；正式 X 仍需人工驗收與 `/推推`；未明確授權不得使用 DC／本機。

## 工作結束前的交付驗證

產品 PR 建立後不表示任務完成。尚在 queued/in_progress/pending 的 CI 只能續查，不可最終回報「已派工」就離開；成功時在同一可執行回合繼續合併 localX、驗證 HEAD、工單留言、結案回讀，失敗時主動查 log 修復並重測。單一工具受阻時立即處理其他合法可行動作，不得將 blocker 當整體停止程序；`/推推` 仍是正式 X 發布唯一授權。
`localX` 成功合併並完成 GitHub SHA 回讀之後立刻 `NEXT_ISSUE_DISCOVERY_REQUIRED`：在原 Issue 結案前／同時查下一張符合依賴、無重複施工、目前 OPEN 的工單，直接切入派工與實作；不能把原 Issue close 當下一張搜尋的先決條件。沒有可執行工單則記錄真實 `NO_ELIGIBLE_ISSUE`。
