---
name: 執行開發任務
description: 依已核准規格或工單執行實作。用於進入實作者階段、修改 production/test/Skill、跑 targeted 驗證、產生 durable checkpoint，並在 WHD 專案遵守派工、Preflight、owning Issue、remote QA 與 resume 規則。
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: development-task-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 執行開發任務

## WORK_SLOT_EXECUTION_MODE_V1

每個工作槽／互動 runtime 在開始實質工作前，必須保存本輪 `execution_mode`，並 bridge 到 `tools/execution_scope_gate.py`。工作槽 identity、runtime identity、execution location 與 execution mode 是不同概念，不得混用。

- `UPDATE_ONLY`：只完成指定 update + validation + readback；不得跨到下一張工單。
- `EXECUTE_TICKET`：只完成指定 owning Issue 到 terminal。
- `EXECUTE_CHAIN`：允許在目前 chain authority 下進下一個 successor。
- `SCHEDULER_LANE`：允許 recurring lane dynamic discovery / successor continuation，但仍受 claim/dependency/Guard 約束。

**progress/status 不得改變 execution_mode**。CHECKPOINT、heartbeat、remote QA PASS、Issue close、PR merge 都不能自行升級 mode。

`RUNNING / WAITING_REMOTE / RECOVERING` 的續跑規則只在目前 mode 已授權的 scope 內成立；continuity 不能創造新的工單 authority。跨 successor、dynamic discovery、recovery 或 takeover 前使用 `tools/execution_scope_gate.py` 做 machine decision。

依使用者已核准的規格或工單實作，不重新發明需求。

## 1. 開始前

- 先讀目前工單／規格、`Requirement Authority`、`Approved RED IDs`、`AI Library References`、依賴與 acceptance criteria。
- 若是 WHD / Phase6，先依 `AGENTS.md` 完成 Knowledge Preflight，並同時遵守 `.agents/skills/engineering/派工/SKILL.md`。
- Git repository 修改必須已在本任務的新 work branch；不得直接 patch production target。
- GitHub-backed ticketed work 在第一個 production write 前，必須反讀真實 GitHub owning Issue 的 `issue_number + URL`。`.scratch/**`、聊天 T 編號、branch、checkpoint 都不能替代。
- 長流程持續執行與停工點踩坑固定反讀 `個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md`。

若施工途中才發現漏建 Issue：停止新增 production 變更 → 補建 Issue → 明標 `Retroactive provenance / 施工後補建` → 寫入實際 branch/commit/run → 反讀成功 → 再 resume。不得倒填 chronology。

## 2. 實作方式

- 使用實際可用的 TDD Skill／測試工具執行 RED → GREEN；WHD 專案的 repository TDD 參考 `.agents/skills/engineering/tdd/SKILL.md`。
- 測試 seam 以已核准 requirement 與 public interface 為準；不要為了讓測試好寫而改產品語意。
- 每次只完成一個可驗證 slice，再跑與該 slice 最接近的 targeted test。
- typecheck、lint、單檔測試等只在專案實際存在對應工具時執行；不得虛構命令或把缺少工具說成已通過。
- 驗證 expected/fixture/probe 只能判定對錯，不能反向成為 production 計算來源。

## 3. Durable checkpoint / resume

每張已驗收工單要有實體 checkpoint。長回歸前若已有未封裝變更，先封 checkpoint。

fresh extract、restore、工具回合重建或手動複製後，先驗 execution-tree fingerprint；若與最近已驗收 checkpoint 不符，視為混合狀態，必須完整還原 checkpoint 後再續工。

checkpoint/state 至少記錄 branch+HEAD、已完成/pending/failed、修改檔、最後驗證結果、owning Issue、下一步 resume 指令。

### EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE

本 Skill 的 execution-state 文字規則只負責**語意與操作責任**；durable state integrity、runtime-cut reload 與 workflow finalization 的 machine enforcement 一律委派 `.agents/skills/engineering/executable-continuity-controller/SKILL.md` 與 `tools/continuity_controller.py`。

