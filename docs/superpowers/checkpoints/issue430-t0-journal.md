# Issue #430 / T0 — Single-host baseline census journal

## Authority
- Master: #429
- Task: #430 / T0
- Target: `cleanup/2d-3d-sync`
- Exact post-Phase-5 baseline: `50e14c7054916cb0b9597c61194725939c5de323`
- Work branch: `qa/issue430-t0-single-host-census-20260920`
- T0 scope: characterization/evidence/tests only; no production runtime edit.

## Knowledge Preflight
- first fail-closed run: `35494744058` — missing reading evidence, expected process RED
- harness-only false RED: `35495093718` — canonical preflight was all ✓; noncanonical grep caused wrapper failure
- canonical task preflight GREEN: `35495142279`
- changed-file preflight GREEN: `35495290137`
- durable evidence: `docs/superpowers/checkpoints/issue430-t0-preflight-evidence.txt`

## Baseline census
The current presentation is mutually exclusive, but three direct left-content hosts exist:
- normal: `fold_editor_host`
- assembly: `assembly_parts_panel`
- Corner Data: `corner_data_panel`

The exact source and lifecycle census is recorded in:
`docs/superpowers/checkpoints/issue430-t0-census.md`

## Accepted remote characterization
- RUN: `35495541940`
- JOB: `106037701015`
- TESTED HEAD: `a3a3a8ec67b1ece5cc27b8392298737ed2c53772`
- artifact: `issue430-t0-census` / ID `10599994493`
- artifact SHA256: `42ee0fde4cc477a53c31d6c0fd3e102bb0439b3f10864fac0c1d363dfadf841a`

Focused result:
```text
4 passed
1 intended failed
0 skipped
```

The sole failure is exactly:
`tests/test_issue430_single_host_red.py::test_t0_intended_red_all_three_modes_require_one_direct_shared_content_host`

Observed direct host identities:
```text
normal      .!frame.!frame6
assembly    .!frame.!frame5
corner_data .!frame.!frame7
count=3
target=1
```

The four GREEN characterization guards prove:
- workspace active-part + existing `_phase6_3d_display_mode` remain the authority boundary;
- repeated switching reuses existing mode surface objects;
- refresh and add/delete do not accumulate extra mode surfaces;
- fresh workspace instances do not reuse stale Tk widget objects.

The workflow also proved:
```text
POST_PHASE5_ROOT_EXACT=1
KNOWLEDGE_PREFLIGHT_RC=0
SHARED_CONTENT_HOST_CENSUS_COMPLETE=1
MODE_AUTHORITY_CENSUS_COMPLETE=1
MOUNT_UNMOUNT_CENSUS_COMPLETE=1
DUPLICATE_REGION_RED_INTENDED=1
PRODUCTION_RUNTIME_EDIT=0
```

## Accepted conclusion
T0 is accepted. The defect is characterized as a **physical host ownership problem**, not duplicate active-part state and not repeated-switch widget leakage.

T1 may now replace the three direct-left host ownership paths with one dedicated shared-content host and one mutually exclusive presentation controller. T1 must not create new workspace, visibility, corner-data, geometry, persistence, or callback authority.

## State
```text
STATE=ACCEPTED
ACCEPTED_HEAD=a3a3a8ec67b1ece5cc27b8392298737ed2c53772
ACCEPTED_RUN=35495541940
NEXT_ACTION=#431 / T1
```
