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
- executable guard is required before each work-branch write.

## Knowledge Preflight
- first fail-closed run: `35494744058` — missing reading evidence, expected RED
- harness-only false RED: `35495093718` — canonical preflight was all ✓; extra noncanonical grep failed
- canonical task preflight GREEN: `35495142279`
- changed-file preflight GREEN: `35495290137`
- durable evidence: `docs/superpowers/checkpoints/issue430-t0-preflight-evidence.txt`

## Baseline census
Current presentation is mutually exclusive but currently has three direct left-content hosts:
- normal: `fold_editor_host`
- assembly: `assembly_parts_panel`
- Corner Data: `corner_data_panel`

The exact mount/unmount and mode authority census is in:
`docs/superpowers/checkpoints/issue430-t0-census.md`

The intended RED is deliberately narrow: ascend each mode surface to the first child directly owned by `self.left`; #429 requires all three to resolve to one identity.

The remaining lifecycle guards do **not** assert that three hosts are correct. They only prove:
- existing mode/workspace authority remains single-source;
- repeated switching does not accumulate more surface objects;
- refresh + add/delete does not accumulate more surface objects;
- a fresh workspace does not reuse stale Tk objects across instances;
- only one mode surface is mounted at a time.

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

## Current state
```text
STATE=RUNNING
NEXT_ACTION=Run qa-issue430-t0-census on the exact characterization HEAD; require 4 PASS + exactly 1 intended RED and zero production runtime edits.
```
