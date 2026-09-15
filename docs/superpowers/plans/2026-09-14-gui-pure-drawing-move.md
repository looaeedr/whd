---
whd_doc_role: HISTORICAL
whd_contract: implementation-plan-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# GUI Pure Drawing Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the first proven-safe drawing/helper seams out of root `gui.py` without changing any observable behavior or authoritative state/geometry ownership.

**Architecture:** Root `gui.py` remains the application orchestrator and compatibility surface. A new one-way dependency `gui.py -> gui_modules.drawing -> ae_engine.sheetmetal_drawing` owns only pure preview coordinate helpers and Canvas presentation of an already-authoritative `DrawingScene`; it never imports `gui.py`, never owns state, and never reconstructs manufacturing geometry.

**Tech Stack:** Python 3.12, Tkinter Canvas-compatible call surface, pytest, GitHub Actions/Xvfb where required by project gates.

**Spec:** GitHub #203 master + #207 T3 ticket; accepted architecture evidence is #204/T0, #205/T1, and #206/T2. T3 preflight evidence is `.scratch/issue207/preflight-evidence.md`.

## Global Constraints

- Production baseline is `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687` unless a remote refetch proves drift before implementation.
- Strict Move-Only: signatures, algorithms, return values, coordinates, Canvas styles/tags/layers, state ownership, geometry, DXF, persistence, and operator workflow must not change.
- No `gui_modules -> gui.py` import is allowed.
- No Event Bus, Store, 2D authoritative state, 3D authoritative state, or second render/geometry source may be introduced.
- `gui.py` must keep compatibility names for moved symbols during staged migration.
- `_project_toolbar_presentation` stays in `gui.py` for #208/T4 because it is presentation responsibility, not drawing responsibility.
- HOLD symbols `layout_reference_overlay_rects`, `_YMirroredPreviewTransform`, and `render_structural_result` remain untouched.
- The #206 characterization test must be carried forward unchanged before production movement and must remain GREEN after movement.
- Validation/test expected values remain one-way correctness evidence only.

---

### Task 1: Re-establish the characterization contract on the fresh T3 branch

**Files:**
- Create: `tests/test_issue206_gui_modularization_characterization.py`
- Verify: `gui.py`

**Interfaces:**
- Consumes: current root `gui` compatibility names `_corner_preview_canvas_point`, `_corner_preview_flip_y_for_target`, `_project_toolbar_presentation`, `render_drawing_scene`.
- Produces: the exact 13-case characterization contract accepted by #206.

- [ ] **Step 1: Copy the accepted #206 characterization test byte-for-byte into the T3 branch.**

Source authority is the closed #206 branch `test/issue206-characterization-20260914`, file `tests/test_issue206_gui_modularization_characterization.py`.

- [ ] **Step 2: Run the characterization test before moving production code.**

Run:
```bash
pytest -q tests/test_issue206_gui_modularization_characterization.py
```
Expected: `13 passed`, `0 failed`.

- [ ] **Step 3: Verify repository invariants around the test.**

Run before/after hashes for `config.ini` and all `基準檔/**`; require exact equality and `git diff --exit-code -- config.ini '基準檔'`.

- [ ] **Step 4: Commit only the permanent characterization test.**

Commit message:
```text
test(issue207): carry forward gui extraction characterization
```

### Task 2: Create the drawing module with exact moved implementations

**Files:**
- Create: `gui_modules/__init__.py`
- Create: `gui_modules/drawing.py`
- Modify: `gui.py` only after module files exist
- Test: `tests/test_issue206_gui_modularization_characterization.py`

**Interfaces:**
- `gui_modules.drawing._corner_preview_canvas_point(point, *, ox, oy, scale, span, flip_y=True)` returns `(canvas_x, canvas_y)` exactly as current `gui.py`.
- `gui_modules.drawing._corner_preview_flip_y_for_target(target_key)` returns the current boolean orientation rule exactly.
- `gui_modules.drawing.render_drawing_scene(canvas, scene, transform, *, skip_layers=())` emits the same Canvas calls and mutates neither `scene` nor authoritative state.
- `gui.py` re-exports all three names by importing them from `gui_modules.drawing`.

- [ ] **Step 1: Create `gui_modules/__init__.py` as an intentionally minimal package marker.**

Content:
```python
"""Presentation-only GUI helper modules; authoritative application state stays in gui.py/controllers."""
```

- [ ] **Step 2: Create `gui_modules/drawing.py` with exact existing implementations.**

Required imports:
```python
from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive
```

