# Reference UI and Undo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make right-click the sole nine-anchor selector, attach compact reference controls to the active crosshair, add 50-step Undo/Ctrl+Z, and move all tests into `tests/`.

**Architecture:** Keep geometry/reference calculations unchanged. Add editor-local snapshot history around committed user actions, and keep transient cancel snapshots separate from Undo history. Reuse existing floating overlay placement but make the reference controls a single compact group driven by active crosshair geometry.

**Tech Stack:** Python, Tkinter, pytest, Shapely.

## Global Constraints
- Right-click is the only reference-anchor selector.
- Keep nine existing anchors and existing Finished Boundary math.
- Undo depth is capped at 50.
- `Esc` behavior remains transaction-aware.
- All `test_*.py` files live under `tests/`.

---

### Task 1: Test layout migration
**Files:** move root `test_*.py` to `tests/`.
- [ ] Move all tests without changing names.
- [ ] Run `pytest -q` and verify baseline still passes.

### Task 2: Undo history engine
**Files:** modify `gui.py`; test `tests/test_unified_hole_editor_undo.py`.
- [ ] Write failing tests for snapshot push, 50-step cap, and undo restore semantics.
- [ ] Implement editor-local history helper/state.
- [ ] Wire committed insert/process/rotation/reference/round-pattern changes to history.
- [ ] Bind `Ctrl+Z` and add `↶ 回上一步` button.

### Task 3: Right-click-only anchor UI
**Files:** modify `gui.py`; test `tests/test_unified_hole_reference_ui.py`.
- [ ] Write failing source/interaction tests that anchor combobox is absent and context-menu anchor commands remain.
- [ ] Remove anchor combobox/list UI while retaining `reference_anchor` state internally.
- [ ] Ensure right-click anchor change refreshes reference math and pushes Undo state.

### Task 4: Floating compact reference controls
**Files:** modify `gui.py`; test `tests/test_unified_hole_reference_ui.py`.
- [ ] Write failing tests for 12-13pt fields and confirm/cancel in floating overlay.
- [ ] Re-layout border/neighbor fields and confirm/cancel as one crosshair-following group.
- [ ] Preserve footprint/overlay collision avoidance.

### Task 5: Fresh verification
- [ ] Run `pytest -q`.
- [ ] Run `python -m py_compile` for core modules.
- [ ] Run Tk/Xvfb smoke test for editor, right-click anchor menu, Undo button/Ctrl+Z, and floating controls.
