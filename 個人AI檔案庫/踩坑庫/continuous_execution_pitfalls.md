---
whd_doc_role: REFERENCE
whd_contract: continuous-execution-operations
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 長流程持續執行 / 停工點踩坑規則

## SCHEDULED_WAKEUP_STATUS_ONLY_PITFALL

排程／automation 只是 wake-up trigger，不是 execution owner；canonical shorthand：`wake-up trigger != execution owner`。醒來後只做狀態回報再停止，等同把排程誤當 execution cadence，屬於 continuity regression。

- 先恢復 owning issue/checkpoint/branch/current concrete RUN identity。
- 有 concrete RUN：沿 canonical remote-QA contract 追到 terminal，然後直接進下一個 autonomous step。
- 沒有 concrete RUN 但 owning plan 需要 RUN：分類 `RUN_NOT_CREATED`，立即處理會建立 RUN 的 prerequisite/trigger/fix，禁止等待。
- `status update != exit`；GREEN/RED 都不是自動停點。
- 若平台被迫切斷，先留下完整 durable checkpoint，下一次 wake-up 從 exact next action 恢復。
- 本段是 REFERENCE/pitfall；唯一 scheduled-wakeup execution authority 仍是 `.agents/skills/engineering/executable-continuity-controller/SKILL.md`。

## Authority status

本文件只保留歷史事故、操作提醒與相容性回歸背景，角色是 **REFERENCE**，不是 executable authority。

- executable machine CURRENT：`tools/continuity_controller.py`
- operations/semantic CURRENT：`.agents/skills/engineering/executable-continuity-controller/SKILL.md`
- marker/string presence is **documentation compatibility evidence**, not executable enforcement.
- 本文件若與上述 CURRENT authority 衝突，以上述 CURRENT 為準；不得從本文件的 marker、字串或舊 test 反推 machine state/finalization 行為。

## 事故模式：把派工完成當成停工點

WHD 曾發生：Master 與子工單已建立、第一張可執行子工單也已明確，但 AI 以「派工完成」作為回覆終點，把後續實作留給使用者再輸入「繼續」。這是流程缺陷，不是正常 checkpoint。

## 永久規則

- **進度回報不是工作終點。** branch created、issue created、commit/push、QA started、run_id acquired、focused PASS、下一步明確，都只是中間態。
- 只要**存在可自主執行的下一步**，且沒有真正 blocker / Runtime interruption，就必須在同一工作流程繼續執行；不得輸出 terminal/final 狀態把控制權交回使用者。
- **使用者不是續跑 scheduler。** 不得依賴使用者再輸入「繼續」「輪」「跑」「continue」「poll」才讓既有非終態工作前進。
- Gate RED / preflight FAIL 是 fail-closed boundary：禁止越過受保護階段，但仍要繼續完成 Gate 所要求的 evidence、readback 或修復，直到 GREEN 或出現真正 blocker。
- Test / QA FAIL 可自行診斷時要進 recovery：evidence → root cause → minimal fix → validation → retry；FAIL 本身不是停工理由。
- 只有 COMPLETE、真正需要產品決策/權限/不可推導資料的 BLOCKED，或平台實際 Runtime/tool interruption，才允許離開目前工作鏈。
- Runtime 被硬切時要留下 durable checkpoint；下一回合先驗 drift，再從 next exact action 續跑，不重新要求使用者交代已知上下文。

以上是 reference guidance；真正 checkpoint schema、合法 state、transition 與 finalization 是否可通過，必須由 `tools/continuity_controller.py` 的實際 behavior 判定。

## CHECKPOINT 可見層事故

WHD 曾出現 durable checkpoint / resume contract 已存在，但只有內部流程責任、沒有 user-visible gate；結果長流程中的一般進度回報逐漸取代 CHECKPOINT，使用者長時間看不到可恢復狀態。這不是「checkpoint 不需要了」，而是可見層漏規則。

永久規則：

