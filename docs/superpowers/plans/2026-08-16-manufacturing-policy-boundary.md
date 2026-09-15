# Manufacturing Policy Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Remove all direct AE dependencies from automatic Door/EndCap bridges while preserving finished-face semantics and manufacturing output.

**Architecture:** Add a portable typed `ManufacturingPolicy` and policy-aware helpers to the existing headless API. Automatic bridges will construct context/specs and call API helpers only; wrapped AE compatibility remains confined to `manufacturing_api.py`.

**Tech Stack:** Python dataclasses, existing AE/sheetmetal modules, pytest, ezdxf.

## Global Constraints
- Do not change automatic DXF ownership/source recognition.
- Do not change finalized `info_data` authority.
- Do not change live `自動開孔替換.csv`.
- Automatic callers use finished-face 1:1 mm Feature semantics.
- GUI migration compatibility remains `feature_space="legacy_unfolded"`.
- `contracts.py` and `manufacturing_api.py` must be byte-identical in AE and split packages.

---

### Task 1: Typed Manufacturing Policy Contract

**Files:**
- Modify: `contracts.py`
- Test: `tests/test_manufacturing_policy_boundary.py`

**Interfaces:**
- Produces: `ManufacturingPolicy` and `ManufacturingContext.policy`.

- [x] Write RED tests asserting policy fields exist, context accepts an injected policy, and contracts still import without GUI.
- [x] Run focused RED.
- [x] Implement the frozen dataclass and optional context field without importing `ae`.
- [x] Run focused GREEN.

### Task 2: Policy and Manufacturing Helpers in Headless API

**Files:**
- Modify: `manufacturing_api.py`
- Test: `tests/test_manufacturing_policy_boundary.py`

**Interfaces:**
- Produces: `resolve_policy(context)`, `door_finished_face_size(spec, context)`, `indicator_box_opening_feature(groups, thickness, center, context)`, `door_indicator_offset_for_finished_center(spec, groups, desired_center, context)`, `indicator_small_door_spec(groups, thickness, context)`.

- [x] Write RED tests using monkeypatched AE defaults to prove `resolve_policy()` centralizes AE reads and injected policy overrides them.
- [x] Write RED tests proving indicator helpers match existing AE geometry/formulas.
- [x] Run focused RED.
- [x] Implement helpers using wrapped AE only inside `manufacturing_api.py`.
- [x] Run focused GREEN and existing API regressions.

### Task 3: Remove AE From Automatic Bridges

**Files:**
- Modify: `modules/automatic_door_bridge.py`
- Modify: `modules/automatic_endcap_bridge.py`
- Test: `tests/test_automatic_manufacturing_policy_boundary.py`
- Existing tests: automatic door/endcap/replacement/export task suites.

**Interfaces:**
- Consumes: Phase 4 portable API helpers.
- Produces: automatic bridges with no direct AE import/reference.

- [x] Write source-level RED asserting both bridges contain zero `ae.` references/imports.
- [x] Write behavior RED capturing exact policy/spec values passed to API.
- [x] Run RED.
- [x] Replace default thickness/FW/gap/fold reads with `resolve_policy(context)`.
- [x] Replace door finished-size call with `door_finished_face_size()`.
- [x] Replace indicator-box opening and small-door formulas with API helpers.
- [x] Run focused automatic regressions GREEN.

### Task 4: Portable Sync, Real DXF, Overlay Packaging

**Files:**
- Sync: `contracts.py` → `modules/contracts.py`
- Sync: `manufacturing_api.py` → `modules/manufacturing_api.py`
- Update: `HEADLESS_API.md`, `整合出圖合併注意事項.MD`, `最新修正日誌.md`
- Package: AE full ZIP + split update ZIP + overlay verification ZIP.

**Interfaces:**
- Produces byte-identical portable API files and direct-overlay update package.

- [x] Verify source hashes are identical across AE/split copies.
- [x] Run AE API + GUI adapter focused regressions and compile.
- [x] Run split automatic regressions and compile.
- [x] Run real Door/EndCap/indicator-box DXF smoke with ezdxf readback.
- [x] Overlay update package onto Phase 3 split full package and rerun automatic regressions.
- [x] Verify update ZIP excludes live CSV/log/cache/tmp artifacts.
