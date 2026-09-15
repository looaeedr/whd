# Phase6 通用設定面板深模組設計規格

## 目的

把 `fold_designer_bridge.py` 內「schema 驅動的通用 Tk 設定面板」抽成 `phase6_settings_panel.py`，讓 Bridge 不再同時擁有設定 UI 建構、頁面快取、baseline lazy view 與進階欄位顯示規則。

本輪不改變任何設定值、機械公式、CornerType、assembly、EndCap FW、ProjectSession 或 manufacturing query 行為。

## Source of Truth 邊界

- `phase6_settings_center.py`：`SettingSpec`、context、預設值與 persisted/runtime settings schema。
- `fold_designer_bridge.py::_settings_values`：3D transaction 期間的 settings draft；本輪不搬移、不複製。
- `phase6_settings_panel.py`：只擁有 Tk/UI state，例如 `StringVar/BooleanVar`、page cache、目前 context、advanced 是否顯示、baseline data 是否展開。
- CornerType／assembly／EndCap FW：仍由既有 domain owner + Bridge adapter 處理，不進 SettingsPanel。

## 模組介面

新增 `Phase6SettingsPanel`，由 Bridge 建立並注入 callback：

- `values_snapshot() -> Mapping[str, object]`
- `stage_setting_update(key, value) -> None`
- `flush_settings() -> object`
- `save_defaults(context) -> bool`
- `query_baseline_rows(context, model, values) -> Iterable[Mapping]`
- `is_unknown_baseline(model) -> bool`
- `should_show_baseline_data(context, baseline_specs) -> bool`
- `render_context_extensions(parent, context, start_row) -> SettingsPanelExtensionState`
- `sync_context_extension(page, context) -> None`

其中 `render_context_extensions` 是唯一 domain editor extension seam；Bridge 用它插入 assembly / EndCap FW / CornerType controls。

## SettingsPanel 擁有的責任

1. 依 `settings_for_context()` 與 `SettingSpec` 建立一般欄位。
2. 排除 left editor 已擁有的 setting keys。
3. 區分一般、baseline-only、advanced、Corner compatibility hidden groups。
4. 建立與保存 `setting_vars`。
5. 管理 page cache 與 context 切換。
6. advanced 顯示／隱藏。
7. baseline data lazy query、顯示文字與展開／收合。
8. 右側 settings center header/footer 與「儲存預設值」按鈕文字。
9. 左側全域 W/H/D/T、文字大小、STOCK 與基準型號 widgets 的通用 UI wiring。
10. 只透過 callback stage/flush/save，不直接改 manufacturing state。

## Bridge 保留的責任

- `_settings_values` 與 `_phase6_input_snapshot` transaction draft。
- `_phase6_stage_setting_update()` / `_phase6_flush_pending_settings()` / `_phase6_apply_setting_updates()`。
- `_phase6_refresh_profiles_from_settings()` 與 manufacturing redraw。
- `_phase6_build_corner_settings()`。
- `_phase6_build_assembly_settings()`。
- `_phase6_build_endcap_fw_settings()`。
- `_phase6_reset_initial_values()` 的 factory reset 與 profile rebuild。
- confirm/cancel transaction。
- baseline model 改變後的 domain state 切換。

## UI-only state

以下狀態移入 `Phase6SettingsPanel`，Bridge 若需相容名稱只能透過 property 指向同一 backing state，不得保留第二份：

- `setting_vars`
- `_settings_page_cache`
- `_settings_current_page`
- `settings_context`
- `advanced_settings_visible`
- `_phase6_settings_rendering`
- `baseline_data_frame`
- `baseline_data_toggle_button`
- `baseline_setting_cells`
- settings center widgets
- left global widget vars / controls

`_phase6_settings_guard` 不搬；它保留在 Bridge，因為它同時保護外部 settings apply / reset / transaction wiring。

## 驗證契約

1. 同一 `SettingSpec` 在 Panel 建立正確 widget；修改 var 只呼叫 `stage_setting_update`，不直接更新 AE 或 profile。
2. advanced 收合只改 UI state，不刪 draft 值。
3. baseline data 只有展開時才呼叫 query callback；收合不觸發 manufacturing。
4. `Phase6SettingsPanel` 不 import `ae_engine`、`fold_designer_bridge`、`phase6_project_session`、`phase6_project_controller`、`phase6_workspace_controller`、`phase6_final_scene_view`。
5. Bridge 不再擁有通用 setting widget/page/baseline/advanced 實作。
6. CornerType／assembly／EndCap FW controls 仍透過 extension seam 正常顯示與同步。
7. 3D draft W=500 後 Cancel，Main committed W 仍維持原值；Panel 不成為第二個 Source of Truth。
8. `config.ini` 不因本輪重構被修改。

## 非目標

- 不修改 SettingsService。
- 不變更 SettingSpec schema。
- 不重寫 CornerType editor。
- 不改 manufacturing query。
- 不改 Fold Profile。
- 不拆 project toolbar / transaction buttons。