- durable checkpoint 與 user-visible CHECKPOINT 是同一狀態的兩個責任層；只做內部 durable state 不算完成 checkpoint 呈現責任。
- system hard-cut 前與重要 execution state transition 必須刷新固定標題 `CHECKPOINT`；一般 progress update 不得冒充或取代它。
- 可見 CHECKPOINT 仍是 non-terminal observation / recovery surface；只要 next action 可自主執行，就必須在顯示 CHECKPOINT 後繼續，不得把 CHECKPOINT 變成停工點。
- `.agents/skills/engineering/執行開發任務/SKILL.md` 的 `USER_VISIBLE_CHECKPOINT_GATE` 是唯一 canonical CHECKPOINT 呈現 authority；不得在其他 Skill 建第二套欄位、refresh 或 execution state machine。
- 所有可獨立進入長流程的入口目前至少包含 `.agents/skills/engineering/派工/SKILL.md`、`.agents/skills/engineering/monitoring-remote-qa/SKILL.md`、`.agents/skills/engineering/issue-closure-gate/SKILL.md`，都必須以 `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE` 強制 bridge 回 canonical gate；入口 Skill 的 progress/polling/closure domain responsibility 不取代 CHECKPOINT 呈現責任。
- `USER_VISIBLE_CHECKPOINT_GATE`、各 bridge 與 `tests/process/test_checkpoint_resume_contract.py` 只負責 presentation/routing regression coverage；它們不是 executable durable-state/finalization authority。

## Remote QA 邊界

Remote QA 的 polling 細節與 `REMOTE_QA_ACTIVE_LOCK` 仍以 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 為唯一 authority；本規則不建立第二套 polling state machine。Durable WAITING/RECOVERING state 仍由 executable controller 判定。

## 相容性／回歸參考（非 executable enforcement）

- `.agents/skills/engineering/執行開發任務/SKILL.md` → `NONTERMINAL_NEXT_ACTION_GATE` + canonical `USER_VISIBLE_CHECKPOINT_GATE`
- `.agents/skills/engineering/派工/SKILL.md` → PM → Implementer 同工作流程轉移規則 + `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE`
- `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` → `REMOTE_QA_ACTIVE_LOCK` + `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE`
- `.agents/skills/engineering/issue-closure-gate/SKILL.md` → closure gate + `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE`
- `tests/process/test_checkpoint_resume_contract.py`
- `tests/process/test_continuous_execution_durable_contract.py`

上述 marker/string/tests 可證明文件與 routing 沒 drift；不能證明 runtime state 已保存、resume identity 正確或 non-terminal finalization 已被 machine 拒絕。

## ISSUE188_EXECUTION_WINDOW_RECOVERY_PITFALL

#188 在 real Tk/Xvfb 與 inherited QA 已 terminal GREEN 後，execution window interruption 發生在 durable writeback 前。如果因視窗重開就把 RED/GREEN/remote QA 全部從頭重跑，會浪費 runner、模糊 tested-head provenance，甚至把新的 harness noise 誤當舊 production regression。

永久規則：

- execution window interruption 只把語意狀態切到 `RECOVERING`；它本身不撤銷既有 completed phase evidence。
- 先 remote refetch production target、反讀 owning Issue recovery checkpoint、核對 work branch + HEAD 與既有 run identity；無 drift 就接 exact next action。
- **只有 drift 才重驗受影響範圍**；不能因 runtime 重開就重跑全部已完成 phase。
- exact tested HEAD / ancestry 未變時，既有 terminal QA 可繼續作 evidence；若 run identity / ancestry 改變才重新分類。
- **使用者不是續跑 scheduler。** recovery identity 驗完且 next action 可自主執行時，要直接續做，不等使用者再說「繼續」。

這些 recovery 提醒不建立第二套 state machine；實際 `RECOVERING` checkpoint 合法性與 transition 仍交給 `tools/continuity_controller.py`。

## ISSUE188_STALE_WAIT_PITFALL

這次 #188 又暴露另一個長流程失敗模式：checkpoint 寫著 `WAITING_REMOTE_QA`，但實際 GitHub 已無 active run，worker 仍把舊 waiting 字樣當成目前真實狀態，因而無限等待。

永久規則：

