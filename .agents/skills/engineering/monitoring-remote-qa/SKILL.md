---
name: monitoring-remote-qa
description: Use when a task has synchronized changes to a remote repository and starts or relies on remote CI/QA such as GitHub Actions, especially while workflow run status can still change.
whd_doc_role: CURRENT
whd_contract: remote-qa-monitoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Monitoring Remote QA

## Canonical remote-QA contract

Remote QA is an actively monitored condition loop, not a fire-and-forget action. Long-log handling delegates to `.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`; durable wait/recovery/finalization delegates to `.agents/skills/engineering/executable-continuity-controller/SKILL.md` and `tools/continuity_controller.py`. User-visible CHECKPOINT formatting delegates to the canonical `執行開發任務` gate.

## Run identity / no-run-no-wait

- A real remote wait requires a concrete `run_id + head_sha` owned by the current ticket/branch.
- **NO RUN IDENTITY => NO WAIT.** If a run should exist but does not, classify `RUN_NOT_CREATED` and immediately diagnose/fix/execute the prerequisite or trigger that should create it. Never enter polling merely because a workflow was expected.
- Once a non-terminal run identity exists, lock to that exact run/head. Do not create duplicates because a poll shows no change.
- A chat/runtime cut does not invalidate a remote run. Resume by loading durable identity and reading the same run first; never blindly retrigger.

## Active polling

- While a locked run is `queued` or `in_progress`, poll run -> jobs -> active/pending/failed steps approximately every 30 seconds while the runtime is available.
- A progress report is an observation, not a turn boundary. Do not wait for the user to type `繼續`, `輪`, `continue`, or `poll`.
- On failure, locate the failed step/error marker and inspect a bounded log slice; do not repeatedly inject the full log into chat context.
- Terminal run status releases the remote-active lock but does not itself close acceptance: counts, classification, invariants, artifacts, cleanup, and durable writeback still have to pass.

## CI sharding qualification contract

These rules are permanent for WHD optimized CI:

1. **Deterministic ownership.** `FULL_COLLECTION == UNIQUE_SHARD_UNION`; missing, extra, or duplicate node ownership is FAIL. Ownership must be stable for the same manifest inputs. Do not use collection-index modulo or Python built-in `hash()` as shard authority. HRW/Rendezvous is the default deterministic owner; versioned duration-aware weighted/LPT rebalance is allowed only from measured evidence.
2. **Concurrency budget is explicit.** Logical shard count is not runner concurrency. Respect `CI_CONCURRENCY_BUDGET` / workflow `max-parallel`; increasing logical shards must not silently increase runner pressure.
3. **Duration-aware rebalance is evidence-driven.** Rebalance only when measured shard durations demonstrate imbalance; keep the algorithm/version/input evidence reproducible and re-check complete node ownership after rebalance.
4. **GUI isolation.** Xvfb/Tk shards remain isolated display/process executions unless a separate state-isolation proof explicitly authorizes more concurrency. Never apply global GUI `pytest -n auto` for speed.
5. **Safe result capture.** Capture pytest/Xvfb return code and result artifacts before shell fail-fast can abort classification. `CLASSIFICATION_NOT_RUN` means classification evidence never executed/was not produced; it is **not** equivalent to HANG/TIMEOUT and must not be reported as one without timeout evidence.
6. **Flaky retry semantics.** First-run RED followed by retry GREEN remains `[FLAKY-WARNING]`; retry success does not erase the original instability. Preserve both attempts in evidence and the Unified Summary.
7. **Inherited RED must be exact.** Accepted inherited failures require exact node identity and accepted classification/provenance. Any new or unclassified RED is fail-closed.
8. **One-page Unified Summary.** Final aggregation must publish a concise one-page Markdown summary to `$GITHUB_STEP_SUMMARY` and retain complete machine-readable artifacts. The summary must expose collection/union counts, PASS/SKIP/FAIL classifications, inherited/new/flaky/unclassified status, shard completeness, protected invariants, and timing.
9. **Timing vocabulary is fixed.** Report `EXECUTION_WALL_CLOCK`, `END_TO_END_WALL_CLOCK`, and queue time separately. Do not hide queue latency inside execution performance claims.
10. **A/B authority switch.** Legacy vs optimized qualification uses the same exact source SHA and compares collection, failed-node set, allowed-skip contract, missing/duplicate ownership, protected drift, and timing. A faster run with weaker coverage is not acceptance.
11. **Protected invariants.** CI optimization must not mutate production geometry/UI/persistence/DXF behavior for convenience. Preserve config.ini, protected DXF/project/tracked-tree invariants and read them back after acceptance.
12. **Cleanup safety.** Secure final acceptance evidence before cleanup. Before deleting temporary QA refs, run a fresh OPEN PR `head.ref/base.ref` protection gate; never delete a live PR ref and never fake deletion by moving a ref. Verify absence by fresh remote readback.
13. **Fresh branch rule.** Every code/workflow/skill modification starts from a fresh branch. Never modify `cleanup/2d-3d-sync` directly.
14. **Integration authorization.** Qualification may determine an integration shape but must not mutate/merge production until the user explicitly says `合`.

