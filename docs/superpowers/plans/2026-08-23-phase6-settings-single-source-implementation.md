# Phase6 Settings 單一 Runtime 狀態來源實作計畫

> **代理執行要求：** 必須使用 `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans` 逐項執行；步驟以核取方塊追蹤。

**目標：** 讓 `SettingsService` 成為 Phase6 committed runtime settings 的唯一所有者，同時保留 3D transaction draft 隔離與 `config.ini` 明確持久化。

**架構：** `phase6_settings_center.py` 新增 immutable `Phase6Settings` 與 UI-agnostic `SettingsService`。Main GUI 只透過此 seam 更新 runtime；Fold Designer `_settings_values` 保留為 transaction draft；持久化 defaults 與 runtime commit 被明確分離。

**技術：** Python 3、Tkinter、configparser、pytest、既有 `ae_engine.ae` compatibility mirror。

**規格：** `docs/superpowers/specs/2026-08-23-phase6-settings-single-source-design.md`

## 全域限制

- `config.ini` 是 persisted defaults，不是 runtime Source of Truth。
- `ae.default_config` 仍是「還原初始值」唯一 Factory Defaults 來源。
- 3D `_settings_values` 是 transaction-local draft，不可因 Save Defaults 偷渡成 committed runtime。
- `.p6fold` schema 不變。
- 不改 CornerType、EndCap、Fold Profile、PartRenderData 幾何規則。
- 不拆 `gui.py` / `fold_designer_bridge.py`。
- `config.ini` 交付前 SHA256 必須與修改前相同。

---

### Task 1: 建立 SettingsService 深模組

**Files:**
- Modify: `phase6_settings_center.py`
- Create: `tests/test_phase6_settings_service.py`

**Interfaces:**
- Consumes: existing `SETTING_SPECS`, `load_settings_from_ae`, `load_factory_defaults_from_ae`, `apply_settings_to_ae`, `save_defaults_to_ini`.
- Produces: `Phase6Settings`, `SettingsService.snapshot()`, `factory_snapshot()`, `update()`, `persist_defaults()`.

- [x] **Step 1: 寫 RED：snapshot 必須 immutable / defensive**

```python
def test_settings_service_snapshot_is_defensive(fake_ae):
    service = SettingsService(fake_ae)
    snapshot = service.snapshot()
    copied = snapshot.as_dict()
    copied["w"] = 999
    assert service.snapshot()["w"] == 400.0
```

- [x] **Step 2: 執行 RED**

Run: `python -m pytest -q tests/test_phase6_settings_service.py::test_settings_service_snapshot_is_defensive`

Expected: FAIL/ERROR because `SettingsService` does not exist.

- [x] **Step 3: 最小實作 `Phase6Settings` / service startup**

實作 immutable Mapping snapshot；service constructor 讀 persisted settings、factory defaults，並把 current 套到 AE mirror。

- [x] **Step 4: GREEN**

Run: `python -m pytest -q tests/test_phase6_settings_service.py::test_settings_service_snapshot_is_defensive`

Expected: PASS.

- [x] **Step 5: 寫 RED：update 只改 runtime，不寫 INI**

```python
def test_update_changes_runtime_and_ae_without_persisting(fake_ae):
    service = SettingsService(fake_ae)
    service.update({"w": 450})
    assert service.snapshot()["w"] == 450.0
    assert fake_ae.W == 450.0
    assert read_ini_w(fake_ae.INI_PATH) == 400.0
```

- [x] **Step 6: GREEN：實作 changed-only update**

只 coercion 合法 key，僅把變更 key 傳給 `apply_settings_to_ae`。

- [x] **Step 7: 寫 RED：persist explicit draft 不得改 runtime**

```python
def test_persist_explicit_draft_does_not_commit_runtime(fake_ae):
    service = SettingsService(fake_ae)
    service.update({"w": 450})
    service.persist_defaults(values={"w": 500}, keys=("w",))
    assert read_ini_w(fake_ae.INI_PATH) == 500.0
    assert service.snapshot()["w"] == 450.0
    assert fake_ae.W == 450.0
```

- [x] **Step 8: GREEN：分離 persistence 與 runtime apply**

為 `save_defaults_to_ini(..., apply_runtime=True)` 增加 compatibility flag；service 固定用 `False`。

- [x] **Step 9: 驗 factory snapshot 不受 persisted/runtime 變動**

加入 factory test，確認來源只看 `default_config`。

- [x] **Step 10: 跑 module suite**

Run: `python -m pytest -q tests/test_phase6_settings_service.py tests/test_endcap_regression_and_text_scale.py`

Expected: 0 failures.

---

### Task 2: Main GUI runtime ownership 改接 SettingsService

