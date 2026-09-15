# Phase6 3D Designer 草稿工作區設計規格

## 目標

將 `fold_designer_bridge.py` 目前分散的 3D 草稿板件生命週期狀態收斂到單一 `Phase6DesignerWorkspace`，讓「板件是否存在、目前 active/selected、profile/feature stash、dirty、切換中的交易狀態」有明確 owner；Bridge 只保留 Tk、Editor、Hole preview、manufacturing query 與幾何 adapter。

## 非目標

本輪不修改：

- 統一開孔編輯器。
- AE / `PartRenderData` 製造幾何。
- CornerType / EndCap FW / linked Fold Chain 的機械公式。
- `Phase6ProjectSession` / `Phase6WorkspaceController` / `SettingsService` 的既有 ownership。
- `.p6fold` schema。
- UI 版面、按鈕文案、操作流程。

## 現況問題

Bridge 目前同時保存並協調：

- `available_parts`
- `active_part_key`
- `selected_part_key`
- `_phase6_part_profiles`
- `_phase6_part_features`
- `_phase6_part_face_features`
- `_phase6_workspace_dirty`
- `_phase6_switching_part`

而 `save / activate / add / remove / show_home / export` 直接依賴這些欄位的先後順序。既有測試也大量直接呼叫 `_fix11_save_current_part()`、`_fix11_add_part()`、`_fix11_remove_part()` 或用 `SimpleNamespace` 偽造這些欄位，代表公開測試 seam 還是 implementation detail。

## 新 owner

新增 `phase6_designer_workspace.py`。

### `Phase6DesignerWorkspace`

純 Python；不得 import Tk、AE、renderer、Bridge、ProjectSession、SettingsService。

持有：

- `available_parts`
- `active_part`
- `selected_part`
- `part_profiles`
- `part_features`
- `part_face_features`
- `dirty`
- `switching`

### 主要介面

```python
workspace = Phase6DesignerWorkspace.from_snapshot(snapshot)
workspace.select_part(key)
workspace.begin_switch(key)
workspace.finish_switch()
workspace.show_home()
workspace.add_part(key, default_profiles=None, default_features=())
workspace.remove_part(key)
workspace.stash_profiles(key, profiles)
workspace.stash_features(key, features)
workspace.snapshot()
```

所有傳入／傳出 profile、feature dict/list 都做 defensive copy。

## Invariant

### 1. 箱身不可刪除

`remove_part("box_body")` 必須丟出 `ValueError`。

### 2. 刪除只移除 presence

刪除非箱身板件：

- 從 `available_parts` 移除。
- 若 selected/active 是該板件，清除 selection/activity。
- **不得刪除既有 `part_profiles` / `part_features` stash**。

因此 remove → add 可以恢復原資料。

### 3. 新增優先恢復 stash

`add_part()` 若 stash 已存在，不得以 factory defaults 覆蓋；只有 stash 不存在時才接受 caller 提供的 defaults。

### 4. `begin_switch()` 不做 UI／幾何

它只驗證目標板件存在、設定 `switching=True`、更新 selected/active；實際把 profile 放進 Bend UI、載入 holes、render，仍由 Bridge 做。

### 5. Home 是正式狀態

`show_home()` 清除 active/selected，但不清 stash、不清 available parts。

### 6. Dirty 的 owner 唯一

add/remove/stash 實際資料改變時設 `dirty=True`；`mark_clean()` 只有 snapshot 已交付後由 caller 明確呼叫。

### 7. 不接管機械語意

`Phase6DesignerWorkspace` 不得：

- 建立 standard/endcap profile。
- 讀寫 CornerType。
- 計算 linked EndCap。
- 將 holes 投影到 preview face。
- 決定 Fold UI tabs。

這些都由 Bridge 或現有 domain owner 完成後，以資料形式交給 workspace stash。

## Bridge 整合

`Phase6FoldDesignerApp` 持有：

```python
self.designer_workspace: Phase6DesignerWorkspace
```

舊欄位保留成 compatibility property：

- `available_parts`
- `active_part_key`
- `selected_part_key`
- `_phase6_part_profiles`
- `_phase6_part_features`
- `_phase6_part_face_features`
- `_phase6_workspace_dirty`
- `_phase6_switching_part`

但不得存在第二份 backing state；property 必須直接映射同一 `designer_workspace`。

production method 在新實作完成後，應直接使用 `designer_workspace`，不再依賴上述 legacy alias 做 ordering。

## Save / Switch ordering

切換板件仍由 Bridge 完成 UI 副作用，但 ordering 變成：

1. flush pending settings。
2. 若有 outgoing active part，Bridge 從 Editor 收集資料並 `workspace.stash_profiles(...)`。
3. `workspace.begin_switch(target)`。
4. Bridge 從 workspace 取得 target stash／domain defaults，套入 Bend UI。
5. Bridge 載入 holes preview。
6. settings panel/context sync。
7. FinalScene render。
8. `workspace.finish_switch()`。

## Export

Bridge 仍負責把 editor/domain 值轉成 `.p6fold` payload；presence/profile/feature 的原始 stash 必須從 `designer_workspace.snapshot()` 取得，避免再次手工拼多份 state。

## 回歸條件

至少鎖定：

1. remove → add 保留 profile/feature stash。
2. 切換時 outgoing profile 先 stash，再 active 改到 target。
3. Home 清 active/selected 但保留 stash。
4. active part 被刪除後回 Home。
5. export snapshot 的 existing_parts / active_part / part_profiles / features 來自同一 workspace snapshot。
6. compatibility property 不在 `designer.__dict__` 形成第二份 state。
7. owner module 不 import Tk / AE / renderer / ProjectSession / SettingsService。
