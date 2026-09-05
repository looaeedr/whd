# Phase6 Core Fold / Dimensions / Project File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Correct core-based folding and retain ownership, replace coordinate axes with dimensions, reduce initial 3D redraw work, and add all-in-one `.p6fold` save/load.

**Architecture:** Manufacturing returns scene/material plus normalized BEND guides. The bridge folds against semantic core segments and conditionally applies each fold according to guide coverage. Project persistence serializes the complete Phase6 snapshot and diagnostics, while GUI startup can restore it from a `.p6fold` argv path.

**Tech Stack:** Python, Tkinter, Matplotlib 3D, Shapely, ezdxf, pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-phase6-core-fold-dimensions-project-file-design.md`

## Global Constraints
- Do not modify `fold_designer_original.py`.
- Preserve authoritative `PartRenderData.scene/material` ownership.
- Tail stays native orientation, no mirror.
- TDD for every behavior change.

---

### Task 1: Semantic core + BEND ownership
**Files:** modify `ae_engine/manufacturing_api.py`, `fold_designer_bridge.py`; test `tests/test_phase6_core_fold_ownership.py`.
- [ ] Add failing tests proving tail Y core is `endcap_d_core`, head/tail core span stays 244, and a y=16 fold applies only inside the final BEND span while the retained shoulder still receives the next y=41 fold.
- [ ] Add immutable `FoldGuide` data and `PartRenderData.fold_guides` derived from final BEND lines.
- [ ] Make profile geometry choose semantic core and make point mapping conditionally enable individual folds from guides.
- [ ] Split tessellation at guide span endpoints; route true CUTTING mesh through guide-aware mapping.
- [ ] Run targeted tests.

### Task 2: 3D operator view + startup performance
**Files:** modify `fold_designer_bridge.py`; test `tests/test_phase6_3d_operator_view.py`.
- [ ] Add failing tests for axis-off configuration, door finished W/H labels, stable initial camera, no root text-scale apply during Phase6 init, and coalesced first visible render.
- [ ] Hide coordinate axes and draw W/H dimension annotations plus fold-size summary using finished operator dimensions.
- [ ] Set initial view to a W-horizontal/H-vertical orientation without overriding user view after interaction.
- [ ] Reuse the existing text-scale controller factor without rescanning the root widget tree.
- [ ] Coalesce automatic initial/configure draws without changing manual refresh semantics.
- [ ] Run targeted tests.

### Task 3: All-in-one `.p6fold` project
**Files:** create `phase6_project_file.py`; modify `fold_designer_bridge.py`, `gui.py`; test `tests/test_phase6_project_file.py`.
- [ ] Add failing tests for UTF-8 `.p6fold` round trip, all-part snapshot coverage, main-GUI restore, argv open path and Windows HKCU association command generation.
- [ ] Implement schema validation/read/write helpers and Windows association helper.
- [ ] Save all parts in one file: settings, corner state, workspace, part/face features, indicator state and each available part's final scene/material diagnostic.
- [ ] Restore the project into main GUI state and auto-open Phase6 at saved active part.
- [ ] Make the existing `存檔` button save `.p6fold` instead of per-part diagnostic JSON.
- [ ] Run targeted tests.

### Task 4: Full verification and delivery
- [ ] Run full pytest suite and py_compile.
- [ ] Verify `fold_designer_original.py` SHA against input package.
- [ ] Create clean ZIP and patch, unzip delivery ZIP, rerun full tests and py_compile.