- 長流程 checkpoint 必須能以 `Checkpoint` 模型表達；`RUNNING / WAITING_REMOTE / RECOVERING / BLOCKED` 都是 non-terminal，必須有非空 `next_action`。
- remote QA 進 `WAITING_REMOTE` 時必須持久化 exact `run_id + head_sha`；已知時同步保存 `job_id / log_cursor / evidence`。
- runtime/tool window 被切斷後先 `load_checkpoint`，驗 branch/HEAD/run identity；無 drift 就執行保存的 exact `next_action`，不得重新要求使用者驅動。
- 在任何 workflow/issue/acceptance closure 或「本工作可以終止」的 machine gate 前，必須對 durable checkpoint 執行 `assert_finalizable`。非 terminal checkpoint 必須 raise `FinalizationBlocked` / CLI nonzero；不得因本 Skill 文字出現 `final 禁止` 就視為已 enforce。
- 語意 `COMPLETE` 只有在所有 acceptance evidence 完成後，才能落成 controller 的 `TERMINAL_SUCCESS`；不可恢復且有完整終態 evidence 的失敗才可落成 `TERMINAL_FAILURE`。單純 `BLOCKED` 仍是 non-terminal，不通過 workflow finalization。
- `tests/process/test_continuity_controller.py` 是 machine behavior authority；字串 marker tests 只做文件相容性 guard，不能取代 executable behavior proof。

### CHECKPOINT_RESUME_CONTRACT

遇到平台／工具的 system hard-cut 時，`system hard-cut → checkpoint`；checkpoint 不是 COMPLETE evidence，**不得把系統硬切寫成 COMPLETE**。checkpoint 最低欄位必須完整包含：

- `issue / task id`
- `current role`
- `branch`
- `HEAD SHA`
- `production target`
- `latest commit`
- `remote QA run_id / head_sha / status`
- `completed / pending / failed / blocked`
- `dirty files`
- `validation commands / results`
- `config / baseline invariant status`
- `temporary workflows / branches`
- `next exact action / resume command`

#### RESUME_DRIFT_GATE

下一回合或 runtime 重建後先讀 checkpoint 並驗證 repo / branch / run drift：

- `無 drift → resume next exact action`，不得要求使用者重新交代，也不得從頭重查整條工作鏈。
- `有 drift → 只重驗受 drift 影響部分`，先界定受影響 authority / diff / run，再更新 checkpoint；**不得整條工作鏈無條件重跑**。

#### CHECKPOINT_IDENTITY_LOCK

resume 前必須確認 checkpoint 的 `branch + HEAD SHA` 與目前 execution tree 一致；若 checkpoint 記有 remote QA，還必須確認 `run_id + head_sha` identity。`不一致時先分類 drift / stale checkpoint`，不得直接沿舊結果宣告 PASS、BLOCKED 或 COMPLETE。

#### USER_VISIBLE_CHECKPOINT_GATE

Durable checkpoint 不只要存在於內部／repo 狀態；在需要跨 runtime 恢復或長流程重要轉折時，也必須讓使用者看得到。

- system hard-cut 前的最後一個 user-visible update 必須使用固定標題 `CHECKPOINT`，不得只留一般 progress update 或只在內部保存。
- CHECKPOINT 至少顯示：`issue / task`、`role`、`branch + HEAD`、`production target`、`remote QA lock`、`completed / pending / failed / blocked`、`validation / invariant`、`temporary workflows / branches`、`next exact action`。
- 長流程遇到重要 execution state transition 時刷新可見 checkpoint，至少包含 `RUNNING ↔ WAITING_REMOTE ↔ RECOVERING`、`branch / HEAD / production target` identity 改變、`remote QA lock acquired / terminal`、`accepted slice / major checkpoint`。不需要把每個 30 秒 observation 都升格成 checkpoint。
- progress update 不得冒充 checkpoint；一般進度回報仍依 cadence 執行，但不能因此取代 durable/user-visible checkpoint。
- 可見 checkpoint 不能成為正常停工點；`non-terminal state 顯示 CHECKPOINT 後仍必須繼續 next action`。只有 genuine BLOCKED、evidence-backed COMPLETE 或實際 system hard-cut 才能離開正常執行鏈。

## 4. 測試 timeout

