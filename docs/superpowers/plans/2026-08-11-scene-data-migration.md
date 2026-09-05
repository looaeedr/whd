# Scene Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Remove the legacy geometry dictionary and make stretched/indicator producers return `DrawingScene` primitives directly.

**Architecture:** Introduce `SceneData(scene, params, metadata)` in `sheetmetal_drawing.py`. Baseline mapping functions append typed drawing primitives directly; exporters serialize `SceneData.scene`. Non-drawing values move to params or metadata.

**Tech Stack:** Python, dataclasses, pytest, ezdxf at serialization/baseline-reading boundary only.

## Global Constraints
- No manufacturing geometry formula changes.
- No `geom['polylines']`, `geom['lines']`, or `geom['circles']` remain in production code.
- Remove `legacy_geom_to_primitives()` when migration is complete.
- Preserve existing DXF output layers and representative entity counts.

---

### Task 1: SceneData contract
- [x] Add failing tests for `SceneData` scene/params/metadata.
- [x] Verify RED.
- [x] Implement `SceneData`.
- [x] Verify GREEN.

### Task 2: Stretched End Cap
- [x] Add regression test expecting `SceneData` and structural primitives.
- [x] Verify RED.
- [x] Replace legacy dict appends with typed primitives.
- [x] Update exporter to consume `.scene/.params`.
- [x] Verify GREEN.

### Task 3: Stretched Box Body
- [x] Add regression test expecting `SceneData` bend primitives.
- [x] Verify RED.
- [x] Replace dict appends with typed primitives.
- [x] Update consumer.
- [x] Verify GREEN.

### Task 4: Stretched Door
- [x] Add regression test expecting `SceneData` and metadata indicator layout.
- [x] Verify RED.
- [x] Replace dict appends/reads with scene primitives.
- [x] Update exporter.
- [x] Verify GREEN.

### Task 5: Indicator Box
- [x] Add regression test expecting `SceneData`.
- [x] Verify RED.
- [x] Build scene primitives directly.
- [x] Update exporter/tests.
- [x] Verify GREEN.

### Task 6: Remove legacy adapter and verify
- [x] Delete `legacy_geom_to_primitives()` and import.
- [x] Update tests.
- [x] Run `pytest -q`.
- [x] Run py_compile on core modules.
- [x] Audit for `geom['polylines']`, `geom['lines']`, `geom['circles']`, and `legacy_geom_to_primitives`.
- [x] Run representative DXF round-trip checks.
