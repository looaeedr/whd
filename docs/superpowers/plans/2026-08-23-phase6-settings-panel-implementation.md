# Phase6 通用設定面板實作計畫

> **供代理執行者：** 必須逐項使用 TDD 執行；每個 production 變更前先建立可觀察的 RED，再做最小 GREEN。

**目標：** 新增 `Phase6SettingsPanel`，把 schema 驅動的通用 Tk 設定 UI ownership 從 `fold_designer_bridge.py` 移出，同時保持 3D settings draft 與機械 editor ownership 不變。

**架構：** `phase6_settings_panel.py` 只持有 UI state 並透過 callbacks 與 Bridge 溝通。Bridge 繼續擁有 `_settings_values`、debounce、profile rebuild、CornerType/assembly/EndCap FW 與 transaction。

**技術棧：** Python、Tkinter/ttk、pytest、Xvfb。

**規格：** `docs/superpowers/specs/2026-08-23-phase6-settings-panel-design.md`

## 全域限制

- 不修改 `config.ini`。
- 不搬 `_settings_values` ownership。
- 不讓 `phase6_settings_panel.py` import AE / ProjectSession / manufacturing renderer。
- CornerType、assembly、EndCap FW editor 只能由 extension callback 注入。
- 所有可翻譯交付文件使用繁體中文。

---

### 任務 1：建立純 UI 分類與顯示 helper

**檔案：**
- 建立：`phase6_settings_panel.py`
- 建立：`tests/test_phase6_settings_panel_ownership.py`

**介面：**
- `setting_number_text(value) -> str`
- `baseline_row_text(row) -> str`
- `partition_setting_specs(context, specs, hidden_keys) -> SettingSpecGroups`

- [x] 先寫 RED：一般 / baseline / advanced / Corner compatibility 分組與 baseline row 文字。
- [x] 執行指定測試，確認因 module/interface 不存在而失敗。
- [x] 實作最小 helper，完全不 import Bridge/AE。
- [x] 重跑指定測試至 GREEN。

### 任務 2：建立 `Phase6SettingsPanel` page cache 與欄位 widgets

**檔案：**
- 修改：`phase6_settings_panel.py`
- 修改：`tests/test_phase6_settings_panel_ownership.py`

**介面：**
- `Phase6SettingsPanel(...callbacks...)`
- `build_settings_center(parent, renderer_widget, initial_context)`
- `render_context(context)`
- `invalidate_context(context)`
- `toggle_advanced()`
- `toggle_baseline_data()`

- [x] RED：Panel 依 SettingSpec 建立 var；改值只呼叫 stage callback。
- [x] RED：advanced toggle 不改 values snapshot。
- [x] RED：baseline query 只在展開時呼叫。
- [x] 實作最小 page cache / widget / lazy baseline view。
- [x] 用 Xvfb 跑 Panel 測試至 GREEN。

### 任務 3：建立 domain editor extension seam

**檔案：**
- 修改：`phase6_settings_panel.py`
- 修改：`tests/test_phase6_settings_panel_ownership.py`

**介面：**
- `render_context_extensions(parent, context, start_row)` callback
- `sync_context_extension(page, context)` callback

- [x] RED：Panel 本身不 import CornerType/assembly/EndCap FW，但可接受 extension 建立額外 controls。
- [x] 實作 extension state 保存與 context render 後同步。
- [x] 重跑 Panel tests 至 GREEN。

### 任務 4：Bridge 接入 `Phase6SettingsPanel`

**檔案：**
- 修改：`fold_designer_bridge.py`
- 修改：`tests/test_phase6_settings_panel_ownership.py`
- 視既有測試需求修改：`tests/test_phase6_ui_state_regressions.py`

**介面：**
- Bridge 建立 `self.settings_panel`。
- Bridge 的 domain extension callback 內呼叫既有 `_phase6_build_assembly_settings`、`_phase6_build_endcap_fw_settings`、`_phase6_build_corner_settings`。
- Bridge 的 stage callback 呼叫既有 `_phase6_stage_setting_update()`。

- [x] RED：Bridge source 仍含 `_phase6_add_setting_widget/_phase6_build_settings_page/_phase6_toggle_baseline_data` 等通用 UI 實作。
- [x] 接入 Panel，移除 Bridge 中通用 UI implementation。
- [x] 必要的舊公開 method 只保留 direct delegation/property compatibility，不保留第二套 state。
- [x] 跑 settings/UI/CornerType regression 至 GREEN。

### 任務 5：左側全域 controls 收斂到 Panel

**檔案：**
- 修改：`phase6_settings_panel.py`
- 修改：`fold_designer_bridge.py`
- 修改：`tests/test_phase6_settings_panel_ownership.py`

**介面：**
- `build_left_global_controls(parent, baseline_models, initial_model, unknown_model)`
- callbacks：baseline changed、stage setting、flush、UI text size、save global defaults。

- [x] RED：W/H/D/T／文字大小／STOCK 由 Panel 擁有 vars，Bridge 不保留第二份 backing vars。
- [x] 搬 UI wiring，Bridge 保留 domain callback。
- [x] 驗證 baseline model change、UI text scaling、Save Defaults 行為。

### 任務 6：交易與完整資料鏈回歸

**檔案：**
- 修改：`tests/test_phase6_settings_panel_ownership.py`
- 必要時修改既有測試 fixture，但不得在 production 加 fallback 後門。

- [x] 驗證 3D draft setting 取消不污染 Main committed。
- [x] 驗證確定後 settings 仍正常提交。
- [x] 驗證 CornerType/assembly/EndCap FW editor 正常。
- [x] 跑 settings、ProjectSession、FinalScene、linked profile 關聯回歸。
- [x] 跑完整原始 suite，記錄既有 `/mnt/data/自訂.p6fold` 缺件。
- [x] 明確排除該外部 fixture 後跑 0-failure suite。

### 任務 7：文件、所有權 guard 與封包

**檔案：**
- 修改：`使用說明書.md`
- 修改：`DELIVERY_README.md`
- 修改：`修改日誌/20260823.md`
- 修改：`個人AI檔案庫/06_踩坑記錄與防錯經驗庫.md`（若實際路徑存在）
- 建立：`docs/superpowers/verification/2026-08-23-phase6-settings-panel-verification.md`

- [x] ownership guard：Panel 不依賴 AE/Project/manufacturing，Bridge 不再擁有通用 settings UI 實作。
- [x] `py_compile`。
- [x] 比對 `config.ini` SHA256。
- [x] 所有計畫 checkbox 勾選完成。
- [x] 以 Asia/Taipei `YYYYMMDD_HHMMSS` 同一時間戳建立 FULL／UPDATE。
- [x] UPDATE 排除 `config.ini`、BACKUP、快取。
- [x] 對兩包執行 `zipfile.testzip()` 與 `unzip -t`。
