# Fold Diagnostic Save + Tail Native Orientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make tail 3D folding use native Y orientation and add a JSON diagnostic save file containing exact fold profiles/dimensions and authoritative final geometry.

**Architecture:** Keep AE `PartRenderData` authoritative. Fix only the editor/profile-to-scene orientation for tail. Add a serializer at the bridge boundary so the save file captures the same draft payload and final render data actually consumed by 3D.

**Tech Stack:** Python, Tkinter, Shapely, Matplotlib, pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-fold-diagnostic-save-tail-native-orientation-design.md`

## Global Constraints
- Do not modify `fold_designer_original.py`.
- Do not add a second hole/corner engine.
- Save is diagnostic/export only; it must not commit the transaction.
- Tail final scene remains unmirrored in AE.

---

### Task 1: Tail native Y profile
**Files:** Modify `fold_designer_bridge.py`; Test `tests/test_phase6_tail_native_orientation_and_save.py`.
- [ ] Add RED test asserting head and tail Y profile phase6_key order differ and tail is `ybottom1,endcap_d_core,fw,ytop1`.
- [ ] Run RED.
- [ ] Add part-aware endcap profile builder and use it for initialization/reset.
- [ ] Run targeted tests.

### Task 2: Diagnostic JSON builder
**Files:** Modify `fold_designer_bridge.py`; Test `tests/test_phase6_tail_native_orientation_and_save.py`.
- [ ] Add RED test for JSON-serializable diagnostic dict containing all part profiles, active payload, final scene CUTTING and material mapping.
- [ ] Run RED.
- [ ] Implement serializer helpers and error-preserving final geometry snapshot.
- [ ] Run targeted tests.

### Task 3: Save button
**Files:** Modify `fold_designer_bridge.py`; Test `tests/test_phase6_tail_native_orientation_and_save.py`.
- [ ] Add RED source/UI test requiring button text `存檔` wired to diagnostic save action.
- [ ] Run RED.
- [ ] Add file dialog + UTF-8 JSON writer; cancellation is no-op.
- [ ] Run targeted tests.

### Task 4: Verification/package
- [ ] Run full pytest under Xvfb.
- [ ] Run py_compile.
- [ ] Verify `fold_designer_original.py` SHA unchanged from input package.
- [ ] Package clean ZIP and re-run full tests from extracted ZIP.
