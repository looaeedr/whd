---
name: 派工
description: 人工指定「派工」時使用：執行 WHD 的 PM → Implementer → QA 角色切換、GitHub owning Issue、checkpoint/journal、30 秒進度回報與 remote QA 監控協定。
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: dispatching-workflow
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 派工

這個 Skill 是 WHD 的施工狀態機。它的目標不是模擬「把工作丟給另一個人」，而是確保每張已核准工單都有可追溯 authority、真正的 owning Issue、唯一施工 ownership、可恢復 checkpoint/journal、可被其他 AI 看見的進度、可判讀的 QA 證據，以及明確的 PM → Implementer → QA 轉移。

**REQUIRED SUB-SKILL:** monitoring-remote-qa

同步遠端 QA / GitHub Actions QA 一旦啟動，上述 sub-skill 強制生效；必須鎖定同一 `run_id + head_sha` 主動輪詢到 terminal。

### LIVE_REMOTE_QA_AUTHORITY_BRIDGE
claim/checkpoint 的 remote QA 狀態只是 durable snapshot；只要存在 exact `run_id + head_sha`，每次 resume / poll / final gate 都必須 fresh-read GitHub Actions，**live run status/conclusion 永遠高於 snapshot**。
- claim/checkpoint 若仍是 `queued / in_progress / WAITING_REMOTE / RUN_NOT_CREATED`，但 live exact run 已 terminal，立即標記 `stale remote-QA snapshot`；禁止套用 10 分鐘保護，也禁止沿用舊的「poll to terminal」next action。
- live exact run `completed + success` → 同一 flow 立即 reconcile durable state，接續 counts/invariants、cleanup、drift audit、Issue closure/release；有 dependency-unblocked successor 時續做下一票。
- live exact run failure/cancelled/timed_out → 同一 flow 立即讀 exact failed-job evidence、分類並 repair/retry；不得因 stale snapshot 假等。
- stale snapshot 只能觸發 reconcile/recovery，**不能成為 stop condition**；本 bridge 與 `monitoring-remote-qa` 的 stale-wait / terminal continuation 規則同義，衝突時採較嚴格的 continuation 規則。

### USER_VISIBLE_CHECKPOINT_GATE_BRIDGE
本 Skill 一旦進入長流程、remote QA、recovery 或 closure chain，強制服從 `執行開發任務` 的 `USER_VISIBLE_CHECKPOINT_GATE`。該 gate 是 user-visible CHECKPOINT 的唯一 canonical authority；本 Skill 不複製其欄位／refresh state machine，且不得建立第二套 CHECKPOINT authority。

- 需要顯示 CHECKPOINT 時，沿用 canonical gate 的固定標題、欄位與重大 state transition refresh 規則。
- progress update 不得取代可見 CHECKPOINT；30 秒 observation 仍只屬 progress。
- non-terminal CHECKPOINT 不是停工點；顯示後仍依本 Skill 原有 owner contract 繼續 next action。
- 本 Skill 只保留自己的 domain responsibility；CHECKPOINT 呈現責任一律 bridge 回 canonical gate。

### NON_TERMINAL_CONTINUE
只要本票仍有任何 required step 處於 pending，例如 Requirement/RED、production/test/Skill 修改、GREEN 驗證、remote QA、workflow cleanup、tested-head → closing-head drift audit、AI Library writeback、owning Issue terminal evidence/closure，該狀態只能標示為「進行中／pending」，**但 pending 本身不是停工點，也不是結束回合的理由**。

- progress update、CHECKPOINT、「尚未完成」、「因此不宣稱完成」都只是 observation，不能當作 `return` condition。
- 除非使用者明確中止、遇到不可繞過且需要外部輸入的 capability/blocker，或安全／專案硬閘門明確要求停止，否則必須在同一次可用工作流程中立即執行下一個可執行 action。
- 若遇 blocker，必須先把能完成的非阻塞 prerequisite/evidence 做完，再精確記錄 blocker；不得以籠統「pending」提前結束。
- 「不假報完成」與「持續施工」是兩個獨立義務：前者禁止假綠，後者禁止非終態自行停工。
- 任何 user-visible progress/checkpoint 後，只要沒有合法 stop condition，就必須接續下一個 tool/action；不得輸出狀態後直接結束回合。

### FINALIZATION_TRANSACTION_HARD_GATE_V1

Child acceptance terminal 與 process closure 是兩件事。任何 child 進入 `TERMINAL_SUCCESS / TERMINAL_FAILURE` 後，仍必須服從 `tools/continuity_controller.py` 的 canonical `ClosureState`；terminal checkpoint **不是** turn-exit authority。

固定 durable closure progression：

```text
FINALIZATION_PENDING
→ ISSUE_CLOSE_PENDING
→ RELEASE_HANDOFF_PENDING
→ CLOSED
```

- `FINALIZATION_PENDING`：**先**把 terminal checkpoint durable 推進到 `ISSUE_CLOSE_PENDING`；此階段禁止提前 mint finalization proof。
- `ISSUE_CLOSE_PENDING`：在這個 exact、之後不再改寫的 checkpoint 上執行 `authorize-finalization → verify-finalization-proof`。proof GREEN 後到 owning Issue close 完成前，**禁止任何 checkpoint mutation**；直接 close Issue，立即 fresh-read 驗 `closed/completed`，readback 成功後才推進 `RELEASE_HANDOFF_PENDING`。
- `RELEASE_HANDOFF_PENDING`：最後一個 coordination mutation 必須把 **checkpoint `closure_state=CLOSED` + shared claim `phase=RELEASED` + successor/chain handoff** 放在同一個 durable coordination commit；禁止先 release claim 再另補 checkpoint，因 release 後 owner 已失去 active mutation authority。
- `CLOSED`：只代表本 child 的 closure transaction 已完整落盤；若 `chain_state=NEXT_CHILD_EXECUTABLE`，Master continuity 仍必須立即前進下一 child，不得把 child CLOSED 當 Master terminal。
- 任一 pending closure state 都必須有非空 `closure_next_action`；`assert_turn_exitable` 必須拒絕 normal return。scheduler/interactive executor 都不得以「checkpoint 已 terminal」「Issue 已 close」「PR 已 merge」單項證據繞過。
- 舊 terminal checkpoint 若缺 closure metadata，canonical loader 必須 fail-safe recovery 成 `FINALIZATION_PENDING`，由 durable evidence 重建 closure；不得默認成已 CLOSED。
- `authorize_finalization()` 的 machine gate 必須直接拒絕 `closure_state != ISSUE_CLOSE_PENDING`；這不是只靠文件順序提醒。
- finalization proof 綁 checkpoint fingerprint；proof 產生後若又 advance closure、補 evidence 或重寫 checkpoint，proof 立即 stale，必須重新回到 current `ISSUE_CLOSE_PENDING` checkpoint 產生新 proof。
- 本節只定義派工責任；狀態 schema、合法 transition、resume/turn-exit machine enforcement 由 `executable-continuity-controller` 唯一擁有，禁止在 prompt/Skill 複製第二套 parser。

## 1. 啟動與能力邊界
### 1.1 先遵守專案啟動鏈
任何實質派工、production/test/Skill/SOP 修改前，先依 `AGENTS.md` 執行 Phase6 Knowledge Preflight，讀完 required Skills / required references 並留下 evidence。預計修改檔已知後，再依專案規則帶 `--changed-file` 重跑。

修改任務一律遵守 branch-first：反讀 authoritative target HEAD → 從該 HEAD 建新 work branch → 反讀 branch base → 才能寫檔。不得直接 patch `cleanup/2d-3d-sync` / `main`。

