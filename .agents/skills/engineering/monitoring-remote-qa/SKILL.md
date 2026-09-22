---
name: monitoring-remote-qa
description: Use when a task has synchronized changes to a remote repository and starts or relies on remote CI/QA such as GitHub Actions, especially while workflow run status can still change.
whd_doc_role: CURRENT
whd_contract: remote-qa-monitoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Monitoring Remote QA


## ACTIONS_USER_VISIBLE_TRADITIONAL_CHINESE_V1

GitHub Actions 是使用者直接觀察 WHD 執行狀態的介面。**所有新建或修改、且會被觸發的 GitHub Actions workflow，其使用者可見名稱一律使用繁體中文**；不得把使用者逼進 RUN 才能知道這顆在做什麼。

固定契約：

- 每個新建／修改 workflow 都必須明確設定 top-level `name:` 與 `run-name:`，且兩者都包含繁體中文；禁止缺少 `run-name` 後讓 GitHub fallback 到英文 commit message。
- Actions 清單外層的 `run-name` 必須直接表達「工單／階段／用途」，例如：`WHD｜#524 A3｜窄委派／別名與 Facade 收斂驗收`。
- 每個 job 必須設定 user-visible `name:`，每個 step 也必須設定 user-visible `name:`；顯示名稱使用繁體中文。SHA、Issue 編號、A1/A2、pytest、Xvfb、DXF、API 等不可替代技術識別可以保留。
- one-shot census、RED/GREEN、Combined Acceptance、reduction gate、finalization、integration、post-integration smoke、Remote Guard 等都適用；「只是暫時 workflow」不是例外。
- 歷史已完成 RUN 無法 retroactive 改名，不要求重跑；規則從新 workflow／新 RUN 起生效。
- workflow dispatch 前，對本次新增／修改的 exact workflow path 執行：
  `python tools/actions_visible_naming_guard.py <workflow.yml> [...]`
- guard 非 GREEN 時分類為 `RUN_NOT_CREATED` prerequisite failure：先修正顯示名稱，再 dispatch；不得先觸發後補名字。
- executable authority：`tools/actions_visible_naming_guard.py`；behavior tests：`tests/process/test_actions_visible_naming_guard.py`。本 Skill 擁有 remote-QA 命名 dispatch gate，其他 Skill 只 bridge，不建立第二套判定器。


## SCHEDULED_WAKEUP_CONTINUITY_BRIDGE

Scheduled wake-up execution is owned by `.agents/skills/engineering/executable-continuity-controller/SKILL.md`; this Skill **does not own scheduled wake-up execution** and must not create a second execution authority. A schedule only wakes the owning execution context.

On wake-up, restore the exact owning checkpoint/branch and concrete `run_id + head_sha` before polling. If the owning plan requires a run but no concrete RUN exists, classify `RUN_NOT_CREATED` and immediately execute/fix the prerequisite or trigger instead of waiting. While a locked run is queued/in-progress, retain this Skill's existing polling contract. Terminal status releases only the remote lock; unfinished acceptance returns to the continuity owner as `RUNNING(next_action)` and continues.

### WATCHDOG_FALLBACK_ONLY_CONTRACT

A watchdog / automation / schedule is **only interruption insurance**. It never becomes the execution owner and never weakens the active-loop duties of this Skill.

Canonical rules:

- `watchdog/schedule presence != permission to stop`.
- 當前 Runtime 仍可執行時，必須繼續目前施工／polling；不得因「已掛 watchdog／排程稍後會再檢查」而結束目前 turn、停止修復、停止 acceptance、或把使用者當 scheduler。
- Schedule/watchdog cadence 只決定「被平台切斷後多久再喚醒」，**不決定當前 execution cadence**。目前 Runtime 還活著時，active polling 仍依本 Skill 的約 30 秒 loop。
- `watchdog wake-up → restore owner → continue exact next action`。喚醒後必須先反讀 owning issue/checkpoint/branch/run identity，再直接續工；禁止只發 `status-only watchdog response` 後再次退出。
- watchdog 可在長鏈執行前／中建立作為 fallback，但它不能把 `RUNNING / WAITING_REMOTE / RECOVERING` 轉成可退出狀態，也不能取代 `REMOTE_QA_ACTIVE_LOCK` 或 global turn-exit gate。
- 終止條件固定為：`owning chain COMPLETE/closed + final acceptance/cleanup finished`。只有這個條件成立後才 **disable the watchdog**；不得因單一 child issue、單一 RUN、focused GREEN 或 partial acceptance 就提前關閉。
- watchdog 若在 owning chain 已完成後被喚醒，先驗證 master/closure evidence，通知完成狀態後立即 **disable the watchdog**，不得留下 orphan recurring monitor。

