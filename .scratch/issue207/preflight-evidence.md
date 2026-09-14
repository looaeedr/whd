# #207 T3 Preflight Evidence

[當前角色：T3 實作者]

Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
Branch: `refactor/issue207-pure-drawing-move-20260914`

READ_SKILL: 程式碼庫設計
READ_SKILL: Python測試實務
READ_SKILL: tdd
READ_SKILL: UI設計與去AI味
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_PROCESS: AGENTS.md Phase6 Knowledge Preflight / Branch-First / dispatch / issue closure
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md

Inherited accepted evidence:
- #204/T0 dependency inventory run `34806853791`;
- #205/T1 state ownership + SAFE/HOLD classification run `34807186543`;
- #206/T2 characterization run `34807475278`: 13 PASS / 0 FAIL.

T3 constraints:
- strict Move-Only; no signature/algorithm/value/style/state/geometry behavior changes;
- module split is by responsibility, not line count;
- `gui_modules` must not import `gui.py`;
- no second Store/Event Bus/2D state/3D state/render authority;
- `gui.py` remains application orchestrator and compatibility surface;
- only `_corner_preview_canvas_point`, `_corner_preview_flip_y_for_target`, and `render_drawing_scene` move in T3;
- `_project_toolbar_presentation` remains for #208/T4 presentation extraction;
- `layout_reference_overlay_rects`, `_YMirroredPreviewTransform`, and `render_structural_result` remain HOLD and untouched;
- T2 characterization test is carried forward unchanged before extraction;
- validation evidence cannot become production calculation authority.
