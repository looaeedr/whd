# Phase 5 / Issue #424 T3 Journal

## Authority

- MASTER_ID: `#413`
- TASK_ID: `#424 / T3`
- TARGET_X: `cleanup/2d-3d-sync`
- FROZEN_X_BASE_SHA: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- ACCEPTED_PREDECESSOR: `#423 @ b3d798c1a1d8ec3ad690948bee833d7c174df122`
- WORK_ORDER_BRANCH: `refactor/issue413-phase5-assembly-presentation-20260920`
- Requirement Authority: Phase 5 v1.7 accepted master #413
- T3 scope: render-time BoxBody physical-piece presentation only.

## Knowledge Preflight

Changed-file preflight on accepted predecessor. Remote changed-file preflight later expanded the route to include `截角資料入口收斂` plus its 2D-entry and DM7 references; those authorities were fresh-read before retrying RED:

```text
REQUIRED_SKILLS=9
REQUIRED_REFERENCES=10
KNOWLEDGE_PREFLIGHT_RC=0
```

READ_SKILL: Python測試實務
READ_SKILL: 截角資料入口收斂
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
READ_REFERENCE: 個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
SUPPORTING_REFERENCE_READ: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md

## Accepted T3 Characterization

Current owner chain at predecessor:
```text
Phase6FinalSceneViewAdapter.query_assembly_render_data()
→ part.part_key == "box_body"
→ FinalSceneDependencies.refresh_box_body_piece_info
→ Bridge _phase6_refresh_box_body_piece_info_rows(self, render_data)
→ _phase6_box_body_piece_dimension_projections(render_data)
→ render_data.pieces
```

Current semantic contracts:
- piece key/order source is render-time `render_data.pieces`;
- topology/DM7 does not pre-create BoxBody piece presentation rows;
- rows rebuild only when projected key tuple changes;
- every refresh rewrites formed/blank/corner StringVars even when rows are reused;
- number formatting uses `phase6_settings_panel.setting_number_text`;
- corner text uses existing `_phase6_render_data_corner_dimension_text`;
- projected key with no matching raw role uses exact `截角尺寸：無`;
- any non-empty projection overwrites logical `box_body` texts with:
  - `成形尺寸：見下方各片`
  - `展開料：見下方各片`
  - `截角尺寸：見下方各片`
- current piece visibility is preserved through `_phase6_box_body_piece_visibility_stash`;
- piece detail/collapse state uses `_phase6_box_body_piece_detail_open_stash`;
- late piece rows receive recursive MouseWheel/Button-4/Button-5 binding.

## T3 Design Boundary

Panel may consume narrow presentation callables:
- `label_for(key)`
- `number_text(value)`
- `corner_text_for_render_data(render_data)`

Panel must not import SettingsPanel or manufacturing/FinalScene owners for formatting/geometry authority.

Bridge remains a thin compatibility/action seam only. Final Scene callback timing/order remains unchanged.

## State

```text
STATE=RED
HEAD=e6465a6d17600a92a98ec613744ce53065f7db05
RUN_ID=35488144492
RUN_STATUS=PREFLIGHT_HARNESS_FAILURE
EVIDENCE=Remote Preflight stopped before pytest because 截角資料入口收斂 and two required references were not yet recorded; this run is NOT requirement RED evidence.
NEXT_ACTION=Retry focused T3 requirement RED after complete Preflight evidence; require assertion RED with no collection/import/syntax error.
```


## RED / GREEN Evidence

### Preflight harness classification

- RUN `35488144492` @ `e6465a6d17600a92a98ec613744ce53065f7db05`: `PREFLIGHT_HARNESS_FAILURE`.
- Remote changed-file Preflight required `截角資料入口收斂`, `08_WHD截角資料與2D入口收斂規則.md`, and `dm7_part_navigation_pitfalls.md`.
- Pytest did not run; this run is NOT requirement RED evidence.
- Missing authorities were fresh-read and added before retry.

### Valid requirement RED

- RUN `35488238799` @ `7d9766aa636b7e0ae0e2fee7f09865cd5ab9ab92`: SUCCESS.
- `KNOWLEDGE_PREFLIGHT_RC=0`.
- `T3_SCOPE_EXTERNAL_DRIFT=0`.
- focused Xvfb: `12 failed / 1 passed`.
- `T3_RED_INTENDED=1`.
- `T3_RED_PYTEST_RC=1`.
- no collection/import/syntax harness error.
- legacy BoxBody Assembly regression lane remained `21 passed / 1 skipped`.
- `CONFIG_INVARIANT=GREEN`.

