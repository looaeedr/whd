# #207 / T3 Checkpoint

- Parent: #203
- Depends on: #206 CLOSED / completed
- Current role: 總控審查
- Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
- Branch: `refactor/issue207-pure-drawing-move-20260914`
- Plan: `docs/superpowers/plans/2026-09-14-gui-pure-drawing-move.md`

## Scope completed
Move-only extraction of:
- `_corner_preview_canvas_point`
- `_corner_preview_flip_y_for_target`
- `render_drawing_scene`

Deferred to T4 and unchanged:
- `_project_toolbar_presentation`

HOLD / untouched:
- `layout_reference_overlay_rects`
- `_YMirroredPreviewTransform`
- `render_structural_result`

## Terminal acceptance
- Final Acceptance run: `34808093104`
- Tested head: `8c1c036bb4f092970514b4b343408f85d365e983`
- Result: SUCCESS
- Xvfb focused/regression: `71 PASS / 0 FAIL` (120 font/syntax warnings only)
- Phase6 changed-file preflight: GREEN
- exact Move-Only source contract: GREEN
- compatibility re-export from `gui.py`: GREEN
- `gui_modules` → `gui.py` import-cycle guard: GREEN
- allowed-diff guard: GREEN
- `config.ini` invariant: GREEN
- protected `基準檔/**` invariant: GREEN
- temporary T3 workflows: removed from current branch

## Cleaned branch audit
Production baseline → current T3 branch contains only:
- `.scratch/issue207-t3-checkpoint.md`
- `.scratch/issue207/preflight-evidence.md`
- `docs/superpowers/plans/2026-09-14-gui-pure-drawing-move.md`
- `gui.py`
- `gui_modules/__init__.py`
- `gui_modules/drawing.py`
- `tests/test_issue206_gui_modularization_characterization.py`

No unrelated production source, geometry, DXF baseline, config, project schema, or temporary workflow drift remains.

## Handoff
#207/T3 is terminal GREEN and ready to close. #208/T4 must start on a fresh branch from this cleaned accepted lineage (not by mutating the T3 branch) so the accepted Move-Only changes are preserved without integrating to `cleanup/2d-3d-sync` before final combined acceptance.