## LONG_LOG_CONTEXT_SAFE_EXECUTION_V1 bridge

Remote QA 的 polling 狀態機仍由本 Skill 擁有；**長 Log 的讀取方式一律委派** `.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`。正常 poll 只讀 run/jobs/steps + bounded tail/new chunk；完整 raw log 落檔／artifact。FAIL 先定位 failed step/error marker 再讀有限上下文，禁止每輪把整份 job log 灌進 context。
## Overview
Remote QA is a monitored condition loop, not a fire-and-forget action. Triggering a workflow run starts this skill; it does not complete the QA stage.

### USER_VISIBLE_CHECKPOINT_GATE_BRIDGE

本 Skill 一旦進入長流程、remote QA、recovery 或 closure chain，強制服從 `執行開發任務` 的 `USER_VISIBLE_CHECKPOINT_GATE`。該 gate 是 user-visible CHECKPOINT 的唯一 canonical authority；本 Skill 不複製其欄位／refresh state machine，且不得建立第二套 CHECKPOINT authority。

- 需要顯示 CHECKPOINT 時，沿用 canonical gate 的固定標題、欄位與重大 state transition refresh 規則。
- progress update 不得取代可見 CHECKPOINT；30 秒 observation 仍只屬 progress。
- non-terminal CHECKPOINT 不是停工點；顯示後仍依本 Skill 原有 owner contract 繼續 next action。
- 本 Skill 只保留自己的 domain responsibility；CHECKPOINT 呈現責任一律 bridge 回 canonical gate。

### EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE

Remote-QA polling mechanics 仍由本 Skill 唯一擁有，但 durable wait/recovery/finalization state 必須委派 `.agents/skills/engineering/executable-continuity-controller/SKILL.md` 與 `tools/continuity_controller.py`。

- 一旦取得 non-terminal remote `run_id + head_sha`，先把 controller checkpoint transition/persist 成 `WAITING_REMOTE`，`next_action` 必須明確為同一 locked run 的 poll；已知時同步保存 `job_id / log_cursor / evidence`。
- `WAITING_REMOTE` checkpoint 若缺 run identity 或 next action，controller 必須 fail closed；不能只因文字 checkpoint 寫著 WAITING 就繼續假等。
- chat/tool Runtime hard-cut 後，先 `load_checkpoint` 取得 exact run/head/cursor，再做 live readback；無 drift 續 poll 同一 run，不新 trigger。
- terminal run 只代表解除 remote active lock；若 counts/invariants/cleanup/issue closure 還沒完成，controller 應 transition 回 `RUNNING(next_acceptance_action)`，不能直接 `TERMINAL_SUCCESS`。
- 每次準備離開整條 workflow／關單前，由 owning execution/closure gate 呼叫 `assert_finalizable`；本 Skill 的 `REMOTE_QA_ACTIVE_LOCK` / `final 禁止` 文字只提供操作規範，不再被當成 machine enforcement 本身。

## Active polling is mandatory

Remote QA monitoring is **active polling**, not event notification.

- Once a remote `run_id + head_sha` is known, the assistant must proactively query the run state on a recurring loop while the current Runtime is available.
- Each polling cycle must read at least: **run → jobs → active/pending/failed steps**. When a job or step fails, immediately locate the failed step/error marker and retrieve only a bounded failure slice; if the provider exposes only a full download, persist it first and search/chunk it outside the chat context.
- Do **not** wait for GitHub/webhook/UI/event notifications to tell the assistant that the run changed state. Notifications may be supplemental evidence only; they never replace polling.
- A lack of new events/messages is **not** a reason to stop. If the run remains `queued` / `in_progress`, schedule the next poll in the same execution loop.
- During normal active monitoring, poll approximately every **30 seconds** unless a tool call itself is still executing. If a terminal state appears sooner, handle it immediately.
- Never create duplicate remote runs merely because a poll returned no change. Keep the same locked `run_id + head_sha` until it reaches terminal, unless a diagnosed fix explicitly creates a replacement run.
- If the chat/tool Runtime is interrupted, the remote runner continues independently; when control returns, the first monitoring action is to re-read the durable `run_id + head_sha` and resume active polling from that exact run.