當 target 是 X 第二主分支、或同時存在 A/B/C/D 等多個 Master 工單鏈時，**REQUIRED REFERENCE:** `個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md`。

### WORK_ORDER_LINEAGE_CONTRACT
當一個 Master / 工單被拆成 T1/T2/... 多張子票時，branch-first 的單位是**整張工單**，不是每張子票各自重新從 production 起跑。

- 派工開始時，從當下 authoritative production target HEAD 建立唯一長期 **工單主分支**，並記錄 work-order branch、base SHA、production target、production HEAD。
- 工單主分支是該 Master 在 final integration 前的 accepted lineage owner。每完成一張子票並通過必要 acceptance，就把 accepted result non-force 收回工單主分支，更新其 accepted HEAD。
- **子票不得重新從 production target 起跑**。下一張子票的 authoritative base 必須是目前工單主分支 accepted HEAD；如果 production 尚未包含上一張子票，這正是不能從 production 重開的原因。
- 若需要隔離修改／QA，可從目前工單主分支 HEAD 開短命 `task/QA branch`；該 branch 只負責隔離施工或驗證，驗收後 non-force 回到工單主分支，不得成為新的長期 lineage owner。
- 工單完成前，**production target 只作 integration target / drift authority**；可用來 refetch、比較 drift、檢查外部變更，但不得用其較舊 HEAD 覆蓋或取代前序 accepted lineage。
- 每張 child Issue / checkpoint / handoff 必須同時記錄 `work-order branch + accepted HEAD + production target + production HEAD`；只寫 production SHA 不足以作下一張票的 branch base authority。
- Tn → Tn+1 handoff 前必須證明 Tn accepted HEAD 是 Tn+1 base 的 ancestor；若不成立，先分類 lineage divergence，禁止直接施工。
- 只有整張工單 Combined Acceptance、durable Skill/AI writeback、config/protected invariants、temporary QA cleanup、tested-head→closing-head drift audit 全完成後，才把**整張工單 final verified work-order HEAD**對 production 做**一次 non-force 整合**。
- production 整合後才由 post-integration ticket / sentinel 以 actual production HEAD 作 authority；若 post-integration FAIL，從 actual production HEAD 開 fresh hotfix/revert branch，不 force target 回舊 SHA。
- 若既有工單已發生 T3/T4 類 lineage divergence，先保留所有已驗收 commit/evidence，建立或修復單一 work-order lineage，再續工；不得為了「從 production 重新開始比較乾淨」而丟掉前序 accepted work。

### X_SECOND_MAIN_INDEPENDENT_CHAIN_CONTRACT
當 `X` 被指定為第二主分支／主要整合目標（WHD 現行 `X = cleanup/2d-3d-sync`），且 A/B/C/D 等多個 Master 工單組可能並行時，本節是 `WORK_ORDER_LINEAGE_CONTRACT` 的強化硬閘門。

1. **每個 Master 都有自己的 frozen X base。** 建立 A/B/C/D 任一 Master 時，先反讀 X HEAD，記錄 `FROZEN_X_BASE_SHA`，從該 exact SHA 建該 Master 的 `WORK_ORDER_BRANCH`，並反讀證明 branch base 正確。若 A/B/C/D 是同一批次同時建立，除非使用者另有指定，應共用同一個 X snapshot SHA；不同時間建立則各自在建立當下凍結自己的 X HEAD。
2. **active chain 不追 X。** Master 建立後，即使 X 前進，也禁止 merge X → chain、rebase chain onto X、reset 到新 X、以新 X HEAD 取代 child parent，或因「X 比較新」重開 child branch。`CURRENT_X_HEAD` 只能用於 drift / integration-readiness 觀測。
3. **兄弟鏈完全隔離。** A/B/C/D 之間禁止 merge、rebase、cherry-pick 尚未進 X 的 production change、共用另一條 chain 的 accepted HEAD、temporary QA lineage 或 remote QA acceptance evidence。若存在真 dependency，該 chain 停在 dependency gate，不能偷搬 sibling commit。
4. **child parent 唯一合法來源是上一個 accepted HEAD。** `Tn accepted HEAD → Tn+1 base` 必須有 ancestor 證明；不得跳回 X，也不得跳到兄弟鏈。
5. **整鏈完成前禁止合回 X。** child GREEN、focused QA、單票 ACCEPT、局部 PR success 都不是 X integration gate。只有完整 Master Chain Task Acceptance 後才可進入 Integration Acceptance。
6. **Task Acceptance 與 Integration Acceptance 必須分離。** Task Acceptance 驗 sealed chain 本身；Integration Acceptance 才比較 `FROZEN_X_BASE_SHA → FINAL_CHAIN_HEAD`、`FROZEN_X_BASE_SHA → CURRENT_X_HEAD` 與兩者 overlap/conflict/drift。不得為了 integration readiness 反向污染已驗收 chain history。
7. **READY_FOR_X_INTEGRATION 不等於自動 merge。** 完整 chain 最多先到 `ACCEPTED / READY_FOR_X_INTEGRATION`。若 Master、工單或使用者明確寫 `DO_NOT_MERGE_X`／「完成後先不要合回 X」，必須停在此狀態直到取得新的 explicit authorization。
8. **對 X 的正式整合只能 non-force 且一次整鏈完成。** 整合前再次反讀 current X identity，完成 conflict/drift audit，確認 post-integration owner/sentinel；不得把 partial task 分段塞回 X。
9. **每張票與 QA identity 必須帶 chain authority。** 至少包含 `MASTER_ID / TASK_ID / TARGET_X / FROZEN_X_BASE_SHA / EXPECTED_PARENT_SHA / WORK_ORDER_BRANCH / CHAIN_HEAD / CURRENT_X_HEAD(observation only)`；remote QA 再鎖 `RUN_ID + HEAD_SHA + BRANCH`。若 RUN 尚未建立，狀態是 `RUN_NOT_CREATED`，不得等待不存在的 RUN，應立即處理 prerequisite。
10. **任何 cross-chain contamination 一律 fail closed。** frozen base 不明、parent 不符、兄弟鏈 commit 混入、active chain 被 merge/rebase newer X、RUN HEAD 錯鏈、partial task 被要求直接 merge X，都必須先停止該 chain 的 production mutation並修正 authority。

### 1.2 能力偵測
- 若環境真的支援獨立 Subagent Runtime，可以把 Worker/QA 放到隔離上下文；每個 Subagent 仍必須自行重跑相同 Preflight、讀相同 authority 並留下自己的 evidence。
- 若環境**不支援**真正背景 Subagent Runtime，必須由同一執行者在同一工作上下文自動完成角色切換，不能停下來等不存在的第三方。
- 不得宣稱「已派給工程師、等回報」而實際沒有可觀測的 runtime / task / result。
- 聊天回合不是 remote runner；需要跨回合續工的狀態必須落到 checkpoint / journal / GitHub Issue / remote run，而不是只存在對話文字。

## 2. 狀態機
固定狀態：

```text
[總控 PM]
    ↓ 使用者核准 Requirement RED + 工單 breakdown
[轉移至：實作者]
    ↓
[當前角色：Tn 實作者]
    ↓ 實作 + checkpoint
[轉移至：總控審查]
    ↓
[當前角色：總控審查]
    ↓ QA ACCEPT 或退回 Implementer
```

如果任務本身不需要拆成 T1/T2…，仍要依該任務的設計/驗收 gate 決定何時從 PM 轉 Implementer；不得因「任務小」跳過專案 Preflight、branch-first 或必要 QA。

## 3. PM：工單與 Authority Gate
### 3.1 Requirement RED-first
若需要拆工單，固定先讀：

`.agents/skills/engineering/拆解任務工單/SKILL.md`

PM 必須：

