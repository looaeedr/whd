# Phase6 Workspace Controller 化驗證報告

## 變更範圍

- 新增 `phase6_workspace_controller.py`
- `gui.py` workspace ownership 改由 Controller 提供
- 四個舊 workspace 欄位只留 compatibility property
- 既有 linked Head/Tail profile 幾何推導位置不變
- 修正跨專案 `box_body_profile` stale state
- 更新相關測試 fixture 與新增 Controller contract tests

## TDD 證據

1. 新 module 尚不存在時：`tests/test_phase6_workspace_controller.py` import RED。
2. 純 Controller 最小實作後：6 tests GREEN。
3. 真 GUI 尚未 wiring 時：缺 `workspace_controller` RED。
4. wiring 後：compatibility alias / single backing state GREEN。
5. ownership guard 在 production method 尚使用 legacy aliases 時 RED；全部改用 Controller 後 GREEN。
6. 載入無 box profile 的第二專案時 stale 999 Fold Chain RED；明確 None replacement 修正後 GREEN。

## 架構檢查

- `phase6_workspace_controller.py` 不含 `tkinter` import。
- `phase6_workspace_controller.py` 不含 `ae_engine` import。
- Head/Tail linked geometry 仍由既有 `build_linked_endcap_xy_profiles()` 推導。
- `gui.py` 四個 legacy workspace 名稱只存在 compatibility property 定義；production methods 由 AST ownership test 防止重新依賴。
- Controller 刪除後，presence / active / profile stash / replacement invariants 會重新散回多個 GUI caller，通過 deep-module deletion test。

## 回歸結果

### 關聯回歸

`158 passed, 2 skipped, 4 deselected, 0 failure`

涵蓋：Workspace Controller、ProjectController、ProjectSession、ProjectFile、SettingsService、linked Fold Chain、UI presence、EndCap ownership、shared assembly/dimensions。

### 原始完整 suite

`293 passed, 2 skipped, 4 failed`

四個 failure 全部為同一既知外部 fixture 缺件：`/mnt/data/自訂.p6fold`。

### 排除既知外部 fixture

`293 passed, 2 skipped, 4 deselected, 0 failure`

## 語法與設定

- `py_compile`：通過。
- `config.ini` 修改前／後 SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`，完全相同。

## 封包

最終交付檔名：

- `PHASE6_WORKSPACE_CONTROLLER_FULL_20260823_130323.zip`
- `PHASE6_WORKSPACE_CONTROLLER_UPDATE_20260823_130323.zip`

FULL / UPDATE 共用 Asia/Taipei 時間戳 `20260823_130323`；UPDATE 明確排除 `config.ini`。封包 CRC 與最終 ZIP SHA256 以交付回覆中的最終封包驗證結果為準。
