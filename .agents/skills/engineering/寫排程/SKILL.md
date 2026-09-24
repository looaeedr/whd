---
name: 寫排程
description: 建立、修改、修復 WHD 的 recurring scheduler／ChatGPT automation prompt、lane、cadence 與續工契約。當使用者要求「新增排程」「修改排程」「寫排程」「排程 prompt」「排程一直停」「把排程補硬閘門」，或需要把 recurring automation 寫成可持續施工、可驗證、不可偷偷停工的 durable contract 時使用。
whd_doc_role: CURRENT
whd_contract: scheduler-authoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 寫排程

本 Skill 擁有「怎麼建立／修改 WHD recurring scheduler / automation prompt」的 authoring contract。它**不**擁有派工狀態機、execution claim、Remote Guard、Remote QA、continuity state 或 Issue closure；這些一律 bridge 回既有 canonical Skill / executable authority。

目標不是把 prompt 寫得很長，而是避免每次「縮短、補一句、改名稱、改 cadence」時不小心刪掉真正的 safety / continuity contract。

## 1. Authority 與啟動鏈

### PROMPT_MINIMUM_CONTRACT_V1

任何 WHD 施工型 scheduler prompt 建立或修改前，固定依序取得 authority：

1. 使用者本輪明確要求。
2. live automation state：automation id、title、schedule、timing_mode、enabled、完整 prompt、updated_at、last_run_time。
3. repo owning branch 的 `.agents/skills/engineering/派工/SKILL.md`；無合法最新版才依其規則 fallback。
4. `.agents/skills/engineering/remote-execution-guard/SKILL.md`（canonical name：**遠端執行守門**）。
5. `monitoring-remote-qa`、`executable-continuity-controller` 與當輪 Preflight required Skills / references。
6. automation host 的實際 capability / cadence 限制。

固定硬規則：

- **派工 + 遠端執行守門**不得因 prompt 壓縮、改名或「看起來已在派工 Skill 裡」而省略。
- prompt 只能引用 live Skill / executable authority，不得複製一套會漂移的 Guard schema、TTL、stale threshold 或 parser。
- 修改 repo 內 Skill / SOP 時，仍先走 `AGENTS.md` + `寫技能` Preflight；本 Skill 不取代它。

## 2. 先做 Baseline Snapshot，禁止直接改

每次修改 automation 前，先 fresh-read 並保存：

- `automation_id`
- `title`
- `schedule`
- `timing_mode`
- `is_enabled`
- 完整 `prompt`
- `updated_at`
- `last_run_time`
- prompt 內的 durable lane owner
- entrypoint identity / label
- sibling entrypoints / sibling lanes

未取得 baseline snapshot，不得更新 automation。

修改後必須能回答：

- 哪些欄位是使用者要求改的；
- 哪些欄位必須保持不變；
- 哪些 sibling 明確不在本次 scope；
- 若修改失敗，要用哪份 baseline rollback。

## 3. Schedule、Lane、Entrypoint 三者必須分離

### RECURRING_STAYS_ENABLED

- `schedule` = 何時喚醒。
- durable lane owner = 哪個 logical worker / mutex owner。
- entrypoint = 同一 lane 的哪個喚醒入口。

禁止把三者混成同一 identity。

同一 logical lane 的多個 entrypoint 可以共用 durable owner；它們是 wake-up slots，不是彼此平行的 workers。

真正要平行施工時，必須使用**不同 durable lane owner**，並仍由 shared claims / dependency / integration scope 判斷能否安全平行。

除非使用者明確要求：

- 不得停用、刪除、完成或重排 recurring automation；
- 不得改 sibling 的 cadence；
- 不得改 sibling 的 durable lane identity；
- 不得把「本 invocation 結束」寫成「recurring task 完成」。

若 host 的單一 automation 最快只能每小時一次，而使用者需要 30 分鐘 logical cadence，可用兩個 hourly offset entrypoints 組成一條 lane；是否共用 owner 取決於「同 lane 互斥」還是「不同 lane 真平行」，不可只看時間決定。

