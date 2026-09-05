# Vault XY Upright Fold Designer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the Vault designer so EndCap/Tail expose authoritative X+Y fold chains, top WHD is global, ±90 is inverted only in UI, and EndCap/Tail preview geometry is actually upright without editing the original renderer or manufacturing engine.

**Architecture:** `fold_designer_bridge.py` owns all profile mapping, angle display conversion, global-WHD synchronization, mode hiding, and post-render 3D placement. `fold_designer_original.py` and `ae_engine/` remain byte-identical. `gui.py` remains the Phase6 snapshot/apply boundary.

**Tech Stack:** Python 3, tkinter/ttk, matplotlib mplot3d, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-vault-xy-upright-design.md`

## Global Constraints
- Do not modify `fold_designer_original.py`.
- Do not modify `ae_engine` manufacturing files.
- Do not move CornerType into the designer.
- Do not create a second hole editor.
- Preserve manufacturing outputs on no-op round trip.

---

### Task 1: Authoritative EndCap X/Y profiles
**Files:** `fold_designer_bridge.py`, `tests/test_original_fold_designer_bridge.py`
- [ ] Add failing tests for X=`yl1|W-4T|yr1` and Y=`ytop1|FW|D-3T|ybottom1`.
- [ ] Verify RED.
- [ ] Implement build/read helpers with Phase6 keys and derived W/D cores.
- [ ] Verify GREEN.

### Task 2: ±90 UI-only inversion
**Files:** `fold_designer_bridge.py`, `tests/test_original_fold_designer_bridge.py`
- [ ] Add failing tests for engine/UI angle conversion and no geometry-sign mutation in stored profiles.
- [ ] Verify RED.
- [ ] Invert only displayed/saved ±90 values in `Phase6BendingUI`.
- [ ] Verify GREEN.

### Task 3: Global WHD synchronization
**Files:** `fold_designer_bridge.py`, `tests/test_original_fold_designer_bridge.py`
- [ ] Add failing tests for W/D propagation to EndCap/Tail derived cores and H staying global across part switches.
- [ ] Verify RED.
- [ ] Unify box/head/tail around X/Y profile storage and propagate canonical W/H/D.
- [ ] Verify GREEN.

### Task 4: Upright EndCap/Tail preview placement
**Files:** `fold_designer_bridge.py`, `tests/test_original_fold_designer_bridge.py`
- [ ] Add failing pure transform test proving an XY panel becomes an XZ vertical panel.
- [ ] Add Tk integration test proving original Renderer source hash is unchanged and rendered head/tail artist geometry is vertical after bridge placement.
- [ ] Verify RED.
- [ ] Apply post-render transform only for active head/tail and redraw 3D axis.
- [ ] Verify GREEN.

### Task 5: Remove user-visible prototype mode switch
**Files:** `fold_designer_bridge.py`, `tests/test_original_fold_designer_bridge.py`
- [ ] Add failing Tk test that no visible `標準十字型` / `金庫型(三件)` radio remains.
- [ ] Hide only those mode widgets from the bridge after original UI construction.
- [ ] Verify GREEN.

### Task 6: Regression / preview / package
**Files:** tests, docs, package overlay only.
- [ ] Verify `fold_designer_original.py` SHA256 equals `/mnt/data/mainapp.py`.
- [ ] Verify `ae_engine` is byte-identical to FIX11 input tree.
- [ ] Run full Phase6 tests under fresh Xvfb.
- [ ] Export actual head and tail screenshots for user inspection.
- [ ] Build FIX12 overlay ZIP and patch; install actual ZIP on a clean FIX11 tree and rerun verification.


### Task 7: EndCap authoritative round-trip and baseline reload
**Files:** `fold_designer_bridge.py`, `gui.py`, `tests/test_original_fold_designer_bridge.py`, `tests/test_original_fold_designer_gui_integration.py`
- [x] Add regression test that edits Head X/Y through the actual BendingUI controls and exports new `W/D/FW/yl1/yr1/ytop1/ybottom1`.
- [x] Prevent stale box-body profile state from overwriting Head/Tail global values during export.
- [x] Apply all EndCap parameters back to the authoritative Phase6 Tk variables.
- [x] Invalidate baseline-derived caches without calling `on_baseline_changed()` so edited values are not restored to baseline defaults.
- [x] Re-run `update_calculations()` so the selected baseline is re-read/re-stretched using the new dimensions.
- [x] Verify the authoritative EndCap PartSpec and geometry consume the edited values.

