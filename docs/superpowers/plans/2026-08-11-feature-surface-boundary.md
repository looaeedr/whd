# Feature Surface Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make hole placement generic to any valid sheet-metal surface and reject any hole whose full footprint leaves its owning polygon.

**Architecture:** `FeatureSurface` owns a polygon in feature-world coordinates. Feature placement remains anchor-based; validation converts the actual circle/rectangle footprint to geometry and uses polygon containment. GUI consumes the validation API and never stores Canvas pixels.

**Tech Stack:** Python 3.11, dataclasses, Shapely, Tkinter, existing `sheetmetal_features.py` / `sheetmetal_geometry.py`.

## Global Constraints
- Any valid structural outline may become a `FeatureSurface`; no part-name allow-list in the validation engine.
- The entire feature footprint must be covered by the surface polygon; center-only checks are forbidden.
- Invalid drag keeps the last valid feature state.
- Existing head/tail legacy hole dictionaries and DXF mapping remain compatible.
- GUI pixels remain presentation-only.

---

### Task 1: Generic FeatureSurface and footprint containment
**Files:** Create tests in `test_feature_surface.py`; modify `sheetmetal_features.py`.
- [x] Write failing tests for circle/rectangle full-footprint containment, non-rectangular polygon corners, and structural-result surface creation.
- [x] Run tests and verify RED.
- [x] Add `FeatureSurface`, footprint generation, `feature_is_within_surface`, and structural-result/rect surface factories.
- [x] Run tests and verify GREEN.

### Task 2: Validated placement and drag
**Files:** Modify `test_feature_surface.py`, `sheetmetal_features.py`.
- [x] Write failing tests that invalid movement returns the last valid feature and valid movement updates anchor/offset.
- [x] Verify RED.
- [x] Add validated placement/move helpers.
- [x] Verify GREEN.

### Task 3: End-cap editor boundary integration
**Files:** Modify `gui.py`; add `test_hole_surface_gui_contract.py`.
- [x] Write failing GUI contract tests requiring FeatureSurface validation and forbidding center-only clamping as the authority.
- [x] Verify RED.
- [x] Replace end-cap click/drag boundary logic with `FeatureSurface` full-footprint validation; invalid drag remains at last valid position.
- [x] Verify targeted tests.

### Task 4: Regression verification
**Files:** Tests only.
- [x] Run full test suite.
- [x] Compile core modules.
- [x] Verify end-cap circle/rectangle near-edge rejection and DXF export of valid holes.
- [x] Audit production source for Canvas-pixel persistence and part-name branching inside FeatureSurface validation.
