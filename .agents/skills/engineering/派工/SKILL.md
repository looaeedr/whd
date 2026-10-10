---
name: 派工
description: 建立或選定 WHD GitHub 工單，直接派交開發，不使用原生執行交易管理。
whd_doc_role: CURRENT
whd_contract: direct-issue-dispatch
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /派工

## 硬閘門：`DISPATCH_CLOUD_BUILD_DC_LOCALX_ONLY`

**`/派工` 絕不能在使用者本機施工。** `DISCOVERY / BUILD / TEST / COMMIT / PUSH / PR / CI` 階段限 `execution_location=GITHUB|SCHEDULER|REMOTE_ACTION`，雲端執行器不得暗接使用者裝置。此階段 `Remote Desktop Commander / RC / whd-dev / /workspace/whd / Z:\新WHD` 均為 `DISPATCH_LOCAL_EXECUTION_DENIED`；不得以「沒有遠端 executor」為由轉本機，更不能暗自切為 `/接手`。缺雲端施工能力就回報 `REMOTE_EXECUTOR_UNAVAILABLE`。

確認 GitHub Issue／依賴／owner 後由遠端隔離工作分支施工、測試、commit、push 到 `looaeedr/whd`，建立 base=`localX` PR，持續查 exact HEAD CI。**CI SUCCESS 之前禁止用 DC**。

### 唯一可使用 DC：`LOCALX_INTEGRATION`

當 exact PR SHA 的必要 CI 全部 SUCCESS 且可整合時，**才允許**透過 Desktop Commander → CoreELEC `whd-dev:/workspace/whd`，將已驗證的遠端工作分支成果合併至使用者**本機 `localX`**。連線後先查本機工作樹／`localX`／Git refs，保留未發布修改，不得 reset、force、蓋掉髒檔，也不得在這個階段直接改產品程式補測（修正須回遠端工作分支重新測試 CI）。本機整合成功、必要整合測試通過後，非強制同步 GitHub `localX`，回讀本機 HEAD、遠端 SHA、PR 狀態；不能光靠遠端 PR merge 就聲稱本機已整合。

**唯一斷線備援：** DC 實際無法連線或逾時，經記錄 `DC_UNREACHABLE` 與 exact Issue/PR/head SHA／CI 後，才可把工作 PR 合併至**GitHub 遠端 `localX`**；強制註記 `LOCALX_SYNC_PENDING`，不得宣稱本機 `localX` 已同步。後續恢復 DC 才對齊。若 DC 能連卻遇到本機衝突／髒檔／權限拒絕／驗收失敗，不得假稱斷線而改用遠端備援；須回報真正 blocker，不可繞過平台安全審查。

`/接手` 是另一入口，只有使用者明確下達時才允許**在本機施工**。此 `/派工` 的 DC 例外只是最終合併，不是暗中開啟 `/接手`。無論哪條路，產品從 `localX` 到正式 X 仍須當次 `/推推`；治理白名單文件依 `tools/change_lane_gate.py` 另走治理通道。

## 工單授權延續與公開交付

依 `AGENTS.md` 的 `ISSUE_SCOPE_AUTHORIZATION_REUSE`，同一 Issue、工作分支、施工範圍、repo 與 base=`localX` 已明確核准後，修復 CI 或必要產品測試產生的新 SHA 不必再次詢問**同一範圍**的 push／PR／CI／localX 整合許可。**每個新 HEAD 仍需範圍 diff 與必要 CI 重驗**，不沿用舊版 GREEN。不得把 #1466 核准沿用 #1467，亦不得擴大到正式 X；使用者明示只准固定 SHA 時照較窄界線執行。

本節**不允許 `/派工` 以 DC 施工**，亦不放寬任何平台公開上傳安全審查。平台實際拒絕就回報 `PUBLIC_UPLOAD_REVIEW_BLOCKED` 與拒絕操作、必要補證，不得更換管道規避或無限重問相同核准。**純治理文件必須優先 GitHub 直送 X，不得未經另外明確授權而使用 DC**。

## 發出產品 PR 之後必須續作

1. `PR_OPEN / CI_QUEUED / CI_IN_PROGRESS / CI_PENDING` 一律 `CONTINUE_POLL`，**不是可結束的交付狀態**；在當前回合持續輪詢 exact PR SHA 與對應 run，不得把「正在測試」當成派工完成。
2. `CI_SUCCESS` 且 PR 可整合，**先由 DC 最終整合到本機 `localX`**、驗證後非強制同步 GitHub `localX`，回讀兩端 HEAD、PR 與 Issue 後留言、close Issue + readback；**只在 DC 真正不可連線時**可備援遠端 GitHub `localX` 並記錄 `LOCALX_SYNC_PENDING`。整段不必使用者再喊「繼續」。
   **重要先後次序**：本機 `localX` merge＋雙端 SHA 回讀成功（或已標記 DC 斷線、遠端合併及本機待同步）後，**立刻啟動 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，同步完成原 Issue 留言／close/readback；**不得等 Issue CLOSED 才找下一張**，也不得以 Issue close/readback 為流程終點。
   搜尋下一張 OPEN 且前置工單已完成的可執行 Issue；檢查相同工作是否已有 owner/PR，避免重複；可施工就建立真實工作分支、寫入派工留言並繼續執行。找不到則輸出已核查清單與 `NO_ELIGIBLE_ISSUE`，不得假報成功派工。

3. `CI_FAILURE / CANCELLED / TIMED_OUT`：讀取 job/step/log，定位和修復後再次測試；若 run 完全缺席，先修正 workflow branch/path 接線並觸發，不得聲稱已驗收。
4. 回報至少每 2–3 次實質操作一次；回報不構成退出。只有**實際無法繼續的外部阻塞**或回合／工具限制造成無法續跑時，才能清楚報出已驗證 blocker、last exact PR/SHA 與下一步，**不可聲稱 DONE**。ChatGPT 回合結束後不會自行輪詢，除非另有正式排程。
5. 產品 `localX → X` 仍需使用者當次 `/推推`。不加新的 GitHub 分支保護、不恢復 Flow v2。
