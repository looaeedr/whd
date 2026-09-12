---
name: monitoring-remote-qa
description: Use when a task has synchronized changes to a remote repository and starts or relies on remote CI/QA such as GitHub Actions, especially while workflow run status can still change.
---

# Monitoring Remote QA

## Overview
Remote QA is a monitored condition loop, not a fire-and-forget action. Triggering a workflow run starts this skill; it does not complete the QA stage.

## Active polling is mandatory

Remote QA monitoring is **active polling**, not event notification.

- Once a remote `run_id + head_sha` is known, the assistant must proactively query the run state on a recurring loop while the current Runtime is available.
- Each polling cycle must read at least: **run → jobs → active/pending/failed steps**. When a job or step fails, fetch its log immediately.
- Do **not** wait for GitHub/webhook/UI/event notifications to tell the assistant that the run changed state. Notifications may be supplemental evidence only; they never replace polling.
- A lack of new events/messages is **not** a reason to stop. If the run remains `queued` / `in_progress`, schedule the next poll in the same execution loop.
- During normal active monitoring, poll approximately every **30 seconds** unless a tool call itself is still executing. If a terminal state appears sooner, handle it immediately.
- Never create duplicate remote runs merely because a poll returned no change. Keep the same locked `run_id + head_sha` until it reaches terminal, unless a diagnosed fix explicitly creates a replacement run.
- If the chat/tool Runtime is interrupted, the remote runner continues independently; when control returns, the first monitoring action is to re-read the durable `run_id + head_sha` and resume active polling from that exact run.

## Required loop
1. Record the remote head SHA, workflow/run ID, intended QA gates, and any invariant such as `config.ini` SHA before treating the run as evidence.
2. **Actively poll** the workflow run, then its jobs and steps, until every required job reaches a terminal state. Do not wait for event notifications/webhooks. A progress update to the user is only an observation point; it must not stop the polling loop.
3. If a job fails, fetch that job log immediately. Classify the failure as production/test failure vs harness/runner/setup failure using the project debugging/timeout rules. Apply the smallest valid fix or rerun only the affected scope, then monitor the replacement run to terminal state.
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
| 「卡住太久，只能把控制權交回使用者」 | 錯。保持 lock；只有合法 terminalization 或真正 Runtime interruption 才能中斷。 |
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
- 每次非 polling 工具呼叫與每次送出 `final` 前都必須自問：目前是否存在 non-terminal locked run？若是且 Runtime/tools 仍可用，該動作非法，先 poll。