### Minimal GREEN implementation

- panel late-piece owner commit: `29a6ce43f9dae4cccf2c3e4cded75fcac7ae6fdc`.
- Bridge thin-delegate commit: `3c888a622cbda3f63f28336b00d04dfc33a8ba57`.
- first GREEN qualification RUN `35488369693` exposed one implementation regression:
  `_phase6_query_assembly_render_data` compatibility delegate was accidentally removed by an overly broad patch boundary.
- regression was not classified as stale test debt.
- compatibility delegate was restored unchanged in `08ee6129f1353245affd1f803a41a04e370e79ce`.

### Accepted GREEN

- RUN `35488437899` @ `08ee6129f1353245affd1f803a41a04e370e79ce`: SUCCESS.
- focused Xvfb: `13 passed`.
- `T3_GREEN=1`.
- `BOX_PIECE_ROW_SOURCE_RENDER_DATA_PIECES=true`.
- `BOX_PIECE_ROW_SOURCE_SWITCH_TO_DM7=0`.
- `BOX_PIECE_ROW_CREATION_MOVED_TO_TOPOLOGY_TIME=0`.
- `BOX_PIECE_ROW_CREATION_TIMING_PARITY=GREEN`.
- `BOX_PIECE_ROW_ORDER_PARITY=GREEN`.
- `BOX_PIECE_VAR_OWNER_IS_PANEL=true`.
- `BOX_PIECE_VISIBILITY_STASH_PARITY=GREEN`.
- `LATE_PIECE_WHEEL_COVERAGE=GREEN`.
- `BOX_PIECE_TEXT_REWRITTEN_ON_EVERY_REFRESH=true`.
- `BOX_PIECE_TEXT_REFRESH_WITHOUT_ROW_REBUILD_PARITY=GREEN`.
- `BOX_BODY_LOGICAL_TEXT_SUMMARY_PARITY=GREEN`.
- `BOX_PIECE_FORMED_TEXT_FORMAT_PARITY=GREEN`.
- `BOX_PIECE_BLANK_TEXT_FORMAT_PARITY=GREEN`.
- `BOX_PIECE_CORNER_TEXT_FORMAT_PARITY=GREEN`.
- `BOX_PIECE_MISSING_ROLE_CORNER_FALLBACK=截角尺寸：無`.
- `PANEL_BRIDGE_IMPORTS=0`.
- `PANEL_DM7_IMPORTS=0`.
- `PANEL_SETTINGS_IMPORTS=0`.
- `PANEL_DISPLAY_MODE_REFS=0`.
- `PANEL_MANUFACTURING_SOLVE=0`.
- `PANEL_PROJECT_MUTATION=0`.
- legacy BoxBody Assembly lane: `21 passed / 1 skipped`.
- `LEGACY_BOX_PIECE_REGRESSIONS=GREEN`.
- `CONFIG_INVARIANT=GREEN`.
- the single skip remains an explicit SKIP and is not counted as PASS.

## Accepted T3 Ownership

- `Phase6AssemblyPanel.refresh_box_body_piece_info(...)` owns late piece row create/update.
- piece row source remains render-time `render_data.pieces` through T1 `project_box_body_piece_rows`.
- piece visibility/text/widget registries and visibility/open stashes are panel-owned long-lived dicts.
- Bridge legacy piece registries alias those panel dicts exactly once.
- Bridge `_phase6_refresh_box_body_piece_info_rows` is a narrow delegate that injects existing label/number/corner formatters.
- Final Scene callback position remains unchanged and executes only for the resolved logical `box_body` part.
- no DM7 source substitution, topology-time precreation, formatting redesign, visibility-policy change, manufacturing solve, or project mutation was introduced.

## Acceptance State

```text
STATE=GREEN
TESTED_IMPLEMENTATION_HEAD=08ee6129f1353245affd1f803a41a04e370e79ce
RUN_ID=35488437899
NEXT_ACTION=Run exact-head closing qualification/finalization proof with no further production changes.
```
