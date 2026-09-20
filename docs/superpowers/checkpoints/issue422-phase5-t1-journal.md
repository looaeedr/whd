# Phase 5 / Issue #422 T1 Journal

## Authority

- MASTER_ID: `#413`
- TASK_ID: `#422 / T1`
- TARGET_X: `cleanup/2d-3d-sync`
- FROZEN_X_BASE_SHA: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- ACCEPTED_PREDECESSOR: `#421 @ b31409e7c1736df31bd554afe4ac779d49b30aaa`
- WORK_ORDER_BRANCH: `refactor/issue413-phase5-assembly-presentation-20260920`
- Requirement Authority: Phase 5 v1.7 accepted master #413
- T1 scope: pure Assembly presentation contracts/projections only

## Knowledge Preflight

Machine changed-file preflight returned `RC=0` before T1 RED write. Remote changed-file preflight later revealed the test-path route also requires `Python測試實務`; that Skill was fresh-read and added before retrying RED.

READ_SKILL: Python測試實務
READ_SKILL: 截角資料入口收斂
READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: executable-continuity-controller
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md

## T1 Characterization Contract

- top-level rows consume `phase6_part_navigation.operator_part_selector_keys`
- Door/BasePlate parent rows are presentation-only synthetic groups
- BoxBody physical-piece rows remain render-time `render_data.pieces` projection
- BoxBody piece dimensions are copied from `formed_outer_dimensions` / `material_dimensions`
- pure T1 module owns no Tk, bridge, app/workspace/project mutation, manufacturing solve, or live visibility store
- group parent owns no visibility/text authority
- row visibility is construction/rebuild seed only

## State

```text
STATE=RED
HEAD=3c0b5089716f6bb7e4a39e3b5c94ce48400a66bf
RUN_ID=35486741374
RUN_STATUS=PREFLIGHT_HARNESS_FAILURE
EVIDENCE=Knowledge Preflight stopped before pytest because Python測試實務 evidence was missing; this run is NOT requirement RED evidence.
NEXT_ACTION=Retry focused assertion RED after complete 7-Skill preflight; module must be missing without collection/import/harness errors.
```
