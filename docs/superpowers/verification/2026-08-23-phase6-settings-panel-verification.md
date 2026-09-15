# Phase6 通用設定面板驗證報告

## 結論

本輪已將 schema 驅動的通用 Settings Tk/UI ownership 從 `fold_designer_bridge.py` 移至 `phase6_settings_panel.py`，而 `_settings_values` 仍維持 3D transaction draft Source of Truth；CornerType、assembly、EndCap FW、profile rebuild 與 manufacturing query ownership 未搬移。

## 架構驗證

- `phase6_settings_panel.py` 不包含 `_settings_values`。
- 不 import `ae_engine`、`fold_designer_bridge`、ProjectSession／ProjectController／WorkspaceController／FinalSceneView。
- Bridge 已移除通用 setting widget、page cache 建構、baseline rows、advanced toggle、左側全域 W/H/D/T/STOCK widget wiring。
- CornerType／assembly／EndCap FW 只透過 extension callback 插入 Panel。
- Bridge compatibility 欄位只指向 Panel 同一份 UI state。

## TDD / 回歸

- SettingsPanel ownership 專測：`11 passed`。
- Settings／UI／CornerType／ProjectFile 聚焦回歸：`89 passed`。
- 關聯資料鏈：`166 passed, 2 skipped`，另 4 項只因 `/mnt/data/自訂.p6fold` 缺件。
- 原始完整 suite：`322 passed, 2 skipped, 4 failed`；4 個 failure 全部為既知外部 fixture `/mnt/data/自訂.p6fold` 不存在。
- 明確排除該 4 項後：`322 passed, 2 skipped, 4 deselected, 0 failure`。
- `py_compile`：通過。
- Ownership 靜態檢查：`OWNERSHIP_OK`。

## 行為契約

- widget 修改只透過 stage callback，不由 Panel 保存 draft。
- advanced 顯示／隱藏不修改 draft。
- baseline data 只在展開時 lazy query。
- external settings 同步 Panel vars 不會再次 stage。
- 3D Cancel／Confirm 仍由既有 SettingsService + ProjectSession regression 保護。

## config.ini

本輪不修改 `config.ini`；修改前 SHA256：

`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`