1. 依 Requirement 建立 requirement-level RED，且實跑到能證明目前狀態不符合使用者需求。
2. 與使用者逐條確認 RED 是否代表真正需求。
3. 在使用者核准 RED 前，**不得拆解工單**、不得建立 tracker/local ticket、**不得轉移至：實作者**。
4. RED 核准後才草擬 T1/T2… breakdown；breakdown 本身仍需使用者第二次核准。

### 3.2 每張票的 Authority
每張核准工單至少明列：

- `Requirement Authority`
- `Approved RED IDs`
- `AI Library References`
- `AI Library Writeback`
- baseline / target SHA
- blocking dependency
- acceptance criteria
- Combined Acceptance owner（若適用）

拆票前必須實際搜尋/讀取相關 `個人AI檔案庫/**`。不得只口頭寫「AI 庫已讀」。若 AI 庫與使用者本輪已核准規格衝突，**最新使用者核准規格**是 authority，並把 AI 庫修正標成 `AI Library Writeback: REQUIRED`。

### 3.3 GitHub owning Issue 硬閘門
若施工來源是 GitHub repository，**每張核准工單都必須先建立真正的 GitHub owning Issue**，再遠端反讀確認：

- `issue_number`
- canonical URL
- title
- baseline/target SHA
- Approved RED IDs
- Requirement Authority
- AI Library References / Writeback
- dependency
- acceptance criteria

`issue_number` / URL / title 任一 undefined、null 或空值即 fail closed。`.scratch/**/issues/*.md`、聊天中的 T 編號、checkpoint、branch 名稱都只是 mirror/provenance，不能代替 GitHub owning Issue。

若事後才發現漏建 Issue：立即停止新增 production 變更，補建 Issue，並明確標示 **Retroactive provenance / 施工後補建**；寫入實際施工 branch、已發生 commit/run/evidence 與 target。不得假裝事後 Issue 原本就存在。

### 3.4 NO_WORK_WITHOUT_CLAIM / 唯一 execution claim
GitHub owning Issue 建立並反讀後，**還不能直接施工**。多 AI / Worker 共同使用同一 tracker 時，**一張 GitHub owning Issue 同時間只能有一個 execution claim owner**。

1. `production/test/Skill/AI Library 第一筆 write 前`，Worker 必須先成功取得該 owning Issue 的 execution claim。
2. claim authority 必須位於所有 Worker 都讀寫同一份的 **shared coordination namespace/ref**，並使用 **atomic** / mutually-exclusive create-or-compare-and-swap primitive。所有 Worker 必須先讀同一 authority，再嘗試 claim。
3. 每個 implementation branch 各自建立 `.lock` 的 **branch-local lock** 不能作為互斥 authority；兩個 AI 可在不同 branch 同時成功建立同名檔，這不具全域排他性。
4. `Issue comment / label`、聊天宣告、checkpoint 文字、branch 名稱可作 human-readable mirror，但**不是 execution claim authority**，除非底層操作本身具備已證明的 atomic ownership contract。
5. claim 最低 ownership 欄位：owning Issue number/URL、worker identity、work branch、`claimed_at`、base SHA、目前 HEAD（若已存在）。
6. **claim 失敗**、shared authority 已顯示其他 owner、或 atomic compare-and-swap 衝突時，必須 fail closed：**禁止施工該 Issue**、禁止另開平行實作來繞過 claim。若 dispatch pool 尚有可執行的未認領工單，依 `NON_TERMINAL_CONTINUE` 立即轉往下一張，而不是停在「已被鎖定」。
7. 若目前環境沒有任何可提供 shared + atomic ownership 的能力，必須把它記成 capability blocker；不得把 branch-local 檔案或 comment 假裝成安全鎖。

#### EXECUTION_INSTANCE_IDENTITY_V1

新取得 execution claim 時，`worker` 必須是**唯一 execution-instance 的 ownership identity**，不得再用所有聊天室共用的裸 `worker=chatgpt`，也不得用裸 `worker=scheduler` 當新 claim owner。

- interactive ChatGPT 新 claim 的 canonical 形式：`chatgpt.<instance-token>`。
- scheduler / automation 新 claim 的 canonical 形式：`scheduler.<automation-id-or-token>`。
- identity 必須相容 trusted Remote Guard 現行 parser：`[A-Za-z0-9_.-]{1,64}`；不得使用冒號、空白或超出 parser contract 的字元。
- `<instance-token>` 必須在該 execution instance 建立時產生並保持穩定，且要能區分同時存在的其他 ChatGPT / scheduler invocation。不得把固定字串 `chatgpt` 當成 token。
- `executor_source` 只屬 coarse provenance / routing classification；它**不是 ownership identity**、不是 claim authority，也不得因 `executor_source=chatgpt_interactive` 或 `scheduler` 相同就把兩個 execution instance 視為同一 owner。
- 新 claim atomic acquisition 成功後，必須立刻在 user-visible CHECKPOINT / claim report 回顯 exact `worker` identity；之後使用者看到 shared claim 時，才能把 repository provenance 對回實際聊天／排程 execution instance。只有 GitHub 使用者名稱或 `executor_source` 不足以完成這個對應。
- `tools/execution_claim_guard.py` 與 Remote Guard 仍以 claim 中 exact `worker` 做 owner equality gate；呼叫 guard 時必須帶同一個 exact identity，不得降級只比對 `executor_source`。
- claim acquisition path 對**新 claim**看到 generic `worker=chatgpt` / `worker=scheduler` 時必須 fail closed，而不是建立不可追溯的新 ownership。
- legacy migration：已經 active 的 legacy claim（例如既有 `worker=chatgpt`）**不得只為升級格式而中途改 owner**。它保持原 owner 到正常 terminal/release，或依 canonical stale takeover 流程合法轉移；terminal/release 後建立的 successor / new claim 才強制使用 unique execution-instance identity。
- stale takeover 寫回 scheduler owner 時，同樣必須使用該 scheduler invocation 的 unique `scheduler.<automation-id-or-token>` identity；`stale_takeover.previous_executor_source` 可保留 coarse provenance，但不能取代 previous exact worker evidence。

### EXECUTION_CLAIM_PREWRITE_HARD_GATE
成功取得 atomic claim **不等於已獲准寫入**。在每一次會建立或改動 repository state 的動作前，必須立即執行 `tools/execution_claim_guard.py`，以 shared coordination claim 的最新內容作唯一 authority；不得只相信 Issue comment、branch 名稱、聊天記憶或先前一次 guard 結果。

- `branch-create`：任何 implementation / QA branch 建立前都必須先驗 issue、canonical URL、worker、claimed work branch、base SHA 與 claim active state。
- `write` / `commit` / `pr-write`：production、test、Skill、AI Library、workflow 或其他 repo write 前都必須 fail-closed 驗證 owner 與 branch。
- `write/commit` 必須帶實際 `--changed-file`；缺 path identity 一律 fail closed。若 target 符合 `.agents/skills/**/SKILL.md`，同次 guard 還必須帶 `--preflight-evidence`，並由 canonical Phase6 Preflight evidence 證明 `寫技能` + required Skills/references 全部完成；execution claim 不得取代 Skill-authoring Preflight。
- `qa-dispatch` / `workflow-dispatch`：遠端 QA/Actions 啟動前必須重新驗證；只有 claim 中明確列出的 delegated branch 可替 owner branch 執行 QA。
- missing claim、non-owner、issue/URL mismatch、branch mismatch、malformed/stale/inactive/ambiguous claim 一律 **FAIL**；不得用新 branch、手動 comment、重跑 workflow 或其他旁路繞過。
- guard 成功只授權該次 action，不建立永久 session 權限；下一次 repo mutation 必須再次驗證最新 claim。
- 若 guard 本身不可執行或無法讀到 shared claim，視同 capability blocker，禁止 repo mutation；不得降級回 documentation-only `NO_WORK_WITHOUT_CLAIM`。