- GUI targeted gate 若 pytest 已有完整 PASS summary 但 Tk/Xvfb/interpreter 不退出，分類為 `complete_teardown_timeout`。
- 只有點號、局部百分比或不完整輸出時是 `incomplete_timeout`，不得冒充 PASS。
- incomplete batch 只縮小並重跑 pending nodeids；已完成節點禁止為方便重跑。
- process-group、Xvfb ownership、killpg、journal/resume 與 provenance 細節以 `派工` Skill 為準。

## 5. Remote QA Active Lock

只要建立或依賴 non-terminal remote QA run，立即服從 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 的 `REMOTE_QA_ACTIVE_LOCK`。

run terminal 前禁止繼續 code exploration、production/test/Skill write、下一張工單或另一個診斷；只能 poll run/jobs/steps、處理 terminal failure log、做 30 秒進度回報。terminal 後才恢復一般實作流程。

### REMOTE_QA_STATE_BRIDGE

這個 bridge 只把 remote-QA 狀態映射回本 Skill 的語意 execution state；**polling mechanics remain owned by `monitoring-remote-qa`**，不得在此建立第二套 polling authority。

- `queued / in_progress → WAITING_REMOTE`：保持 **same `run_id + head_sha`** lock，沿既有 `WAITING_REMOTE → poll_locked_run` 繼續主動輪詢；30 秒 cadence 只是 observation。
- `terminal success → RUNNING(next_acceptance_action)`：解除該 terminal run 的 active lock，接著執行 result extraction、invariant、cleanup、下一個 acceptance gate；**success 不是自動 COMPLETE**。
- `terminal failure → RECOVERING`：先讀 `failed-job log` 並分類 production / test / harness / environment failure，再沿 evidence → root cause → minimal fix → validation → retry；**不得停在 FAIL 回報**。

## 6. 進度與完成

任務尚未完成時，每 30 秒至少回報一次目前工單、正在做的事項、最新測試/進度數字與 blocker；回報不得中斷正常執行。

### EXECUTION_STATE_MACHINE

這是 WHD 長流程的**語意狀態模型**，不是第二套 runtime database、task store 或 journal。真實 branch / HEAD / run_id / checkpoint 仍寫回既有 Git / GitHub / durable checkpoint authority；本節只定義目前工作鏈允許如何被描述與推進。

- `RUNNING`：已有可自主執行的本地／GitHub next action，必須繼續執行。
- `WAITING_REMOTE`：已有 non-terminal remote run；polling 細節、run lock 與 cadence 唯一服從 `monitoring-remote-qa`。
- `RECOVERING`：已有失敗 evidence 且可自行診斷／修復；必須沿 evidence → root cause → fix → validation → retry 前進。
- `BLOCKED`：只有符合 `BLOCKED_ALLOWED_REASONS` 才成立；不是一般 FAIL、等待或「下一步很明確」的同義詞。
- `COMPLETE`：只有符合 `COMPLETE_REQUIRES_ACCEPTANCE_EVIDENCE` 才成立。

固定 next-action contract：

- `RUNNING → execute_next_action`
- `WAITING_REMOTE → poll_locked_run`
- `RECOVERING → evidence_root_cause_fix_retry`
- `BLOCKED → wait_for_missing_authority`
- `COMPLETE → no_next_action`

任何 `RUNNING`、`WAITING_REMOTE`、`RECOVERING` 都是 non-terminal；**non-terminal state 不得輸出 final** 或把既有工作鏈交回使用者當 scheduler。

#### BLOCKED_ALLOWED_REASONS

`BLOCKED` 僅允許以下原因：

1. 必須由使用者做**產品語意決策**，既有 requirement / code / Skill / AI 庫 / tests / history 無 authority 可決定。
2. 缺少**必要權限**，且 Agent 無法自行取得。
3. 缺少**不可推導資料**，且所有既有 authority 都無法回答。
4. 平台或工具造成**系統硬性中止**；此時要先留下 durable checkpoint，不能把它寫成 COMPLETE。

**可恢復 FAIL 不得進 BLOCKED**；preflight/test/QA/invariant 若有 evidence 可繼續診斷，必須轉 `RECOVERING` 或回 `RUNNING`。

#### COMPLETE_REQUIRES_ACCEPTANCE_EVIDENCE

`COMPLETE` 至少要有目前工單要求的 fresh acceptance evidence，並完成 applicable remote QA、invariant、drift、cleanup、issue-state gate。缺其中任何必要 gate 就維持 non-terminal。

