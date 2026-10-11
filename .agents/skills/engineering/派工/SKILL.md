---
name: 派工
description: 建立或選定 WHD GitHub 工單，直接派交開發，不使用原生執行交易管理。
whd_doc_role: CURRENT
whd_contract: direct-issue-dispatch
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /派工

## 全域 DC 預設禁止（施工階段不可觸碰）

本 Skill 首先遵循 `AGENTS.md` 的 `DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE`。**`/派工` 只有 exact HEAD CI SUCCESS 後、base=`localX` 的 `LOCALX_INTEGRATION` 可使用 DC**，用途僅限本機 `localX` 合併、必要整合驗證／同步／回讀；其他階段連 `list_devices`、`ping`、讀檔或查目錄都不准。使用者另行明確指示某次 DC 操作時，只能依當次限定的目的執行。若其他工作確有 DC 需求，先報明原因、裝置／路徑、預定操作及影響，以 `DC_AUTHORIZATION_REQUIRED` 請求核准，未核准不得接觸 DC，也不得轉用本機 shell 繞過。

## 硬閘門：`DISPATCH_CLOUD_BUILD_DC_LOCALX_ONLY`

**`/派工` 絕不能在使用者本機施工。** `DISCOVERY / BUILD / TEST / COMMIT / PUSH / PR / CI` 階段限 `execution_location=GITHUB|SCHEDULER|REMOTE_ACTION`，雲端執行器不得暗接使用者裝置。此階段 `Remote Desktop Commander / RC / whd-dev / /workspace/whd / Z:\新WHD` 均為 `DISPATCH_LOCAL_EXECUTION_DENIED`；不得以「沒有遠端 executor」為由轉本機，更不能暗自切為 `/接手`。缺雲端施工能力就回報 `REMOTE_EXECUTOR_UNAVAILABLE`。

確認 GitHub Issue／依賴／owner 後由遠端隔離工作分支施工、測試、commit、push 到 `looaeedr/whd`，建立 base=`localX` PR，持續查 exact HEAD CI。**CI SUCCESS 之前禁止用 DC**。

## 本體直接施工優先 `DISPATCH_SELF_EXECUTION_FIRST`

**本體有合法 GitHub 施工能力就直接動手，不走尋找外部代理的前置流程。** 已有指定 Issue、原 PR／工作分支、GitHub 讀寫／提交／PR 和雲端 CI 能力時，由當前 AI 本體直接完成 `BUILD→TEST→COMMIT→CI`，不需要 Codex 雲端程式代理外掛、子代理或獨立 task ID。

1. **沿用既有工作**：核對 Issue／PR／head/base，直接改程式與測試，提交原工作分支並回讀 SHA；GitHub Actions 執行適用測試。GitHub 寫檔、空 commit、文字留言、單獨搜尋外掛都不是已通過測試的證據。
2. **本人實質接取**：工單記錄 `本體直接接取`、`execution_location=GITHUB`、Issue、分支與 PR，後續補首筆實際施工 commit SHA、exact SHA 測試 run ID／結果。只有真實施工動作才能標 `EXECUTOR_START_CONFIRMED`；不得自己留言就聲稱接取完成。
3. **無能力才找外部代理**：先具體核對欠缺 GitHub 寫入／提交／合法雲端測試能力，確定本體無法進行才搜尋 Codex 或其他已可用代理。搜尋不能取代啟動證據；不可用時回報 `DISPATCH_REGISTERED_ONLY`／`REMOTE_EXECUTOR_UNAVAILABLE`，不宣稱背景有人施工。
4. **治理直送獨立 `NON_PRODUCT_GOVERNANCE_DIRECT_X`**：本 Skill／`AGENTS.md`／治理測試等非產品本體修改，照治理通道直接由 GitHub PR 合併 X，不走 `localX`、一般產品派工或 `/推推`。產品施工仍遵守原 CI、`LOCALX_INTEGRATION`、本機 DC 禁令與正式 X 發布權限。

## 真實執行者接取：`DISPATCH_EXECUTOR_HANDOFF_REQUIRED`

**完成登記不等於完成派工。** 先核對指定號碼究竟是 Issue 或 PR；若已有 draft PR 與追蹤工單，沿用原 PR／分支／Issue，不另起一套。完成建立／留言後必須在**本回合**走以下路徑：

