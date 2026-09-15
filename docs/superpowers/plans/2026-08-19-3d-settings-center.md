# Phase6 3D Settings Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move manufacturing/default settings into a schema-driven 3D settings center while preserving config.ini, keeping global main-GUI fields linked, and removing duplicate fold-size inputs from the main GUI.

**Architecture:** Add a focused `phase6_settings_center.py` module that owns setting metadata, INI read/write compatibility, and runtime AE synchronization. `gui.py` owns the shared runtime state and bidirectional bridge callbacks; `fold_designer_bridge.py` renders/edits that state above the unchanged original Renderer.

**Tech Stack:** Python 3, Tkinter/ttk, configparser, pytest, Xvfb.

**Spec:** `docs/superpowers/specs/2026-08-19-3d-settings-center-design.md`

## Global Constraints

- Preserve `config.ini`; do not ship or overwrite a replacement file.
- Preserve `fold_designer_original.py` byte-for-byte.
- Do not modify or bundle `ae_engine` manufacturing core.
- Global W/H/D/T/FW stay visible in the existing GUI and must be bidirectionally linked.
- Fold/part-specific numeric inputs are removed from the old GUI and edited in 3D settings center.
- Setting edits affect current runtime immediately; INI is written only on explicit save-default action.

---

### Task 1: Settings schema and INI persistence

**Files:**
- Create: `phase6_settings_center.py`
- Test: `tests/test_phase6_settings_center.py`

**Interfaces:**
- Produces: `SettingSpec`, `SETTING_SPECS`, `settings_for_context()`, `load_settings_from_ae()`, `apply_settings_to_ae()`, `save_defaults_to_ini()`.

- [ ] Write failing tests for context classification, legacy BASE_PLATE shrink fallback, preserving unknown INI keys, specific shrink keys, indicator-small-door fallback, and runtime AE updates.
- [ ] Run tests and verify RED.
- [ ] Implement schema/read/write/runtime sync.
- [ ] Run tests and verify GREEN.

### Task 2: Shared main-GUI settings state and bridge callbacks

**Files:**
- Modify: `gui.py`
- Test: `tests/test_phase6_settings_center_gui_contract.py`

**Interfaces:**
- Consumes Task 1 settings helpers.
- Produces: `_settings_state`, `_apply_fold_designer_live_settings()`, `_on_main_global_setting_changed()`, `_save_fold_designer_defaults()` and snapshot `settings` payload.

- [ ] Write failing tests proving snapshot contains global/unexposed settings, 3D apply updates T/FW/part vars + AE runtime, global traces can send external updates, and corner state is serialized/restored.
- [ ] Verify RED.
- [ ] Implement minimal shared-state bridge with recursion guard.
- [ ] Verify GREEN.

### Task 3: 3D right-top settings UI

**Files:**
- Modify: `fold_designer_bridge.py`
- Test: `tests/test_phase6_settings_center_bridge.py`

**Interfaces:**
- Consumes snapshot `settings`, optional `on_settings_change`, optional `on_save_defaults` callbacks.
- Produces: right-top `settings_center`, context rendering, `show_global_settings()`, `apply_external_settings()`.

- [ ] Write failing tests for right-top settings host, global-home default, part-specific context switching, live callback, save-default callback, and unchanged original Renderer type.
- [ ] Verify RED.
- [ ] Implement settings UI and callbacks without touching `fold_designer_original.py`.
- [ ] Verify GREEN.

### Task 4: Remove duplicate fold-size inputs from old GUI

**Files:**
- Modify: `gui.py`
- Test: `tests/test_phase6_settings_center_gui_contract.py`

**Interfaces:**
- Existing underlying Tk variables remain for calculations/API compatibility but no duplicate fold Entry widgets remain in the old GUI.

- [ ] Write failing static/UI tests asserting no advanced fold panel is constructed, z_comp Entry is absent from box-body header, base shrink/bend Entries are absent, while W/H/D/T/FW and CornerType remain.
- [ ] Verify RED.
- [ ] Remove only duplicate editor widgets; keep variables/calculation code.
- [ ] Verify GREEN.

### Task 5: Verification and overlay packaging

**Files:**
- Modify: `apply_fold_designer_outside_dims_phase6_fix13.py` only to validate new overlay tokens/file, never to require bundled core.
- Package all changed files, tests and docs; exclude caches/config/core.

- [ ] Run `py_compile` on all Python files.
- [ ] Run focused new tests.
- [ ] Run existing bridge tests that do not require absent ae_engine; run GUI tests against an available full project/core fixture if present and report any environment-only limitation separately.
- [ ] Verify `fold_designer_original.py` SHA256 remains `688c410fb1485186dfae26025031ceccdb09c75f5573f5f1ca673b22b2e82e0e`.
- [ ] Static-check `gui.py` still uses `manufacturing_api.generate_part()` and has no direct `ae.export_*` calls.
- [ ] Build clean ZIP and fresh-extract verification.