CLI precondition 形式：

```text
python tools/execution_claim_guard.py --claim <shared-claim-json> --issue <N> --worker <identity> --branch <branch> --action <branch-create|claim-takeover|write|commit|qa-dispatch|workflow-dispatch|pr-write> --base-sha <base SHA> --head-sha <current HEAD> [--changed-file <repo-relative-path>] [--preflight-evidence <phase6-evidence>]
```

只有 exit code 0 / `EXECUTION_CLAIM_GUARD_GREEN` 才能進行緊接著的單次 action。

#### POST_COMMIT_CLAIM_HEAD_RECONCILIATION_V1
`commit/write` 在合法 GREEN prewrite guard 後把 work branch 從 claim HEAD `H0` 推進到 `H1` 時，shared claim 會短暫仍記 H0。此時禁止把它誤判成普通 stale claim，也禁止直接無 guard 改 claim。

固定做法：
1. fresh-read shared claim blob 與 live work branch H1；
2. 用 Remote Guard 送一張新的 `action=write` request，`head_sha/tested_target_sha=H1`，且 `changed_file` 只能是 exact `.dispatch/claims/issue-<ISSUE>.json`；
3. canonical guard 必須 machine-verify H1 是 H0 的單一直接子 commit，並反查同 Issue 上 prior exact GREEN `write|commit` request/receipt；owner/branch/base/H0/current claim blob、commit changed-file set、receipt window 全部綁定；
4. 新 reconcile receipt GREEN 後，才以 current claim blob SHA 做 optimistic CAS，把 claim `head_sha` 更新為 H1；
5. CAS 後立即 fresh-read verify，再為下一個 repo mutation 重新取得新的 single-use guard。

prior receipt 不能直接重用成 claim write；一般 production/test/Skill `write` 也不能使用此 exception。驗證任一不符即 fail closed，分類 `REMOTE_GUARD_STALE_IDENTITY_AFTER_AUTHORIZED_COMMIT` 或更窄 root cause，禁止旁路。

### 3.5 CLAIM_PROGRESS_STATE / 工單進度共享
execution claim 不只記「誰拿走」，同一 durable coordination state 必須讓其他 AI 看得出**做到哪裡**。至少保存：

- `phase/state`：例如 CLAIMED / RED / IMPLEMENTING / GREEN / REMOTE_QA / CLEANUP / DRIFT_AUDIT / CLOSING；
- `last_update`；
- work `branch`；
- current `HEAD`；
- `remote QA run/status`（有 remote QA 時同時保存 `run_id + head_sha`）；
- `next_action`；
- `blocker`（沒有則明確為 none/null）；
- checkpoint/journal pointer（長任務適用）。

進度不是只在最後補寫。claim acquired、Requirement/contract **RED**、第一筆/重要 production write、focused/full **GREEN**、remote QA queued/in_progress/terminal、workflow **cleanup**、tested-head → closing-head **drift audit**、AI Library writeback、Issue closing/release 等重大 transition 都要更新 `CLAIM_PROGRESS_STATE`。若 store 支援 revision/ETag/SHA，progress update 也使用 optimistic concurrency / compare-and-swap，避免另一個 Worker 的較舊狀態覆蓋新狀態。

列出目前未完成工單時，固定分成：

- `我持有`：顯示 Issue、phase/state、last_update、branch/HEAD、QA 狀態、next_action、blocker；
- `其他 AI 已鎖定`：顯示同樣進度，但不得進場施工；
- `尚未認領`：可由下一個 Worker 嘗試 atomic claim。

### 3.6 STALE_CLAIM_RECOVERY / stale owner 接管

<!-- STALE_CLAIM_EXECUTABLE_TAKEOVER_V1 -->

stale owner 接管的 canonical machine authority 是 `tools/stale_claim_takeover.py`；scheduler 不得靠 prompt、聊天時間感或單看 claim 未更新自行宣告卡住。

- 預設 stale threshold 固定為 **600 秒（10 分鐘）**。
- fresh evidence 至少帶：claim `last_update`、live work-branch HEAD + HEAD commit timestamp、claim 綁定的 exact remote run fresh status/updated_at（若有 run_id）。
- exact run 為 `queued/in_progress/waiting/requested/pending` 時固定分類 `RUN_LIVE`，禁止 takeover，即使 claim 本身已超過 10 分鐘。
- **一般 foreign owner（非 scheduler）**仍維持 600 秒規則：最近 durable progress 未滿 600 秒為 `WAIT_ON_FOREIGN_RUNTIME`；到 600 秒且沒有 active exact run 才可 `EXECUTOR_STUCK/actionable=true`。
- **foreign scheduler owner** 不得再用 claim freshness 冒充 runtime liveness：fresh-read exact claim blob 後，必須讀 owner-authored `WHD_SCHEDULER_RUNTIME_LIVENESS_V1` heartbeat/lease；有效 lease 固定 backoff。
- foreign scheduler 在「無 active exact run + heartbeat missing/expired + exact claim/blob/branch/head identity 一致 + durable progress age >= 90 秒」時，可由 evaluator 分類 `ORPHANED_SCHEDULER_OWNER/actionable=true`，不必等滿一般 600 秒。
- same-lane cross-cycle **ownership** resume 不做 takeover；但為避免 `:00 / :20 / :40` 等 sibling wake 同時進場，`claim.worker == current scheduler lane` 時仍必須先套用 `SCHEDULER_RUNTIME_LIVENESS_V1` 的 same-lane invocation mutex。只有 matching END、或最後 heartbeat 已 stale > 300 秒，才可由新 invocation 進場 mutation；fresh heartbeat ≤ 300 秒時只讀退讓。
- live branch 已前進時，以 **observed live HEAD** 作 resume/takeover identity；recent commit 會重置 stale age，舊 commit 超過 threshold 才可接。
- evaluator malformed/missing evidence 必須 fail closed。
- 真正 ownership 轉移使用 Remote Guard 單次 action `claim-takeover`，取得 fresh GREEN receipt 後才能 CAS 更新 shared claim；不得拿一般 `commit` receipt 或舊 receipt 代替。
- CAS writeback 必須保留既有 evidence，寫入 `executor_source=scheduler` 與 `stale_takeover.previous_executor_source / observed_stale_seconds / observed_live_head_sha / evidence / taken_over_at`。
- takeover 後下一次 repository mutation 仍要重新取得對應 action 的 fresh guard；`claim-takeover` receipt 不是 session token。

「很久沒更新」不等於可以偷鎖。stale claim recovery 必須先查 owning branch、目前 HEAD、checkpoint/journal、`last_update`、remote QA run/status、Issue 最新活動與既有 owner 是否仍有 non-terminal work。

- **不得直接搶鎖**、覆蓋 owner 或刪除 claim。
- 必須使用明確的 recovery / compare-and-swap 路徑，只能在「讀到的舊 revision/owner 仍然沒變」時原子轉移 ownership。
- takeover 要留下 `recovery evidence`：原 owner、舊 revision/last_update、檢查過的 branch/QA/checkpoint、判定理由、新 owner、接管時間與 resume point。
- 若 remote QA 還在 non-terminal，先遵守 `REMOTE_QA_ACTIVE_LOCK`；不得為了接管再 trigger 一套重覆 QA。
- 無法證明 claim stale 或無法安全 compare-and-swap 時，保持 blocked，不得並行施工同一票。

