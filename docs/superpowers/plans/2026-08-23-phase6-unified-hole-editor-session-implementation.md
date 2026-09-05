# Phase6 統一開孔編輯器交易狀態機實作計畫

> **代理工作者要求：** 必須使用 TDD，逐項完成下列核取方塊；所有程式識別字可保留英文，說明與文件一律繁體中文。

**目標：** 建立純 Python `Phase6HoleEditorSession`，把統一開孔編輯器的選取、active edit、Undo、多 context 與 Confirm/Cancel ordering 從 Tk method 收斂成單一 owner。

**架構：** Session 直接管理 caller 提供的 feature list reference 與交易 metadata；Tk/Canvas 只計算 candidate feature、發 action、刷新畫面。所有孔位幾何與 manufacturing 規則留在既有模組。

**技術棧：** Python 3、dataclass、pytest、Tkinter/Xvfb。

**設計規格：** `docs/superpowers/specs/2026-08-23-phase6-unified-hole-editor-session-design.md`

## 全域限制

- 不修改 `config.ini`。
- 不改 feature JSON/project schema。
- 不搬 Canvas renderer 或 manufacturing 幾何。
- Session 不 import Tk、AE renderer、ProjectSession、SettingsService、GUI。
- 已知 `/mnt/data/自訂.p6fold` 外部 fixture 缺件需與既有 4 項 failure 分離報告。

---

### 任務 1：建立純 Python Session 與封閉 Action

**檔案：**
- 新增：`phase6_hole_editor_session.py`
- 新增：`tests/test_phase6_hole_editor_session.py`

**介面：**
- `HoleEditorAction` classmethods：`select`、`insert`、`replace_selected`、`commit_active`、`cancel_active`、`replace_selected_committed`、`delete_selected`、`undo`、`preview_all`。
- `Phase6HoleEditorSession.execute(action)`。
- `Phase6HoleEditorSession.activate_context(key, feature_list)`。
- `Phase6HoleEditorSession.snapshot()`。
- `Phase6HoleEditorSession.finish(commit=...)`。

- [x] 先寫失敗測試，覆蓋 insert/cancel、commit/undo、replace/cancel、delete/undo。
- [x] 執行測試確認因模組／介面不存在而 RED。
- [x] 最小實作 Session，讓第一組測試 GREEN。
- [x] 增加 context switch、Cancel All、Confirm All、Undo 50 上限測試。
- [x] 實作多 context invariant 並保持 GREEN。

### 任務 2：把 Tk editor active edit／Undo 委派給 Session

**檔案：**
- 修改：`gui.py` 的 `_open_unified_hole_editor()`
- 修改／新增：`tests/test_phase6_hole_editor_session.py`

**介面：**
- Tk callback 只讀 `session.snapshot().selected_index` / `session.active_features`。
- 所有 insert/select/replace/commit/cancel/delete/undo 經 `session.execute(...)`。

- [x] 先寫 AST ownership 測試，要求 method 不再建立 `active_snapshot`、`undo_history_ref`、`context_feature_lists`、`context_original_features`。
- [x] 執行 RED。
- [x] 將交易 callback 改成 Session action，保留既有 refresh/redraw/sync 副作用順序。
- [x] 執行 Session + GUI ownership 測試 GREEN。

### 任務 3：收斂多 Context 與圓孔排列 transaction

**檔案：**
- 修改：`gui.py`
- 修改：`tests/test_phase6_hole_editor_session.py`

**介面：**
- `_switch_editor_context()` 呼叫 `session.activate_context(...)`。
- round fill/refill preview 呼叫 `preview_all()`；取消／確定分別走 `cancel_active()` / `commit_active()`。
- `confirm_all()` / `cancel_all()` 呼叫 `session.finish(commit=True/False)`。

- [x] 先寫 RED，鎖 context switch 必須取消 transient edit、round preview 可取消／Undo。
- [x] 改 `_switch_editor_context()` 與 round dialog transaction。
- [x] 改 Confirm/Cancel All。
- [x] 執行純 Session 與 Tk 聚焦回歸。

### 任務 4：回歸、ownership、文件與交付

**檔案：**
- 修改：`使用說明書.md`
- 修改：`修改日誌/20260823.md`
- 修改：`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- 修改：`docs/superpowers/README.md`
- 新增：`docs/superpowers/verification/2026-08-23-phase6-unified-hole-editor-session-verification.md`
- 修改：`DELIVERY_README.md`

- [x] 執行 `py_compile`。
- [x] Xvfb 執行 Session／開孔／Door／Indicator／ProjectSession 關聯回歸。
- [x] 執行原始完整 suite，確認只有既知外部 fixture failure。
- [x] 排除固定 4 項外部 fixture 後執行完整 0-failure suite。
- [x] 比對 `config.ini` SHA256 未變。
- [x] 更新繁中使用說明、修改日誌、踩坑、驗證報告。
- [x] 產生同一 Asia/Taipei 時間戳的 FULL／UPDATE；UPDATE 不含 `config.ini`。
- [x] `zipfile.testzip()`、`unzip -t`、SHA256 全部驗證。
