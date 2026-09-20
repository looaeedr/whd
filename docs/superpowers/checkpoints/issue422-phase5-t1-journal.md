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


## RED / GREEN Evidence

### Harness classification

- RUN `35486741374`: `PREFLIGHT_HARNESS_FAILURE`; changed-file Preflight correctly required `Python測試實務`. Pytest did not run. Not requirement RED evidence.
- RUN `35486838972`: `PYTEST_DEPENDENCY_HARNESS_FAILURE`; Preflight and RED scope passed, runner lacked pytest (`No module named pytest`). Not requirement RED evidence.

### Valid requirement RED

- RUN `35486892445` @ `424ee6d712520acf557a10182d3f09944d459004`: SUCCESS
- `KNOWLEDGE_PREFLIGHT_RC=0`
- `T1_RED_PRODUCTION_IMPLEMENTATION_CHANGED=0`
- pytest: `7 failed in 0.20s`
- `T1_RED_INTENDED=1`
- `T1_RED_PYTEST_RC=1`
- no collection/import/syntax harness error
- production module absent as required

Dual-mode harness readback:
- RUN `35486945834` @ `9ef14d9de11ae28c435d0a4f27dad36fa126ce25`: SUCCESS
- RED branch remained valid before production module creation
- `CONFIG_INVARIANT=GREEN`

### Minimal GREEN

- Production module commit: `fb1baabed4931ec7831a48801708e4d25c1649c6`
- RUN `35486990874` @ exact HEAD `fb1baabed4931ec7831a48801708e4d25c1649c6`: SUCCESS
- focused pytest: `7 passed in 0.16s`
- `T1_GREEN=1`
- `TOP_LEVEL_PRESENTATION_ORDER_PARITY=GREEN`
- `SYNTHETIC_GROUP_PARITY=GREEN`
- `BOX_PIECE_SOURCE_PARITY=GREEN`
- `BOX_PIECE_ORDER_PARITY=GREEN`
- `BOX_PIECE_DIMENSION_SOURCE_PARITY=GREEN`
- `TK_REFS=0`
- `BRIDGE_IMPORTS=0`
- `APP_OWNER_REFS=0`
- `WORKSPACE_MUTATION=0`
- `MANUFACTURING_SOLVE=0`
- `PROJECT_MUTATION=0`
- `T1_SCOPE_EXTERNAL_DRIFT=0`
- `CONFIG_INVARIANT=GREEN`

## Acceptance State

```text
STATE=GREEN
TESTED_HEAD=fb1baabed4931ec7831a48801708e4d25c1649c6
RUN_ID=35486990874
NEXT_ACTION=Run exact-head T1 closing qualification/finalization proof with no further production changes.
```
