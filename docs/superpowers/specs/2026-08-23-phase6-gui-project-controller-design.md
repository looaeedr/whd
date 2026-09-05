# Phase6 GUI 專案 Controller 化設計規格

## 目的

把目前散落在 `gui.py` 的「專案檔持久化、ProjectSession 交易生命週期、3D draft 儲存保護、active_part 導航提示」收斂成一個不依賴 Tk 的深模組 `Phase6ProjectController`。

這一輪不是把 `gui.py` 按檔案大小硬拆，也不搬移 `draw_*`、孔位 editor、Tk widget 建立或幾何運算。

## 已核准方向

使用者已核准進入 `gui.py` Controller 化。這一輪採漸進式 controllerization：先抽出最高風險、已經有 `ProjectSession` Source of Truth 的專案交易 seam。

## 現況問題

`ProjectSession` 已經擁有 `loaded_baseline / committed / draft / project_path`，但 `gui.py` 仍自行協調：

- 何時從主 GUI capture committed；
- active 3D draft 時 Save 必須讀 committed，而不能重新 capture 主 GUI；
- `active_part` 只可作導航 metadata，且只能指向 committed 已存在板件；
- `.p6fold` payload schema、`saved_at`、`final_geometry` envelope；
- `read_project()` / `write_project()`；
- load 時取代舊 draft；
- 3D open / confirm / cancel 對 `ProjectSession` 的呼叫順序。

這些規則目前跨 `_capture_phase6_committed_snapshot()`、`_build_phase6_project_payload()`、`_write_phase6_project_to_path()`、`load_phase6_project()`、`open_original_fold_designer()` 與 `_apply_fold_designer_corner_transaction()`。

## 三種方案

### A. 只把現有方法搬到新檔

不採用。只是搬行數，呼叫者仍必須知道 session 的 ordering 與 draft 規則，模組會很淺。

### B. 建立 `Phase6ProjectController` 深模組（採用）

Controller 吃 `ProjectSession` 與專案檔 adapter，隱藏 capture / draft / save / load ordering。Tk GUI 只提供 canonical snapshot provider 與 snapshot apply view adapter。

### C. 一次建立大型 `Phase6MainController`

暫不採用。若同時吃 Settings、幾何、孔位、workspace presence，會形成新的 God Controller，locality 反而下降。

## 模組與 seam

新增：`phase6_project_controller.py`

```text
BoxCalculatorGUI (Tk / View Adapter)
    │
    │ canonical snapshot provider
    │ apply loaded snapshot
    ▼
Phase6ProjectController
    ├─ ProjectSession
    ├─ read_project adapter
    └─ write_project adapter
```

### Controller Interface

```python
class Phase6ProjectController:
    @property
    def project_path(self) -> str | None: ...

    @property
    def has_draft(self) -> bool: ...

    def set_project_path(self, path) -> str | None: ...

    def capture_committed(self, snapshot) -> dict: ...

    def begin_designer(self, snapshot_provider) -> dict: ...

    def cancel_designer(self) -> dict | None: ...

    def confirm_designer(self, committed_snapshot) -> dict: ...

    def build_payload(self, snapshot_provider, *, active_part_hint=None) -> dict: ...

    def save(self, path, snapshot_provider, *, active_part_hint=None) -> str: ...

    def load(self, path) -> tuple[dict, dict]: ...
```

`snapshot_provider` 是 callable。Controller 只有在沒有 active draft 時才呼叫它；因此 active 3D Save 無法因 caller 手滑而重新 capture 未確認資料。

## 核心 invariant

1. **Controller 不擁有 Tk state。** 不 import `tkinter`，不讀 widget。
2. **ProjectSession 仍是交易 Source of Truth。** Controller 只是 application orchestration module，不另存 committed/draft mirror。
3. **active draft 儲存只讀 committed。** `snapshot_provider` 在 active draft 時不得被呼叫。
4. **active_part 是純導航 metadata。** 只有 `active_part_hint in committed existing_parts` 時才可覆寫 snapshot 與 workspace 的 `active_part`。
5. **load 是明確頂層操作。** 由 `ProjectSession.load_project()` 取代 active draft。
6. **confirm 只能提交 GUI 已套用後重新 compose 的 canonical snapshot。** Controller 不接受 bridge draft 當正式 committed。
7. **config.ini / SettingsService 不進本 Controller。** Settings ownership 已在前一階段完成。
8. **不更動 `.p6fold` schema。** payload 欄位保持 `schema / saved_at / snapshot / final_geometry`。

## GUI 改造

`BoxCalculatorGUI` 保留：

- `_compose_phase6_project_snapshot_from_main_gui()`：View → canonical snapshot adapter；
- `_apply_phase6_project_snapshot()`：snapshot → View adapter；
- `save_phase6_project_as()` / `save_phase6_project()` / `open_phase6_project()`：Tk file dialog 與 messagebox；
- `open_original_fold_designer()`：Toplevel 建立與 Bridge wiring。

但上述方法不再直接操作 `ProjectSession` ordering 或 project read/write。

相容性：

- `self.project_session` 暫時保留為 `self.project_controller.session` alias，讓既有測試與舊呼叫端不一次斷裂；它不是第二份 session。
- `_phase6_loaded_project_path` 暫保 compatibility property，改委派 Controller。

## TDD seams

### Seam 1：`Phase6ProjectController`

純 Python 測試，不啟動 Tk：

- active draft save 不呼叫 snapshot provider；
- active_part hint 只可更新已存在板件；
- begin / cancel / confirm 交易順序；
- load 取代 draft 並保存 project path；
- save payload schema 不變。

### Seam 2：`BoxCalculatorGUI` 對外行為

沿用既有 Tk integration tests：

- 3D Cancel 保留 committed；
- 3D Confirm 提交新的 canonical committed；
- 3D Save As 不可洩漏 draft；
- Save As → Save 重用同一路徑；
- Load 後 active_part 正確恢復。

## 本輪明確不做

- 不抽 `draw_*` renderer；
- 不拆統一孔位 editor；
- 不改 CornerType / EndCap 幾何；
- 不改 SettingsService；
- 不把 `fold_designer_part_bundle` 全面型別化；
- 不改 `.p6fold` schema；
- 不重新設計 UI。

## 成功條件

1. `gui.py` 不再直接 import / 呼叫 `read_phase6_project`、`write_phase6_project` 或組裝 payload envelope。
2. ProjectSession ordering 集中在 Controller；GUI 僅保留相容 alias。
3. Controller 純測試完整通過。
4. 既有 ProjectSession / project file / 3D transaction regression 全綠（排除既知外部 fixture 缺件）。
5. `config.ini` SHA256 不變。


## 實作結果

- 採用方案 B：`Phase6ProjectController`。
- GUI 不再直接操作 ProjectSession ordering 或 project read/write。
- `snapshot_provider` 成為 active-draft Save 保護的正式 interface。
- compatibility `app.project_session` 與 controller session 是同一物件，沒有新增 mirror。
- 最終完整可執行回歸：`284 passed, 2 skipped, 4 deselected, 0 failure`。
