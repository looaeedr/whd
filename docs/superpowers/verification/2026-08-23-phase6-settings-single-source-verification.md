# Phase6 Settings 單一 Runtime 狀態來源驗證報告

## 驗證目標

確認 `SettingsService` 已成為 Phase6 **已確認 Runtime Settings** 的唯一所有者，並證明以下三種資料不再混為同一份狀態：

1. `ae.default_config`：Factory Defaults／「還原初始值」。
2. `config.ini`：下次啟動 persisted defaults。
3. `SettingsService`：目前 committed runtime；AE module globals 僅是 compatibility mirror。

Fold Designer `_settings_values` 刻意保留為 3D transaction-local draft；取消不提交、確定才提交。

## TDD RED → GREEN 證據

### 1. Immutable / defensive snapshot
- RED：`SettingsService` 尚不存在，測試在 public seam 直接失敗。
- GREEN：新增 `Phase6Settings` immutable Mapping 與 `SettingsService.snapshot()`；修改 `as_dict()` 回傳值不會反向污染 service。

### 2. Runtime update 與 INI 持久化分離
- RED：service 尚無 `update()`／`persist_defaults()`。
- GREEN：
  - `update({"w": 450})` → service W=450、AE.W=450、INI 保持原值。
  - `persist_defaults(values={"w": 500})` → INI W=500，但 service/AE 仍維持原 committed runtime。

### 3. Main GUI ownership
- RED：真 Tk `BoxCalculatorGUI` 沒有 `settings_service`。
- GREEN：Main GUI 建立單一 `SettingsService`；`_settings_state` 已移除，Tk trace／主設定收集／3D 確定套用都經 service。

### 4. 3D「儲存為預設值」真 Bug
- RED：main committed W=400、3D draft W=500，未確定先執行「儲存為預設值」；舊路徑會讓 `config.ini=500` **且 `AE.W=500`**，證明 draft 已污染目前 runtime。
- GREEN：改由 `SettingsService.persist_defaults(..., apply_runtime=False)` seam；結果 `config.ini=500`，service/AE 仍為 400。只有 3D「確定」才讓兩者成為 500。

### 5. 3D transaction
- Cancel：draft W=500 → service/AE committed 仍 W=400。
- Confirm：draft W=500 → service/AE committed 同步成 W=500。

## 聚焦回歸

執行：

```bash
xvfb-run -a python -m pytest -q \
  tests/test_phase6_settings_service.py \
  tests/test_endcap_regression_and_text_scale.py \
  tests/test_phase6_ui_state_regressions.py \
  tests/test_phase6_project_file.py \
  tests/test_phase6_shared_assembly_and_dimensions.py \
  tests/test_phase6_3d_view_regressions.py
```

結果：

```text
94 passed
```

Linux Xvfb 下只有 DejaVu Sans 缺部分繁體中文字形的 Tk/Matplotlib warning，沒有功能失敗。

## 完整回歸

原始完整 suite：

```bash
xvfb-run -a python -m pytest -q tests
```

結果：

```text
271 passed, 2 skipped, 4 failed
```

4 個 failure 與上一版完全相同，均為既有測試硬編碼讀取 `/mnt/data/自訂.p6fold`，本交付環境未提供該外部 fixture：

- `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
- `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
- `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
- `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

明確排除上述四個外部 fixture 測試後：

```text
271 passed, 2 skipped, 4 deselected
0 failure
```

## 語法檢查

```bash
python -m py_compile \
  phase6_settings_center.py \
  gui.py \
  fold_designer_bridge.py \
  phase6_project_session.py
```

結果：通過。

## Ownership 靜態檢查

- `gui.py` 不再包含 `_settings_state`。
- Main GUI production path 不直接呼叫 `load_settings_from_ae()`、`apply_settings_to_ae()`、`save_defaults_to_ini()`。
- Fold Designer `_settings_values` 仍存在，但只作 transaction-local draft，未升格成 committed source。
- `config.ini` persistence 與 runtime commit 已由 `SettingsService.persist_defaults()` / `SettingsService.update()` 分開。

## config.ini 保護

修改前／修改後 SHA256 相同：

```text
5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d
```

本輪交付不得覆蓋現場 `config.ini`；UPDATE 包必須排除該檔。

## 結論

本輪沒有新增測試 failure。已確認 Runtime Settings 的 ownership 已從 GUI dict / AE globals / INI 混合狀態收斂到 `SettingsService`；3D Save Defaults 的 runtime 污染 seam 已用真 RED→GREEN 鎖住，並保持既有 ProjectSession、CornerType、EndCap 與 Fold Designer transaction 行為。


## 最終交付封包

- FULL：`PHASE6_SETTINGS_SINGLE_SOURCE_FULL_20260823_123344.zip`
- UPDATE：`PHASE6_SETTINGS_SINGLE_SOURCE_UPDATE_20260823_123344.zip`
- 共用 Asia/Taipei 時間戳：`20260823_123344`。
- UPDATE 僅含本輪修改／新增檔，明確排除 `config.ini`。
- FULL／UPDATE 已以 Python `zipfile.testzip()` 與 `unzip -t` 進行 CRC／壓縮完整性檢查；UPDATE 另驗證不含 `config.ini`。
