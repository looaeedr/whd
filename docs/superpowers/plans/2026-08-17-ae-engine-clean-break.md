# AE Engine Clean Break Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Delete all transitional AE shims, switch every consumer to `ae_engine`, and rename the split-only hole catalog to `automatic_hole_catalog.py`.

**Architecture:** `ae_engine/` is the sole manufacturing core. Split-owned source/replacement logic remains in `modules/automatic_*`; no compatibility duplicate remains.

**Tech Stack:** Python, pytest, ezdxf, Tkinter/Xvfb.

## Global Constraints
- Do not change manufacturing geometry or automatic recognition semantics.
- Do not overwrite live `自動開孔替換.csv`, logs, `config.ini`, or split-owned catalog rules.
- RO registry remains present but RO geometry remains unimplemented.

### Task 1: Lock clean-break boundary
- [x] Add RED structural tests requiring old shim files/imports to be absent.
- [x] Run RED and verify failures are the old files/imports.

### Task 2: AE standalone cleanup
- [x] Rewrite remaining tests to import `ae_engine` directly.
- [x] Delete root AE shim files.
- [x] Run AE core and GUI regression.

### Task 3: Split cleanup and catalog rename
- [x] Rename `modules/hole_catalog.py` to `modules/automatic_hole_catalog.py`.
- [x] Rewrite production/tests to import core from `ae_engine` and catalog from the renamed module.
- [x] Delete all `modules` AE shim files.
- [x] Run split regression.

### Task 4: Delivery verification
- [x] Run py_compile and real-DXF smoke.
- [x] Verify no old shim/import remains.
- [x] Verify live CSV/catalog ownership is untouched by AE-only overlay.
- [x] Package AE full ZIP, split update ZIP, and fresh verified split ZIP.