## Required loop
1. Record the remote head SHA, workflow/run ID, intended QA gates, and any invariant such as `config.ini` SHA before treating the run as evidence.
2. **Actively poll** the workflow run, then its jobs and steps, until every required job reaches a terminal state. Do not wait for event notifications/webhooks. A progress update to the user is only an observation point; it must not stop the polling loop.
3. If a job fails, locate the failed step/error first and read a bounded slice under `LONG_LOG_CONTEXT_SAFE_EXECUTION_V1`; do not repeatedly fetch/paste the whole log. Classify the failure as production/test failure vs harness/runner/setup failure using the project debugging/timeout rules. Apply the smallest valid fix or rerun only the affected scope, then monitor the replacement run to terminal state.
4. While the run is `queued` or `in_progress`, continue monitoring in the current execution. **不得只因「已觸發／已開始／還在跑」就停止任務或用進度回報收尾。**
5. On success, extract exact pass/fail counts and required invariant checks from logs. Remove temporary QA workflow/trigger files, then re-read the remote branch to confirm cleanup.
6. Write durable state/provenance with run ID, head SHA, terminal conclusion, pass counts, cleanup result, and remaining blockers. Only after this may dispatching QA accept/close the ticket.

## Fail-closed conditions
- Run ID is unknown or evidence belongs to a different head SHA.
- Any required job/step is still pending, queued, or in progress.
- Failure logs were not inspected.
- Temporary QA files remain when the workflow is intended to be one-shot.
- Durable state does not contain the terminal remote QA evidence.

## Quick reference
| State | Action |
|---|---|
| queued / in_progress | poll run → jobs → steps → progress observation if due → **immediately poll the same locked run again**; never final and never wait for the user to say continue |
| failed | fetch failed-job log → diagnose → fix/rerun affected scope → monitor again |
| success | capture counts/invariants → cleanup temp files → durable state → accept |
| cancelled / timed_out | inspect logs/state; classify and rerun only unresolved scope |

## Common mistakes
- Treating “workflow triggered” as completed work.
- Ending a response because the run is still executing even though monitoring tools are available.
- Treating GitHub/event notifications as the monitor instead of proactively polling the locked run.
- Polling only the run status and never checking which job/step failed.
- Re-fetching or pasting the complete long job log on every poll instead of using bounded failed slices / tail + cursor.
- Closing the ticket before temporary workflow cleanup and durable state are verified remotely.
- Sending a 30-second progress update and then ending the assistant turn while the same locked run is still non-terminal.
- Waiting for the user to type `繼續`, `輪`, `continue`, or `poll` before resuming a remote-QA loop.

## Runtime-cut resilience

聊天／工具 Runtime 的執行時間窗不是 remote QA 的生命週期 owner。長遠端 QA 必須設計成 **controller-independent**：

1. **Remote run 自己續跑**：durable runner 的 exit 75/checkpoint 必須由同一 GitHub Actions job / remote controller 自動 resume，同一 journal 直到 terminal state；不得要求聊天端下一次 poll 才啟動下一批。
2. **每輪 run 必須自帶 resume evidence**：至少上傳或落盤 `run_id`、`head_sha`、collection SHA/count、headless/xvfb state、journal、config/tree fingerprint、unresolved failed/timeout nodeids。
3. **遠端可見狀態**：長 gate 應在 `if: always()` 終態 step 將 resumable summary 寫到對應 GitHub Issue / job summary。聊天被切後，下一個 Runtime 可直接從 Issue + artifact 恢復，不依賴前一回合文字。
4. **聊天 polling 只做觀測，不做驅動**：即使 assistant poll 中斷，已觸發的 remote job 必須繼續到自己的 terminal state；不得把「下一次 ChatGPT 回合」當遠端 runner 的 scheduler。
5. **terminal failure 也要 durable**：failure/cancel/timeout 仍必須 `always()` 上傳 journal/state，讓下一 Runtime 精確定位 owning ticket，不重跑已完成證據。
6. **恢復順序**：取得控制權 → 讀最新 durable run_id/head_sha → 讀 terminal status → 下載 artifact/journal → 分類 blocker → 才決定修正/重跑。禁止先重 trigger。

