# Issue #431 / T1 — Shared-content host & mutually-exclusive mode controller

## Authority
- Parent: #429
- Predecessor: #430 CLOSED/completed
- Predecessor tested SHA: `a3a3a8ec67b1ece5cc27b8392298737ed2c53772`
- Exact T1 base / #430 closing SHA: `95ab91c900e9a531ce0fec25a698123116392cc2`
- Work branch: `refactor/issue431-t1-shared-content-host-20260920`

## Knowledge Preflight
- preflight HEAD: `22bb3a35b80858c121ff0e38eabe31c0c5039b30`
- RUN: `35495987364`
- JOB: `106038887410`
- result: SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

Required owners verified by the machine preflight:
- UI設計與去AI味
- phase6-corner-3d-model-integrity
- diagnosing-bugs
- tdd
- monitoring-remote-qa
- long-log-context-safe-execution
- executable-continuity-controller
- 驗證板件與DXF

## Pre-agreed behavior seam
The T0 accepted RED is the primary public Tk/layout seam:
`tests/test_issue430_single_host_red.py::test_t0_intended_red_all_three_modes_require_one_direct_shared_content_host`

T1 adds two behavior-level requirements:
1. one dedicated shared host owns all three existing content trees;
2. the controller maps exactly one of those existing trees at a time.

A third guard verifies that `designer_workspace.active_part` and `_phase6_3d_display_mode` remain the existing authority sources; T1 must not invent a replacement state authority.

## RED phase
This commit is tests/docs/workflow only. `fold_designer_bridge.py` must remain byte-identical to T1 base.

Expected RED run:
```text
5 PASS
3 intended FAIL
0 SKIP
```

Expected failures:
- inherited #430 direct-host count RED
- T1 shared-host ownership RED
- T1 shared-content controller RED

## T1 target
```text
SHARED_CONTENT_HOST_COUNT=1
ACTIVE_SHARED_CONTENT_MODE_COUNT=1
SEPARATE_ASSEMBLY_REGION=0
SEPARATE_CORNER_DATA_REGION=0
MODE_SWITCH_CREATES_STATE_AUTHORITY=0
```

## State
```text
STATE=RED_PENDING
NEXT_ACTION=Run exact T1 RED remotely. Do not edit production until exact intended failure set is confirmed.
```