## 4. Scheduler Prompt 必備契約

施工型 scheduler prompt 至少必須清楚包含以下語意；標題可調整，但責任不能刪：

### 4.1 SKILL_FIRST_HARD_GATE

在任何 Guard、claim、branch、PR、workflow、Issue、repository mutation、takeover、reconciliation 前：

- fresh-read `派工`；
- fresh-read `遠端執行守門`；
- 依兩者載入 required `monitoring-remote-qa`、`executable-continuity-controller`；
- 驗證 canonical name / contract；
- live authority 與 prompt 衝突時，live authority 優先。

### 4.2 UNCONSUMED_GREEN_FIRST_RECOVERY

上一 invocation 若留下仍 exact-valid 的 `WHD_REMOTE_GUARD_RESULT_V1 result=GREEN`，但授權 mutation 尚未發生：

- 下一 wake 第一個 repo-side substantive action就是依《遠端執行守門》驗證並 single-use consume；
- consume → exact mutation → fresh readback 完成前，禁止新 Guard、禁止跳去別票、禁止正常 return；
- identity drift 先 reconcile，禁止盲 consume。

### 4.3 HEARTBEAT_IS_NOT_WORK

`WHD_SCHEDULER_RUNTIME_LIVENESS_V1` 只是 runtime lease / liveness evidence。

以下都**不等於 substantive work**：

- heartbeat
- progress comment
- CHECKPOINT
- Guard request
- Guard GREEN receipt
- QA PASS / workflow success 本身

只要 exact next_action 仍可執行，就必須繼續。不得因「本輪已有 durable comment」誤判成可以收工。

若存在 pending unconsumed GREEN，應先 consume transaction，再發布新的 heartbeat；避免 heartbeat 變成假進度終點。

### 4.4 BLOCKED_IS_NOT_AN_ESCAPE_HATCH

`BLOCKED` 只允許 genuine external authority / capability / dependency blocker，且必須有 fresh durable evidence。

下列 scheduler 自己能完成的事情不是 blocker：

- fresh discovery
- 查 Actions run 是否存在
- poll 已知 / 可發現 run
- 讀 logs / Issue / claim / branch
- 依 live Skill 發 Guard
- consume GREEN
- exact mutation
- readback
- stale metadata reconciliation

「尚未找到 run」不等於 `RUN_NOT_CREATED`；先 fresh-query exact branch/head。存在 run 就鎖 exact `run_id + head_sha`。

### 4.5 EXACT_REMOTE_RUN_LOCK

一旦 exact remote QA / Guard run 存在：

- 鎖同一 `run_id + head_sha` / orchestrator identity；
- poll 到 terminal；
- 禁止 duplicate dispatch；
- terminal success 同輪前進 acceptance / cleanup / closure；
- terminal failure 同輪抓 exact evidence → recovery；
- stale durable snapshot 不能壓過 live run。

### 4.6 TURN_EXIT_MACHINE_GATE

正常 return 前不能只「文字判斷可以停」。

必須實際走 live continuity authority 的 machine gate，例如 canonical `tools/continuity_controller.py ... assert-turn-exitable` / 等價 `ASSISTANT_TURN_EXIT_GATE_V1`。

下列任一存在，都禁止正常 return：

- unconsumed GREEN
- 可執行 `next_action != null`
- `RUNNING / WAITING_REMOTE / RECOVERING`
- terminal child 仍有 `NEXT_CHILD_EXECUTABLE`

只有 machine gate 放行時，才可寫 owner-authored `WHD_SCHEDULER_RUNTIME_END_V1`，並 fresh-read 驗證 END 與本 invocation identity exact match。

沒有 matching END 的 invocation 不得被下一 wake 當成「正常完成」；必須依 live liveness / continuity 規則 resume。

## 5. Dynamic Discovery，不准寫死工單

Scheduler prompt 不得硬編：

