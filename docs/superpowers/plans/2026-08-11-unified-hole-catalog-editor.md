# Unified Hole Catalog & Panel Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every primary panel use the same hole editor, with catalog entries sourced only from `基準檔/開孔/開孔.csv` and `基準檔/開孔/管孔尺寸清單.csv`, custom circle/rectangle blind-hole checkbox, and DXF profile layers preserved.

**Architecture:** `hole_catalog.py` owns catalog parsing and DXF profile semantics. `sheetmetal_features.py` owns immutable placement/rotation/containment. GUI owns only selection, rendering, and interaction. All panel tabs bind the same generic feature-surface editor; end-cap legacy storage remains compatible at the boundary.

**Tech Stack:** Python 3.11, Tkinter, ezdxf, Shapely, pytest.

## Global Constraints
- Catalog sources are exactly `開孔.csv` and `管孔尺寸清單.csv` under `基準檔/開孔/`.
- Numeric `開孔.csv` entries default to `CUTTING`.
- DXF-backed `開孔.csv` entries preserve the DXF entity layers.
- Pipe catalog entries are `BLIND_HOLE` with DATUM centerlines.
- Custom circle/rectangle features default to `CUTTING`; one `盲孔` checkbox switches them to `BLIND_HOLE`.
- Rotation options are 90/180/270/360 and containment uses the rotated footprint.
- Every primary panel has visible double-click/right-click access to the same editor.

---

### Task 1: Catalog source and custom process contract
- [ ] Add failing tests for exact two-file source policy and custom default/blind semantics.
- [ ] Run targeted tests and verify RED.
- [ ] Implement minimal catalog/process helpers.
- [ ] Run targeted tests and verify GREEN.

### Task 2: Layer-preserving DXF profiles
- [ ] Add failing DXF test containing CUTTING + MARKING + BLIND_HOLE/DATUM entities.
- [ ] Run targeted test and verify RED.
- [ ] Preserve supported profile entity layers through rotation, preview and DrawingScene.
- [ ] Run targeted test and verify GREEN.

### Task 3: Unified editor on all panels
- [ ] Add failing source/behavior tests for double-click/right-click bindings and one generic editor.
- [ ] Run targeted tests and verify RED.
- [ ] Bind Box Body, Door, Base Plate, Indicator Box, Indicator Door, Head and Tail consistently.
- [ ] Replace end-cap visible built-in hole choices with catalog + custom circle/rectangle controls while preserving legacy persistence.
- [ ] Run targeted tests and verify GREEN.

### Task 4: Full verification
- [ ] Run full pytest suite.
- [ ] Run py_compile on core modules.
- [ ] Instantiate Tk GUI under virtual display.
- [ ] Round-trip DXF and verify CUTTING/BLIND_HOLE/MARKING/DATUM profile layers.
