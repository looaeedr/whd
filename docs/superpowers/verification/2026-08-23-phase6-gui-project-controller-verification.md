# Phase6 GUI Project Controller 化驗證報告

## 範圍

本輪只收斂主 GUI 的專案交易／持久化 orchestration：

- 新增 `phase6_project_controller.py`。
- `ProjectSession` 仍是 `project_path / loaded_baseline / committed / draft` Source of Truth。
- `gui.py` 保留 View → canonical snapshot 與 snapshot → View adapter。
- 不改 SettingsService、CornerType、EndCap 幾何、孔位、DXF/NC schema 或 UI 外觀。

## TDD 證據

### RED 1：Controller module 尚不存在

首次執行 `tests/test_phase6_project_controller.py`：

```text
ModuleNotFoundError: No module named 'phase6_project_controller'
```

之後只加入最小 Controller，使 active draft Save 可以在不呼叫 snapshot provider 的情況下保存 committed。

### RED 2：Main GUI 尚未擁有 Controller

新增 real Tk integration contract 後：

```text
AttributeError: 'BoxCalculatorGUI' object has no attribute 'project_controller'
```

再把 GUI 的 project/session ordering 改委派 Controller。

## Controller interface 驗證

`tests/test_phase6_project_controller.py` 鎖住：

- active draft Save 不呼叫 snapshot provider；
- active_part hint 只可指向 committed existing part；
- load 取代舊 draft 並更新 project path；
- confirm 提交 canonical committed；
- save 成功後才更新 project path；
- writer failure 不改 project path；
- GUI 不得直接呼叫 project read/write 或 ProjectSession ordering。

最終 Controller 純測試：`7 passed`。

## 最終新鮮驗證

### 語法

```text
python -m py_compile phase6_project_controller.py phase6_project_session.py
phase6_settings_center.py gui.py fold_designer_bridge.py ae_engine/*.py
→ 通過
```

### 聚焦回歸

範圍：Project Controller、project file、ProjectSession、SettingsService、UI state regressions。

```text
67 passed, 20 warnings
```

警告為 Linux 測試環境 DejaVu Sans 缺少部分繁中文字形，無功能 failure。

### 原始完整 suite

```text
284 passed, 2 skipped, 4 failed
```

4 個 failure 全部為既有測試硬編碼 `/mnt/data/自訂.p6fold`，目前交付環境沒有該外部 fixture：

1. `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
2. `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
3. `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
4. `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

### 明確排除上述 4 個既知外部 fixture

```text
284 passed, 2 skipped, 4 deselected, 65 warnings
0 failure
```

## Ownership 靜態檢查

`gui.py` 中不存在：

- `read_phase6_project(...)` direct call；
- `write_phase6_project(...)` direct call；
- `project_session.capture_committed(...)`；
- `project_session.begin_draft(...)`；
- `project_session.commit_draft(...)`；
- `project_session.cancel_draft(...)`；
- `project_session.load_project(...)`；
- `project_session.snapshot_for_save(...)`。

結果：`OWNERSHIP_OK`。

`app.project_session` 僅保留為 `app.project_controller.session` 同一物件 compatibility alias。

## 程式規模

- `gui.py`：8311 行。
- `phase6_project_controller.py`：98 行。

行數不是成功指標；重點是 project transaction interface knowledge 已從 GUI caller 收斂到 Controller。

## config.ini

修改前後 SHA256：

```text
5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d
```

未修改。

## 結論

本輪沒有新增功能 failure。`.p6fold` schema 與使用者操作流程保持不變，ProjectSession ordering／active-draft Save 保護／payload envelope／project path 失敗安全已由 `Phase6ProjectController` 單一 seam 擁有。
