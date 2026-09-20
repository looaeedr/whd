# Phase 5 / Issue #423 T2 Journal

## Authority

- MASTER_ID: `#413`
- TASK_ID: `#423 / T2`
- TARGET_X: `cleanup/2d-3d-sync`
- FROZEN_X_BASE_SHA: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- ACCEPTED_PREDECESSOR: `#422 @ cb7ae0d906e52d286e740e5c8fb984c40728be83`
- WORK_ORDER_BRANCH: `refactor/issue413-phase5-assembly-presentation-20260920`
- Requirement Authority: Phase 5 v1.7 accepted master #413
- T2 scope: Assembly panel Tk owner, top-level/synthetic rows, Tk registries, collapse/detail state, recursive wheel binding, rebuild-safe legacy aliases.

## Knowledge Preflight

Changed-file preflight route was evaluated against accepted predecessor and returned:

```text
REQUIRED_SKILLS=9
REQUIRED_REFERENCES=8
KNOWLEDGE_PREFLIGHT_RC=0
```

READ_SKILL: Python測試實務
READ_SKILL: UI設計與去AI味
READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: executable-continuity-controller
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: 驗證板件與DXF

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md

SUPPORTING_REFERENCE_READ: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md

## T0 Evidence Consumed

Source: #421 final T0 artifact `10598365413`, accepted HEAD `b31409e7c1736df31bd554afe4ac779d49b30aaa`.

T2-relevant characterization:
- assembly presentation registries have Bridge/test readers outside the row builder;
- current rebuild replaces multiple registry dicts;
- T2 must not retain a one-time alias to a dict that the panel later replaces;
- accepted strategy: panel-owned long-lived dict identity, rebuilt with `clear()/update()` or equivalent identity-preserving mutation;
- legacy Bridge attributes may point at those same long-lived registries;
- BoxBody late physical-piece registry remains T3/T4 scope and is not migrated in T2;
- recursive wheel behavior covers `<MouseWheel>`, `<Button-4>`, `<Button-5>`.

## T2 RED Contract

Required production owner:
- `phase6_assembly_panel.py`

Panel must own:
- host/canvas/scrollbar/content construction
- top-level row and synthetic Door/BasePlate group builders
- top-level/synthetic-child visibility BooleanVars
- formed/blank/corner StringVars
- collapse/detail registries + stashes
- recursive wheel binding and scroll routing
- identity-preserving registry rebuild

Forbidden:
- BoxBody late piece migration
- Final Scene port rewiring
- new non-Tk visibility store
- app/self service bag
- display-mode read
- manufacturing solve / project mutation

## State

```text
STATE=RED
HEAD=cb7ae0d906e52d286e740e5c8fb984c40728be83
RUN_ID=RUN_NOT_CREATED
NEXT_ACTION=Add T2 requirement RED tests and focused Xvfb workflow; production panel module must still be absent.
```


## RED / GREEN Evidence

### Valid requirement RED

- RUN `35487634133` @ `e0c631a96e08795c55fd7dd1d74cd09564a0a4cd`: SUCCESS
- `KNOWLEDGE_PREFLIGHT_RC=0`
- `T2_SCOPE_EXTERNAL_DRIFT=0`
- pytest/Xvfb: `16 failed in 0.92s`
- `T2_RED_INTENDED=1`
- `T2_RED_PYTEST_RC=1`
- no collection/import/syntax harness error
- `CONFIG_INVARIANT=GREEN`

### Focused GREEN

- panel owner commit: `7c9089a948eaac895075e308f741236dfe401a2c`
- Bridge ownership rehost commit: `30150738839424fbd4376eade6b15cc7d8409cd5`
- RUN `35487745374` @ `30150738839424fbd4376eade6b15cc7d8409cd5`: SUCCESS
- focused Xvfb: `16 passed in 0.93s`
- `T2_GREEN=1`
- `LEGACY_ALIAS_STRATEGY_ASSIGNED=1`
- `LEGACY_ALIAS_SURVIVES_REBUILD=GREEN`
- `STALE_LEGACY_REGISTRY_REFERENCE=0`
- `UNGROUPED_ROW_UI_PARITY=GREEN`
- `SYNTHETIC_GROUP_UI_PARITY=GREEN`
- `WHEEL_BASE_ROW_COVERAGE=GREEN`
- `PANEL_BRIDGE_IMPORTS=0`
- `PANEL_APP_SERVICE_BAG=0`
- `PANEL_DISPLAY_MODE_REFS=0`
- `PANEL_MANUFACTURING_SOLVE=0`
- `PANEL_PROJECT_MUTATION=0`
- `PANEL_BOX_PIECE_MIGRATION=0`
- `CONFIG_INVARIANT=GREEN`

### Legacy Assembly regression GREEN

- closing qualification precursor RUN `35487820074` @ `8e0fa207a1aef624e0d0e12240801fedc24a79fb`: SUCCESS
- focused T2 Xvfb: `16 passed in 0.86s`
- legacy #376/#385/#386/layout: `21 passed / 1 skipped`
- `LEGACY_ASSEMBLY_REGRESSIONS=GREEN`
- `CONFIG_INVARIANT=GREEN`
- the single skip is retained as an explicit pytest SKIP, not counted as PASS.

## Accepted T2 Ownership

- `phase6_assembly_panel.py` owns Assembly Parts host/canvas/scrollbar/content, top-level/synthetic row widgets, visibility/text Tk vars, collapse/detail registries and recursive wheel binding.
- Bridge legacy registry attributes alias the panel's long-lived dict objects.
- rebuild mutates registry dicts in place; no one-time alias + dict replacement.
- Bridge remains the action seam for display-mode-aware visibility updates.
- render-time BoxBody physical-piece rows/registries remain Bridge-owned for later Phase 5 scope.
- Final Scene/manufacturing/project authorities are unchanged.

## Acceptance State

```text
STATE=GREEN
TESTED_IMPLEMENTATION_HEAD=30150738839424fbd4376eade6b15cc7d8409cd5
LEGACY_REGRESSION_HEAD=8e0fa207a1aef624e0d0e12240801fedc24a79fb
RUN_ID=35487820074
NEXT_ACTION=Run exact-head closing qualification/finalization proof; no further production changes.
```
