# #207 / T3 Checkpoint

- Parent: #203
- Depends on: #206 CLOSED / completed
- Current role: T3 實作者
- Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
- Branch: `refactor/issue207-pure-drawing-move-20260914`
- Plan: `docs/superpowers/plans/2026-09-14-gui-pure-drawing-move.md`

## Scope
Move-only extraction of:
- `_corner_preview_canvas_point`
- `_corner_preview_flip_y_for_target`
- `render_drawing_scene`

Deferred to T4:
- `_project_toolbar_presentation`

HOLD / untouched:
- `layout_reference_overlay_rects`
- `_YMirroredPreviewTransform`
- `render_structural_result`

## Completed
- production refetched; baseline unchanged;
- fresh T3 branch created from exact production baseline;
- T3 process/architecture preflight sources reread;
- implementation plan written and self-reviewed;
- compatibility strategy fixed: `gui.py` re-exports moved names from `gui_modules.drawing`.

## Pending
1. remote changed-file Phase6 preflight for planned T3 files;
2. carry #206 13-case characterization file unchanged;
3. prove baseline characterization GREEN on T3 branch;
4. create `gui_modules/__init__.py` and `gui_modules/drawing.py`;
5. replace only the three bodies in `gui.py` with imports/re-exports;
6. focused/import/source/invariant remote QA;
7. cleanup temporary workflow and drift audit;
8. total-control review / close T3 only on terminal GREEN.