## Required acceptance loop

1. Lock exact branch/head and expected gates; capture protected invariant fingerprints.
2. If no concrete run exists when required, diagnose trigger immediately (`RUN_NOT_CREATED`); do not poll an imaginary run.
3. When a run exists, actively poll it to terminal and classify failures from bounded evidence.
4. Reconcile authoritative collection against unique shard union and result union. Fail on missing/duplicate/unclassified nodes.
5. Preserve exact inherited RED, `[FLAKY-WARNING]`, and `CLASSIFICATION_NOT_RUN` semantics.
6. Verify concurrency budget, shard timing, execution/end-to-end/queue metrics, Unified Summary, artifacts, and protected invariants.
7. Secure evidence, then perform PR-protected temporary cleanup and fresh remote readback.
8. Persist run/head/counts/classification/timing/artifact/cleanup evidence. Only then may the owning closure gate accept the ticket.

## Quick reference

| State | Required action |
|---|---|
| expected workflow but no run ID | diagnose/fix trigger now; **do not wait** |
| queued / in_progress | poll exact run -> jobs -> steps; 30s observation does not end turn |
| failed | bounded failed-step evidence -> classify -> minimal fix/rerun unresolved scope |
| retry GREEN after initial RED | retain `[FLAKY-WARNING]` |
| classifier never ran | `CLASSIFICATION_NOT_RUN`, not HANG unless timeout evidence exists |
| success | reconcile counts/classification/invariants/timing -> secure artifacts -> safe cleanup -> durable writeback |

## Fail-closed conditions

- Run identity is missing while code is trying to enter a wait/poll state.
- Evidence belongs to a different head SHA.
- Required job/step is still non-terminal at acceptance time.
- Full collection differs from unique shard union, or ownership has missing/extra/duplicate nodes.
- New RED is unclassified, inherited RED identity drifts, or a retry RED is silently erased.
- Classification did not run but is mislabeled as HANG/TIMEOUT.
- Execution/end-to-end/queue metrics or Unified Summary/artifacts are absent when required.
- Protected invariants drift.
- Temporary cleanup is attempted before evidence is secured or without fresh OPEN PR ref protection.
- Production integration is attempted without explicit `合`.

## Runtime-cut resilience

Remote runners are controller-independent: a chat/tool runtime cut must not be the scheduler. Durable evidence should preserve `run_id`, `head_sha`, collection identity, lane/shard state, journal/result artifacts, protected fingerprints, and unresolved node IDs. On recovery: load durable identity -> read terminal/live status -> inspect artifact/journal -> classify blocker -> continue only unresolved work. Never retrigger first.

## User-visible cadence and final-response gate

During active remote QA, report approximately every 30 seconds while the runtime is available, including locked run/head, current job/step, and latest durable state. If the run remains non-terminal, immediately continue polling; the user is not the scheduler. A final response is allowed only after the locked run is terminal, the user changes/cancels the goal, or the runtime/tooling is actually interrupted. Terminal success still requires acceptance reconciliation and durable writeback before ticket closure.