## User-visible reporting cadence

在 active remote QA 監控期間，對使用者的狀態回報節奏固定為 **每 30 秒一次**。

- 只要 remote run 尚未 terminal，且聊天 Runtime 仍在線，就約每 30 秒回報一次目前狀態。
- 回報內容至少包含：固定 `run_id`、`head_sha`、目前 step / mode（Headless 或 Xvfb）、最近一次 durable state（completed/pending/failed/timeout）。
- 不因「沒有變化」而完全靜默；若 30 秒內沒有新結果，明確回報「仍在同一 run/step，無新 blocker」。
- 若 run 已 terminal，立即回報，不必等滿 30 秒。
- 30 秒 cadence 只影響聊天中的觀測回報；**不得用聊天回報節奏驅動 remote runner**。遠端 durable checkpoint/resume 仍必須 controller-independent。
- 若聊天 Runtime 被平台切斷，remote runner 照常繼續；下一 Runtime 先讀 durable `run_id/head_sha/state/artifact` 後恢復監控，不補發缺失的 30 秒訊息。

## Progress updates are not turn boundaries

**進度回報不是 assistant turn / response 的結束點。** 30 秒回報只是同一個 active polling loop 裡的 observation。

- 若 locked run 仍是 `queued` / `in_progress`，而 polling tools 與目前 Runtime 仍可用，送出 commentary 進度回報後，**下一個動作必須是同一個 locked `run_id + head_sha` 的 poll**。
- 不得因「我已經回報過 30 秒狀態」就結束 assistant turn；回報本身不解除 `REMOTE_QA_ACTIVE_LOCK`。
- **不得要求或依賴使用者輸入「繼續」「輪」「continue」「poll」**才恢復監控。**使用者不是 remote-QA scheduler**；scheduler/controller 責任在目前持有 lock 的 assistant/runtime。
- 「狀態沒有變化」只代表下一輪仍然 poll 同一 run，不是把控制權交回使用者的理由。
- run 疑似 hang/stale 時仍保持 lock。若專案 timeout policy 與目前工具明確提供合法 cancel/timeout 能力，才可依該 policy terminalize；若沒有，就繼續 poll 到 terminal 或實際 Runtime/tool interruption，不能用「卡太久」作為 status-only final 的理由。
- 使用者若明確改變／取消目前目標，可依最新指示重新判斷；除此之外，non-terminal monitoring loop 不得由使用者訊息驅動。

## Final-response gate

在送出任何 `final` 前，先執行這個 turn-completion gate：

1. 檢查目前是否存在 `REMOTE_QA_ACTIVE_LOCK`。
2. 若存在，而且 locked run 仍是 **non-terminal**，且 polling tools/runtime 仍可用：**final 禁止**；下一個動作必須回到同一 `run_id + head_sha` 的 poll。
3. commentary 形式的 30 秒進度觀測不滿足 final gate，也不算本回合完成。
4. 只有 locked run 已 terminal、使用者明確改變／取消當前目標，或實際 Runtime/tool interruption，才允許離開 non-terminal polling loop。

### Rationalization guard

| 想法 | 正確判定 |
|---|---|
| 「先回報一下，等使用者再說繼續」 | 錯。回報後立即 poll 同一 locked run。 |
| 「沒有狀態變化，可以先停」 | 錯。無變化就是下一輪仍 poll。 |
| 「我已經回報 30 秒，所以這回合完成」 | 錯。cadence 是 observation，不是 turn boundary。 |
| 「卡住太久，只能把控制權交回使用者」 | 錯。保持 lock；只有合法 terminalization 或真正 Runtime interruption才可中斷。 |
| 「使用者可以打『輪』再叫我查」 | 錯。使用者不是 scheduler，不能靠下一則訊息驅動監控。 |