只有 owning **Issue terminal** evidence、必要 workflow cleanup、durable state/writeback、tested-head → closing-head drift audit 都完成後，才可 `release claim`。單純 code GREEN、commit 完成或 remote QA success 都不足以釋放 ownership。

### 3.7 PM → Implementer
只有 requirement RED 已核准、breakdown 已核准、owning Issue 已建立且反讀成功、必要 AI Library authority 已讀完，且該 Worker 已成功取得唯一 execution claim，才輸出：

`[轉移至：實作者]`

然後同一次工作流程直接進下一狀態，不以「已派工」作為停工點。

## 4. Implementer：實作與 Checkpoint
### 4.1 角色標記
進 Worker 時回覆開頭使用：

`[當前角色：Tn 實作者]`

`Tn` 依實際工單替換。Implementer 專注於該票 production/test/Skill 修改，不混入新的 PM scope decision。

### 4.2 實體 checkpoint
每完成一個可恢復的實質修改單位，必須產出**實體 checkpoint path**；可使用 ZIP、durable worktree snapshot、remote artifact 或專案核准的等價形式。checkpoint 不能只是一段聊天文字。

checkpoint / state 至少記錄：

- task id / 工單 id
- 目前角色
- branch + HEAD
- 已完成 / pending / failed / blocked
- 相關 production/test/Skill/AI Library 檔案
- 驗證命令與最後結果
- 下一步 resume command
- owning Issue

若下一步是長回歸，已有尚未封裝的變更時，**先封 checkpoint 再進長回歸**。

### 4.3 checkpoint provenance
每個已驗收 checkpoint 都要保存 **checkpoint provenance**：來源 FULL/上一 checkpoint SHA256、已修改檔案清單與 SHA256，組成可重算的 **execution tree fingerprint**。

fresh extract、checkpoint restore、Runtime 重建或手動複製後，在 resume 前重算 execution tree fingerprint，與**最近已驗收 checkpoint**比對。

若出現部分檔案舊、部分新版、來源包 identity 不符或 fingerprint 不同，標記為**混合狀態**。混合狀態不得靠 mtime、聊天記憶或挑檔補拷貝續工；必須回乾淨目錄從最近已驗收 checkpoint 完整恢復，再重放未驗收變更。

### 4.4 Implementer → QA
實質修改與 checkpoint 已落盤後輸出：

`[轉移至：總控審查]`

然後進 QA。

## 5. QA：審查與完成條件
### 5.1 角色標記與審查責任
QA 開頭使用：

`[當前角色：總控審查]`

QA 以獨立 reviewer 視角對照 Requirement Authority、actual diff、tests、AI Library 與 owning Issue。若不合格，退回 Implementer；不得為了關票降低 oracle、改規格或掩蓋失敗。

### 5.2 AI Library QA
任何 `AI Library Writeback: REQUIRED` 在 QA ACCEPT 前必須：

- 實際落盤；
- 遠端反讀引用路徑；
- 移除/標記會誤導未來施工的 stale authority；
- 確認內容與最終已核准 requirement / production 結果一致。

### 5.3 Owning Issue QA
GitHub ticketed work 必須反讀 owning Issue，確認 terminal run / PASS-FAIL、final head / target SHA、dependency、acceptance 結果已回寫。沒有 owning Issue 或只有 `.scratch` mirror，不得宣告工單完成。

若使用 execution claim，QA 同時確認 claim owner 與實際施工 branch 一致，`CLAIM_PROGRESS_STATE` 已更新到目前終態，且 claim 尚未在 cleanup / drift audit / Issue terminal evidence 完成前被提早釋放。

### 5.4 QA 完成條件
若本票進入測試回歸，只有同時滿足下列條件才可 ACCEPT：

- intended nodeids 全部有 terminal 狀態，沒有 pending；
- 若要求全綠，failed = 0；
- collection count / **collection SHA** 與 journal 相符；
- 無殘留 pytest / Xvfb / child Python process；
- timeout 的 teardown/harness 問題有獨立紀錄，不混成 production failure；
- 已通過區段沒有因 timeout 被無意義重跑；
- REQUIRED AI Library Writeback 已落盤並反讀；
- owning Issue terminal evidence 完整；
- 若啟動 remote QA，已完成第 7 節 lock 到 terminal、cleanup 與 drift audit；
- execution claim 的 terminal progress 已寫回，Issue terminal + cleanup + drift audit 後才 release claim。

## 6. 測試 Runner / TIMEOUT 協定
### 6.1 每批獨立 process group
每個 pytest / GUI batch 使用獨立 **process group / session**（例如 `start_new_session=True` 或等價機制）。timeout、取消或外層 Runtime 中斷時，要終止**整個 process group**，不能只 kill 父 pytest。

優先 TERM，短暫 grace 後再 KILL；最後確認沒有殘留 pytest / Xvfb / child Python。若 runner 有 `killpg` 能力，以整個 process group 為 cleanup 單位。

禁止留下 99% CPU orphan pytest 污染下一批。

### 6.2 Xvfb ownership / hard kill
長 GUI batch 不依賴 `xvfb-run` 當唯一 lifecycle owner。優先由 runner 自行啟動 Xvfb、等待 DISPLAY ready、傳入 pytest，最後自行清理。

Linux 外層可能 `SIGKILL` runner 時，只靠 Python `finally` 不夠；Xvfb child 要有 kernel **parent-death** guard（例如 `PR_SET_PDEATHSIG` / `PDEATHSIG`）。hard-kill regression 必須真的 `SIGKILL` 父 runner，再確認 Xvfb PID 已死亡/成 zombie，不只 mock callback。

若只能用 `xvfb-run`，只跑短批，並以 pytest log summary 判讀測試本體，不用 wrapper timeout 直接判 production fail。

### 6.3 TIMEOUT 分類
收到 TIMEOUT / 外層時間切斷後，第一動作是讀 log + process 狀態，**不得直接重跑**。

**complete**

- 有完整 pytest summary；
- 沒有 failed / error / collection error；
- 即使 wrapper 後續 timeout，測試本體仍算完成。

**complete_teardown_timeout**

- pytest 已明確印出**完整 PASS summary**；
- 但 interpreter / Tk / Matplotlib / Xvfb / wrapper 在 teardown 不退出。

只有完整 PASS summary 才准用此狀態。**只看到點號**、局部 `%`、單顆 print、scene dump、`[100%]` 但沒有最終 summary、或 wrapper 自己說 success，都**不得標記 complete_teardown_timeout**。

此狀態記測試本體完成，kill 殘留 process group，並另追 harness/teardown；**不得重跑已完成** nodeids。

**incomplete_timeout**

- 沒有完整 summary，或只跑到中途。
- 不得判 PASS，也不得直接判 production FAIL。
- kill process group，保存已完成 nodeid 證據，只重跑 pending。

只有 pytest 自己的 `FAILED` / `ERROR` / collection failure 才是**真 RED**。

### 6.4 Timeout 後縮批
`incomplete_timeout` 後把未完成範圍二分：例如 100 → 50 → 25 → 10 → 單檔/單 nodeid。

已具完整 PASS summary 的 batch/nodeid 從 pending 移除，禁止為方便整段重跑。單顆獨立 PASS、放在某 prefix 後才 hang/fail 時，用 prefix/binary bisection 找 order-dependent 污染源；禁止改 production 幾何、尺寸常數或放寬 oracle 來讓 gate 過。

### 6.5 Journal / Resume
長回歸維護可恢復 journal（JSONL 或等價），每批結束立即落盤，至少包含：

- collection count；
- collection SHA / nodeid list hash；
- batch / nodeids；
- `complete` / `complete_teardown_timeout` / `incomplete_timeout` / `failed`；
- passed / skipped / failed；
- log path；
- elapsed time。