1. **能力核對與啟動**：依 `DISPATCH_SELF_EXECUTION_FIRST`，先由有合法 GitHub 寫入／提交／CI 能力的同一合法雲端執行者直接施工；缺少必要能力時才辨識並呼叫獲授權的 `GITHUB|SCHEDULER|REMOTE_ACTION` 外部施工入口。GitHub issue/PR 寫入、加 assignee、留言提及另一人、建立 CI、只寫排程 prompt，**都不等於啟動施工**。
2. **回讀接取證據**：只有可回讀 `EXECUTOR_START_CONFIRMED`（身分、執行入口、Issue、分支、首個真實施工動作）才能回報「已派工／已接取／執行中」。本體直接施工使用 commit SHA 與相應 CI run ID，不需外部 task ID；委派代理才需對方 task/run ID 或相當接取證據。接取人應在同一 Issue 留身份及實質進度；**由派工者代貼『請施工』不算接取**。
3. **失敗即真實回報**：僅寫入 PR／Issue／派工留言而沒有執行者，回報 `DISPATCH_REGISTERED_ONLY` 並在未找到可用雲端入口時明列 `REMOTE_EXECUTOR_UNAVAILABLE`。有入口但啟動失敗／接取未證實則回報 `DISPATCH_START_UNCONFIRMED` 與具體操作／錯誤／證據。**不得標完成，不得宣稱背景有人運作，不得為了補外觀另建 PR 或 Issue，也不得轉用 DC／本機。**
4. **成功後連續施工**：執行者按原 Issue 規格在合法雲端進行 BUILD→TEST→COMMIT→PR→CI，隨後依 `LOCALX_INTEGRATION` 整合。每次更新以真實 commit/run/Issue 留言為準；回合無法跨時自主續作時不得宣稱能自行喚醒。

### 唯一可使用 DC：`LOCALX_INTEGRATION`

當 exact PR SHA 的必要 CI 全部 SUCCESS 且可整合時，**才允許**透過 Desktop Commander → CoreELEC `whd-dev:/workspace/whd`，將已驗證的遠端工作分支成果合併至使用者**本機 `localX`**。連線後先查本機工作樹／`localX`／Git refs，保留未發布修改，不得 reset、force、蓋掉髒檔，也不得在這個階段直接改產品程式補測（修正須回遠端工作分支重新測試 CI）。本機整合成功、必要整合測試通過後，非強制同步 GitHub `localX`，回讀本機 HEAD、遠端 SHA、PR 狀態；不能光靠遠端 PR merge 就聲稱本機已整合。

**DC 斷線備援（不等於使用者授權 GitHub-only）：** DC 實際無法連線或逾時，經記錄 `DC_UNREACHABLE` 與 exact Issue/PR/head SHA／CI 後，才可把工作 PR 合併至**GitHub 遠端 `localX`**；強制註記 `LOCALX_SYNC_PENDING`，不得宣稱本機 `localX` 已同步。後續恢復 DC 才對齊。若 DC 能連卻遇到本機衝突／髒檔／權限拒絕／驗收失敗，不得假稱斷線而改用遠端備援；須回報真正 blocker，不可繞過平台安全審查。

`/接手` 是另一入口，只有使用者明確下達時才允許**在本機施工**。此 `/派工` 的 DC 例外只是最終合併，不是暗中開啟 `/接手`。無論哪條路，產品從 `localX` 到正式 X 仍須當次 `/推推`；治理白名單文件依 `tools/change_lane_gate.py` 另走治理通道。

## 工單授權延續與公開交付

依 `AGENTS.md` 的 `ISSUE_SCOPE_AUTHORIZATION_REUSE`，同一 Issue、工作分支、施工範圍、repo 與 base=`localX` 已明確核准後，修復 CI 或必要產品測試產生的新 SHA 不必再次詢問**同一範圍**的 push／PR／CI／localX 整合許可。**每個新 HEAD 仍需範圍 diff 與必要 CI 重驗**，不沿用舊版 GREEN。不得把 #1466 核准沿用 #1467，亦不得擴大到正式 X；使用者明示只准固定 SHA 時照較窄界線執行。

本節**不允許 `/派工` 以 DC 施工**，亦不放寬任何平台公開上傳安全審查。平台實際拒絕就回報 `PUBLIC_UPLOAD_REVIEW_BLOCKED` 與拒絕操作、必要補證，不得更換管道規避或無限重問相同核准。**純治理文件必須優先 GitHub 直送 X，不得未經另外明確授權而使用 DC**。

## GitHub-only 遠端 localX 整合 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1`

