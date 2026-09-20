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
