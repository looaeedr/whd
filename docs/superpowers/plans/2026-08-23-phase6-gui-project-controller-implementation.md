# Phase6 GUI 專案 Controller 化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把 `.p6fold` 讀寫、ProjectSession 交易 ordering、3D draft 儲存保護與 active_part 導航提示從 `gui.py` 收斂到 `Phase6ProjectController`。

**Architecture:** 新增純 Python `phase6_project_controller.py`，依賴既有 `ProjectSession` 與可注入的 project read/write adapters。`BoxCalculatorGUI` 只保留 snapshot compose/apply 與 Tk 對話框，並以相容 alias 暫時暴露同一個 `ProjectSession`。

**Tech Stack:** Python 3、Tkinter、pytest、既有 `phase6_project_file.py` / `phase6_project_session.py`。

**Spec:** `docs/superpowers/specs/2026-08-23-phase6-gui-project-controller-design.md`

## Global Constraints

- 不更動 `.p6fold` schema。
- Controller 不 import Tkinter、不讀任何 widget。
- ProjectSession 仍是 committed/draft/path 的唯一 Source of Truth；Controller 不保存第二份 mirror。
- active 3D draft 儲存時不可呼叫主 GUI snapshot provider。
- `active_part` 只可更新為 committed `existing_parts` 中已存在的板件。
- 不改 SettingsService、CornerType、EndCap、2D/3D 幾何與 UI 外觀。
- `config.ini` 不得修改。

---

### Task 1: 建立 Phase6ProjectController 深模組

**Files:**
- Create: `phase6_project_controller.py`
- Create: `tests/test_phase6_project_controller.py`

**Interfaces:**
- Consumes: `ProjectSession`, `read_project(path)`, `write_project(path, payload)`, `PHASE6_PROJECT_SCHEMA`。
- Produces: `Phase6ProjectController.project_path`, `has_draft`, `capture_committed()`, `begin_designer()`, `cancel_designer()`, `confirm_designer()`, `build_payload()`, `save()`, `load()`。

- [x] **Step 1: RED — active draft Save 不得呼叫 snapshot provider**

```python
def test_active_draft_build_payload_uses_committed_without_calling_snapshot_provider():
    controller = make_controller()
    controller.capture_committed({"w": 400.0, "existing_parts": ["box_body", "head"]})
    controller.begin_designer(lambda: (_ for _ in ()).throw(AssertionError("provider must not run")))
    payload = controller.build_payload(
        lambda: (_ for _ in ()).throw(AssertionError("provider must not run")),
        active_part_hint="head",
    )
    assert payload["snapshot"]["w"] == 400.0
    assert payload["snapshot"]["active_part"] == "head"
```

Run: `python -m pytest tests/test_phase6_project_controller.py -q`
Expected: FAIL because `phase6_project_controller` does not exist.

- [x] **Step 2: GREEN — 實作最小 Controller 與 payload 規則**

Controller 必須：

```python
class Phase6ProjectController:
    def __init__(self, *, session=None, read_project, write_project, schema, clock=None): ...
    def capture_committed(self, snapshot): ...
    def begin_designer(self, snapshot_provider): ...
    def cancel_designer(self): ...
    def confirm_designer(self, committed_snapshot): ...
    def build_payload(self, snapshot_provider, *, active_part_hint=None): ...
    def save(self, path, snapshot_provider, *, active_part_hint=None): ...
    def load(self, path): ...
```

`begin_designer()` 在無 active draft 時先 capture provider 的 canonical snapshot，再 `session.begin_draft()`；若 caller 已先 capture committed，仍允許使用現有 committed。

- [x] **Step 3: GREEN 驗證**

Run: `python -m pytest tests/test_phase6_project_controller.py -q`
Expected: PASS.

- [x] **Step 4: 增加 load / confirm / invalid active_part 契約測試**

```python
def test_invalid_active_part_hint_cannot_change_committed_navigation(): ...
def test_load_replaces_old_draft_and_returns_payload_and_committed(): ...
def test_confirm_designer_commits_canonical_snapshot_once(): ...
```

Run: `python -m pytest tests/test_phase6_project_controller.py -q`
Expected: PASS.

---

### Task 2: 將 GUI 專案檔與 ProjectSession ordering 委派給 Controller

**Files:**
- Modify: `gui.py:1-220`
- Modify: `gui.py:566-620`
- Modify: `gui.py:1594-1700`
- Modify: `gui.py:1769-1899`
- Test: `tests/test_phase6_project_file.py`
- Test: `tests/test_phase6_project_session.py`

**Interfaces:**
- Consumes: Task 1 的 `Phase6ProjectController`。
- Produces: `BoxCalculatorGUI.project_controller`；`BoxCalculatorGUI.project_session` 保留為同一 session 的相容 alias。

- [x] **Step 1: RED — GUI 應存在 project_controller 且與 project_session 共用同一 session**

在 `tests/test_phase6_project_file.py` 新增：

```python
def test_main_gui_project_controller_owns_same_project_session():
    app = make_app()
    assert app.project_controller.session is app.project_session
```