Resume：

- collection count 或 SHA 改變 → **拒絕沿用舊 journal**；
- collection 相同 → **只跑 pending**；
- Runtime 被切斷 → 先讀現有 log/journal，再決定續跑範圍，不憑聊天記憶重建進度。

journal 的 collection identity 不能代替 source-tree execution tree fingerprint；兩者都一致才可安全 resume。

## 7. Remote QA Active Lock
### 7.1 啟動監控
只要建立 GitHub Actions / remote current-head QA / 等價 remote CI run，立即讀並使用：

`.agents/skills/engineering/monitoring-remote-qa/SKILL.md`

鎖定本輪 **`run_id + head_sha`**。workflow trigger 只代表監控開始，不是 QA 完成。

### 7.2 REMOTE_QA_ACTIVE_LOCK
`monitoring-remote-qa` 一旦鎖定 non-terminal run，派工狀態機進入 **`REMOTE_QA_ACTIVE_LOCK`**。

Lock 期間不得：

- 回 Implementer 做新修改；
- 探索其他模組；
- 啟動下一張票；
- 以「順便先查」插入非 polling 工作。

Lock 期間允許：poll run/jobs/steps、terminal failure log classification、必要的 30 秒使用者進度回報。

若 job failure：先讀 failed-job log，依本 Skill TIMEOUT 分類與 `diagnosing-bugs` 判定 production / harness / workflow failure。只有需要 replacement run 時才解除舊 run 的 terminal lock；新 run 建立後立即以新 `run_id + head_sha` 重新上鎖。

### 7.3 Terminal 後仍未完成
`completed + success` 後仍要：

- 取得 exact PASS/FAIL + invariant evidence；
- 清除 one-shot workflow / trigger；
- 遠端反讀 cleanup；
- 更新 checkpoint/journal/state；
- 做 tested-head → cleaned-head drift audit；
- 回寫 owning Issue terminal evidence。

全部完成才可 QA ACCEPT / close。

聊天/工具 Runtime **不得成為 remote QA scheduler**。長 run 本身要能 durable checkpoint/resume；若 Runtime 中斷，下回合從既有 `remote_qa_run_id` / `run_id + head_sha` 接手，禁止因聊天斷線重新 trigger 全套。

## 8. 30 秒進度回報
只要派工任務尚未完成，對話層**每 30 秒**至少回報一次；內容至少包含：

- **目前工單**；
- 正在做什麼；
- **最新測試**或進度數字；
- 是否 blocked，以及 blocker 是什麼。

回報只是觀測點，**不得中斷**正在執行的正常工作、不得因此 kill 測試、不得把回報當作停工點。若單次不可中斷 tool call 本身超過 30 秒，工具返回控制權後立即補報。

未完成前不得只回「還在跑」後結束；TIMEOUT 也不是停工理由，而是進入 log 判讀、process-group cleanup、縮批與 resume 的觸發條件。

## 9. 掃描深模組來源檢查
若工作由 `掃描深模組` 候選轉入實作，任何 Implementer production write 前再確認：

- owning Issue 已建立並反讀；
- 唯一 execution claim 已取得；
- breakdown 已指定 AI Library Writeback owner；
- breakdown 已指定 Combined Acceptance owner；
- 任一 ownership 缺失就退回 PM 補齊；branch、checkpoint、HTML 報告、`.scratch/**` 都不能代替；
- closing owner 的 QA 必須包含 AI Library writeback、Combined terminal QA、workflow cleanup、drift audit、integration evidence。

## 10. Skill 自我檢查
修改本 Skill 後必須確認：

- [ ] frontmatter `name: 派工`，且沒有 stale `name: dispatching`。
- [ ] description 只描述觸發邊界與核心責任，不塞完整 workflow。
- [ ] Skill 少於 500 行。
- [ ] `AGENTS.md` / Preflight / branch-first 明確且不被派工繞過。
- [ ] `WORK_ORDER_LINEAGE_CONTRACT`：多子票 Master 只建立一條工單主分支；子票從 accepted work-order HEAD 續工，production 只作 integration target / drift authority，整張工單 final verified work-order HEAD 才一次 non-force 整合。
- [ ] `X_SECOND_MAIN_INDEPENDENT_CHAIN_CONTRACT`：每個 Master 凍結自己的 X base；active chain 不追 X；A/B/C/D 彼此隔離；child 只接 previous accepted HEAD；完整 Master Task Acceptance 後才進 Integration Acceptance；`DO_NOT_MERGE_X` 時停在 `READY_FOR_X_INTEGRATION`。
- [ ] X task-chain dispatch / checkpoint / QA identity 帶 `MASTER_ID / TASK_ID / TARGET_X / FROZEN_X_BASE_SHA / EXPECTED_PARENT_SHA / WORK_ORDER_BRANCH / CHAIN_HEAD`，current X 只作 observation；RUN 不存在時標示 `RUN_NOT_CREATED` 並立即修 prerequisite，不等待不存在的 run。
- [ ] `NON_TERMINAL_CONTINUE`：pending / CHECKPOINT /「尚未完成」只可當 observation；沒有合法 stop condition 時立即執行下一個可執行 action。
- [ ] 「不假報完成」與「持續施工」兩個義務都存在，前者不能被拿來當停工理由。
- [ ] PM → Implementer → QA 角色標記完整。
- [ ] Requirement RED-first + 使用者核准 + breakdown 第二次核准完整。
- [ ] 每票都有 `Requirement Authority`、`AI Library References`、`AI Library Writeback`。
- [ ] GitHub 專案每票在 Worker 前都有真正 GitHub owning Issue 並反讀 number + URL + title。
- [ ] `NO_WORK_WITHOUT_CLAIM`：一票同時只有一個 execution claim owner；第一筆施工 write 前必須 atomic claim shared coordination authority。
- [ ] `EXECUTION_CLAIM_PREWRITE_HARD_GATE`：每次 branch-create / write / commit / QA dispatch 前都要執行 `tools/execution_claim_guard.py`；missing/non-owner/branch mismatch/base SHA/head SHA/stale/malformed/inactive/ambiguous 一律 fail closed。
- [ ] Skill write/commit 帶 `--changed-file` + `--preflight-evidence`；`.agents/skills/**/SKILL.md` 沒有 `寫技能` canonical Preflight evidence 時不得 mutation。
- [ ] branch-local lock / Issue comment / label 沒有被誤當全域互斥 authority；claim 失敗時 fail closed 並轉下一張可執行未認領票。
- [ ] `CLAIM_PROGRESS_STATE` 同步 phase/state、last_update、branch/HEAD、remote QA、next_action、blocker，重大 transition 即時更新。
- [ ] 未完成工單可分成 `我持有` / `其他 AI 已鎖定` / `尚未認領`，且 claimed ticket 可看見進度與下一步。
- [ ] `STALE_CLAIM_RECOVERY` 不直接搶鎖；先查 branch/QA/checkpoint/last_update，再用 compare-and-swap + recovery evidence 接管。
- [ ] `SCHEDULER_RUNTIME_LIVENESS_V1`：same-lane 判活使用 parser-compatible V1 heartbeat（`emitted_at`）+ matching `WHD_SCHEDULER_RUNTIME_END_V1`；heartbeat ≤300 秒退讓，>300 秒 same-lane resume；600 秒 claim stale threshold 不得冒充 invocation liveness；V1 TTL 仍 ≤300 秒以保持 foreign takeover machine contract。
- [ ] Issue terminal + cleanup + drift audit 前不提早 release claim。
- [ ] 漏建 Issue 用 Retroactive provenance，不能偽造時序。
- [ ] checkpoint / journal 能讓下一回合不靠聊天記憶續工。
- [ ] checkpoint provenance + execution tree fingerprint 阻止混合狀態續工。
- [ ] process group + killpg/等價 cleanup 完整。
- [ ] `complete_teardown_timeout` 與 `incomplete_timeout` 分開，前者要求完整 PASS summary。
- [ ] 只看到點號/局部輸出不得算 complete_teardown_timeout。
- [ ] timeout 後不重跑已通過區段，只跑 pending。
- [ ] collection SHA + journal/resume 防止舊證據誤用。
- [ ] Xvfb 有 SIGKILL / parent-death guard 契約。
- [ ] remote QA 建立 run 即啟動 `monitoring-remote-qa`，鎖 `run_id + head_sha` 到 terminal。
- [ ] `REMOTE_QA_ACTIVE_LOCK` 期間沒有其他工作插隊。
- [ ] success 後仍做 cleanup + durable state + drift audit 才 ACCEPT。
- [ ] 未完成派工每 30 秒回報目前工單、正在做的事項、最新測試/進度數字與 blocker，且不得中斷執行。
- [ ] 未宣稱不存在的背景工程師、subagent 或 scheduler 正在替你工作。

