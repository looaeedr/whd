# Phase6 ProjectSession 交易狀態設計規格

## 目標

把 Phase6 專案的 `loaded baseline / committed / draft / project path` 交易語意收斂到單一 `ProjectSession` module，讓「開啟 3D、取消、確定、儲存、另存、讀檔」不再依賴 `gui.py` 多個 `_phase6_*` 欄位與 callback 默契維持正確性。

本次不改 `.p6fold` schema、不改 AE factory defaults、不拆 `gui.py`、不改 CornerType／Fold Profile 幾何規則。

## 核心語意

### Factory Defaults 不屬於 ProjectSession

`還原初始值` 仍由 AE / `phase6_settings_center` 的 immutable factory defaults 負責。ProjectSession 不保存也不解讀 factory defaults。

### ProjectSession 四個狀態

- `project_path`：目前 committed 專案的儲存路徑；沒有路徑代表尚未另存。
- `loaded_baseline`：最近一次從 `.p6fold` 成功讀入的原始 snapshot。之後 main GUI 或 3D 確定都不能改寫它。
- `committed`：目前主 GUI 已確認的完整專案 snapshot；所有正式儲存只允許讀這份資料。
- `draft`：目前 3D 交易的**隔離種子／生命週期標記**。Fold Designer 取得 defensive copy 後自行維護即時 editor view model；ProjectSession 不同步每一次 Tk 編輯。取消時丟棄交易，確定時由套用後的 main GUI canonical snapshot 成為 committed。

所有跨 interface 的 snapshot 都必須 `deepcopy`，caller 取得的 dict 不得能反向修改 session 內部狀態。

## ProjectSession interface

新增 `phase6_project_session.py`，公開：

```python
class ProjectSession:
    project_path: str | None
    has_draft: bool

    def set_project_path(self, path: str | Path | None) -> str | None: ...
    def load_project(self, path: str | Path, snapshot: Mapping[str, object]) -> dict: ...
    def capture_committed(self, snapshot: Mapping[str, object]) -> dict: ...
    def begin_draft(self) -> dict: ...
    def replace_draft(self, snapshot: Mapping[str, object]) -> dict: ...
    def commit_draft(self, snapshot: Mapping[str, object] | None = None) -> dict: ...
    def cancel_draft(self) -> dict | None: ...
    def committed_snapshot(self) -> dict | None: ...
    def draft_snapshot(self) -> dict | None: ...
    def loaded_baseline_snapshot(self) -> dict | None: ...
    def snapshot_for_save(self) -> dict: ...
```

`begin_draft()` 在沒有 committed 時拋 `RuntimeError`。`commit_draft()` 在沒有 active draft 時拋 `RuntimeError`。`snapshot_for_save()` 永遠回 committed，永不回 draft。**active draft 存在時 `capture_committed()` 也必須拒絕執行**，避免 caller 繞過 transaction 邊界直接覆寫 committed；只有明確的頂層 `load_project()` 可以取代目前交易並清除舊 draft。

## Main GUI 交易資料流

### 開啟 3D

1. 若目前沒有 draft，從 main GUI 建立完整 committed snapshot。
2. `ProjectSession.capture_committed(...)`。
3. `ProjectSession.begin_draft()` 取得隔離副本。
4. 只對傳入 Fold Designer 的副本補 `_runtime_project_path` 等 runtime-only 資訊；不得寫回 committed。

### 取消 / X

1. `ProjectSession.cancel_draft()`。
2. 關閉 3D 視窗。
3. 不套用任何 3D payload，不重算 main GUI，不改 loaded baseline / committed / project path。

### 確定

1. 保留 active draft，先關閉 3D。
2. 將 Fold Designer transaction payload 套用到 main GUI。
3. 從已套用後的 main GUI 建立完整 canonical snapshot。
4. `ProjectSession.commit_draft(canonical_snapshot)`；此操作同時清除 draft。

若套用失敗，不得把錯誤 payload 寫成 committed。

### 儲存 / 另存

- 沒有 active draft：先從 main GUI capture committed，再儲存 committed。
- 有 active draft：禁止從 Fold Designer 或 main GUI 重建**機械專案狀態**；直接 `snapshot_for_save()`，所以尺寸、CornerType、Fold Profile、開孔、板件增刪等仍是 3D 開啟前的 committed。
- 唯一例外是 `active_part`：它是純工作區導航位置，不是機械製造狀態。從 3D 全域 Save/Save As 可把目前 active part 當作 `active_part_hint` 寫入輸出 payload，但**僅限該板件已存在於 committed `existing_parts`**；不得因此把 draft 新增板件或任何 draft 幾何帶入存檔。
- `_runtime_project_path` 是執行期資訊，只能臨時注入傳給 3D 的 draft 副本，不得持久化進 committed snapshot / `.p6fold`。
- `.p6fold` payload schema 保持 `phase6-fold-project-v1`。

### 讀檔

1. `read_project(path)` 驗證並 decode。
2. `ProjectSession.load_project(path, payload["snapshot"])`，同時設定 loaded baseline、committed、清除 draft。
3. 把 session 回傳的 snapshot 套用到 main GUI。
4. 若 `open_designer=True`，從 committed 開新的 draft，不沿用舊 3D draft。

## Bridge seam

Main GUI 連接的 Fold Designer 不得自行把 staged 3D workspace 當正式 project save。

`Phase6FoldDesignerApp` 增加可選 `on_project_save(save_as: bool, active_part: str | None)` callback：

- main GUI 連接時，`designer.save_project_file()` / `save_project_file_as()` 都轉呼叫 main GUI 的 committed save；designer 只可額外傳遞目前 `active_part` 導航提示。
- standalone designer 沒有 callback 時，保留既有 bridge 自己寫 `.p6fold` 的相容行為。

這確保所有 main-app project save 都跨同一 seam。

## 相容性

- `.p6fold` schema 不變。
- `_phase6_loaded_project_path` 若需要保留給既有測試／舊 caller，改成 `ProjectSession.project_path` 的 computed compatibility property，不保存第二份欄位。
- `_phase6_existing_parts`、`fold_designer_part_bundle`、`_fold_designer_last_part_key` 第一階段仍可作 UI/render cache，但不再擁有 transaction lifecycle。

## 強制驗證情境

1. committed W=400 → begin draft → draft W=500 → cancel → committed 仍 400。
2. committed W=400 → draft W=500 → commit → committed 500。
3. load W=400 → loaded baseline=400 / committed=400 → main edit capture 450 → loaded baseline 仍 400。
4. committed=400 / active draft=500 → Save → `.p6fold` 必須是 400。
5. main-connected `designer.save_project_file()` 在 draft=500 時也必須走 committed save，不能輸出 500。
6. load new project while draft active → 舊 draft 消失，新 loaded baseline / committed 來自新檔。
7. active draft 存在時直接呼叫 `capture_committed()` → 必須拒絕，不能繞過 transaction。
8. 3D 目前 active part=`head` 且 `head` 已存在於 committed → Save 可保存 `active_part=head`；但 staged W=500 仍不得取代 committed W=400。
9. `active_part_hint` 指向只存在於 draft、未存在於 committed `existing_parts` 的板件 → 必須忽略。
10. 正式 `.p6fold` snapshot 不得包含 `_runtime_project_path`。

## 不在本次範圍

- ProjectSession 不成為所有 Tk widget value 的即時 store。
- 不升級 `.p6fold` schema。
- 不新增 UI 按鈕。
- 不變更 Factory Default / 還原初始值。
- 不修改 EndCap / CornerType / Fold Profile 幾何規則。
