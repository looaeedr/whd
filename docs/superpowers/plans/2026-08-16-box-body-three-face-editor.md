# Box Body Three-Face Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make Box Body editing behave like Multi-Door: show left/back/right faces, edit each face independently in direct WHD enclosure coordinates, map those features to the single unfolded StripFoldChain DXF, and use `箱身.dxf` as the fixed-feature baseline when present.

**Architecture:** User-facing Box Body feature coordinates are face-local enclosure coordinates: left=`D×H`, back=`W×H`, right=`D×H`. A pure mapping layer converts each face-local feature to the authoritative unfolded StripFoldChain face segment (`depth_left`, `front`, `depth_right`) only at preview/export time. Baseline CIRCLE and Color 211 MARKING linework are mapped by the shared baseline mapper, then classified into the three authoritative face segments and projected back into the same face-local WHD coordinate system for overview/editor display.

**Tech Stack:** Python 3, Tkinter, ezdxf, existing `sheetmetal_geometry` / `sheetmetal_features` / `sheetmetal_part_adapters` / `sheetmetal_drawing`, pytest + Xvfb.

## Global Constraints

- Box Body face editor dimensions are direct WHD: left=`D×H`, back=`W×H`, right=`D×H`; do not show `D-2T`, `W-2T`, or `H-2T` as user coordinates.
- Box Body remains one physical part and one `box_body_z.dxf`; the three faces are editing surfaces only.
- StripFoldChain remains the single source of truth for CUTTING/BEND structural geometry.
- `箱身.dxf` contributes fixed baseline features only; it does not replace formula-generated main structure.
- When `箱身.dxf` exists, status must say `基準檔：<model>/箱身.dxf（固定特徵映射）`; otherwise say `未使用基準檔（程式計算生成）`.
- Formal tests go under `tests/`; temporary smoke scripts/output/patches go under `tmp/`.

---

### Task 1: Pure Box Body face coordinate mapping

**Files:**
- Modify: `sheetmetal_features.py`
- Test: `tests/test_box_body_faces.py`

**Interfaces:**
- Produces `BoxBodyFaceContext`, `box_body_face_dimensions()`, `box_body_face_contexts_from_strip()`, `resolve_box_body_face_features()`, and unfolded/local point conversion helpers.

- [x] Write failing tests proving `W=500,H=600,D=200,T=2` exposes left `200×600`, back `500×600`, right `200×600`, while local `T..outer-T` maps to each authoritative unfolded face segment and `T..H-T` maps to `0..H-2T`.
- [x] Run the focused tests and confirm RED.
- [x] Implement the minimal pure mapping helpers.
- [x] Run focused tests and confirm GREEN.

### Task 2: Baseline fixed features split into three face-local views

**Files:**
- Modify: `ae.py`
- Test: `tests/test_box_body_faces.py`

**Interfaces:**
- Consumes Task 1 face contexts.
- Produces `get_box_body_baseline_face_features(model_name, ...)` and an explicit Box Body baseline status label.

- [x] Write failing tests using the real `基準檔/金庫型/箱身.dxf` and verify mapped baseline circles and Color 211 MARKING linework are assigned only to left/back/right face regions and represented in direct WHD coordinates.
- [x] Run focused tests and confirm RED.
- [x] Implement classification/project-back on top of one shared Box Body baseline mapper; preserve the legacy circle-only API as a compatibility view.
- [x] Run focused tests and confirm GREEN.

### Task 3: One face-owned feature store and single-DXF export

**Files:**
- Modify: `ae.py`
- Modify: `gui.py`
- Test: `tests/test_box_body_faces.py`

**Interfaces:**
- GUI store: `self.box_body_face_features = {"left": [], "back": [], "right": []}`.
- Export: `export_box_body_dxf(..., face_features=...)` resolves all three local stores into unfolded primitives before serialization.

- [x] Write failing tests proving a local back-face circle at `(120,300)` maps into the `front` StripFoldChain segment and survives DXF readback, while left/right features remain in their own segments.
- [x] Run focused tests and confirm RED.
- [x] Implement face-feature resolution in `_build_box_body_scene()` and export API.
- [x] Run focused tests and confirm GREEN.

### Task 4: Three-face overview and per-face unified editor

**Files:**
- Modify: `gui.py`
- Test: `tests/test_box_body_gui.py`

**Interfaces:**
- Main Box Body canvas shows left/back/right rectangles using direct WHD proportions.
- Canvas-level hit test + manual rapid-second-click opens `open_box_body_face_editor(face_key)`.
- Unified editor receives a simple `0..D/W × 0..H` rectangular surface/reference guide and the corresponding face feature list.

- [x] Write failing Xvfb GUI tests for three visible face regions, selection, rapid second click dispatch, direct WHD reference dimensions, and baseline status.
- [x] Run focused tests and confirm RED.
- [x] Replace the unfolded Box Body main-canvas interaction with three-face overview; keep formula unfolded geometry only for output/internal conversion.
- [x] Add per-face editor entry using the existing unified editor.
- [x] Run focused tests and confirm GREEN.

### Task 5: Regression, real DXF smoke, packaging

**Files:**
- Modify: `README_MULTI_DOOR_TRIAL.md`
- Create: `tmp/box_body_three_face_editor.patch`

**Interfaces:**
- Final ZIP root remains `multi_door_layout_trial/`.

- [x] Run full `xvfb-run -a pytest -q`.
- [x] Run `python -m py_compile` on production modules.
- [x] Export real `box_body_z.dxf` with features on all three faces and verify with ezdxf that the features land in the three expected StripFoldChain segments.
- [x] Verify baseline source/status with real `基準檔/金庫型/箱身.dxf`.
- [x] Build a clean ZIP, extract it fresh, rerun full tests and smoke verification.
