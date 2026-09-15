# Axis-Paired Reference Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Group X edge + X neighbor controls together and Y edge + Y neighbor controls together while preserving crosshair-following placement, avoidance, Undo, and all existing hole-editor behavior.

**Architecture:** Keep the existing reference math unchanged. Replace the two semantic groups `edge_group` / `neighbor_group` with axis groups `x_group` / `y_group`; update the overlay layout helper so the X group follows the horizontal crosshair and the Y group follows the vertical crosshair, while the confirm/cancel panel stays on the crosshair and all controls avoid the feature footprint and one another.

**Tech Stack:** Python, Tkinter, pytest.

## Global Constraints

- Right-click remains the only nine-point reference selector.
- No reference Combobox returns.
- Reference input font stays compact at 12pt.
- Confirm/cancel remains a floating control following the active crosshair.
- Undo/Ctrl+Z and round-hole pattern behavior are unchanged.
- All tests remain under `tests/`.

---

### Task 1: Axis-paired floating layout

**Files:**
- Modify: `gui.py`
- Test: `tests/test_reference_axis_grouping.py`

**Interfaces:**
- Consumes: active crosshair canvas point, selected feature canvas bounding box, X/Y reference directions.
- Produces: `layout_axis_reference_overlay_rects(...)` returning non-overlapping rectangles for `x_group`, `y_group`, and `panel`.

- [ ] **Step 1: Write failing tests** asserting X group contains X edge/X neighbor controls, Y group contains Y edge/Y neighbor controls, and their rectangles move with the crosshair without overlapping the feature.
- [ ] **Step 2: Run targeted tests and verify RED.**
- [ ] **Step 3: Replace UI grouping and layout helper with axis-paired groups.**
- [ ] **Step 4: Run targeted tests and verify GREEN.**
- [ ] **Step 5: Run full pytest regression and py_compile.**

