# Phase6 Workspace Controller 化實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把主 GUI 的 committed workspace 狀態與 invariant 收斂到 `Phase6WorkspaceController`，保持 UI、幾何、ProjectSession 與 Settings 行為不變。

**Architecture:** 新 Controller 僅保存 presence / active part / profile stash / box body Fold Chain，並提供 defensive-copy API。GUI 保留 widget 同步與幾何 adapter；舊欄位改成同一 Controller 的 compatibility property，不保存 shadow state。

**Tech Stack:** Python 3、Tkinter、pytest、既有 Phase6 bridge / AE。

**Spec:** `docs/superpowers/specs/2026-08-23-phase6-workspace-controller-design.md`

## Global Constraints

- 不改 UI 外觀與操作流程。
- 不把 Head/Tail linked profile 幾何公式搬進 Controller。
- 不修改 `config.ini`。
- 不改 `.p6fold` schema。
- `box_body` 永遠存在。
- 刪除板件只改 presence，不刪 profile stash。
- 新 production code 不依賴 legacy workspace compatibility property。

---

### Task 1: 建立純 Python Workspace Controller

**Files:**
- Create: `phase6_workspace_controller.py`
- Create: `tests/test_phase6_workspace_controller.py`

**Interfaces:**
- Produces: `Phase6WorkspaceController`
- Produces: `current_existing_parts(indicator_box_enabled=False) -> set[str]`
- Produces: `commit_workspace(workspace: Mapping[str, object]) -> dict`
- Produces: `set_part_presence(key: str, present: bool) -> set[str]`
- Produces: `set_active_part(key: str | None) -> str | None`
- Produces: `workspace_snapshot() -> dict`

- [x] **Step 1: RED — defensive copy、mandatory box、authoritative presence、profile stash、active fallback**

```python
controller = Phase6WorkspaceController(default_existing_parts={"box_body", "head", "tail"})
controller.commit_workspace({
    "existing_parts": ["box_body", "tail"],
    "active_part": "tail",
    "part_profiles": {"tail": {"Y": [{"len": 10.0}]}},
})
controller.set_part_presence("tail", False)
assert controller.current_existing_parts() == {"box_body"}
assert controller.profile_for("tail")["Y"][0]["len"] == 10.0
assert controller.active_part == "box_body"
```

- [x] **Step 2: 執行新測試，確認因 module 不存在而 RED**

Run: `python -m pytest -q tests/test_phase6_workspace_controller.py`
Expected: FAIL during import because `phase6_workspace_controller` does not exist.

- [x] **Step 3: 實作最小 Controller**

實作 immutable boundary、exact presence、profile stash 與 active fallback；不得 import tkinter / ae_engine / gui。

- [x] **Step 4: 執行新測試，確認 GREEN**

Run: `python -m pytest -q tests/test_phase6_workspace_controller.py`
Expected: all PASS.

### Task 2: Main GUI 接上單一 Workspace Controller

**Files:**
- Modify: `gui.py`
- Modify: `tests/test_phase6_workspace_controller.py`
- Test: `tests/test_phase6_ui_state_regressions.py`
- Test: `tests/test_phase6_linked_fold_chain_and_parts.py`

**Interfaces:**
- Consumes: `Phase6WorkspaceController`
- Produces: `app.workspace_controller`
- Compatibility only: `fold_designer_part_bundle`, `_phase6_existing_parts`, `_fold_designer_last_part_key`, `fold_designer_box_body_profile`

- [x] **Step 1: RED — 真 GUI 必須有 workspace_controller，舊欄位不得是第二份 backing state**

```python
app = gui.BoxCalculatorGUI(root)
assert isinstance(app.workspace_controller, Phase6WorkspaceController)
app._phase6_existing_parts = {"box_body", "head"}
assert app.workspace_controller.current_existing_parts() == {"box_body", "head"}
```

- [x] **Step 2: 執行聚焦測試確認 RED**

Run: `xvfb-run -a python -m pytest -q tests/test_phase6_workspace_controller.py`
Expected: FAIL because GUI is not wired yet.

- [x] **Step 3: Wiring + compatibility property**

初始化 `workspace_controller`；移除四個 legacy backing assignments；property 直接委派 Controller。

- [x] **Step 4: `_phase6_current_existing_parts` / `_phase6_set_part_presence` 改由 Controller 擁有 invariant**

GUI 僅傳入 legacy indicator fallback hint，並負責刷新 widget/render cache。

- [x] **Step 5: 執行聚焦測試確認 GREEN**

Run: `xvfb-run -a python -m pytest -q tests/test_phase6_workspace_controller.py tests/test_phase6_ui_state_regressions.py`
Expected: PASS except no external fixture dependency.

### Task 3: Snapshot / load / 3D confirm 改吃 Controller

**Files:**
- Modify: `gui.py`
- Test: `tests/test_phase6_project_file.py`
- Test: `tests/test_phase6_linked_fold_chain_and_parts.py`

**Interfaces:**
- Consumes: `workspace_controller.workspace_snapshot()`
- Preserves: existing ProjectController / ProjectSession transaction behavior

- [x] **Step 1: RED — workspace store 後 Controller 必須保存重新推導的 Head/Tail profiles**

在既有 linked fold chain 測試旁新增 controller ownership assertion；預期舊版沒有 controller state。

- [x] **Step 2: `_store_fold_designer_workspace()` 保留幾何推導、改由 Controller 原子保存結果**

`build_linked_endcap_xy_profiles()` 仍在既有層；Controller 只接收最終 profiles。

- [x] **Step 3: snapshot compose/read 改用 Controller**

`existing_parts / active_part / part_profiles / box_body_profile` 從 Controller 取得，不直接讀 legacy backing state。

- [x] **Step 4: 專案與 3D 交易聚焦回歸**

Run: `xvfb-run -a python -m pytest -q tests/test_phase6_project_file.py tests/test_phase6_project_controller.py tests/test_phase6_linked_fold_chain_and_parts.py`
Expected: only the four known `/mnt/data/自訂.p6fold` fixture failures in the raw run; zero new failures.

### Task 4: Ownership guard、文件與完整回歸

**Files:**
- Modify: `使用說明書.md`
- Modify: `DELIVERY_README.md`
- Modify: `修改日誌/20260823.md`
- Modify: `個人AI檔案庫/06_踩坑記錄與防錯經驗庫.md`
- Create: `docs/superpowers/verification/2026-08-23-phase6-workspace-controller-verification.md`

- [x] **Step 1: ownership 靜態檢查**

確認 `phase6_workspace_controller.py` 不 import Tk/AE，且 `gui.py` 不再有四個 legacy backing assignment。

- [x] **Step 2: `py_compile`**

Run: `python -m py_compile gui.py phase6_workspace_controller.py phase6_project_controller.py phase6_project_session.py phase6_settings_center.py`
Expected: exit 0.

- [x] **Step 3: 完整原始 suite**

Run: `xvfb-run -a python -m pytest -q`
Expected: no new failures; known external fixture failures are reported separately.

- [x] **Step 4: 排除四個既知外部 fixture，取得 0-failure 證據**

Run full suite with the four exact `REAL_PROJECT=/mnt/data/自訂.p6fold` tests deselected.
Expected: 0 failure.

- [x] **Step 5: config.ini SHA256 比對**

Expected: before/after identical.

- [x] **Step 6: FULL / UPDATE 同時間戳封包與 CRC**

UPDATE 不含 `config.ini`；兩包使用 Asia/Taipei `YYYYMMDD_HHMMSS` 同一時間戳，並通過 `zipfile.testzip()` 與 `unzip -t`。