## MASTER_CHAIN_TURN_EXIT_HARD_GATE_V1
多子票 Master 的 child terminal **不是整條工單 terminal**。每次 child ACCEPT/CLOSE 時，durable child checkpoint 必須結構化寫入：

- `master_issue`
- `chain_state`
- `next_issue`（若適用）
- `chain_next_action` 或 `chain_reason`

固定狀態：`NEXT_CHILD_EXECUTABLE / NEXT_CHILD_BLOCKED / CHAIN_COMPLETE / USER_STOPPED`。

- `NEXT_CHILD_EXECUTABLE`：child 可關票，但 **assistant turn exit 必須 fail closed**；立即 claim/start `next_issue`。
- `NEXT_CHILD_BLOCKED`：只接受真正外部 authority/capability wait，且必須有 `chain_reason`。
- `USER_STOPPED`：只接受使用者明確停止／取消整條已授權 Master chain。
- `CHAIN_COMPLETE`：只有整條 Master 已完成 required child/closing gate 才成立。
- run terminal、child terminal、Master-chain terminal 三者不得互相代替。

Turn-exit caller 已知目前屬於 Master 時，必須呼叫 canonical guard 並傳入 fresh `expected_master_issue`；checkpoint 漏填或填錯 Master handoff evidence 一律 fail closed。禁止從聊天句子、Issue comment 或 evidence 字串猜 handoff。

Primary behavior guard：`tests/process/test_issue473_master_chain_turn_exit_gate.py` + `tools/continuity_controller.py`。

## GLOBAL_TURN_EXIT_GATE_BRIDGE
`NON_TERMINAL_CONTINUE` 的 machine enforcement 一律委派 `executable-continuity-controller::ASSISTANT_TURN_EXIT_GATE_V1`。任何 progress/CHECKPOINT/QA PASS/code integrated 回報後，只要 owning checkpoint 仍為 `RUNNING / WAITING_REMOTE / RECOVERING`，結束 assistant turn 前必須呼叫 `assert_turn_exitable`；被拒絕就立即執行 `next_action`，不得等待使用者再輸入「繼續／輪／GO」。

對 Master child closure，除了 child checkpoint state，還必須套用 `MASTER_CHAIN_TURN_EXIT_HARD_GATE_V1`；child terminal 若 `chain_state=NEXT_CHILD_EXECUTABLE`，仍視為本 turn 有 autonomous work，禁止退出。

`BLOCKED` 只有既有 `BLOCKED_ALLOWED_REASONS` 類真正外部 authority/capability wait 才能合法 turn-exit；`BLOCKED` 仍不得冒充 workflow COMPLETE。

### TRUSTED_REMOTE_FINALIZATION_EXECUTOR_V1_BRIDGE

當 scheduler / automation 已有 terminal owning checkpoint，但目前 execution runtime 無法直接執行 canonical continuity controller 時，closure 不得退化成 Issue comment marker。固定 remote path 是專用窄 executor `.github/workflows/whd-remote-finalization.yml`，只接受 fixed identity fields，執行 `authorize-finalization` → `verify-finalization-proof`，並產生 `WHD_REMOTE_FINALIZATION_RECEIPT_V1` + bound proof artifact。

- 禁止 arbitrary command / shell payload input；generic executor 不得替代。
- workflow run / artifact identity 必須 fresh 綁 issue + worker + branch + HEAD + checkpoint blob/fingerprint + claim blob + trusted authority SHA。
- Issue comment 中單獨出現 `FINALIZATION_GUARD_PASS` / `FINALIZATION_PROOF_VALID` 文字一律不是 closure authority。
- executor terminal GREEN 後仍要 fresh-read artifact receipt，exact match 後才可 close Issue；close 後 remote readback，再 release claim。

### SCHEDULER_TAKEOVER_OPERATIONAL_USAGE_V1

Recurring WHD scheduler 的操作細節以 `docs/governance/whd_scheduler_takeover_usage.md` 為 durable 使用手冊；本 Skill 保留 canonical execution contract。scheduler 必須遵守：

1. **wake-up trigger != execution owner**：每輪從 `coord/dispatch-claims`、Issue、checkpoint、branch、exact run fresh reconstruct，不得硬編 issue/branch/SHA/run_id。
2. `scheduler.<automation-id>` 是 durable lane identity；fresh claim 為同 lane 時不做 ownership takeover，但任何 substantive mutation 前仍必須套用 `SCHEDULER_RUNTIME_LIVENESS_V1` 的 **same-lane invocation mutex**：matching END 可立即續工；無 END 且 heartbeat age ≤ 300 秒時退讓；heartbeat age > 300 秒時視為前一 invocation stuck/gone，由本輪 same-lane resume。`ACTIVE_WITHIN_10M`／600 秒 claim stale threshold 不得拿來判斷同 lane 前一個 ChatGPT runtime 是否仍活著。
3. foreign owner 只有「無 active exact run + newest durable progress >= 600 秒」才可申請 stale takeover；sibling scheduler 也視為 foreign owner。
4. stale takeover 固定 `WHD_REMOTE_GUARD_REQUEST_V1 → exact Guard run → exact GREEN claim-takeover receipt → claim CAS → fresh readback → same-cycle next_action`。GREEN、CAS、status update 都不是 return condition。
5. 每輪開始先檢查尚未 consume 的同 lane GREEN；identity 仍 exact match 時直接 consume，不 duplicate request。GREEN 是 single-use mutation authority。
6. work HEAD 因合法 commit `H0→H1` 而 claim 還在 H0 時，走 `POST_COMMIT_CLAIM_HEAD_RECONCILIATION_V1`，不得 self-takeover。
7. terminal checkpoint 優先使用 trusted `WHD_REMOTE_FINALIZATION_REQUEST_V1` Issue-comment transport；machine receipt + proof artifact + `FINALIZATION_PROOF_VALID` 才能 close。
8. recurring lane 的 cycle blocker 只允許結束當輪 invocation；不得因 foreign active、WAITING_REMOTE、capability blocker、platform boundary 或 fully blocked 自行 disable/刪除/重排 recurring automation。


### SCHEDULER_RUNTIME_LIVENESS_V1

`scheduler lane identity != invocation identity`。這個 contract 同時處理兩件不同的事：**same-lane invocation 互斥／卡死接續**，以及 **foreign scheduler orphan takeover evidence**。兩者不得再用同一個「10 分鐘沒更新」概念混在一起。

