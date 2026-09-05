# GUI Manufacturing API Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Route every GUI DXF export through `manufacturing_api.generate_part()` while preserving existing geometry, baseline behavior, filenames, multi-door ownership, and UI behavior.

**Architecture:** Extend the stable headless contracts to cover End Cap formula parameters, Base Plate, and Indicator Box. Add pure GUI adapter helpers that translate current Tk state into immutable `PartSpec` objects; export methods then call only `manufacturing_api.generate_part()`. `ae` remains available to GUI preview/render code but no GUI export path may call `ae.export_*` directly.

**Tech Stack:** Python dataclasses, Tkinter, existing AE exporters, pytest, ezdxf.

## Global Constraints

- Do not alter geometry algorithms, finished-face semantics, baseline DXFs, or GUI layout.
- Preserve current filenames and multi-door per-cell feature ownership.
- Door/End Cap baseline selection remains inside `manufacturing_api`.
- Box Body main structure remains StripFoldChain; baseline only supplies fixed features.
- GUI export path must contain zero direct `ae.export_*` calls after migration.
- Existing destination replacement remains atomic through `generate_part()`.

---

### Task 1: Complete stable PartSpec coverage

**Files:**
- Modify: `contracts.py`
- Modify: `manufacturing_api.py`
- Test: `tests/test_manufacturing_api.py`

**Interfaces:**
- Extend `EndCapPartSpec` with optional `height`, `fold_left`, `fold_right`, `fold_top`, `fold_bottom`, `box_fold_left`, `box_fold_right`.
- Add `BasePlatePartSpec` and `IndicatorBoxPartSpec`.
- `generate_part()` accepts all five part families.

- [x] Write failing API tests for End Cap full arguments, Base Plate, and Indicator Box.
- [x] Run focused tests and confirm RED.
- [x] Implement minimal contracts and dispatcher/export adapters.
- [x] Run focused tests and confirm GREEN.

### Task 2: Add GUI state-to-PartSpec adapters

**Files:**
- Modify: `gui.py`
- Test: `tests/test_gui_manufacturing_adapter.py`

**Interfaces:**
- Add `_manufacturing_context(draw_stock)`.
- Add pure builders for box body, end cap, door, base plate, indicator box, and indicator small-door specs.
- Multi-door cell builder receives the existing validated `DoorLayoutCell` and per-cell state.

- [x] Write failing tests that construct GUI state and assert exact PartSpec contents.
- [x] Run focused tests and confirm RED.
- [x] Implement minimal adapter helpers without changing widgets or geometry.
- [x] Run focused tests and confirm GREEN.

### Task 3: Route GUI exporters through the API

**Files:**
- Modify: `gui.py`
- Test: `tests/test_gui_manufacturing_adapter.py`

**Interfaces:**
- `export_multi_door_layout_dxfs()` calls `manufacturing_api.generate_part()` once per Door cell.
- `export_multi_door_indicator_box_parts()` routes both box and small-door through API.
- `export_selected_dxf()` routes box body, head, tail, single/multi door, base plate, single/multi indicator parts through API.

- [x] Write failing tests monkeypatching `manufacturing_api.generate_part()` and asserting no legacy exporter is called.
- [x] Run focused tests and confirm RED.
- [x] Replace direct GUI export calls with adapter + API calls.
- [x] Add static regression asserting GUI export region has no `ae.export_*` calls.
- [x] Run focused tests and confirm GREEN.

### Task 4: Real-DXF parity and package verification

**Files:**
- Update: `HEADLESS_API.md`
- Test: existing full suite plus new parity smoke scripts under `tmp/`

- [x] Export representative Door, multi-door, Box Body, Head/Tail, Base Plate, Indicator Box, Indicator Door through GUI adapter/API and read them back with ezdxf.
- [x] Run full pytest suite.
- [x] Run `py_compile` on production modules.
- [x] Package ZIP, extract fresh, and rerun focused adapter tests plus hash/content checks.
