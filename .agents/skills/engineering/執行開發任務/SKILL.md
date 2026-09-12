---
name: 執行開發任務
description: 依已核准規格或工單執行實作。用於進入實作者階段、修改 production/test/Skill、跑 targeted 驗證、產生 durable checkpoint，並在 WHD 專案遵守派工、Preflight、owning Issue、remote QA 與 resume 規則。
disable-model-invocation: true
---

# 執行開發任務

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

## 4. 測試 timeout

- GUI targeted gate 若 pytest 已有完整 PASS summary 但 Tk/Xvfb/interpreter 不退出，分類為 `complete_teardown_timeout`。
- 只有點號、局部百分比或不完整輸出時是 `incomplete_timeout`，不得冒充 PASS。
- incomplete batch 只縮小並重跑 pending nodeids；已完成節點禁止為方便重跑。
- process-group、Xvfb ownership、killpg、journal/resume 與 provenance 細節以 `派工` Skill 為準。

## 5. Remote QA Active Lock

只要建立或依賴 non-terminal remote QA run，立即服從 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 的 `REMOTE_QA_ACTIVE_LOCK`。

run terminal 前禁止繼續 code exploration、production/test/Skill write、下一張工單或另一個診斷；只能 poll run/jobs/steps、處理 terminal failure log、做 30 秒進度回報。terminal 後才恢復一般實作流程。

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