- `WAITING_REMOTE_QA` 不是 durable truth；它必須由 exact `run_id + head_sha` 的 live readback 支持。沒有 run identity 或 run 已 terminal，就不得繼續 waiting。
- checkpoint 寫著 WAITING_REMOTE_QA 但 GitHub 已無 active run 時，分類為 `STALE_WAIT`，不是「還在跑」。
- exact run terminal 時立即退出 waiting；非 terminal 但找不到 matching active run 時，以連續 2 次 observation 排除短暫 API 延遲，之後強制進 `RECOVERING_STALE_WAIT`。
- recovery 必須先 remote refetch、反讀 checkpoint、驗 work/production HEAD 與 exact run identity；無 drift 就接 next exact action，不重跑已完成證據。
- global active run = 0 只作 supporting evidence；exact `run_id + head_sha` 才是 canonical remote-QA identity。
- polling cadence 由 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 負責，不是使用者責任；durable state / resume / finalization 則由 `tools/continuity_controller.py` 負責。**使用者不是 watchdog**，不得靠使用者再輸入「輪／繼續」才讓 stale wait 解鎖。
- `.agents/skills/engineering/monitoring-remote-qa/SKILL.md::STALE_WAIT_WATCHDOG` 與 `tests/process/test_continuous_execution_durable_contract.py` 是 remote-QA/documentation regression guards；它們不取代 executable checkpoint state/finalization authority。

## WORK_ORDER_LINEAGE_PITFALL

#185 暴露工單級 branch lineage 缺陷：T3 尚未整合回 production 時，T4 依「每張子票從 latest production 開 fresh branch」起跑，結果 **T4 吃到舊 T3 HEAD**，形成已驗收前序成果與後續子票分叉。

永久規則：

- 派工一個含 T1/T2/... 的 Master 工單時，先從當下 authoritative production target 建立唯一 **工單主分支**；此 branch 持有整張工單從第一個 accepted slice 到 final Combined Acceptance 的前序 accepted lineage。
- 子票不得重新從 production target 起跑。下一張子票的 authoritative base 必須是工單主分支目前 accepted HEAD，或是從該 HEAD 開出的短命 `task/QA branch`；完成後回到工單主分支。
- `production target` 在工單完成前只作 **integration target / drift authority**；不能因它尚未包含上一張子票，就拿它覆蓋工單主分支 lineage。
- `task/QA branch` 只負責隔離實作或驗證，不得成為新的長期 lineage owner；驗收後 non-force 回到工單主分支，臨時 QA workflow/branch 依 cleanup 規則處理。
- 工單內所有 checkpoint / owning Issue / handoff 都必須記錄 `work-order branch + accepted HEAD + production target HEAD` 三者，避免只寫 production SHA 造成下一張票誤起跑。
- 只有整張工單 final Combined Acceptance、durable writeback、invariants、cleanup、closing drift audit 全完成後，才把 final verified work-order HEAD **一次 non-force 整合**到 production target。
- 整合後另做 production-head verification/readback；若 FAIL，從 actual production HEAD 開 fresh hotfix/revert branch，不能倒退或 force production。
- 若歷史工單已發生 lineage divergence，先 classify accepted commits，建立/修復單一 work-order lineage，再續工；不得把舊 production branch 當作「比較乾淨」而丟掉前序 accepted lineage。
- `.agents/skills/engineering/派工/SKILL.md::WORK_ORDER_LINEAGE_CONTRACT` 與 `tests/process/test_continuous_execution_durable_contract.py` 是 workflow lineage regression guards；它們不建立另一套 executable continuity state machine。

## REMOTE_TERMINAL_CLOSING_LOCK_GAP

### 事故模式

Remote QA 在 `queued / in_progress` 時有 `REMOTE_QA_ACTIVE_LOCK`，所以 30 秒回報後仍會繼續 poll；但 run 一 terminal，remote lock 解除，工作其實通常才進入 counts → invariant → cleanup → tested→closing drift → AI writeback → issue/Master closure。舊流程只有 `assert_finalizable`，沒有 machine-level assistant turn-exit gate，因此最容易在「QA PASS」「code integrated」「process incomplete」回報後結束回合。

