# Phase6 3D Single-Source Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make Phase6 3D a pure consumer of authoritative manufacturing render geometry, with no baseline parsing, CornerType building, hole classification, or CUTTING polygon reconstruction inside the 3D bridge.

**Architecture:** `PartSpec -> manufacturing_api.build_part_render_data()` owns all manufacturing work and returns `PartRenderData(scene, material)`. `material` is the completed sheet material including outer shape/corner reliefs/through holes; `scene` carries final BEND/MARKING/BLIND_HOLE operations. Phase6 3D only triangulates/folds `material` and projects operation graphics from the same scene.

**Tech Stack:** Python, Tkinter, Shapely, Matplotlib, pytest.

**Spec:** Approved in chat on 2026-08-21: AE/2D final geometry is the only manufacturing source; 3D only folds and renders it.

## Global Constraints
- 3D must not read baseline DXF.
- 3D must not build or resolve CornerType geometry.
- 3D must not classify CUTTING vs MARKING/BLIND_HOLE.
- 3D must not polygonize CUTTING linework to rediscover holes/material.
- 3D may triangulate already-final `material`, map it through folds, and project final BEND/MARKING.
- `fold_designer_original.py` remains unchanged.

---

### Task 1: Lock the architectural boundary
- [x] Add source/runtime guards proving the bridge has no second manufacturing builders/parsers.
- [x] Verify the guards fail against the previous second-engine implementation.

### Task 2: Add authoritative manufacturing render boundary
- [x] Keep `manufacturing_api.build_part_scene(spec, context)` as the existing final-operation scene boundary.
- [x] Add `PartRenderData(scene, material)` and `manufacturing_api.build_part_render_data()`.
- [x] Resolve material at the manufacturing boundary, including through CUTTING features while preserving MARKING/BLIND_HOLE.
- [x] Ignore duplicate mapped legacy structural outlines rather than interpreting them as giant holes.

### Task 3: Make 3D a pure renderer
- [x] GUI converts current draft settings to PartSpec and asks manufacturing API for `PartRenderData`.
- [x] Cache identical render requests in GUI to avoid repeated baseline/manufacturing work on redraw.
- [x] Remove bridge baseline merge/alignment/hole parser/CornerType manufacturing helpers.
- [x] Remove bridge CUTTING polygonize/material-reconstruction helpers entirely.
- [x] Render path consumes only `render_data.material` + `render_data.scene`.
- [x] Derive fold positions from final BEND lines and fold material; no CornerType lookup occurs in render path.

### Task 4: Regression and package
- [x] Migrate old 3D tests from the removed second-engine contract to the single-source contract.
- [x] Verify synthetic Door: MARKING stays material, real CUTTING hole is absent at the authoritative mapped position.
- [x] Run full pytest under xvfb and py_compile.
- [x] Confirm original renderer SHA unchanged.
- [x] Package and reverify from ZIP.