使用者已**對本工單明確授權遠端 GitHub `localX` 合併**且明示不准 DC／本機時，不應以 DC-first 無法執行為由停在 `Ready for review`；必須在 exact PR HEAD CI SUCCESS、PR base=`localX`、合併前 head/base/mergeable 回讀無異常後，用 GitHub PR merge（設定 `expected_head_sha`）整合遠端 `localX`，再回讀 PR merged、merge_commit_sha 與 GitHub localX HEAD；記錄 `GITHUB_ONLY_LOCALX_MERGED + LOCALX_SYNC_PENDING`，本機 localX 未查一律 UNKNOWN。絕不可把這條寫成 `DC_UNREACHABLE`，不可替使用者虛構遠端合併授權。若原指令只寫「禁止 DC」，沒有授權整合 remote localX，仍是 `LOCALX_INTEGRATION_PENDING`，需明列缺口，不得擅自合併。只有原 Issue/PR 範圍已授權整合時，才不需反覆詢問。此例外不變更正式 X 產品 `/推推` 及本機保留限制。

## 退出前決策：`DISPATCH_TURN_EXIT_GATE_V1`

當次回合準備收尾時，先套用 `AGENTS.md` 和 `.agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json`，不能因為已發進度報告就退出：

1. 讀當前 PR `base/head_sha` 以及 **exact SHA** Product Regression 的 `run_id/status/conclusion`（含 jobs）；不存在、SHA 不符或資訊不足 → `RECONCILE_ONLY`，定向補讀，不得沿用舊 GREEN。
2. `requested/queued/waiting/pending/in_progress` → `CONTINUE_POLL`，同一回合繼續查狀態；每 2–3 次操作回報，而非結束。避免高頻重抓完整 CI log。
3. `completed/success` → `LOCALX_INTEGRATION_PENDING`：驗收通過後繼續既有 `LOCALX_INTEGRATION` 或獲使用者明確授權的 GitHub-only 整合，保留本機修改；即使 PR 仍 Draft，也不能以「綠燈但還未合併」作為完成。其他 terminal conclusion → `REPAIR_AND_RETEST`。
4. `localX` 整合、Issue close/readback、`NEXT_ISSUE_DISCOVERY_REQUIRED` 未完成 → `CONTINUE_FINALIZATION`，不能冒稱 `RELEASED`；只有所有義務已驗證才宣告交付完成。
5. **唯一非完成式退出**：真正的外部障礙 `BLOCKED_WITH_EVIDENCE` 或真實工具／回合上限 `RUNTIME_LIMIT_UNRESOLVED`；附 `Issue/PR/head_sha/run_id/last_observation/blocker/next_exact_action`，不得稱 DONE，不能假裝背景會繼續。ChatGPT 平台沒有可由此文件攔截的「關閉回答」鉤子；此規則依賴執行者按規則行動。

只增加現有流程的真實退出決策，不需要 Codex、不建新排程、不改本機施工授權，也不恢復退役 lease／claim／Flow v2。

## 發出產品 PR 之後必須續作

1. `PR_OPEN / CI_QUEUED / CI_IN_PROGRESS / CI_PENDING` 一律 `CONTINUE_POLL`，**不是可結束的交付狀態**；在當前回合持續輪詢 exact PR SHA 與對應 run，不得把「正在測試」當成派工完成。
2. `CI_SUCCESS` 且 PR 可整合，**先由 DC 最終整合到本機 `localX`**、驗證後非強制同步 GitHub `localX`，回讀兩端 HEAD、PR 與 Issue 後留言、close Issue + readback；DC 真正不可連線可走斷線備援；使用者明確授權 GitHub-only remote `localX` 整合可走 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1`；兩者均記錄 `LOCALX_SYNC_PENDING`，不可假稱 DC 已斷線。整段不必使用者再喊「繼續」。
   **重要先後次序**：本機 `localX` merge＋雙端 SHA 回讀成功（或已標記 DC 斷線、遠端合併及本機待同步）後，**立刻啟動 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，同步完成原 Issue 留言／close/readback；**不得等 Issue CLOSED 才找下一張**，也不得以 Issue close/readback 為流程終點。
   搜尋下一張 OPEN 且前置工單已完成的可執行 Issue；檢查相同工作是否已有 owner/PR，避免重複；可施工就建立真實工作分支、寫入派工留言並繼續執行。找不到則輸出已核查清單與 `NO_ELIGIBLE_ISSUE`，不得假報成功派工。

3. `CI_FAILURE / CANCELLED / TIMED_OUT`：讀取 job/step/log，定位和修復後再次測試；若 run 完全缺席，先修正 workflow branch/path 接線並觸發，不得聲稱已驗收。
4. 回報至少每 2–3 次實質操作一次；回報不構成退出。只有**實際無法繼續的外部阻塞**或回合／工具限制造成無法續跑時，才能清楚報出已驗證 blocker、last exact PR/SHA 與下一步，**不可聲稱 DONE**。ChatGPT 回合結束後不會自行輪詢，除非另有正式排程。
5. 產品 `localX → X` 仍需使用者當次 `/推推`。不加新的 GitHub 分支保護、不恢復 Flow v2。
