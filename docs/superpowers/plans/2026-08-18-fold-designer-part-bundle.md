# Fold Designer Part Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the FIX10 data bridge so the unchanged original fold designer receives the current Phase6 part set and hole data, selects the previously active part, defaults to one box body only when no parts exist, and can add missing known parts.

**Architecture:** `gui.py` builds a Phase6 snapshot/bundle. `fold_designer_bridge.py` owns part records, profile adapters, preview-hole projection, selection, and add-part behavior. `fold_designer_original.py` remains byte-identical and Renderer is never subclassed or replaced.

**Tech Stack:** Python 3, tkinter/ttk, matplotlib, pytest.

## Global Constraints
- Do not edit `fold_designer_original.py`.
- Do not edit `ae_engine` manufacturing geometry.
- Do not move CornerType into the designer.
- Do not expose the duplicate original HolesUI tab.
- Preserve raw Phase6 features exactly on no-op round trips.
- Only box body owns fixed D-W-D identities.

---

### Task 1: Part bundle and active-part contract
**Files:** `tests/test_original_fold_designer_bridge.py`, `fold_designer_bridge.py`
- [ ] Write failing tests for existing-part ordering, active-part preference, and box-body fallback.
- [ ] Run tests and verify RED.
- [ ] Add pure bundle normalization helpers.
- [ ] Run tests and verify GREEN.

### Task 2: Hole data projection without duplicate editor
**Files:** `tests/test_original_fold_designer_bridge.py`, `fold_designer_bridge.py`
- [ ] Write failing tests that raw features survive and circle/rect features project to original renderer holes.
- [ ] Run tests and verify RED.
- [ ] Add projection helpers that never mutate source features.
- [ ] Run tests and verify GREEN.

### Task 3: Designer part switching/addition with original Renderer
**Files:** `tests/test_original_fold_designer_bridge.py`, `fold_designer_bridge.py`
- [ ] Write failing Tk tests for part selector, active selection, hidden hole tab, add-missing-part action, original Renderer identity, and D-W-D row locking.
- [ ] Run tests and verify RED under Xvfb.
- [ ] Add the thinnest wrapper controls around the original MainApp and reuse the original BendingUI grid/Renderer.
- [ ] Run tests and verify GREEN under Xvfb.

### Task 4: Phase6 GUI snapshot integration
**Files:** `tests/test_original_fold_designer_gui_integration.py`, `gui.py`
- [ ] Write failing tests for current-part snapshot, all existing features, optional indicator components, no-op round trip, and fallback box body.
- [ ] Run tests and verify RED.
- [ ] Extend snapshot/apply methods without changing manufacturing calculations.
- [ ] Run tests and verify GREEN.

### Task 5: Regression/package verification
**Files:** package overlay and docs only.
- [ ] Verify `fold_designer_original.py` SHA256 unchanged.
- [ ] Verify all `ae_engine` manufacturing files byte-identical to FIX10/FIX7.
- [ ] Run full Phase6 tests with fresh Xvfb batches.
- [ ] Build FIX11 overlay ZIP and patch.
- [ ] Install actual ZIP onto a clean Phase6+FIX7 base and rerun tests plus config/baseline hash checks.
