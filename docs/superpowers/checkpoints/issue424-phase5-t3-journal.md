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
REQUIRED_REFERENCES=8
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
