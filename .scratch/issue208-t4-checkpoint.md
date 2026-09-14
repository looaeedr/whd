# #208 / T4 Checkpoint

- Parent: #203
- Depends on: #207 CLOSED / completed
- Current role: 總控審查
- Base: accepted T3 head `2c3185ca863adf0cd9861ad5e04f594185c95ced`
- Branch: `refactor/issue208-layout-presentation-20260914`
- Execution PR: #221

## Accepted slice
Move-only extraction of `_project_toolbar_presentation` into `gui_modules/layout.py`.

## Terminal acceptance
- Pre-implementation Phase6 preflight: `34824145664` GREEN
- Move implementation run: `34825034790` GREEN
- Move implementation commit: `5d8123f2d37af9b1c7f920684705cb861e5f3b8b`
- Exact-head acceptance run: `34825126767` SUCCESS
- Tested head: `b9a47841a48a408898d304e4775bae9b0b030cf8`
- Xvfb characterization/focused UI + 3D renderer regression: `71 PASS / 0 FAIL / 120 warnings` in 13.29s
- Phase6 changed-file preflight: GREEN
- exact parent-body == moved-body source contract: GREEN
- old body absent from `gui.py`; compatibility import count == 1: GREEN
- `gui_modules -> gui` import-direction guard: GREEN
- allowed T4 production diff only: GREEN
- `config.ini` invariant: GREEN
- protected `基準檔/**` invariant: GREEN

## Cleanup completed
Removed from the T4 branch after terminal acceptance:
- `.github/workflows/issue208-t4-preflight.yml`
- `.github/workflows/issue208-t4-apply-move.yml`
- `.scratch/issue208/apply_t4_move.py`
- `.scratch/issue208/validate_t4_move.py`

## Handoff
T4 is ready for cleaned-head drift audit. Acceptance evidence is anchored to tested head `b9a47841...`; cleanup commits after that head remove only temporary QA machinery/evidence scripts and do not alter accepted production implementation. If the cleaned diff contains only `gui.py`, `gui_modules/layout.py`, T4 evidence, and the T4 plan relative to accepted T3, #208 may close and #209 must branch fresh from the cleaned T4 head.