每次 scheduler invocation 若持有 active claim，必須以 owning Issue top-level comment 投影 runtime heartbeat，第一行固定 `WHD_SCHEDULER_RUNTIME_LIVENESS_V1`。為相容 canonical parser `tools/scheduler_runtime_liveness.py`，欄位固定至少為：

`issue / scheduler_lane / invocation_identity / claim_blob_sha / branch / head_sha / executor_source=scheduler / emitted_at / expires_at`

若綁 active exact run，只能成對使用 parser 現行欄位 `active_run_id + active_run_head_sha`。**不得**在 V1 comment 任意加入 `entrypoint_id`、`heartbeat_at`、`run_id`、`run_head` 等 parser 未支援 key；其中 `emitted_at` 就是該 heartbeat 的 freshness timestamp。

#### Same-lane invocation mutex

Recurring lane 的 `:00 / :20 / :40` 只是 wake-up entrypoints，不是不同 owner。新 invocation 在任何 Guard request、workflow dispatch、claim/PR/Issue/repository mutation 前，先 fresh-read同一 owning Issue 上該 `scheduler_lane` 最新 heartbeat，以及最新 `WHD_SCHEDULER_RUNTIME_END_V1`：

1. 每個 invocation 使用唯一 `invocation_identity`；不得沿用前一輪 identity。
2. active invocation 至少每 **300 秒**發一個新的 V1 heartbeat；重大 mutation readback 前後、長 poll/wait 前後、Guard GREEN consume 前也刷新。
3. V1 的 `expires_at - emitted_at` 仍必須 **≤ 300 秒**，以保持 `stale_claim_takeover.py::MAX_RUNTIME_LIVENESS_SECONDS` 相容。這個 `expires_at` 是 foreign-scheduler machine lease ceiling，**不是** 20 分鐘 wake cadence 的主要 same-lane 判活依據。
4. 正常 return 前必須留 owner-authored top-level `WHD_SCHEDULER_RUNTIME_END_V1`，至少帶 `issue / scheduler_lane / invocation_identity / ended_at / final_phase / final_next_action`。若 latest END 與 latest heartbeat 的 `invocation_identity` exact match，前一 invocation 已正常結束；下一 wake 可立即 same-lane 續工。
5. 若 latest heartbeat 沒有 matching END，計算 `heartbeat_age = now - emitted_at`：
   - `heartbeat_age <= 300 秒` → `SAME_LANE_PREVIOUS_INVOCATION_ACTIVE`：前一 runtime 視為仍活著，本輪只能 fresh-read／觀測後退讓，禁止 mutation、Guard、dispatch。
   - `heartbeat_age > 300 秒` → `SAME_LANE_PREVIOUS_INVOCATION_STUCK_OR_GONE`：不論舊 `expires_at`、claim `last_update` 或 600 秒 stale threshold，新的 invocation 都可 **same-lane resume**；先以 live GitHub reconcile，再繼續 durable `next_action`。這不是 foreign takeover，不改 claim owner。
6. exact GitHub Actions run 仍在 queued/in_progress/waiting/pending/requested，**只證明外部 run 還活著，不證明舊 ChatGPT invocation 還活著**。same-lane 接手者鎖同一 `run_id + head_sha` 繼續 poll，禁止 duplicate dispatch。
7. PR／Issue／branch／claim／checkpoint 在舊 runtime 消失後已前進時，live GitHub wins：新 invocation 先 reconcile durable state，再續做；禁止重播已成功 mutation。
8. claim blob、branch、HEAD 任一 identity drift 時，舊 heartbeat 不可作 mutation authority；先 fresh reconstruct。heartbeat 只證明 invocation liveness，不取代 claim/checkpoint/Remote Guard。

因此，**600 秒（10 分鐘）claim stale threshold 永遠不是 same-lane invocation 判活規則**。20 分鐘 wake cadence 下，判斷前一輪是否仍在執行要看「最新 heartbeat freshness + matching END」，不是等一張固定 lease 自然過期。

#### Foreign scheduler takeover 邊界

foreign scheduler ownership 仍由 `tools/scheduler_runtime_liveness.py` + `tools/stale_claim_takeover.py` 擁有 machine authority：

- V1 heartbeat TTL 最長 300 秒；canonical orphan grace 仍為 90 秒。
- foreign scheduler 有有效 machine heartbeat → backoff；heartbeat missing/expired 且符合 exact claim/blob/branch/head、無 active run及 orphan/stale條件時，才可依 `ORPHANED_SCHEDULER_OWNER` / `EXECUTOR_STUCK` 走 guarded takeover。
- same-lane stuck/gone resume 與 foreign scheduler claim-takeover 是兩條不同路徑；不得因 same-lane heartbeat stale 就 self-takeover。
- platform hard boundary 若來不及寫 END，heartbeat 會停止刷新；下一 sibling wake 在 freshness > 300 秒後即可 same-lane 接續，不必等 600 秒 claim stale。
- durable comment parser/selector authority：`tools/scheduler_runtime_liveness.py`；foreign takeover decision authority：`tools/stale_claim_takeover.py`。


## ACTIVE_DELEGATED_WORK_TAKEOVER_GATE_V1 — helper/proof/dependency 是 parent liveness

父 Issue/claim 或 branch 安靜不得直接判 stale。只要 parent durable state 指向 helper/proof/blocking repair/dependency，takeover 前沿 pointer 讀到 executable leaf；machine authority 是 `tools/stale_claim_takeover.py`。

- canonical link：`delegated_work[] = {child_issue, relationship, helper_key}`；legacy `proof_issue / blocking_repair_issue / helper_issue / dependency_issue` 仍辨識。
- open + active child → `ACTIVE_DELEGATED_WORK`、`actionable=false`；禁止 takeover parent、禁止再開 helper。
- child stale → 接 child leaf，不得反向搶 parent。
- pointer 存在但 child Issue/claim/blob/live HEAD evidence 缺失或 half-terminal mismatch → fail closed。
- child 必須 Issue closed + claim terminal/released 才解除 parent delegated lock。
- helper 建立前用 stable `helper_key` 跑 `assert_helper_creation_allowed`／CLI `--candidate-helper-key`；`ACTIVE_HELPER_DUPLICATE` 固定 resume/reuse。
- helper Issue 建立後第一個 durable coordination write 必須把 canonical `delegated_work[]` 寫回 parent claim，pointer 未落盤不得開始 helper substantive work。

禁止循環：parent 看似安靜 → 誤判 stale → takeover → 再開 helper → 無限 helper/takeover。

<!-- ISSUE646_DISPATCH_WRITEBACK_V1 -->
## ISSUE646_DISPATCH_WRITEBACK_V1

Resume/takeover/helper-create/turn-exit 固定順序：fresh identity → unresolved Guard recovery → live drift reconciliation → structured delegated/proof/helper/dependency traversal → active child沿到 leaf → same helper key reuse/reservation → canonical stale evaluator → guarded mutation → fresh readback。

EXPIRED_UNCONSUMED 的舊 GREEN 永久不可 consume；fresh reconcile後才可 mint one fresh recovery Guard。Equivalent duplicate GREEN exact-equivalent時 deterministic dedupe；真正 identity conflict仍 AMBIGUOUS → FAIL_CLOSED。

Checkpoint fingerprint 禁止 raw JSON hash；只用 load_checkpoint + checkpoint_fingerprint 或 authorize-finalization。#641：36051135751 FAIL → 36051265277 GREEN。

EXECUTOR_PROVENANCE_AND_INTERACTIVE_LIVENESS_FOLLOWUP_V1：interactive 必須保存 exact conversation/chat identity + invocation identity；scheduler 保存 exact lane + invocation identity；另補 chatgpt_interactive heartbeat/liveness。此為 required follow-up，在 machine owner完成前不得宣稱已 enforcement。