- current Issue / child / master number
- branch
- SHA
- run_id
- claim blob
- next issue
- current next_action

固定 identity 只可以是：

- scheduler automation / lane own identity
- entrypoint identity
- 使用者明確要求固定的 target repo / logical role

每次 invocation 從 live GitHub durable authority fresh-discover executable leaf。

若是平行 lane，claim 前另外 fresh-read：

- 全部 active claims
- dependency graph
- work branch / mutation scope
- integration / finalization ownership

不同 lane identity **不是**搶同一 scope 的許可。

## 6. 修改 Prompt 的 Transaction

### POST_UPDATE_READBACK

每次更新 automation 固定：

1. fresh-read baseline。
2. 明列 intended delta。
3. 建完整 replacement prompt；禁止用「縮短版」偷偷遺失 required Skills / gates。
4. 更新**單一 automation**。
5. 立刻 fresh-read同一 automation。
6. 驗證：
   - title（除非本輪要求改名）
   - schedule
   - timing_mode
   - enabled
   - durable lane owner
   - entrypoint
   - `派工`
   - `遠端執行守門`
   - UNCONSUMED GREEN responsibility
   - HEARTBEAT_IS_NOT_WORK
   - BLOCKED legality
   - EXACT_REMOTE_RUN_LOCK
   - TURN_EXIT_MACHINE_GATE
   - RECURRING_STAYS_ENABLED
7. 任一 invariant 漂移：立即以 baseline rollback；不得繼續修改 sibling。
8. 多 entrypoint 需要相同 core contract 時，一個一個更新、一個一個 readback；不能假設第一個成功代表全部成功。

**禁止行為：**

- 為了「讓 prompt 短一點」刪掉 Skill identity。
- 只保留 `派工`，把 `遠端執行守門` 當成隱含 prerequisite。
- 更新 prompt 時順便改 cadence / enabled / lane identity。
- 只看 automation update API 回 SUCCESS，不做 readback。
- 用 heartbeat 或 BLOCKED 掩蓋 invocation continuity violation。

## 7. Guard Transport 不從記憶硬抄

Remote Guard request / receipt schema 完全由 live《遠端執行守門》擁有。

特別注意：

- host / claim 的 provenance wording 可能和 trusted transport parser 不同；
- 送 request 前必須 fresh-read live Skill / workflow parser；
- 遇到 parser FAIL，讀 exact log 修 schema，不得繞過 Guard；
- Actions job success 本身不等於 Guard GREEN；
- GREEN 是 single-use transaction，不是 session token。

## 8. RED → GREEN 驗證

建立或修改本 Skill / scheduler contract 時：

1. 先建立 contract RED，能抓到「缺遠端執行守門」「heartbeat-only」「BLOCKED escape」「沒有 machine turn-exit」其中至少一項。
2. 最小修改。
3. 跑 targeted contract GREEN。
4. Registry / Preflight route 驗證。
5. 若啟動 remote QA，依 `monitoring-remote-qa` 鎖 exact run 到 terminal。
6. 修改 automation 後，用實際 live readback驗 schedule / identity / enabled / prompt hard gates，不以文字宣告代替。

## 9. Durable Correction Propagation

只要發現 scheduler authoring 的可重複錯誤：

- 更新本 Skill；
- 更新 scheduler prompt authoring pitfalls；
- 必要時更新 Registry route / contract test；
- 搜尋所有受影響的 active automation prompt，確認是否同型缺口；
- 不得只修眼前一個 entrypoint。

## 10. 完成回報

只回報可反讀 evidence：

- 哪些 automation / Skill 被修改；
- automation id / title / schedule / lane owner 是否保持；
- Guard / Remote QA exact run；
- repo branch / commit；
- contract test / Preflight 結果；
- post-update readback 結果；
- 尚未完成的 next_action / blocker。

不得說「寫進 prompt 了，所以一定不會再停」。真正 enforcement 仍以 live executable guard / continuity state / durable evidence 為準。
