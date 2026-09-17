---
name: monitoring-remote-qa
description: Use when a task has synchronized changes to a remote repository and starts or relies on remote CI/QA such as GitHub Actions, especially while workflow run status can still change.
whd_doc_role: CURRENT
whd_contract: remote-qa-monitoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Monitoring Remote QA

## SCHEDULED_WAKEUP_CONTINUITY_BRIDGE

Scheduled wake-up execution is owned by `.agents/skills/engineering/executable-continuity-controller/SKILL.md`; this Skill **does not own scheduled wake-up execution** and must not create a second execution authority. A schedule only wakes the owning execution context.

On wake-up, restore the owning issue/checkpoint/branch and exact RUN identity. If a concrete RUN exists, this Skill owns only the remote polling mechanics: lock `run_id + head_sha`, poll to terminal, read terminal evidence, then return control to the owning continuity plan for the next autonomous step. If no required RUN exists, report `RUN_NOT_CREATED` to the continuity owner and immediately execute/fix the prerequisite/trigger instead of waiting.

## Active polling is mandatory

Once a remote `run_id + head_sha` is known, proactively poll run → jobs → steps until terminal. Progress updates are observations, not turn boundaries. Poll approximately every 30 seconds while runtime is available. Never create duplicate runs merely because a poll has no change.

On failure, locate the failed step/error marker, read a bounded failure slice, classify production/test vs harness/runner/setup failure, apply the smallest valid fix, and monitor replacement evidence. On success, capture counts/invariants, perform required cleanup, persist durable evidence, and continue the owning acceptance chain.

## Runtime-cut resilience

Remote runners continue independently. If chat/tool runtime is interrupted, reload the durable exact `run_id + head_sha` and resume that run; do not trigger a replacement merely to recover context. If forced to end before completion, the continuity owner must persist the full durable checkpoint required by `SCHEDULED_WAKEUP_CONTINUITY_CONTRACT`.

## Remote QA Active Lock

While a locked run is queued/in-progress, the next actions remain polling that exact run/jobs/steps or bounded failed-log handling. A 30-second user-visible progress update does not release the lock. Terminal status releases only the remote lock, not the owning workflow; unfinished acceptance returns to the continuity owner as `RUNNING(next_action)`.