## Remote QA Active Lock

這是 active polling 的**不可跳過執行鎖**，不是提醒。

- 一旦取得 `run_id + head_sha`，且該 run 仍為 `queued` / `in_progress`，立即進入 `REMOTE_QA_ACTIVE_LOCK`。
- Lock 存在期間，下一個工具動作只能是：
  1. poll 該 `run_id`；
  2. poll 該 run 的 jobs/steps；
  3. 若 terminal failure，讀 failed-job log；
  4. 對使用者送出 30 秒進度觀測；**若觀測後 run 仍 non-terminal，必須立即回到第 1/2 項繼續 poll，不能結束 assistant turn**。
- **禁止**在 non-terminal run 期間轉去讀無關 code、修改 production/test/skill、建立另一個 workflow/run、做 branch cleanup、開新診斷或處理別張票。這些動作一律等 terminal 後才可執行。
- **禁止**把下一次使用者訊息當成 scheduler：不得以「等你說繼續／輪」取代 assistant 自己的 active polling。
- 只有三種情況可中斷目前 polling loop：
  - 該 locked run 到達 terminal；
  - 使用者明確改變／取消目前目標；
  - Runtime/tooling 被平台實際切斷。下次取得控制權時，若目標未改，第一個動作必須用 durable `run_id + head_sha` 恢復同一 lock。
- terminal failure 後，先抓 log 並完成 failure classification；之後才可解除舊 run lock、進修正流程。修正若觸發 replacement run，立即對新 `run_id + head_sha` 建立新的 active lock。
- 每次非 polling工具呼叫與每次送出 `final` 前都必須自問：目前是否存在 non-terminal locked run？若是且 Runtime/tools 仍可用，該動作非法，先 poll。

## STALE_WAIT_WATCHDOG

`WAITING_REMOTE_QA` 不是被動文字狀態；它只有在一個**可驗證、仍 active 的 locked run**存在時才合法。

- **沒有 run_id + head_sha 就禁止進入 waiting**。沒有 durable run identity 時只能分類為 `NOT_SUBMITTED`、`RECOVERING` 或其他實際階段，必須執行可自主完成的 next action；不得寫成「等待 QA」。
- **只有 queued / in_progress 才允許維持 waiting**。每次 resume、checkpoint reread、30 秒輪詢與 final gate 前，都先用保存的 `run_id + head_sha` 查該 exact run；不能只相信舊 checkpoint 的 `WAITING_REMOTE_QA` 字樣。
- **terminal run 立即退出 waiting**。`completed/success` 直接進 counts/invariants/cleanup/closure；`failure/cancelled/timed_out` 立即抓 evidence 並進 failure classification。terminal state 不需要 watchdog 連續確認。
- 若 exact `run_id` 已不存在/404、run identity 與 `head_sha` 不符，或 checkpoint 寫著 `WAITING_REMOTE_QA` 但 repository readback 顯示 **active run = 0**，先標記 `STALE_WAIT`；這是 recovery signal，不是「繼續等」。
- 為避免短暫 API/read-after-write 延遲造成誤判：非 terminal 的「查不到 matching active run」情況以 **連續 2 次**觀測確認；兩次觀測仍無 matching active locked run，就強制轉成 `RECOVERING_STALE_WAIT`。
- `RECOVERING_STALE_WAIT` 固定執行：`remote refetch → owning Issue/checkpoint reread → work HEAD/production HEAD drift verification → exact run identity recheck → continue exact next action`。若沒有 drift，不得重跑已完成 RED/GREEN/terminal QA；若有 drift，只重驗受影響範圍。
- watchdog observation 沿用既有 **30 秒** cadence；但一旦讀到 terminal run、404/invalid identity 或第二次 stale confirmation，就立即處理，不必等滿下一個 30 秒。
- global `active run = 0` 只能作 supporting evidence；canonical 判定仍以保存的 exact `run_id + head_sha` 為先，避免 unrelated workflow 或 pagination 造成誤分類。
- **使用者不是 watchdog**。不得要求使用者輸入「繼續／輪／poll」來解除 stale waiting；一旦判定 `STALE_WAIT` / `RECOVERING_STALE_WAIT`，assistant/controller 必須自己恢復並推進 next action。