### 根因與永久修正

- 根因不是缺少 `NON_TERMINAL_CONTINUE` 文字，而是 enforcement scope 只覆蓋 workflow finalization，沒有覆蓋 assistant turn boundary。
- Canonical fix 是 `tools/continuity_controller.py::assert_turn_exitable` / CLI `assert-turn-exitable`。
- `RUNNING / WAITING_REMOTE / RECOVERING` 必須拒絕 turn exit並回傳 exact `next_action`；`BLOCKED` 可 turn-exit 但不可 finalizable；terminal states 可 turn-exit。
- Remote terminal 後若還有收尾，必須 `WAITING_REMOTE → RUNNING(next_acceptance_action)`，由 global turn-exit gate 無縫接手 remote lock。
- progress / CHECKPOINT / PASS / integrated / process-incomplete 都只是 observation；只要 machine checkpoint 還有可自主 next action，使用者就不是續跑 scheduler。
- Behavior authority：`tests/process/test_continuity_controller.py` 的 remote-success → closing-RUNNING regression。入口文字 marker 只作 routing compatibility guard。

## SILENT_ACTIVE_WORK_PITFALL

### 事故模式

Scheduled Resume 已能自行工作，但 active work 期間完全靜默。對使用者而言，「正常背景執行」「正在等既有 RUN」「Runtime 卡死」外觀完全一樣，導致使用者必須再次輸入「輪／繼續」才能確認系統是不是還活著。

### 永久規則

- active scheduled work 不得用完全靜默作正常 UX；必須 bridge `SCHEDULED_RESUME_PROGRESS_HEARTBEAT`。
- 回報狀態只投影 canonical execution truth：`WORKING / WAITING_REMOTE / RECOVERING / BLOCKED / COMPLETE`，不能建立另一套 state machine。
- WAITING_REMOTE 要帶 exact run identity 與 current step/status；長時間無 remote 變化要明示疑似卡住並進 stale 判定。
- shared lease 被另一 Runtime 合法持有時，要說明 safe no-op，而不是沉默。
- 沒有 active work 才可靜默。
- heartbeat 只是 visibility observation；**進度回報不是停工點**，回報後有自主 next action 就繼續。

Canonical authority：`.agents/skills/engineering/executable-continuity-controller/SKILL.md::SCHEDULED_RESUME_PROGRESS_HEARTBEAT`。

## TERMINAL_EVIDENCE_DELAYED_REPORT_PITFALL

### 事故模式

RUN / task 已經拿到 terminal PASS、FAIL 或 COMPLETE evidence，但執行者繼續做額外 readback、cleanup 或證據整理，直到數分鐘後才回報。對使用者而言，這段空白時間與「卡住」沒有差別。

### 永久規則

- 一旦有 evidence-backed terminal 事實，先**立即回報**，再繼續 secondary verification / cleanup。
- 不得為了讓最終報告更完整而延後已經成立的 PASS / FAIL / COMPLETE 事實。
- immediate report 只是一個 observation；回報後若仍有可自主 next action，仍必須繼續。
- 只有 live terminal evidence 可觸發；不得猜測或提前宣告結果。
- Canonical authority：executable-continuity-controller::IMMEDIATE_TERMINAL_PROGRESS_REPORT。

## POLLING_WITHOUT_PROGRESS_PRODUCER_PITFALL

### 事故模式

系統反覆輪詢某個狀態，但實際上沒有任何 executor / runner / workflow 在推進。結果看起來一直「有在看」，實際上沒有產生任何進度，最後還要靠使用者再輸入「輪／繼續」。

### 永久規則

- 輪詢只能觀測進度，不能產生進度。
- WAITING_REMOTE 前必須先確認 real progress producer 已存在且 active。
- no producer / no active run / RUN_NOT_CREATED 時，立即停止假等，去執行 prerequisite / trigger / repair。
- terminal producer 立即離開 waiting，接下一個真正執行動作。
- status-only loop 是 continuity regression。
- Canonical authority：executable-continuity-controller::POLLING_OBSERVATION_ONLY。
