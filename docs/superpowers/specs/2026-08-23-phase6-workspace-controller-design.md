# Phase6 Workspace Controller 化設計規格

## 目標

把主 GUI 目前分散在 `fold_designer_part_bundle`、`_phase6_existing_parts`、`_fold_designer_last_part_key`、`fold_designer_box_body_profile` 的工作區協調狀態，收斂成單一 `Phase6WorkspaceController`。Controller 只擁有工作區狀態與一致性規則，不擁有 Tk widget、AE 幾何公式、ProjectSession 交易或 Settings runtime。

## 範圍

本輪只處理主 GUI 的 committed workspace cache：

- 實際存在板件 `existing_parts`
- 目前工作板件 `active_part`
- 各板件 fold profile stash `part_profiles`
- 箱身 Fold Chain `box_body_profile`
- 尚未有正式 3D/project workspace 前的 legacy presence fallback

不處理：

- `Phase6FoldDesignerApp._phase6_part_profiles` 的 3D draft 內部編輯狀態
- Head/Tail linked profile 幾何推導
- CornerType / EndCap 幾何
- ProjectSession committed/draft/baseline
- SettingsService
- renderer / DXF / NC
- UI 外觀與 widget layout

## 所有權

### `Phase6WorkspaceController`

唯一擁有：

- 是否已存在 authoritative workspace
- fallback / authoritative `existing_parts`
- committed workspace 的 `active_part`
- `part_profiles` stash
- `box_body_profile`

強制 invariant：

1. `box_body` 永遠存在，不能刪除。
2. authoritative workspace 一旦載入/提交，實際存在板件不再由 export checkbox 推導。
3. 刪除板件只改 presence，不刪除其 profile stash；重新加入可恢復原 profile。
4. `active_part` 必須是目前存在板件，否則回退到第一個存在板件。
5. Controller 對外回傳 defensive copy，外部不能靠修改 dict/list 偷改內部狀態。
6. Controller 不計算 Head/Tail linked geometry；GUI/既有幾何層計算完成後再把最終 profile stash 交給 Controller。

### `BoxCalculatorGUI`

只保留：

- Tk widget / checkbox / Notebook 顯示同步
- 將 GUI 的 legacy indicator toggle 作為「尚無 authoritative workspace」時的 fallback hint
- 呼叫既有 linked-profile resolver，再交給 Workspace Controller 保存
- snapshot view adapter

舊欄位名稱只允許作 compatibility property，不保存第二份 state：

- `fold_designer_part_bundle`
- `_phase6_existing_parts`
- `_fold_designer_last_part_key`
- `fold_designer_box_body_profile`

## 資料流

### 啟動、尚未開過 3D / 專案

`Phase6WorkspaceController(default_existing_parts)` 持有 legacy fallback。Indicator Box toggle 可在 `current_existing_parts(indicator_box_enabled=...)` 查詢時臨時影響 auxiliary presence，但不建立第二份 authoritative workspace。

### 3D 確定 / 專案載入

1. 既有 GUI/geometry adapter 解析 workspace。
2. linked Head/Tail profiles 仍由既有 `build_linked_endcap_xy_profiles()` 產生。
3. `workspace_controller.commit_workspace(...)` 原子保存 presence、active、profiles、box body profile。
4. GUI 只依 Controller 的 `existing_parts` 更新 checkbox、Notebook、結果列。

### 主 GUI 刪除/加入板件

`workspace_controller.set_part_presence(key, present)`：

- 改 presence
- 不刪 profile stash
- 若 active part 被刪除，自動選下一個有效板件
- GUI 再刷新 visibility/render cache

### 專案 snapshot

`_make_original_fold_designer_snapshot()` 與 `_compose_phase6_project_snapshot_from_main_gui()` 不直接讀 legacy dict，而從 Workspace Controller 取得：

- `existing_parts`
- `active_part`
- `part_profiles`
- `box_body_profile`

ProjectController / ProjectSession 邊界不變。

## 相容性

為避免其他既有程式與測試一次性全面改寫，`BoxCalculatorGUI` 暫時提供舊欄位 compatibility property。Property 的 getter/setter 必須直接委派同一 `Phase6WorkspaceController`，不得持有 shadow copy。

新的 production code 不得新增對這些 compatibility property 的依賴；新增程式一律使用 `workspace_controller`。

## 測試契約

至少鎖住：

1. `box_body` 永遠存在。
2. authoritative workspace 的存在板件不受 export checkbox/indicator fallback 影響。
3. 刪除 Tail 後 Tail profile stash 保留；重新加入仍存在。
4. 刪除 active part 後 active 自動落到合法板件。
5. 外部修改 controller 回傳 snapshot 不會污染內部 state。
6. 真 GUI 的 project load / 3D confirm / cancel / save 行為與前版一致。
7. DXF export 仍以 physical presence 而非 export checkbox 決定可否輸出。
8. `config.ini` 不得修改。

## 完成條件

- `gui.py` 不再直接保存四個 workspace backing state。
- 新增 `phase6_workspace_controller.py`。
- compatibility property 指向同一 Controller，沒有 mirror。
- 既有 ProjectSession / Settings / EndCap 測試無新增退化。
- 原始完整 suite 若仍只有 `/mnt/data/自訂.p6fold` 四個既知缺件，需另外排除這四項得到 0 failure 證據。
