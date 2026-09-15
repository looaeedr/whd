# Shared 2D/3D Assembly & Finished Dimensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make 2D and 3D share one authoritative design/manufacturing state for FW, assembly type, end-cap corner parameters, optional parts, and finished dimensions, with manufacturing geometry rebuilt only when the state changes.

**Architecture:** Keep AE/FinalScene as the only manufacturing geometry source. 2D renders the FinalScene directly; 3D folds the same FinalScene and measures finished outside envelopes. Add cabinet-level assembly type to the shared Phase6 snapshot/project state; derive end-cap top CornerType and box-body finished height from it while preserving FW as a global frame-width dimension rather than redistributing it into arbitrary fold segments.

**Tech Stack:** Python, Tkinter, Matplotlib, Shapely, pytest, ezdxf.

**Spec:** User-approved conversation design + `04_WHD鈑金展開幾何引擎規範.md`.

## Global Constraints
- FW means frame width / 邊框寬度; it is not a Fold Chain segment identity.
- 2D and 3D must not maintain duplicate CornerType or dimension formulas.
- Manufacturing geometry / FinalScene is generated once per changed design revision and reused by 2D, 3D, and DXF export.
- 3D single-part dimensions are folded finished outside-envelope dimensions; complete assembly dimensions remain configured W/H/D.
- Box-body finished height depends on head/tail assembly outside occupancy: INSERT=0T; OVERLAY=1T; INSERT_OVERLAY=1T.
- End-cap bottom defaults remain CROSS / extra_cut and do not change cabinet finished-height occupancy.
- Box body cannot be removed; optional parts can be selected and removed without entering their edit page.
- Tail keeps native orientation.

---

### Task 1: FW and Assembly Semantics
**Files:** `fold_designer_bridge.py`, `ae_engine/sheetmetal_geometry.py`, tests.
- [x] Write failing tests proving FW=25 never becomes 41 in linked arbitrary end-cap profiles.
- [x] Write failing tests for INSERT/OVERLAY/INSERT_OVERLAY occupancy and box-body finished height.
- [x] Implement shared assembly helpers and linked end-cap derivation preserving FW semantics.
- [x] Run targeted tests.

### Task 2: Shared Project/GUI State
**Files:** `fold_designer_bridge.py`, `phase6_project_file.py`, `gui.py`, tests.
- [x] Write failing tests for assembly_type project migration/save and shared 2D state.
- [x] Add assembly_type to snapshot/workspace and migrate old projects from existing end-cap top CornerType.
- [x] Add box-body assembly selector to Phase6 UI and end-cap parameter staging.
- [x] Ensure confirm writes the same state back to main 2D.
- [x] Run targeted tests.

### Task 3: Single FinalScene Revision Cache
**Files:** `gui.py`, `fold_designer_bridge.py`, `ae_engine/manufacturing_api.py`, tests.
- [x] Write failing test that unchanged 2D/3D requests reuse the same FinalScene/render-data object/revision.
- [x] Implement design revision invalidation and render-data cache at the bridge/main GUI boundary.
- [x] Ensure DXF export consumes the same scene rather than regenerating manufacturing logic.
- [x] Run targeted tests.

### Task 4: Finished Outside 3D Dimensions
**Files:** `fold_designer_bridge.py`, tests.
- [x] Write failing tests for box-body single-part H=600/598/596 according to assembly occupancy.
- [x] Write failing test that door remains 335x535 finished outside dimensions.
- [x] Implement folded mesh outside-envelope measurement/semantic dimension labels from shared data.
- [x] Run targeted tests.

### Task 5: Selection-Level Part Removal
**Files:** `fold_designer_bridge.py`, tests.
- [x] Write failing GUI-light test for selecting an optional part and deleting without activation.
- [x] Separate part selection from edit activation for delete action and keyboard Delete.
- [x] Preserve transactional cancel/confirm semantics and re-add stash behavior.
- [x] Run targeted tests.

### Task 6: Full Regression & Delivery
- [x] Run uploaded `自訂(1).p6fold` smoke.
- [x] Run full Xvfb pytest suite.
- [x] Run `py_compile`.
- [x] Verify `fold_designer_original.py` SHA unchanged.
- [x] Create clean ZIP/PATCH, extract ZIP, rerun full suite + smoke.