Run under Xvfb: `xvfb-run -a python -m pytest tests/test_phase6_project_file.py::test_main_gui_project_controller_owns_same_project_session -q`
Expected: FAIL because `project_controller` does not exist.

- [x] **Step 2: GREEN — GUI 初始化與 project path compatibility property 改委派**

`gui.py` 改為建立：

```python
self.project_controller = Phase6ProjectController(
    session=ProjectSession(),
    read_project=read_phase6_project,
    write_project=write_phase6_project,
    schema=PHASE6_PROJECT_SCHEMA,
)
self.project_session = self.project_controller.session
```

`_phase6_loaded_project_path` getter/setter 委派 `project_controller`。

- [x] **Step 3: RED/GREEN — payload / write / load 改委派**

`_build_phase6_project_payload()` 只呼叫：

```python
return self.project_controller.build_payload(
    self._compose_phase6_project_snapshot_from_main_gui,
    active_part_hint=active_part_hint,
)
```

`_write_phase6_project_to_path()` 只呼叫 controller `save()`；`load_phase6_project()` 用 controller `load()`。

Run: `xvfb-run -a python -m pytest tests/test_phase6_project_file.py tests/test_phase6_project_session.py -q`
Expected: PASS.

- [x] **Step 4: RED/GREEN — 3D begin / cancel / confirm 改委派**

`open_original_fold_designer()`：

```python
designer_snapshot = self.project_controller.begin_designer(
    self._compose_phase6_project_snapshot_from_main_gui
)
```

cancel 使用 `project_controller.cancel_designer()`；confirm 在 main GUI 已 apply payload 並重新 compose 後使用 `project_controller.confirm_designer(committed_snapshot)`。

Run: `xvfb-run -a python -m pytest tests/test_phase6_project_file.py tests/test_phase6_project_session.py tests/test_phase6_tail_native_orientation_and_save.py -q`
Expected: PASS.

---

### Task 3: 收斂 import 與移除 GUI 內重複 orchestration

**Files:**
- Modify: `gui.py`
- Test: `tests/test_phase6_project_controller.py`
- Test: `tests/test_phase6_project_file.py`

**Interfaces:**
- Consumes: `Phase6ProjectController`。
- Produces: GUI 不再直接 import/use `read_phase6_project`, `write_phase6_project`, `datetime` 僅在其他功能需要時保留。

- [x] **Step 1: 靜態 ownership guard**

新增測試讀取 `gui.py`，確認 project file I/O 只存在於 controller module：

```python
def test_gui_does_not_directly_call_project_file_read_write():
    source = Path("gui.py").read_text(encoding="utf-8")
    assert "read_phase6_project(" not in source
    assert "write_phase6_project(" not in source
```

Run: `python -m pytest tests/test_phase6_project_controller.py -q`
Expected: RED before import cleanup, GREEN after cleanup.

- [x] **Step 2: 移除重複 ordering code**

GUI 不再自行判斷 `project_session.has_draft` 來決定 Save capture；不再自行組 `schema/saved_at/final_geometry` envelope。

- [x] **Step 3: 聚焦回歸**

Run: `xvfb-run -a python -m pytest tests/test_phase6_project_controller.py tests/test_phase6_project_file.py tests/test_phase6_project_session.py tests/test_phase6_settings_service.py tests/test_phase6_ui_state_regressions.py -q`
Expected: PASS.

---

### Task 4: 完整回歸、文件與交付

**Files:**
- Modify: `docs/superpowers/specs/2026-08-23-phase6-gui-project-controller-design.md`
- Modify: `docs/superpowers/plans/2026-08-23-phase6-gui-project-controller-implementation.md`
- Create: `docs/superpowers/verification/2026-08-23-phase6-gui-project-controller-verification.md`
- Modify: `修改日誌/20260823.md`
- Modify: `個人AI檔案庫/06_踩坑記錄與防錯經驗庫.md` if present
- Modify: `DELIVERY_README.md`
- Modify: `使用說明書.md`

**Interfaces:**
- Consumes: Tasks 1–3 完成的 tree。
- Produces: 同時間戳 FULL / UPDATE ZIP。

- [x] **Step 1: 語法與聚焦驗證**

Run:

```bash
python -m py_compile phase6_project_controller.py phase6_project_session.py phase6_settings_center.py gui.py
xvfb-run -a python -m pytest \
  tests/test_phase6_project_controller.py \
  tests/test_phase6_project_file.py \
  tests/test_phase6_project_session.py \
  tests/test_phase6_settings_service.py \
  tests/test_phase6_ui_state_regressions.py -q
```

Expected: 0 failure.

- [x] **Step 2: 完整原始 suite**

Run: `xvfb-run -a python -m pytest -q`
Expected: 若仍只有既知 `/mnt/data/自訂.p6fold` 缺件 4 項，保留原始證據並執行既有明確 deselect 版完整 suite，要求 0 failure。

- [x] **Step 3: config.ini integrity**

起始 SHA256 必須維持：

`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`

- [x] **Step 4: 文件同步與封包**

FULL / UPDATE 使用同一 Asia/Taipei `YYYYMMDD_HHMMSS`。UPDATE 不含 `config.ini`，並對兩包執行 `zipfile.testzip()` 與 `unzip -t`。
