---
whd_doc_role: REFERENCE
whd_contract: issue400-scheduled-resume-census
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #400 / T0 — Scheduled Resume capability census

Baseline: `cleanup/2d-3d-sync @ 57d06c793df66982238e25641fa9f84f20cf970e`

## Existing executable authority

`tools/continuity_controller.py` is the canonical durable continuity engine.

It already owns:
- `ContinuityState`
- durable `Checkpoint`
- exact owner fields `issue / branch / head_sha`
- `WAITING_REMOTE` run identity
- atomic save/load
- transition validation
- turn-exit/finalization guards
- CLI `resume`, which returns the current exact `next_action`

It does **not** currently expose a scheduled wake dispatcher that maps continuity state to a wake action.

## Existing documented wake/watchdog contract

Production skills/tests already contain:
- `SCHEDULED_WAKEUP_CONTINUITY_CONTRACT`
- `SCHEDULED_WAKEUP_CONTINUITY_BRIDGE`
- `WATCHDOG_FALLBACK_ONLY_CONTRACT`
- `STALE_WAIT_WATCHDOG`
- runtime-cut recovery rules
- user-is-not-scheduler rules

These are valid behavioral requirements, but current guards are predominantly Skill/marker contracts. They do not by themselves create a generic executable scheduled-resume dispatcher.

## Actual automation-layer census

At T0 live readback:
- an enabled hourly automation named `Phase 4 GitHub Watch` exists and is scoped to Phase 4 issue #388;
- an older `WHD QA 輪詢` automation exists but is disabled.

The enabled #388 automation demonstrates that hourly wake capability exists, but it is a project-specific condition watch. It is **not** a generic Scheduled Resume Bridge that:
1. discovers/accepts the owning checkpoint;
2. validates issue/branch/HEAD;
3. invokes canonical continuity resume;
4. dispatches state-specific exact action.

Therefore do not destroy/reuse #388 as proof that #399 is complete.

## Frozen wake/resume contract

```
scheduled wake
→ identify owning durable checkpoint
→ fresh live owner readback
→ verify issue / branch / HEAD
→ load canonical continuity state
→ dispatch
   RUNNING          => EXECUTE_NEXT_ACTION
   WAITING_REMOTE   => POLL_LOCKED_RUN
   RECOVERING       => CONTINUE_RECOVERY
   BLOCKED          => REPORT_BLOCKER
   TERMINAL_*       => NO_OP / explicit closing handoff only
```

The bridge may classify/route. It must not become a second workflow state machine.

## T0 classifier

```
CONTINUITY_ENGINE_EXISTS = true
SCHEDULED_WAKE_CONTRACT_EXISTS = true
EXECUTABLE_GENERIC_SCHEDULED_RESUME = false
GENERIC_SCHEDULER_BINDING = false
HOURLY_AUTOMATION_CAPABILITY_EXISTS = true
USER_AS_SCHEDULER = false (contract already exists)
PRODUCTION_SOURCE_DRIFT = 0
```
