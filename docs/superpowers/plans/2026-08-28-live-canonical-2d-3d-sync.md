# Phase6 Live Canonical 2D/3D Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Fold Designer confirm/cancel draft semantics and make 2D, 3D, DXF/NC consume one immediately synchronized canonical Manufacturing state with atomic Head/Tail 3D relief commits.

**Architecture:** Fold Designer publishes its existing full transaction payload through one `on_live_sync(payload)` seam after production edits. Main GUI applies that payload immediately without ProjectSession draft commit/rollback. Dynamic relief solver only returns verified cut answers; Head/Tail are committed together into canonical `assembly_relief_state`, then 3D re-queries the same Manufacturing provider used by 2D/DXF.

**Tech Stack:** Python 3, Tkinter, Shapely, pytest, existing Phase6 Manufacturing API.

**Spec:** `docs/superpowers/specs/2026-08-28-live-canonical-2d-3d-sync-design.md`

## Global Constraints
- Do not modify `config.ini` unless explicitly requested.
- Keep Traditional Chinese UI and documentation.
- No hard-coded production cut dimensions; dynamic relief remains 3D-derived.
- 2D / 3D / DXF/NC must share authoritative PartSpec → PartRenderData.
- Head/Tail relief commit is atomic.
- Final delivery requires FULL + UPDATE with Asia/Taipei `YYYYMMDD_HHMMSS`, same timestamp, UPDATE rooted at project root.

---

### Task 1: Replace transaction UI with live-sync contract

**Files:**
- Modify: `fold_designer_bridge.py`
- Modify: `gui.py`
- Test: `tests/test_phase6_live_canonical_sync.py`

**Interfaces:**
- Produces: `on_live_sync(payload)` constructor callback and `_phase6_publish_live_state(self)`.
- Produces: `BoxCalculatorGUI._apply_fold_designer_live_snapshot(payload)`.

- [x] **Step 1: Write failing tests** asserting transaction buttons are absent, real settings/corner/workspace edits invoke live sync, and window close does not cancel/rollback.
- [x] **Step 2: Run tests and confirm RED** against current transaction implementation.
- [x] **Step 3: Implement minimal live-sync seam** with re-entrancy guard and remove confirm/cancel buttons/callback wiring.
- [x] **Step 4: Run tests and confirm GREEN**.

### Task 2: Make dynamic relief atomic and canonical

**Files:**
- Modify: `fold_designer_bridge.py`
- Modify: `gui.py`
- Modify: `ae_engine/assembly_collision.py` only if replay helper needs adjustment.
- Test: `tests/test_phase6_live_canonical_relief.py`

**Interfaces:**
- Consumes: `on_live_sync(payload)`.
- Produces: one atomic `assembly_relief_state` update containing verified Head and Tail cuts plus source fingerprint.

- [x] **Step 1: Write failing tests** for Head verified/Tail failed => no relief commit and no half-solved render; both verified => one commit then provider replay for both.
- [x] **Step 2: Run tests and confirm RED**.
- [x] **Step 3: Implement atomic two-part solve** collecting both solutions first, committing only when both verify, then re-querying provider.
- [x] **Step 4: Run tests and confirm GREEN**.

### Task 3: Prove real-file 2D/3D identity and stale invalidation

**Files:**
- Test: `tests/test_phase6_user_p6fold_live_sync.py`
- Modify: `gui.py` / `fold_designer_bridge.py` only if the real file exposes a missing invalidation seam.

**Interfaces:**
- Consumes: `/mnt/data/自訂(6).p6fold` in development verification; test fixture may copy/parse its snapshot when available.

- [x] **Step 1: Add regression** loading the real user file and checking stale `INSERT` relief is rejected when current assembly is `INSERT_OVERLAY`.
- [x] **Step 2: Compare canonical 2D EndCap material and assembly 3D provider material**; require symmetric difference area <= 1e-6 after successful atomic solve, or unchanged canonical material when solve fails.
- [x] **Step 3: Run focused suite** and fix only genuine new regressions.

### Task 4: Documentation and delivery verification

**Files:**
- Modify: `個人AI檔案庫/README.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- Modify: `修改日誌/20260828.md`
- Create: `docs/superpowers/verification/2026-08-28-live-canonical-2d-3d-sync.md`

**Interfaces:**
- Documents the single canonical state and atomic relief invariant.

- [x] **Step 1: Update AI/Superpowers docs** with removed confirm/cancel semantics and atomic relief rule.
- [x] **Step 2: Run fresh focused regression, py_compile, UTF-8 strict, config.ini SHA check**.
- [x] **Step 3: Build FULL/UPDATE**, run `testzip`, extracted SHA256 comparison, and overlay UPDATE onto prior FULL then rerun focused regression.

## Completion update — 2026-08-29
- Task 1–4 completed.
- Follow-up UI adds assembly part visibility, assembly/all-part corner dimensions, per-part 2D/3D corner dimensions, and `回2D截角`, all consuming canonical geometry.
- Single-stage INSERT backprojection contact correction verified on `自訂(9).p6fold` at `38×27` for Head/Tail.
- Final documentation gate requires 20260829 log + verification + AI/SOP/handoff updates in the same package.
