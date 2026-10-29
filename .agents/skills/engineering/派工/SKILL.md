---
name: 派工
description: 建立或選定 WHD GitHub 工單，直接派交開發，不使用原生執行交易管理。
whd_doc_role: CURRENT
whd_contract: direct-issue-dispatch
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /派工

## 不得停止程序 `INTERACTIVE_COMMAND_NO_STOP_HARD_GATE_V1`

承接 `/功能 /DEBUG /派工 /接手 /繼續` 的同一工作鏈；`/功能` 定義需求、`/DEBUG` 解決真實錯誤、`/派工` 直接提交／測試／合併／接下一張。**不得預先設停止程序**；可用工具仍可施工時立即呼叫工具，不可用報告、詢問是否繼續、PR 建立、CI queued、單一步驟受阻當停止理由。被拒操作不繞過權限，在同範圍直接換其他合法動作，續讀、修其他獨立部分、追已有 CI；不重做無關前置。每 2–3 次實質動作回報一次，繼續做。執行位置和 `/推推` 權限按 `AGENTS.md` 原規定。


**產品修改先讀再寫**：GitHub／雲端施工者同樣受正式 `AGENTS.md` 的 `SOURCE_READ_BEFORE_MUTATION_V1` 約束。先讀相關程式實際函式及呼叫鏈、CURRENT 文檔／基準資料與測試，回報 `SOURCE_READ_EVIDENCE`；未完成即 `SOURCE_READ_PRECONDITION_FAILED`，只准續查、不准先改後補證據。不得因此改走 DC／RC。

## 全域 DC 預設禁止（施工與整合皆不預設呼叫）

`/派工` 施工及 CI GREEN 後的 `localX` 整合預設只使用 GitHub／雲端，**不因此自動授權 DC**。不要呼叫 `list_devices`、`ping` 探測本機；Windows `Z:\localX` 由使用者以 fast-forward 更新及 GUI 驗收。只有當次明確授權 DC 目的／裝置／路徑／操作且外部核准，才能在指定範圍使用；拒絕不得繞過。
## 硬閘門：`DISPATCH_CLOUD_BUILD_GITHUB_LOCALX_ONLY`

施工倉庫固定為 GitHub `looaeedr/whd`，不由預設 `main` 或 CoreELEC checkout 推斷來源；施工階段 `DISCOVERY/BUILD/TEST/COMMIT/PUSH/PR/CI` 僅 `execution_location=GITHUB|SCHEDULER|REMOTE_ACTION`，不可用 DC/RC/local shell。PR base=`localX`、exact SHA CI 成功後，**預設在 GitHub 合併 localX**；不能擅自發布正式 X，也不因缺雲端執行器轉本機施工。
## 快速迭代與最終完整交付分離