下列事件全部只是中間 evidence：`branch created`、`commit created`、`push complete`、`run_id acquired`、`queued`、`in_progress`、`focused PASS`、`partial acceptance PASS`。**以上事件不得 transition 到 COMPLETE**。

### FAIL_RECOVERY_CONTRACT

任何可自行取得 evidence 並處理的 FAIL 都先進 `RECOVERING`，不得把 failure report 當成停工點：

- `preflight RED → RECOVERING(required_evidence)`：fail-closed 只禁止越過受保護階段；繼續補齊 `required evidence / reference`，完成遠端反讀後 `rerun preflight`，GREEN 才回 `RUNNING`。
- `test FAIL → RECOVERING`：依 `assertion / log → root cause → minimal fix → focused validation → retry` 執行；禁止「`FAIL 一出現就回報使用者並停止`」。
- `remote QA FAIL → RECOVERING`：讀 `job / step / log`，分類 `production / test / environment / contract`；可修復就做最小修正並觸發 `replacement run`，立即重新進 `WAITING_REMOTE` 監控到 terminal。
- `invariant FAIL → RECOVERING`：**不得宣告功能 PASS**；定位污染來源，**恢復 canonical state**，重新驗證 invariant 後才可前進。

只有 `BLOCKED_ALLOWED_REASONS` 中的產品語意決策、必要權限、不可推導資料或實際系統硬中止才可離開 recovery；**可恢復 FAIL 不得進 BLOCKED**。

#### VALIDATION_IS_JUDGE_ONLY

Validation / fixture / expected / probe 只能判定 implementation 是否符合 authority，**不得反推 production 幾何 / 製造計算來源**，也**不得放寬 authoritative acceptance contract**來讓測試通過。若 production 與 validation 衝突，先找 requirement/code/data authority 與 root cause；不能把測試期望值回灌成 production source-of-truth。

### NO_FAKE_COMPLETION_CONTRACT

下列狀態全部都是 non-terminal evidence，不得被包裝成完成或自然停工點：`branch created`、`code modified`、`commit created`、`push complete`、`remote QA started`、`run_id acquired`、`queued / in_progress`、`partial tests PASS`、`focused tests PASS but final acceptance pending`、`Combined PASS but invariant / drift / cleanup pending`、`明確知道 next action`。

未完成只能標示 `IN PROGRESS` 或 `BLOCKED`；若不是符合 `BLOCKED_ALLOWED_REASONS` 的 genuine blocker，就維持 IN PROGRESS 並執行 next action。禁止用「`稍後繼續`」或「`下一續跑點`」**不得作為正常結束語義**；真正 system hard-cut 必須走 `CHECKPOINT_RESUME_CONTRACT`。

#### RESUME_POINT_FINAL_ESCAPE_GUARD

`下一續跑點是` / `下一續跑點就是這裡` 只能出現在 genuine BLOCKED 或 system hard-cut checkpoint；它們不是一般進度回報的合法終止語義。

只要目前仍是 `RUNNING`、`WAITING_REMOTE` 或 `RECOVERING`，且存在可自主執行的 next action，**不得因為已留下 resume point / checkpoint 就結束正常回合**；回報後必須在**同一回合繼續執行該 next action**。checkpoint 只有在 `CHECKPOINT_RESUME_CONTRACT` 的真 hard-cut 情境才是跨回合恢復工具，不能被拿來替代持續執行。

#### PROGRESS_UPDATE_STATE_PRESERVATION

`progress update 只能觀測狀態`，**不得改變 execution state**。回報前是 `RUNNING`、`WAITING_REMOTE` 或 `RECOVERING`，回報後仍保持同一語意 state 與同一合法 next action；`回報後若仍有合法 next action，必須繼續執行`。

#### NORMAL_TERMINATION_GATE

正常終止只允許兩種：`genuine BLOCKED` 或 `evidence-backed COMPLETE`。`non-terminal state 不能產生 COMPLETE / final response`。若遇到 `system hard-cut`，只能留下 durable checkpoint 並依 `CHECKPOINT_RESUME_CONTRACT` 續跑，不能冒充正常終止。

### NONTERMINAL_NEXT_ACTION_GATE