Copy the current bodies of `_corner_preview_canvas_point`, `_corner_preview_flip_y_for_target`, and `render_drawing_scene` without algorithmic or stylistic edits.

- [ ] **Step 3: In `gui.py`, replace the two corner helper definitions and `render_drawing_scene` definition with one-way imports/re-exports.**

Add:
```python
from gui_modules.drawing import (
    _corner_preview_canvas_point,
    _corner_preview_flip_y_for_target,
    render_drawing_scene,
)
```

Do not move `_project_toolbar_presentation`. Do not touch HOLD symbols.

- [ ] **Step 4: Remove only imports from `gui.py` that become truly unused due to this exact move.**

Before removing `PolylinePrimitive`, `LinePrimitive`, or `CirclePrimitive` from the `ae_engine.sheetmetal_drawing` import block, prove repo/file-local remaining usage. If any remains outside the moved function, retain it. No cleanup-by-assumption.

- [ ] **Step 5: Run characterization immediately.**

Run:
```bash
pytest -q tests/test_issue206_gui_modularization_characterization.py
```
Expected: `13 passed`, `0 failed`.

### Task 3: Verify compatibility, import direction, and focused regressions

**Files:**
- Verify: `gui.py`
- Verify: `gui_modules/drawing.py`
- Test: existing direct regressions that call the moved seams.

**Interfaces:**
- Existing `import gui; gui.render_drawing_scene` and underscore helper accesses remain valid.
- `gui_modules.drawing` can import without importing `gui`.

- [ ] **Step 1: Import compatibility check.**

Run:
```bash
python -c "import gui; assert callable(gui._corner_preview_canvas_point); assert callable(gui._corner_preview_flip_y_for_target); assert callable(gui.render_drawing_scene)"
```

- [ ] **Step 2: Import-direction check.**

Run:
```bash
python -c "import sys, gui_modules.drawing; assert 'gui' not in sys.modules"
```
Run this in a fresh Python process before any `gui` import.

- [ ] **Step 3: Run focused existing regressions for the moved contracts.**

At minimum include:
```bash
pytest -q \
  tests/test_issue206_gui_modularization_characterization.py \
  tests/test_phase6_ui_state_regressions.py \
  tests/test_phase6_3d_single_source_renderer.py
```
If an existing file requires Xvfb, run that scope under the project Xvfb harness rather than weakening/skipping the test.

- [ ] **Step 4: Run source scans.**

Require:
- no `from gui` / `import gui` inside `gui_modules/**`;
- no duplicate definitions of the moved functions in `gui.py`;
- `_project_toolbar_presentation` remains defined in `gui.py`;
- HOLD symbols remain unchanged and defined in `gui.py`.

### Task 4: Remote acceptance and cleanup

**Files:**
- Temporary: `.github/workflows/issue207-t3-move-only.yml`
- Evidence: `.scratch/issue207/**`

**Interfaces:**
- Produces terminal remote QA evidence tied to one exact tested head SHA.

- [ ] **Step 1: Run Phase6 preflight with every changed production/test/module file.**

Changed-file scope must include:
```text
gui.py
gui_modules/__init__.py
gui_modules/drawing.py
tests/test_issue206_gui_modularization_characterization.py
```

- [ ] **Step 2: Run remote focused/import/source/invariant gates and actively poll to terminal.**

Lock `run_id + head_sha`. Capture exact pass/fail/skip counts and `config.ini` / `基準檔/**` invariants.

- [ ] **Step 3: If GREEN, remove the temporary workflow.**

- [ ] **Step 4: Compare tested head -> cleaned head.**

Only temporary workflow removal and durable evidence/checkpoint updates may appear after the tested head.

- [ ] **Step 5: Compare production baseline -> cleaned head.**

Allowed T3 functional diff is limited to:
```text
gui.py
gui_modules/__init__.py
gui_modules/drawing.py
tests/test_issue206_gui_modularization_characterization.py
```
plus `.scratch/issue207/**` evidence. Any geometry/DXF/config/schema/unrelated source drift is FAIL.

- [ ] **Step 6: Transfer to total-control review and close #207 only after all evidence is terminal GREEN.**

## Self-Review

- Spec coverage: T3 covers only first pure drawing/helper move; presentation remains T4; state/panels/project/render extraction remain later tickets.
- Placeholder scan: no TBD/TODO/implementation-later placeholders.
- Interface consistency: moved function names/signatures exactly match current `gui.py`; root compatibility names remain available.
- Scope check: no HOLD candidate, state owner, geometry authority, project persistence, or UI redesign is included.