**Files:**
- Modify: `gui.py`
- Modify: `tests/test_phase6_settings_service.py`

**Interfaces:**
- Consumes: `SettingsService` from Task 1.
- Produces: main GUI changes runtime only through `self.settings_service`.

- [x] **Step 1: 寫 RED：真 Tk main setting change 必須更新 service + AE**

```python
def test_main_gui_setting_edit_updates_service_and_ae():
    root = tk.Tk()
    app = BoxCalculatorGUI(root)
    app.w_var.set("451")
    root.update()
    assert app.settings_service.snapshot()["w"] == 451.0
    assert ae.W == 451.0
```

測試結束恢復原 AE W；不寫真實 `config.ini`。

- [x] **Step 2: 執行 RED**

Run under Xvfb. Expected: FAIL because GUI has no `settings_service`.

- [x] **Step 3: 最小整合**

改 `__init__`, `init_variables`, `_collect_main_setting_values`, `_apply_fold_designer_live_settings`, `_on_main_setting_var_changed`, `_apply_original_fold_designer_snapshot`, `_apply_ui_text_size_preference` 使用 service；移除 `_settings_state` runtime owner。

- [x] **Step 4: GREEN + 既有 UI 回歸**

Run: `xvfb-run -a python -m pytest -q tests/test_phase6_settings_service.py tests/test_phase6_ui_state_regressions.py`

Expected: 0 failures.

---

### Task 3: 3D Save Defaults 不得污染 committed runtime

**Files:**
- Modify: `gui.py`
- Modify: `tests/test_phase6_settings_service.py`

**Interfaces:**
- Consumes: `SettingsService.persist_defaults()`.
- Produces: `_save_fold_designer_defaults()` persistence-only behavior.

- [x] **Step 1: 寫 RED：3D draft Save Defaults 只改 INI**

用 temp INI + service committed W=400，呼叫 main GUI `_save_fold_designer_defaults(... values={"w":500})`；assert INI=500、service=400、AE=400。

- [x] **Step 2: 執行 RED**

Expected: FAIL because existing GUI path calls `save_defaults_to_ini` which applies draft to AE.

- [x] **Step 3: 最小整合**

`_save_fold_designer_defaults()` 改呼叫 `self.settings_service.persist_defaults(...)`；corner defaults 路徑保持原樣。

- [x] **Step 4: GREEN**

Run focused test; expect PASS.

- [x] **Step 5: 3D confirm/cancel transaction regression**

Run: `xvfb-run -a python -m pytest -q tests/test_phase6_project_file.py tests/test_phase6_settings_service.py`

Expected: 0 failures.

---

### Task 4: 完整資料鏈回歸、文件與交付

**Files:**
- Modify: `docs/superpowers/README.md`
- Modify: `使用說明書.md`
- Modify: `修改日誌/20260823.md`
- Create: `docs/superpowers/verification/2026-08-23-phase6-settings-single-source-verification.md`
- Modify/Create: project pitfall documentation only if an existing same-purpose file is present.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: verified FULL / UPDATE deliverables.

- [x] **Step 1: 跑聚焦回歸**

Run:
`xvfb-run -a python -m pytest -q tests/test_phase6_settings_service.py tests/test_endcap_regression_and_text_scale.py tests/test_phase6_ui_state_regressions.py tests/test_phase6_project_file.py tests/test_phase6_shared_assembly_and_dimensions.py tests/test_phase6_3d_view_regressions.py`

Expected: 0 failures.

- [x] **Step 2: `py_compile`**

Run: `python -m py_compile phase6_settings_center.py gui.py fold_designer_bridge.py phase6_project_session.py`

Expected: exit 0.

- [x] **Step 3: 跑完整原始 suite**

Run: `xvfb-run -a python -m pytest -q tests`

記錄所有 failure；若仍只有既知 `/mnt/data/自訂.p6fold` 缺件，另外以明確 deselect/ignore 相同 4 tests 驗 0 failure，其餘任何新增 failure 必須先修正。

- [x] **Step 4: 驗 `config.ini` 未被交付流程修改**

比對修改前 SHA256 `/mnt/data/phase6_settings_config_before.sha256`。

- [x] **Step 5: 同步繁中文件與踩坑庫**

記錄：runtime/persistence/draft 三層所有權、Save Defaults 不等於 commit runtime、Factory Defaults 不變。

- [x] **Step 6: 建 FULL / UPDATE**

檔名使用同一 Asia/Taipei `YYYYMMDD_HHMMSS`；UPDATE 僅含本輪修改/新增檔且不含 `config.ini`；FULL 為完整專案，排除 cache / `__pycache__` / 測試暫存。

- [x] **Step 7: 驗 ZIP**

對 FULL / UPDATE 執行 Python `ZipFile.testzip()`；必須回 `None`。
