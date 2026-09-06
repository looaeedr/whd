---
name: monitoring-remote-qa
description: Use when a task has synchronized changes to a remote repository and starts or relies on remote CI/QA such as GitHub Actions, especially while workflow run status can still change.
---

# Monitoring Remote QA

## Overview
Remote QA is a monitored condition loop, not a fire-and-forget action. Triggering a workflow run starts this skill; it does not complete the QA stage.

## Required loop
1. Record the remote head SHA, workflow/run ID, intended QA gates, and any invariant such as `config.ini` SHA before treating the run as evidence.
2. Poll the workflow run, then its jobs and steps, until every required job reaches a terminal state. A progress update to the user is only an observation point; it must not stop the loop.
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
| queued / in_progress | poll run → jobs → steps; continue |
| failed | fetch failed-job log → diagnose → fix/rerun affected scope → monitor again |
| success | capture counts/invariants → cleanup temp files → durable state → accept |
| cancelled / timed_out | inspect logs/state; classify and rerun only unresolved scope |

## Common mistakes
- Treating “workflow triggered” as completed work.
- Ending a response because the run is still executing even though monitoring tools are available.
- Polling only the run status and never checking which job/step failed.
- Closing the ticket before temporary workflow cleanup and durable state are verified remotely.


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

