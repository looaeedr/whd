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
