# Linked Fold Chain / Optional Parts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make arbitrary box-body Fold Chain authoritative in 2D/3D, derive head/tail mating topology from it, and commit optional-part deletion/addition transactionally.

**Architecture:** Carry the editable box profile through BoxBodyPartSpec into final scene/export. Derive head/tail Y profiles from semantic D-W-D anchors plus the ordered outer mating chain, keeping native head/tail orientation. Treat existing_parts as transactional authoritative state and synchronize main-GUI export controls only on Confirm.

**Tech Stack:** Python, Tkinter, Shapely/ezdxf, pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-linked-fold-chain-parts-design.md`

## Global Constraints
- No `if len(profile) == N` topology branches.
- `fold_designer_original.py` must remain byte-identical.
- Cancel/X must not mutate main GUI state.
- 2D and 3D must consume the same final Fold Chain.

---

### Task 1: Arbitrary box Fold Chain in final 2D/manufacturing scene
- [ ] Add failing tests for 5- and 20-segment BoxBodyPartSpec profiles.
- [ ] Verify RED against legacy 8-BEND scene.
- [ ] Add profile contract and final-scene mapping.
- [ ] Verify GREEN and existing manufacturing tests.

### Task 2: Linked head/tail mating profiles
- [ ] Add failing tests using uploaded `自訂.p6fold` and synthetic 3/9/12/20 chains.
- [ ] Verify RED: head/tail remain legacy profiles.
- [ ] Implement semantic mating-chain derivation with native head/tail orientation.
- [ ] Wire box editor updates/load/add-part through the derivation.
- [ ] Verify GREEN.

### Task 3: Confirmed optional-part deletion/addition
- [ ] Add failing transaction tests for remove/add and exact existing_parts persistence.
- [ ] Verify RED.
- [ ] Add remove-part UI/action; keep box_body mandatory.
- [ ] Synchronize main-GUI export/indicator existence controls on Confirm/project load.
- [ ] Verify GREEN.

### Task 4: Bring the committed chain back to 2D and .p6fold
- [ ] Add failing tests that main GUI PartSpec receives committed box profile and project reload re-derives endcaps.
- [ ] Verify RED.
- [ ] Implement snapshot/spec propagation and project migration.
- [ ] Verify GREEN.

### Task 5: Full verification and delivery
- [ ] Run targeted tests.
- [ ] Run full suite.
- [ ] Run py_compile and original-file hash check.
- [ ] Build clean ZIP/patch, extract ZIP, rerun full tests.