在輸出任何 `final`、把控制權交回使用者，或把目前工單描述成可自然停止前，先判定目前 execution state：

1. 若已滿足本票全部 acceptance、必要 QA / invariant / cleanup / issue-state gate，才可視為 `COMPLETE`。
2. 若確實需要使用者產品語意決策、缺必要權限、缺現有 authority 無法推導的資料，才可視為 `BLOCKED`。
3. 若平台 Runtime / tooling 被實際切斷，先留下 durable checkpoint；這不是 `COMPLETE`。
4. 除上述情況外，只要**存在可自主執行的下一步**，`final 禁止`；下一個動作必須直接執行該 next action，而不是等使用者再說「繼續」。

以下一律是 non-terminal：建立 GitHub 工單／branch、完成 commit/push、取得 run_id、QA queued/in_progress、部分或 focused tests PASS、已知下一步、以及單純的進度回報。

`Gate RED` / preflight FAIL 只禁止越過受保護階段，**不是停工點**。若所需資料可自行取得，必須繼續**完成 Gate 所要求的 evidence**、readback 或修復，再重跑 gate；只有符合上述真正 `BLOCKED` 條件才可停。

Test / QA / invariant FAIL 若可自行診斷，必須進 recovery：讀 evidence/log → root cause → minimal fix → validation → retry；FAIL 本身不得直接轉成等待使用者的停止狀態。

Remote QA 的 polling cadence、run lock 與 final gate 不在此重複定義，仍唯一委派給 `monitoring-remote-qa`。

完成前使用實際可用的 code-review Skill／review 工具檢查本票 diff；WHD repo 有 `.agents/skills/engineering/code-review/SKILL.md` 時直接讀取並套用。沒有該能力時以 inline diff review 退化，不得假裝已派 reviewer。

只有 fresh verification 支持的狀態才能宣告完成。若來源不是 Git repository，Git/commit 步驟跳過，不為滿足形式硬造 repository；checkpoint + SHA/provenance 仍要完成。

### EXECUTION_WINDOW_INTERRUPTION_RECOVERY

當對話／工具的 execution window interruption 發生，但 GitHub / Git durable evidence 已存在時，狀態是 `RECOVERING`，不是 rollback、BLOCKED 或 COMPLETE。resume 固定依下列順序執行：

1. `remote refetch` authoritative `production target` 與最新 SHA。
2. 反讀 owning Issue recovery checkpoint，確認最後 durable phase、work branch + HEAD、temporary QA 與 next action。
3. 驗證 `work branch + HEAD`、`production target`、必要時同一 `run_id + head_sha`；identity 不一致先分類 drift。
4. `無 drift → continue exact next unique action`；**不得因 execution window 重開而重跑已完成 phase**。
5. `有 drift → 只重驗受影響範圍`；禁止把整條已驗收鏈重跑一遍來掩蓋 provenance。
6. exact tested HEAD / ancestry 未變時，既有 `terminal QA evidence 保持有效`；不能只因 runtime 重開就重建舊 run。

長任務至少在下列 durable boundary 更新 checkpoint：`RED`、`GREEN`、`remote QA submitted`、`remote QA terminal`、`closing drift`、`integration`、`post-integration terminal`。execution window 被切斷只代表從最近 boundary 恢復；使用者不是續跑 scheduler，若 next action 可自主執行就立即繼續。

## GLOBAL_TURN_EXIT_GATE_BRIDGE

所有長流程的 user-visible response boundary 必須 bridge 到 `executable-continuity-controller::ASSISTANT_TURN_EXIT_GATE_V1`。在準備結束 assistant turn 前，先載入 owning durable checkpoint 並執行 `assert_turn_exitable`／`assert-turn-exitable`。

- `RUNNING / WAITING_REMOTE / RECOVERING` 被 machine guard 拒絕時，輸出只能是 observation，下一個動作必須立刻執行 checkpoint 的 `next_action`；不得把使用者當 scheduler。
- `BLOCKED` 才能因真正外部 authority/capability wait 把控制權交回使用者；但它仍不能通過 `assert_finalizable`。
- Remote QA terminal 後若轉成 `RUNNING(cleanup / invariant / drift / closure)`，remote lock 雖解除，global turn-exit lock 立即接手；PASS 回報不是停工點。
- `USER_VISIBLE_CHECKPOINT_GATE` 只負責呈現/恢復面，不取代 executable turn-exit gate。


