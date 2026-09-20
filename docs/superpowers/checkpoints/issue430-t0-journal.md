# Issue #430 / T0 — Single-host baseline census journal

## Authority
- Master: #429
- Task: #430 / T0
- Target: `cleanup/2d-3d-sync`
- Exact post-Phase-5 baseline: `50e14c7054916cb0b9597c61194725939c5de323`
- Work branch: `qa/issue430-t0-single-host-census-20260920`
- T0 is characterization/evidence/tests only. Production runtime changes are forbidden.

## Execution claim
- Shared authority: `coord/dispatch-claims:.dispatch/claims/issue-430.json`
- Worker: `chatgpt`
- First guarded work-branch write used exact branch/base/head and returned `EXECUTION_CLAIM_GUARD_GREEN`.

## Knowledge Preflight
Initial remote preflight intentionally failed closed because no completed-reading evidence existed:
- RUN `35494744058`
- HEAD `873975a9f73d8eef25ecdf8f34b00c431e114f2c`
- classification: `EXPECTED_PREFLIGHT_FAIL_CLOSED_MISSING_EVIDENCE`

All required Skills and references were then actually read. Durable machine evidence is:
`docs/superpowers/checkpoints/issue430-t0-preflight-evidence.txt`

## Product contract being characterized
Exactly one physical left shared-content host must eventually serve three mutually exclusive presentations:
1. normal part input/display
2. assembly list
3. corner-data content

T0 does not fix the layout. It must prove the current host/mount/widget-tree reality and produce an intended RED if the current runtime violates the single-host contract.

## Required T0 gates
```text
POST_PHASE5_ROOT_EXACT=1
KNOWLEDGE_PREFLIGHT_RC=0
SHARED_CONTENT_HOST_CENSUS_COMPLETE=1
MODE_AUTHORITY_CENSUS_COMPLETE=1
MOUNT_UNMOUNT_CENSUS_COMPLETE=1
DUPLICATE_REGION_RED_INTENDED=1
PRODUCTION_RUNTIME_EDIT=0
```

## Evidence classifications
- UI widget existence / `winfo_manager()` alone is insufficient for operator-visible ownership.
- Assembly state existence alone is insufficient to prove one shared physical host.
- Corner Data enter/exit lifecycle must be symmetric.
- Validation observations are evidence only and may not become product/runtime authority.

## Current state
```text
STATE=RUNNING
LATEST_REMOTE_RUN=35494744058 (terminal expected fail-closed)
NEXT_ACTION=Rerun Knowledge Preflight from committed evidence; require RC=0 before T0 host/mount analysis.
```
