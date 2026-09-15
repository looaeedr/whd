# Phase6 3D Designer 草稿工作區實作計畫

> **給代理工作者：** 必須使用 `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans` 逐項實作。本計畫以核取方塊追蹤。

**目標：** 建立純 Python `Phase6DesignerWorkspace`，收斂 3D Designer 的板件 presence、active/selected、profile/feature stash、dirty 與 switch transaction 狀態，讓 Bridge 只保留 UI／domain adapter。

**架構：** 新 owner 不知道 Tk、AE、renderer 或機械公式。Bridge 從 Editor 收集資料後寫入 workspace，切換 target 後再把 workspace/domain 資料套回 UI；舊欄位只保留同一 owner 的 compatibility property。

**技術堆疊：** Python 3、Tkinter、pytest、現有 Phase6 Fold Designer。

**規格：** `docs/superpowers/specs/2026-08-23-phase6-designer-workspace-design.md`

## 全域限制

- 不修改 `config.ini`。
- 不改 `.p6fold` schema。
- 不改 UI 版面／按鈕操作。
- 不搬 CornerType、linked EndCap、Hole preview 幾何到 workspace owner。
- 所有新文件與說明使用繁體中文；程式識別字保留原文。

---

### 任務 1：建立純 Python Workspace owner

**檔案：**
- 新增：`phase6_designer_workspace.py`
- 新增測試：`tests/test_phase6_designer_workspace.py`

**產出介面：**
- `Phase6DesignerWorkspace.from_snapshot(snapshot)`
- `select_part()` / `begin_switch()` / `finish_switch()` / `show_home()`
- `add_part()` / `remove_part()`
- `stash_profiles()` / `profiles_for()`
- `stash_features()` / `features_for()`
- `snapshot()` / `mark_clean()`

- [x] 先寫 failing tests，鎖 mandatory box body、defensive copy、remove/add restore、home、dirty、switch invariant。
- [x] 執行 `python -m pytest tests/test_phase6_designer_workspace.py -q`，確認因 module/API 不存在而 RED。
- [x] 實作最小 owner，不 import Tk/AE/renderer/domain builder。
- [x] 重跑同一測試，必須 GREEN。

### 任務 2：Bridge 初始化與 compatibility property

**檔案：**
- 修改：`fold_designer_bridge.py`
- 修改測試：`tests/test_phase6_designer_workspace.py`

**介面：**
- `self.designer_workspace`
- legacy property 指向同一 backing state

- [x] 新增真 designer RED：舊欄位不得存在 `__dict__`；property 與 workspace 同步。
- [x] 在 `_fix11_init()` 由 snapshot 建立 `designer_workspace`。
- [x] 將 legacy 欄位改成 compatibility property。
- [x] 跑 owner + GUI init 聚焦測試。

### 任務 3：收斂 add/remove/select/home 生命週期

**檔案：**
- 修改：`fold_designer_bridge.py`
- 修改：`tests/test_phase6_linked_fold_chain_and_parts.py`
- 修改：`tests/test_phase6_shared_assembly_and_dimensions.py`
- 修改：`tests/test_phase6_ui_state_regressions.py`

- [x] RED：production lifecycle methods 必須直接呼叫 `designer_workspace`，而非手動改 legacy lists/dicts。
- [x] 改 `select_part` / `remove_selected_part` / `add_part` / `remove_part` / `show_home`。
- [x] 新增 remove→add stash 回復與 active remove→home 回歸。
- [x] 真 Tk 測試確認操作流程不變。

### 任務 4：收斂 save/switch ordering

**檔案：**
- 修改：`fold_designer_bridge.py`
- 修改／新增：`tests/test_phase6_designer_workspace.py`
- 修改：`tests/test_phase6_3d_view_regressions.py`

- [x] RED：切換必須先 stash outgoing profiles，再 `begin_switch(target)`；switching flag 只能由 workspace 擁有。
- [x] `_fix11_save_current_part()` 改用 `stash_profiles()`。
- [x] `_fix11_activate_part()` 改用 `begin_switch()/finish_switch()`；profile/default 仍由 Bridge/domain builder 決定。
- [x] 保持 pending settings flush、delayed draw cancellation、holes preview、settings render、FinalScene render 原 ordering。
- [x] 跑 3D part switching regressions。

### 任務 5：Export / diagnostics / linked refresh 使用同一 workspace snapshot

**檔案：**
- 修改：`fold_designer_bridge.py`
- 修改：`tests/test_phase6_project_file.py`
- 修改：`tests/test_phase6_diagnostic_snapshot_ownership.py`

- [x] RED：export/project snapshot 不得分別手拼 presence/profile/features backing state。
- [x] 使用 `designer_workspace.snapshot()` 作為 existing_parts / active_part / profiles / features 的來源。
- [x] linked profile refresh 仍由 domain builder 算完再 stash，不移入 workspace。
- [x] 跑 ProjectSession / diagnostics / linked fold chain regressions。

### 任務 6：Ownership guard、完整回歸與文件

**檔案：**
- 新增／修改 ownership tests。
- 更新：`使用說明書.md`
- 更新：`docs/superpowers/README.md`
- 更新：`修改日誌/20260823.md`
- 更新踩坑庫。
- 新增：`docs/superpowers/verification/2026-08-23-phase6-designer-workspace-verification.md`

- [x] AST/static guard：owner 不 import Tk/AE/renderer/ProjectSession/SettingsService；Bridge production methods 不直接做 legacy workspace backing mutation。
- [x] `py_compile`。
- [x] 跑聚焦回歸。
- [x] 跑完整原始 suite，保留 `/mnt/data/自訂.p6fold` 缺件證據。
- [x] 明確排除既知 4 個 fixture 後跑 0-failure suite。
- [x] 確認 `config.ini` SHA256 未變。
- [x] 產出 FULL／UPDATE，共用 Asia/Taipei `YYYYMMDD_HHMMSS` 時間戳，UPDATE 不含 `config.ini`。
