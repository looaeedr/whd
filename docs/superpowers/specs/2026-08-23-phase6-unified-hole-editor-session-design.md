# Phase6 統一開孔編輯器交易狀態機設計

## 目標

把 `gui.py::_open_unified_hole_editor()` 內分散的開孔編輯交易狀態收斂到純 Python 深模組 `Phase6HoleEditorSession`，讓 Tk/Canvas 只負責事件與顯示，Session 單一負責多 context 草稿、選取、active edit、Undo、Confirm/Cancel 的 ordering 與 invariant。

## 不做的事

- 不搬 Tk widget 建立與 Canvas renderer。
- 不搬 `CanvasTransform`、hit-test、reference distance、surface clamp 等幾何公式。
- 不重寫 `sheetmetal_features` 的孔型、排列、移動與合法性判斷。
- 不改 Door 指示燈盒／小門 manufacturing geometry。
- 不碰 `config.ini`。

## 現況問題

`_open_unified_hole_editor()` 約 1494 行，內含 63 個巢狀函式。`selected`、`active_snapshot`、`undo_history_ref`、`context_feature_lists`、`context_original_features`、`active_context_key` 分散被插入、拖曳、旋轉、reference edit、process toggle、delete、round pattern、context switch、Confirm/Cancel 同時修改。呼叫者必須知道「先 commit/cancel 哪個 transient edit、何時 push Undo、切 context 時怎麼清選取」等 ordering，造成狀態機知識留在 Tk method。

## 模組 seam

新增 `phase6_hole_editor_session.py`：

```python
session = Phase6HoleEditorSession("door", door_features, max_undo_steps=50)
session.execute(HoleEditorAction.select(index))
session.execute(HoleEditorAction.insert(feature))
session.execute(HoleEditorAction.replace_selected(feature))
session.execute(HoleEditorAction.commit_active(keep_selected=False))
session.execute(HoleEditorAction.cancel_active())
session.execute(HoleEditorAction.replace_selected_committed(feature))
session.execute(HoleEditorAction.delete_selected())
session.execute(HoleEditorAction.undo())
session.execute(HoleEditorAction.preview_all(features, selected_index=index))
session.activate_context("indicator_box", indicator_features)
session.finish(commit=False)
```

外部主要介面只有：

- `execute(action)`：執行封閉 editor action。
- `activate_context(key, feature_list)`：切換 context；切換前自動取消未確認 active edit，並重置選取與該次 Undo scope。
- `snapshot()`：回傳目前 context、selection、features、active edit、undo depth 的唯讀快照。
- `finish(commit=bool)`：Confirm All 保留所有 context 現況；Cancel All 恢復每個 context 第一次登錄時的 original snapshot。

## Active Edit 模型

Session 不再只保存 `(index, old_feature)`，而是在 active edit 開始時保存**整個 active context 的 before snapshot**。這能把以下動作統一成同一交易：

- 新插入孔
- 拖曳
- 旋轉
- 十字基準變更
- reference distance 移動
- 圓孔排列 preview

`cancel_active()` 直接恢復 before snapshot；`commit_active()` 僅在內容真的有變化時把 before snapshot 推進 Undo。

## Immediate committed action

process toggle、delete 仍維持既有「立即成為 committed action」語意：若前面有 active edit，先 commit；再把操作前 snapshot 推進 Undo，完成修改，清 active transaction。

Session 不知道 `CUTTING/BLIND_HOLE` 如何轉換；Tk adapter 仍用既有 `feature_with_process()` 產生 replacement，再把 replacement 交給 Session。

## 多 Context invariant

- 初始 context 立即記錄 original snapshot。
- 新 context 第一次 `activate_context()` 時才記錄 original snapshot。
- context switch 前若有 transient edit，一律 Cancel，不偷偷 Commit。
- 切換後 selection 清空、active edit 清空、Undo scope 重置，維持現況行為。
- Cancel All 恢復所有已登錄 context original snapshot。
- Confirm All 保留所有 context 現況，即使目前有未按局部「確定」的 transient edit。

## 圓孔排列

圓孔排列的幾何仍由 `generate_round_fill()` / `generate_round_refill()` / `align_circle_to_neighbor()` 產生。Session 只接手 transaction：preview 用 `preview_all()`，對話框取消用 `cancel_active()`，確定用 `commit_active()`。

## Ownership 限制

`phase6_hole_editor_session.py`：

- 不 import `tkinter`。
- 不 import `ae_engine` renderer / ProjectSession / SettingsService。
- 不 import `gui.py`。
- 不做 surface bounds、hit-test、reference distance、孔位幾何推導。

`gui.py::_open_unified_hole_editor()`：

- 不再自行建立 `selected`、`active_snapshot`、`undo_history_ref`、`context_feature_lists`、`context_original_features`。
- 不再自行實作 active edit before/restore/Undo ordering。
- 保留 Tk-only state：dragging、transform、insert mode、overlay widgets、after callbacks、round window、indicator widgets。

## 相容與風險控制

- feature list 仍是原本 caller 提供的 mutable list，Session 直接管理該 list，不建立第二份 committed source。
- Session snapshot 回傳 defensive tuple/list copy，不讓 caller 繞過 transaction 修改 owner 內部 metadata。
- 不改孔 feature 型別與 JSON/專案 schema。

## 驗證

TDD 必須鎖：

1. 插入 → Cancel Active 還原。
2. 插入 → Commit → Undo 還原。
3. Replace/拖曳/旋轉 → Cancel 還原。
4. committed replacement → Undo。
5. Delete → Undo。
6. context switch 先取消 transient edit。
7. context 間 feature list 不互相污染。
8. Cancel All 恢復所有 context。
9. Confirm All 保留所有 context。
10. Undo 上限 50。
11. 圓孔 preview 的 Commit/Cancel 走同一 transaction。
12. ownership guard：Session 不依賴 Tk/AE/Project/Settings，GUI 不重建舊交易狀態。
13. Xvfb 真 Tk 路徑與完整既有 suite 無新增 failure。