## GLOBAL_TURN_EXIT_AFTER_REMOTE_BRIDGE

`REMOTE_QA_ACTIVE_LOCK` 只擁有 remote run 非終態期間的 polling lock；它在 run terminal 時解除，**不代表 assistant turn 因此可結束**。Terminal success 若還有 counts/invariants/cleanup/drift/writeback/closure，先把 durable checkpoint 轉成 `RUNNING(next_acceptance_action)`，再由 `executable-continuity-controller::ASSISTANT_TURN_EXIT_GATE_V1` 接手。

因此 `remote success → RUNNING(cleanup)` 必須讓 `assert_turn_exitable` fail closed；任何「RUN PASS」進度回報之後直接停止，都屬 closing-lock-gap regression。

## CHATGPT_SCHEDULED_REENTRY_REMOTE_QA_BRIDGE

當 primary ChatGPT scheduled re-entry 喚醒後遇到 remote QA：

- fresh-read checkpoint 的 exact `run_id + head_sha`，再讀 live run/jobs/steps；
- active 且未超過 scheduled stale threshold（default 2h）→ 保持同一 remote lock、safe no-op/續 poll，不建立 replacement run；
- terminal / missing / stale / owner mismatch → 退出 WAITING_REMOTE，進 RECOVERING 並保留 exact remote evidence；
- scheduled wake 的 hourly cadence **不取代** live Runtime 內本 Skill 約 30 秒 polling；
- GitHub cron/watchdog 可以輔助觀測 remote state，但不是 ChatGPT executor。

## SCHEDULED_RESUME_PROGRESS_HEARTBEAT_BRIDGE

Scheduled re-entry 的 user-visible heartbeat authority 在 `executable-continuity-controller::SCHEDULED_RESUME_PROGRESS_HEARTBEAT`；本 Skill 只提供 `WAITING_REMOTE` 的 remote evidence，不建立第二套 heartbeat/state machine。

當 scheduled heartbeat 投影為 `WAITING_REMOTE` 時，必須從目前 canonical lock 提供 exact `run_id + head_sha`、目前 step / status、最後一次 remote updated evidence，以及「正常等待既有 RUN」或 stale/recovery 判斷。Active/non-stale run 仍鎖同一 run，禁止另建 replacement RUN；疑似 stale 時沿本 Skill 的既有 stale policy 轉 recovery。

這個 scheduled heartbeat 不取代 live Runtime 約 30 秒一次的 polling/回報；而任何 progress update 都不是停工點，回報後 remote lock 還 active 就繼續 poll。

## IMMEDIATE_TERMINAL_PROGRESS_REPORT_BRIDGE

當 exact locked remote run 從 queued / in_progress 進入 **terminal** 時，先 bridge executable-continuity-controller::IMMEDIATE_TERMINAL_PROGRESS_REPORT：取得 terminal evidence 後要**立即回報** run_id + head_sha + conclusion + terminal step，不得先做 secondary readback 或 cleanup 才讓使用者知道結果。

terminal report 後仍沿既有 contract：
- success → counts / invariant / cleanup / acceptance / closure；
- failure → failed-job evidence → classification → recovery；
- 回報只是一個 observation，**不是** remote-QA 或整體工作的停工點。

## REAL_PROGRESS_PRODUCER_GATE

Remote QA 的 polling 只能觀測已經存在的 progress producer，不能替它工作。

- 有 exact active run / executor：保留 WAITING_REMOTE，鎖 run_id + head_sha 輪詢。
- no executor、沒有 active run、RUN 尚未真正建立、或 producer 已 terminal：禁止繼續假等。
- RUN_NOT_CREATED 時立即執行 trigger/prerequisite/fix，讓真正的 producer 出現；不得靠 polling 製造假進度。
- producer terminal 時立即退出 waiting，success 進下一 acceptance action，failure 進 RECOVERING。
- 如果目前工作本來就必須由 ChatGPT 自己推，則不得把自己放進 WAITING_REMOTE 再一直 poll。
