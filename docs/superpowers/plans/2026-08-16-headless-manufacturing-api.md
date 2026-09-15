# Headless Manufacturing API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a GUI-independent Python API that exports Door, Box Body, End Cap Head/Tail through the existing AE engine without changing manufacturing geometry.

**Architecture:** `contracts.py` owns immutable request/result dataclasses. `manufacturing_api.py` adapts those contracts to the existing `ae.py` exporters, automatically choosing baseline exporters where applicable, and performs safe atomic replacement. Existing GUI and automatic-split code are intentionally unchanged in this phase.

**Tech Stack:** Python 3, dataclasses, pathlib, existing `ae.py`, ezdxf, pytest.

## Global Constraints

- Do not change GUI behavior or automatic DXF extraction in this phase.
- Do not duplicate geometry, fold, baseline mapping, or feature resolver logic.
- Finished-face feature coordinates remain 1:1 mm manufacturing coordinates.
- Door/end-cap baseline is used when the requested model baseline exists; formula is fallback only when the baseline is absent.
- Box Body main geometry stays formula/StripFoldChain while `箱身.dxf` supplies baseline fixed features through the existing exporter.
- Export writes to a temporary sibling and replaces the destination only after exporter success.

---

### Task 1: Stable Headless Contracts

**Files:**
- Create: `contracts.py`
- Test: `tests/test_manufacturing_api.py`

**Interfaces:**
- Produces: `ManufacturingContext`, `DoorPartSpec`, `BoxBodyPartSpec`, `EndCapPartSpec`, `PartExportResult`, `PartSpec`.
- Feature payloads are existing finished-face `sheetmetal_features.Feature` objects or legacy feature dictionaries already accepted by AE.

- [x] Write tests asserting contracts can be constructed without importing `gui` and preserve W/H/D/T/model/features.
- [x] Run focused tests and verify RED because `contracts.py` does not exist.
- [x] Implement immutable dataclasses with explicit manufacturing dimensions/options.
- [x] Run focused tests and verify GREEN.

### Task 2: Canonical `generate_part()` Adapter

**Files:**
- Create: `manufacturing_api.py`
- Test: `tests/test_manufacturing_api.py`

**Interfaces:**
- Consumes: Task 1 contracts.
- Produces: `generate_part(spec, output_path, context=None) -> PartExportResult`.
- Door: baseline `門.dxf` -> `ae.export_stretched_door_dxf`; otherwise `ae.export_door_dxf`.
- Box Body: always `ae.export_box_body_dxf(..., model_name=...)` so StripFoldChain remains authoritative while baseline fixed features load when present.
- End Cap: baseline `封頭尾.dxf` -> `ae.export_stretched_end_cap_dxf`; otherwise `ae.export_end_cap_dxf`.

- [x] Write exporter-dispatch tests with monkeypatched AE exporters and verify RED.
- [x] Implement minimal dispatch and result metadata.
- [x] Verify focused tests GREEN.

### Task 3: Resource Root and Atomic Overwrite Boundary

**Files:**
- Modify: `manufacturing_api.py`
- Test: `tests/test_manufacturing_api.py`

**Interfaces:**
- `ManufacturingContext(resource_root=None, overwrite=True, draw_stock=False)`.
- `resource_root` means the directory containing `config.ini` and `基準檔/`; adapter temporarily redirects AE resource lookup only for the export call.

- [x] Write tests proving a custom resource root selects a baseline outside the AE module directory and that destination is unchanged when exporter raises.
- [x] Verify RED.
- [x] Implement scoped resource lookup override plus temp-file -> `os.replace` flow.
- [x] Verify GREEN.

### Task 4: Real DXF Headless Smoke

**Files:**
- Test: `tests/test_manufacturing_api.py`

**Interfaces:**
- Uses the real `基準檔/金庫型` supplied in the prototype package.

- [x] Export one Door, Box Body, End Cap Head, End Cap Tail through `generate_part()` with no Tk root or GUI object.
- [x] Read every DXF back with ezdxf; assert CUTTING exists and Box Body BEND exists.
- [x] Run full pytest and `py_compile`.
- [x] Package ZIP and rerun focused headless tests from extracted ZIP.
