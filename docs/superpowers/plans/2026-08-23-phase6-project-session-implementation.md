# Phase6 ProjectSession Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 Phase6 的專案讀寫與 3D 確定/取消交易由單一 `ProjectSession` 管理，保證 draft 永遠不能在未確定時污染 committed 專案。

**Architecture:** 新增純 Python `ProjectSession` deep module 作為 transaction seam；main GUI 在交易邊界 capture/apply snapshot，Fold Designer 只拿 draft 副本。main-connected designer 的 project save 反向委派到 main GUI committed save，standalone designer 保留舊行為。

**Tech Stack:** Python 3、dataclasses、copy.deepcopy、Tkinter、pytest、Xvfb。

**Spec:** `docs/superpowers/specs/2026-08-23-phase6-project-session-design.md`

## Global Constraints

- `.p6fold` schema 固定 `phase6-fold-project-v1`，不得升版。
- Factory Defaults / 「還原初始值」不屬於 ProjectSession，行為不得改變。
- snapshot crossing `ProjectSession` interface 一律 defensive deepcopy。
- active draft 存在時，任何 main-connected project save 都只能保存 committed。
- `_phase6_loaded_project_path` 若保留，只能是 computed compatibility alias，不得形成第二份 state。
- 不改 EndCap / CornerType / Fold Profile 幾何規則。

---

### Task 1: 建立 ProjectSession deep module

**Files:**
- Create: `phase6_project_session.py`
- Create: `tests/test_phase6_project_session.py`

**Interfaces:**
- Consumes: project snapshot `Mapping[str, object]` 與 optional path。
- Produces: `ProjectSession` interface defined in spec。

- [x] **Step 1: RED — draft isolation / cancel**
  建立 test：capture committed W=400、begin draft、外部把 draft 改 500、cancel 後 committed 必須 400，且 caller 修改 returned dict 不得污染內部。
- [x] **Step 2: GREEN — minimal ProjectSession**
  實作 constructor、deepcopy helper、`capture_committed`、`begin_draft`、`cancel_draft`、`committed_snapshot`、`draft_snapshot`、`has_draft`。
- [x] **Step 3: RED/GREEN — commit + save ownership**
  加 test：replace/commit draft 500 後 committed=500；active draft 500 時 `snapshot_for_save()` 仍 400。
- [x] **Step 4: RED/GREEN — load baseline/path**
  加 test：load 400 後 baseline/committed=400，capture committed 450 不改 baseline；load 新專案會清除舊 draft；path normalize 成字串。

### Task 2: Main GUI 專案讀寫接上 ProjectSession

**Files:**
- Modify: `gui.py`
- Modify: `tests/test_phase6_project_file.py`

**Interfaces:**
- Consumes: `ProjectSession.capture_committed/load_project/snapshot_for_save/project_path`。
- Produces: `_capture_phase6_committed_snapshot()`；existing project save/load methods behavior unchanged except ownership centralized。

- [x] **Step 1: RED — session exists and loaded baseline stays immutable**
  在 real Tk integration test 驗證 load W=400 後 baseline=400；main edit/save capture 450 後 baseline 仍 400。
- [x] **Step 2: GREEN — instantiate/import session and migrate project_path**
  `BoxCalculatorGUI` 建立 `self.project_session`；`_phase6_loaded_project_path` 改 computed property；Save/Save As/Load 改走 session path/load。
- [x] **Step 3: GREEN — committed payload builder**
  抽出 `_compose_phase6_project_snapshot_from_main_gui()` 與 `_capture_phase6_committed_snapshot()`；無 draft 時 capture main GUI，有 draft 時 `_build_phase6_project_payload()` 只用 `snapshot_for_save()`。

### Task 3: 3D begin/cancel/confirm 交易接上 ProjectSession

**Files:**
- Modify: `gui.py`
- Modify: `tests/test_phase6_project_file.py`

**Interfaces:**
- Consumes: `begin_draft/cancel_draft/commit_draft`。
- Produces: 3D window lifecycle exactly once begins and resolves one draft。

- [x] **Step 1: RED — cancel discards staged W=500**
  real Tk：main committed W=400，open 3D，designer staged W=500，Cancel；main/session committed 仍 400、draft cleared。
- [x] **Step 2: GREEN — open uses begin_draft, cancel uses cancel_draft**
  開啟前 capture committed；傳入 designer 的 snapshot 來自 session draft defensive copy；runtime path 只加到傳入副本。
- [x] **Step 3: RED — confirm commits W=500**
  real Tk：staged settings W=500 → Confirm → main W=500、session committed W=500、draft cleared。
- [x] **Step 4: GREEN — confirm after apply commits canonical main snapshot**
  `_apply_fold_designer_corner_transaction()` 成功後 capture canonical main snapshot 並 `commit_draft(snapshot)`；失敗不提交。

### Task 4: 收斂 3D 專案存檔 alternate path

**Files:**
- Modify: `fold_designer_bridge.py`
- Modify: `gui.py`
- Modify: `tests/test_phase6_project_file.py`

**Interfaces:**
- Consumes: optional `on_project_save(save_as: bool, active_part: str | None)` constructor callback。
- Produces: main-connected `save_project_file()` 委派 main committed save；只允許把已存在 committed 板件的 `active_part` 當導航提示傳回；standalone fallback unchanged。

- [x] **Step 1: RED — designer save while draft=500 writes committed=400**
  real Tk：patch save path，透過 `designer.save_project_file_as()` 儲存，read back 必須 W=400。
- [x] **Step 2: GREEN — add project save callback**
  `_fix11_init` 保存 `_project_save_callback`；`_phase6_save_project_file` 若 callback 可呼叫則直接委派；main GUI 傳入 callback。
- [x] **Step 3: Verify standalone bridge test remains green**
  既有沒有 callback 的 holder/standalone 行為繼續使用 `_phase6_build_project_snapshot()`。

### Task 5: 回歸、文件與交付

**Files:**
- Modify: `修改日誌/20260823.md`
- Create: `docs/superpowers/verification/2026-08-23-phase6-project-session-verification.md`
- Package: FULL / UPDATE with one Asia/Taipei `YYYYMMDD_HHMMSS` timestamp。

**Interfaces:**
- Consumes: all implementation changes。
- Produces: verified distributable packages。

- [x] **Step 1: Run focused tests under Xvfb**
  `tests/test_phase6_project_session.py` + `tests/test_phase6_project_file.py` + UI-state transaction regressions。
- [x] **Step 2: Run py_compile**
  Compile all changed Python files。
- [x] **Step 3: Run full pytest under Xvfb**
  Compare failures with known external-fixture baseline; no new failures accepted。
- [x] **Step 4: Verify `config.ini` unchanged**
  Compare SHA256 before/after。
- [x] **Step 5: Write verification report and change log**
  Record exact commands/results, known environment exclusions, data-chain contract。
- [x] **Step 6: Package FULL / UPDATE**
  FULL contains whole project; UPDATE contains only changed/created files and excludes `config.ini`；run `zipfile -t` on both。