### STARTUP_DEFAULT_AUTHORITY_CONTRACT

當同一產品同時存在 production direct-primary 路徑與 legacy/compatibility UI 路徑時，**啟動預設值必須由 canonical application state owner 建立，不得依賴某個可選 UI widget 的 `.current()`、`.set()` 或 constructor side effect 才成立**。

執行 startup-default 類修正時至少驗證：

1. 真正 production entrypoint 的 fresh startup state；
2. legacy/compatibility entrypoint（若仍存在）；
3. downstream snapshot / adapter projection；
4. project/load 的 explicit saved value 仍可覆蓋 fresh-start default；
5. 不把 presentation side effect 升格成 domain state owner。

WHD 的具體產品規則由 AI Library canonical contract `phase6-startup-baseline-model` 擁有；本 Skill 只保存通用執行方法，不複製產品值。

## CHATGPT_SCHEDULED_REENTRY_EXECUTION_BRIDGE

長任務若因平台 hard-cut 中斷，WHD 採用 hourly ChatGPT scheduled re-entry 自動恢復，不要求使用者當 scheduler。

每次重入固定：

1. fresh-read production target、owning issue、work branch/HEAD、checkpoint、必要時 exact remote run；
2. 取得或尊重 shared GitHub TTL lease；
3. 由 canonical continuity state 決定唯一 next action；
4. 無 drift 直接續工；有 drift 只重驗受影響範圍；
5. 已 accepted phase 不因 runtime 重建而重跑；
6. 目前 Runtime 可繼續時不得因「排程稍後會再醒」而停止。

### SCHEDULED_RESUME_PROGRESS_HEARTBEAT_BRIDGE

跨 Runtime 自動續跑時，user-visible heartbeat 的 canonical 規則由 `executable-continuity-controller::SCHEDULED_RESUME_PROGRESS_HEARTBEAT` 負責；本 Skill 必須 bridge 該規則，不自行發明狀態。

只要 scheduled re-entry 偵測到 active work，就必須讓使用者能分辨正常工作、等待、復原、真 blocker 或完成，並以 `WORKING / WAITING_REMOTE / RECOVERING / BLOCKED / COMPLETE` 之一回報 owning issue、branch、HEAD、必要 run_id 與 exact next_action。另一 runtime 持有有效 lease 時也要以 `WORKING` 說明 safe no-op，而不是靜默到看起來像卡死。

這個 progress update 只能觀測執行狀態，**不得成為停工點**。若回報後仍存在可自主執行的 next action，必須在同一 Runtime 繼續執行；scheduled heartbeat 不覆蓋本 Skill 的 `NONTERMINAL_NEXT_ACTION_GATE`、checkpoint、QA、acceptance 或 closure 規則。

### IMMEDIATE_TERMINAL_PROGRESS_REPORT_BRIDGE

長流程一旦取得 evidence-backed PASS / FAIL / COMPLETE terminal evidence，必須 bridge executable-continuity-controller::IMMEDIATE_TERMINAL_PROGRESS_REPORT，先**立即回報**使用者，再做 secondary readback / cleanup / invariant / writeback / closure。

- PASS：只回報已證實 PASS；若仍有 next action，回報後**繼續**收尾，不得直接 COMPLETE。
- FAIL：先回報 exact failure evidence，再進 RECOVERING；可自行修復時不得停。
- COMPLETE：只有 acceptance/cleanup/closure 真的完成才可使用。
- immediate report 是 progress update；不改 durable state，不繞過 NONTERMINAL_NEXT_ACTION_GATE，也不是 turn-exit 授權。

### POLLING_OBSERVATION_ONLY_BRIDGE

本 Skill 必須 bridge executable-continuity-controller::POLLING_OBSERVATION_ONLY。

若沒有獨立 progress producer 正在推進，禁止把「輪詢」當工作本身。此時必須回 RUNNING / RECOVERING，直接執行能產生下一個 state change 的實作、trigger、修復或驗證 prerequisite。

使用者不是 scheduler，也不是 executor；不得靠使用者反覆輸入「輪／繼續」才讓工作往前。