同一 Bug／功能**先在同一工作批次完成最小修改與相關回歸**，使用合法工作區的 \`python tools/quick_test.py --test tests/test_file.py::test_case\` 做真正 RED→GREEN；多個已修改測試檔可用 \`--auto\`。無法在 GitHub/授權雲端環境執行時只回報未執行，不得偷進 Windows/DC。確認受影響鏈合格再盡量單次 commit/push PR 觸發 \`WHD Product Regression\` 的完整必跑測試；新 SHA 修復例外仍完整重驗。具體唯一流程以 \`AGENTS.md::BATCHED_FAST_FEEDBACK_THEN_CANONICAL_CI_V1\` 為準，不建第二套 SOP；治理及獨立製造／CADCraft 證據不能為湊「一套 CI」而削除。


已有真實 RED 測試 node／本次已改測試檔時，先用 `tools/change_test_profile.py --feedback-test <真實 node-id>` 產生 `fast_feedback.command`，在合法 GitHub／雲端施工執行器先跑定向 RED→GREEN，避免每次試錯都以完整 Canonical CI 作為第一個回饋。`NEEDS_EXPLICIT_TEST` 不得猜成 GREEN，沒有執行環境也不能假稱已測。提交可交付候選後仍按原範圍跑 exact SHA 必要 CI；CI 失敗優先查失敗 node/step，用定向測試修正後再提交新 SHA 重跑**完整必要 CI**。不改 Runner 授權、不撤除完整回歸、不重啟舊交易／背景輪詢。

## 本體直接施工優先 `DISPATCH_SELF_EXECUTION_FIRST`

**本體有合法 GitHub 施工能力就直接動手，不走尋找外部代理的前置流程。** 已有指定 Issue、原 PR／工作分支、GitHub 讀寫／提交／PR 和雲端 CI 能力時，由當前 AI 本體直接完成 `BUILD→TEST→COMMIT→CI`，不需要 Codex 雲端程式代理外掛、子代理或獨立 task ID。

1. **沿用既有工作**：核對 Issue／PR／head/base，直接改程式與測試，提交原工作分支並回讀 SHA；GitHub Actions 執行適用測試。GitHub 寫檔、空 commit、文字留言、單獨搜尋外掛都不是已通過測試的證據。
2. **本人實質接取**：工單記錄 `本體直接接取`、`execution_location=GITHUB`、Issue、分支與 PR，後續補首筆實際施工 commit SHA、exact SHA 測試 run ID／結果。只有真實施工動作才能標 `EXECUTOR_START_CONFIRMED`；不得自己留言就聲稱接取完成。
3. **無能力才找外部代理**：先具體核對欠缺 GitHub 寫入／提交／合法雲端測試能力，確定本體無法進行才搜尋 Codex 或其他已可用代理。搜尋不能取代啟動證據；不可用時回報 `DISPATCH_REGISTERED_ONLY`／`REMOTE_EXECUTOR_UNAVAILABLE`，不宣稱背景有人施工。
4. **治理與產品測試分流、施工來源一致**：本 Skill／`AGENTS.md`／治理測試等非產品本體修改，仍從 GitHub `localX` 開工作分支、以治理專項 CI 驗證並 PR 合回 `localX`；可免一般產品 QA，但不可按舊 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 直接合 X，也不准以此擴大 DC 權限。正式 X 只能依 Windows 人工驗收、當次 `/推推` 與受信任 gate 發布。

## 真實執行者接取：`DISPATCH_EXECUTOR_HANDOFF_REQUIRED`

**完成登記不等於完成派工。** 先核對指定號碼究竟是 Issue 或 PR；若已有 draft PR 與追蹤工單，沿用原 PR／分支／Issue，不另起一套。完成建立／留言後必須在**本回合**走以下路徑：

1. **能力核對與啟動**：依 `DISPATCH_SELF_EXECUTION_FIRST`，先由有合法 GitHub 寫入／提交／CI 能力的同一合法雲端執行者直接施工；缺少必要能力時才辨識並呼叫獲授權的 `GITHUB|SCHEDULER|REMOTE_ACTION` 外部施工入口。GitHub issue/PR 寫入、加 assignee、留言提及另一人、建立 CI、只寫排程 prompt，**都不等於啟動施工**。
2. **回讀接取證據**：只有可回讀 `EXECUTOR_START_CONFIRMED`（身分、執行入口、Issue、分支、首個真實施工動作）才能回報「已派工／已接取／執行中」。本體直接施工使用 commit SHA 與相應 CI run ID，不需外部 task ID；委派代理才需對方 task/run ID 或相當接取證據。接取人應在同一 Issue 留身份及實質進度；**由派工者代貼『請施工』不算接取**。
3. **失敗即真實回報**：僅寫入 PR／Issue／派工留言而沒有執行者，回報 `DISPATCH_REGISTERED_ONLY` 並在未找到可用雲端入口時明列 `REMOTE_EXECUTOR_UNAVAILABLE`。有入口但啟動失敗／接取未證實則回報 `DISPATCH_START_UNCONFIRMED` 與具體操作／錯誤／證據。**不得標完成，不得宣稱背景有人運作，不得為了補外觀另建 PR 或 Issue，也不得轉用 DC／本機。**
4. **成功後連續施工**：執行者按原 Issue 規格在合法雲端進行 BUILD→TEST→COMMIT→PR→CI，隨後依 `LOCALX_INTEGRATION` 整合。每次更新以真實 commit/run/Issue 留言為準；有合法後續工具動作就直接續作，不得用報告取代施工。

### `LOCALX_INTEGRATION` 預設 GitHub 完成

同工單 PR exact HEAD 的 CI GREEN，核對 scope、當前 base/head、mergeable 與 base 演進，必要時只補測受影響部分；用 GitHub PR merge 的 `expected_head_sha` 合併，讀回 PR merged／remote `localX` SHA。報告 `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`，**不呼叫 DC**，Windows `Z:\localX` 由使用者安全 fast-forward 及手動驗收。GitHub 拒絕合併時保持 blocker，不換通道、不 force/reset。
僅使用者當次明確要求 DC 且外部審查准許時才限縮操作。`/接手`、正式產品 `/推推` 保有各自不同的授權門檻。
## 工單授權延續與公開交付

依 `AGENTS.md` 的 `ISSUE_SCOPE_AUTHORIZATION_REUSE`，同一 Issue、工作分支、施工範圍、repo 與 base=`localX` 已明確核准後，修復 CI 或必要產品測試產生的新 SHA 不必再次詢問**同一範圍**的 push／PR／CI／localX 整合許可。**每個新 HEAD 仍需範圍 diff 與必要 CI 重驗**，不沿用舊版 GREEN。不得把 #1466 核准沿用 #1467，亦不得擴大到正式 X；使用者明示只准固定 SHA 時照較窄界線執行。

本節**不允許 `/派工` 以 DC 施工**，亦不放寬任何平台公開上傳安全審查。平台實際拒絕就回報 `PUBLIC_UPLOAD_REVIEW_BLOCKED` 與拒絕操作、必要補證，不得更換管道規避或無限重問相同核准。**純治理文件同樣先 GitHub `localX`，經治理 CI 合回；不得未經另外明確授權而使用 DC，也不得直送 X**。

## 預設自動整合遠端 localX `DISPATCH_DEFAULT_LOCALX_CONTINUATION_V1`

「自動」表示持續執行當下可合法施工的每一步，任何進度回報不得中斷施工。同工單 `/派工` 已授權範圍包含 CI SUCCESS 後 **GitHub `localX` PR 合併**，預設 `GITHUB_LOCALX_FIRST`，不需要另下一張 PR 合併口令，也不需要 DC。Windows 狀態未驗證仍記 `WINDOWS_LOCALX_SYNC_PENDING`。
## GitHub 遠端 localX 預設整合 `GITHUB_LOCALX_FIRST_V1`

已授權的同工單 PR 在 exact SHA CI 全 SUCCESS、PR base=`localX`、scope／work branch／mergeability／最新 base drift 檢查後，即用 GitHub `expected_head_sha` 合併。合併後 readback PR merged 與 remote HEAD，記 `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`；不可把遠端結果冒稱 Windows 已對齊或人工 UAT 通過。這不是 DC 斷線備援；不必探測本機。產品 X 仍需當次 `/推推`。
## 連續執行硬閘門：`DISPATCH_TURN_EXIT_GATE_V1`

**不得停止程序**。依 `AGENTS.md` 和 `.agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json` 直接執行下一個動作，禁止把狀態決策變成預先收尾程序：

1. 讀當前 PR `base/head_sha` 以及 **exact SHA** Product Regression 的 `run_id/status/conclusion`（含 jobs）；不存在、SHA 不符或資訊不足 → `RECONCILE_ONLY`，定向補讀，不得沿用舊 GREEN。
2. `requested/queued/waiting/pending/in_progress` → `CONTINUE_POLL`，同一回合繼續查狀態；每 2–3 次操作回報，而非結束。避免高頻重抓完整 CI log。
3. `completed/success` → `LOCALX_INTEGRATION_PENDING`：這是**待執行動作**而非待使用者再次授權；既有 `/派工` 範圍直接續行預設 GitHub `localX` 合併，不碰 DC。保留本機修改；即使 PR 仍 Draft，也不能以「綠燈但還未合併」作為完成。其他 terminal conclusion → `REPAIR_AND_RETEST`。
4. `localX` 整合、Issue close/readback、`NEXT_ISSUE_DISCOVERY_REQUIRED` 未完成 → `CONTINUE_FINALIZATION`，不能冒稱 `RELEASED`；只有所有義務已驗證才宣告交付完成。
5. **遇阻換合法動作繼續做**：`BLOCKED_WITH_EVIDENCE` 只表示該操作遭拒；其餘允許的來源查證、提交、測試與獨立施工仍直接執行。若所有工具實際無法使用才據實標示 `RUNTIME_LIMIT_UNRESOLVED`；不得把這些代碼拿來預先停工。

只增加現有流程的真實退出決策，不需要 Codex、不建新排程、不改本機施工授權，也不恢復退役 lease／claim／Flow v2。

## 發出產品 PR 之後必須續作

1. `PR_OPEN / CI_QUEUED / CI_IN_PROGRESS / CI_PENDING` 一律 `CONTINUE_POLL`，**不是可結束的交付狀態**；在當前回合持續輪詢 exact PR SHA 與對應 run，不得把「正在測試」當成派工完成。
2. `CI_SUCCESS` 且 PR 可整合，**直接 GitHub PR merge `localX`**，回讀 PR/remote HEAD，工單留言、close/readback；Windows 手動更新與 UAT 待完成，記 `WINDOWS_LOCALX_SYNC_PENDING`，不能虛構 `LOCALX_SYNCED` 或 DC 斷線。整段不必使用者再喊「繼續」。
   **重要先後次序**：GitHub `localX` merge＋遠端 SHA 回讀成功（本機待 Windows 同步）後，**立刻啟動 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，同步完成原 Issue 留言／close/readback；**不得等 Issue CLOSED 才找下一張**，也不得以 Issue close/readback 為流程終點。
   搜尋下一張 OPEN 且前置工單已完成的可執行 Issue；檢查相同工作是否已有 owner/PR，避免重複；可施工就建立真實工作分支、寫入派工留言並**完成首個真實施工動作**，持續執行下一張。**只找到 Issue 號碼、只寫派工留言或只建立分支都不等於接取成功，更不是退出條件**。已有下一張但未開工 → `NEXT_ISSUE_START_REQUIRED`；已有下一張且接取證據可回讀 → `NEXT_ISSUE_ALREADY_STARTED / CONTINUE_NEXT_ISSUE`，仍不能正常結束回合。只有實際核查 OPEN 工單及前置／owner／PR 後無可執行者，附可追溯清單與 `NO_ELIGIBLE_ISSUE` 證據，才允許整條派工佇列正常結束；不得假報成功派工。

3. `CI_FAILURE / CANCELLED / TIMED_OUT`：讀取 job/step/log，定位和修復後再次測試；若 run 完全缺席，先修正 workflow branch/path 接線並觸發，不得聲稱已驗收。
4. 回報至少每 2–3 次實質操作一次；回報不構成退出。**不得停止程序**：若某一步驟受阻，繼續可合法完成的下一步；完全無法實際操作才據實保留 blocker 與最後可驗證的 PR/SHA，不得聲稱 DONE。
5. 產品 `localX → X` 仍需使用者當次 `/推推`。不加新的 GitHub 分支保護、不恢復 Flow v2。
