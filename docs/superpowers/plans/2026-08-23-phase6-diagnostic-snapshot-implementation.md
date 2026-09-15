# Phase6 診斷快照實作計畫

> **給代理執行者：** 必須使用 `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans`，依任務逐項實作；使用核取方塊追蹤完成狀態。

**目標：** 將 Phase6 診斷 schema、Scene／Material／FoldGuide 序列化與 all-part Final Geometry 聚合從 `fold_designer_bridge.py` 收斂到 `phase6_diagnostics.py`。

**架構：** Bridge 保留 Designer/Tk/project adapter；Diagnostics module 接受 plain context 與 injected render providers，回傳純 dict 診斷資料。Project snapshot 的 reloadable state 仍由 Bridge 建立，但 `final_geometry` 改由 Diagnostics 聚合。

**技術：** Python、Shapely、AE `DrawingScene` DTO、pytest。

**規格：** `docs/superpowers/specs/2026-08-23-phase6-diagnostic-snapshot-design.md`

## 全域限制

- 不改 diagnostic schema 與 project schema。
- 不改 manufacturing query／FinalScene／CornerType／Fold Profile。
- Diagnostics 不得依賴 Tk、Bridge、ProjectSession、SettingsService。
- `config.ini` 不得修改。
- FULL／UPDATE 共用 Asia/Taipei `YYYYMMDD_HHMMSS` 時間戳。

---

### 任務 1：建立純 Diagnostics module 與序列化 seam

**檔案：**
- 新增：`phase6_diagnostics.py`
- 新增：`tests/test_phase6_diagnostics_ownership.py`
- 修改：`fold_designer_bridge.py`

**介面：**
- 產出：`DiagnosticSnapshotContext`、`build_active_diagnostic_snapshot()`、`collect_final_geometry_diagnostics()`、`write_diagnostic_json()`。

- [x] **步驟 1：** 新增 RED 測試，要求 module 存在、diagnostic schema 不變、Scene/material/fold guide 可 JSON-safe 序列化，且 source 不 import Tk/Bridge/ProjectSession/SettingsService。
- [x] **步驟 2：** 執行 `python -m pytest -q tests/test_phase6_diagnostics_ownership.py`，確認因 module 尚不存在而 RED。
- [x] **步驟 3：** 實作最小 serializer 與 `DiagnosticSnapshotContext`；Bridge serializer 名稱改 direct alias/re-export。
- [x] **步驟 4：** 重跑 ownership 與既有 diagnostic writer/snapshot 測試，確認 GREEN。

### 任務 2：active diagnostic 聚合與 render error 隔離

**檔案：**
- 修改：`phase6_diagnostics.py`
- 修改：`fold_designer_bridge.py`
- 測試：`tests/test_phase6_diagnostics_ownership.py`
- 測試：`tests/test_phase6_tail_native_orientation_and_save.py`

**介面：**
- 使用：`build_active_diagnostic_snapshot(context, render_provider)`。

- [x] **步驟 1：** RED：render 成功時 `final_geometry.scene/material` 完整；render 失敗時 snapshot 仍產生且只寫 `render_error`。
- [x] **步驟 2：** Bridge `_phase6_build_diagnostic_snapshot()` 只組 context／payload 與注入 active render provider。
- [x] **步驟 3：** 保持 `phase6-fold-diagnostic-v1`、timestamp、settings/workspace/corner payload 欄位相容。
- [x] **步驟 4：** 跑 diagnostic 既有回歸，確認含洞 material 與 UTF-8 JSON 不退化。

### 任務 3：all-part Final Geometry diagnostics 收斂

**檔案：**
- 修改：`phase6_diagnostics.py`
- 修改：`fold_designer_bridge.py`
- 測試：`tests/test_phase6_diagnostics_ownership.py`
- 測試：`tests/test_phase6_project_file.py`

**介面：**
- 使用：`collect_final_geometry_diagnostics(part_keys, payload_provider, render_provider)`。

- [x] **步驟 1：** RED：三個 part 中一個 render provider 丟例外，另外兩個仍完整輸出；錯誤只存在該 row。
- [x] **步驟 2：** `_phase6_build_project_snapshot()` 保留 reloadable snapshot 組裝，但 `final_geometry` 改由 Diagnostics 聚合。
- [x] **步驟 3：** callback 缺失時維持每 part `3D final-scene provider is not connected`。
- [x] **步驟 4：** 跑 project file／ProjectSession／Workspace regressions。

### 任務 4：Ownership guard、文件、完整回歸與封包

**檔案：**
- 修改：`使用說明書.md`
- 修改：`DELIVERY_README.md`
- 修改：`docs/superpowers/README.md`
- 修改：`修改日誌/20260823.md`
- 修改：`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- 新增：`docs/superpowers/verification/2026-08-23-phase6-diagnostic-snapshot-verification.md`

- [x] **步驟 1：** 靜態 ownership guard：Bridge 不再定義 serializer/material-diagnostic 實作；Diagnostics 不依賴 Tk/Bridge/ProjectSession/SettingsService/manufacturing build。
- [x] **步驟 2：** `py_compile` 與 diagnostics/project 聚焦回歸。
- [x] **步驟 3：** 跑原始完整 suite；再明確排除既知 `/mnt/data/自訂.p6fold` 4 項要求 0 failure。
- [x] **步驟 4：** 驗證 `config.ini` SHA256 未變。
- [x] **步驟 5：** 同步繁中規格／使用說明／踩坑／修改日誌，建立同 timestamp FULL／UPDATE；UPDATE 排除 `config.ini`，兩包做 CRC。
