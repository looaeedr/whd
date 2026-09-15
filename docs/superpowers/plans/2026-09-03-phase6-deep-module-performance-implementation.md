# Phase6 深模組效能架構深化 — T01～T14 派工／實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans` 逐工單執行。每一張工單都必須自行重跑 Phase6 Knowledge Preflight；總控的 evidence 不得代用。

**Goal:** 在不改機械真值、不硬拆深模組的前提下，完成 Scheduler 唯一 executor、GUI↔3D anti-echo/atomic init、Bridge orchestration、精準 derived cache、Manufacturing→Collision 單向依賴，並通過真 GUI stress、full Headless/Xvfb 與 fresh-package release gate。

**Architecture:** 先鎖 executor ownership，再處理 sync/Bridge；Cache 在 Executor 穩定後可與 Bridge lane 部分並行；最後才解 Manufacturing/Collision 雙向依賴。四條高風險 seam 不在同一刀修改，T11～T14 由總控統一整合與交付。

**Tech Stack:** Python, Tkinter, Shapely, pytest, Xvfb, Phase6 resumable release runner。

**Spec:** `docs/superpowers/specs/2026-09-03-phase6-deep-module-performance-architecture-design.md`

## Global Constraints

- Scheduler 是唯一 calculation executor。
- debounce 初始 75ms，可依壓力測試在 50–100ms 調整；不得 ≥200ms 掩蓋重算風暴。
- dirty reasons 至少：geometry / assembly / baseline / display / annotation / camera。
- Save / Export / DXF / NC / batch / return-to-2D 前必須 flush authoritative state。
- immutable DXF source fingerprint = normalized path + size + mtime_ns + parser/schema version + reload generation。
- `SOURCE_UNVERIFIED` 只允許 preview 使用 LKG，不允許正式 manufacturing/export 當 fresh truth。
- Manufacturing → Collision 單向；Collision 不反向 import manufacturing orchestration internals。
- Certified Registry / STANDARD / AssemblyJoint / INSERT / OVERLAY / INSERT_OVERLAY / WRAP 機械語意不在本輪重構範圍。
- `config.ini` 不得修改。

---

## 派工依賴圖

```text
T01 → T02 → T03 ───────────────┐
              ├→ T04 → T05 → T06 ─┤
              └→ T07 → T08 ───────┤
                                   ├→ T09 → T10 → T11 → T12 → T13 → T14
                                   └──────────────────────────────────────
```

### 並行規則

- **Lane A**（T01-T03）必須先完成，因為後面所有 mutation/cache/sync 都依賴唯一 executor。
- **Lane B**（T04-T06）與 **Lane C**（T07-T08）在 T03 後可由不同 worker 並行；共同檔案 `gui.py` 的修改必須由總控先切責任區並在整合時 review。
- **Lane D**（T09-T10）等 T06/T08 穩定後才進，避免同時搬兩個高風險邊界。
- **Lane E**（T11-T14）不得分散責任；由總控執行與簽核。


## 每張工單共同硬閘門

1. **開工前自行重跑 Knowledge Preflight**，總控 evidence 不得代用。每張 `briefs/Txx_*.md` 已寫入該工單的精確 `--task` 命令；預計修改檔案確定後，再以所有 changed-file 重跑一次；Required Skills / References 全讀完並留下自己的 evidence。
2. 修改前建立隔離工作區；有 Git 時用獨立 worktree/branch，沒有 Git 時用獨立乾淨副本。不得在共用工作樹互踩。
3. **TDD**：先新增可觀察 invariant 的 red test，再改 production；禁止為了讓測試過而改 oracle。
4. `config.ini` 禁止修改、禁止打包。
5. 本輪不得修改 INSERT / OVERLAY / INSERT_OVERLAY / WRAP（正式名稱「包覆貼外」）機械公式、STANDARD 母規則、Certified Registry 規則值。
6. 不得為縮檔硬拆 `phase6_final_scene_view.py`、`phase6_fold_profiles.py`、`phase6_designer_workspace.py`。
7. 不得用 200ms 以上 debounce、降低幾何精度、關掉 manufacturing/collision 或延遲不更新來製造假快。
8. 每張工單必須回報：changed files、測試命令與結果、counter 前後值、preflight evidence 路徑、commit/hash（若有 Git）、已知殘留風險。

---


### T01: 效能 Counter + Executor Conformance Red Gate

**Lane:** A / Scheduler  
**Depends on:** 無

**Files:**
- Create: `tests/test_phase6_update_executor_conformance.py`
- Modify: `tests/test_phase6_gui_performance_contract.py`
- 可讀但先不改：`gui.py:526-581`, `gui.py:4125-4149`, `gui.py:5926-6064`

**Objective:**  
先建立架構防線與可觀察 counters，鎖住「單一 mutation 只能一次 calculation/scene/render」以及目前 `_on_door_layout_value_changed()` 的 double-preview 路徑。這張工單只做測試/量測 seam，不搬 production ownership。

**Interfaces:**
**Consumes:** 現有 `_Phase6UpdateScheduler`, `BoxCalculatorGUI.update_calculations()`, `draw_preview()`。

**Produces:** 測試 helper `PerfCounters`（可放測試檔內）與 fail-closed AST/inspection gate：一般 mutation handler 不得直接呼叫 `update_calculations()` / manufacturing solve / `draw_preview()`；例外集中 allowlist。後續 T02/T03 以此 gate 為驗收標準。

**Steps:**
- [ ] 建立 `PerfCounters`，至少記 `calculation`, `manufacturing`, `scene_rebuild`, `render`, `publish`, `echo`, `dxf_disk_read`。
- [ ] 寫 red test：呼叫 `_on_door_layout_value_changed(recompute=True)` 時目前應觀察到 calculation 後又 redraw，測試要求最終 `calculation <= 1` 且 `render <= 1`。
- [ ] 寫 transaction red test：同 transaction 三次變數寫入只能形成一次 committed calculation。
- [ ] 寫 display/camera gate：不得走 calculation/manufacturing。
- [ ] 寫 AST conformance gate：掃 `gui.py` 與 `fold_designer_bridge.py` 的一般 mutation handlers；direct executor 只容許 scheduler 內部、bootstrap 相容 fallback、明確測試 seam。
- [ ] 跑：`pytest -q tests/test_phase6_update_executor_conformance.py tests/test_phase6_gui_performance_contract.py`，保存 red baseline；不得修改 production 來讓本工單變綠。

**Acceptance:**
- 新 counter/test 能穩定重現至少一個現有 bypass/double render。
- allowlist 是精確 symbol/line responsibility，不是 `gui.py` 整檔放行。
- 測試只看外部工作量與最終 state，不把私人函式 call 次數當唯一 oracle。

**Worker report contract:**
```text
Task: T01
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T02: Scheduler Dirty Policy / Transaction / Debounce 核心

**Lane:** A / Scheduler  
**Depends on:** T01

**Files:**
- Modify: `gui.py:526-581`
- Test: `tests/test_phase6_update_executor_conformance.py`
- Test: `tests/test_phase6_gui_performance_contract.py`

**Objective:**  
把 `_Phase6UpdateScheduler` 從「只有 dirty set + 全量 update」深化成唯一 executor：正式 dirty reason、transaction coalescing、75ms trailing debounce、立即 commit flush，並提供可量測的單次工作選擇。

**Interfaces:**
**Produces scheduler interface（名稱可沿既有 class，不另造第二 owner）：**
```python
scheduler.begin()
scheduler.mark_dirty(reason: str)
scheduler.request_flush(*, debounce_ms: int = 0)
scheduler.flush_now() -> bool
scheduler.end()
```
Dirty reasons 至少：`geometry`, `assembly`, `baseline`, `display`, `annotation`, `camera`。

**Invariant:** `display/camera` 不可觸發 manufacturing；geometry edit 每 transaction calculation/scene/render 各至多一次。

**Steps:**
- [ ] 先跑 T01 red tests，確認仍紅在 executor ownership，而非測試壞掉。
- [ ] 在 scheduler 內加入 dirty policy map，不得所有 reason 都最後無條件走完整 `update_calculations()`。
- [ ] transaction 最外層 `end()` 只要求 scheduler flush；nested `var.set()` 只 coalesce dirty reason。
- [ ] trailing debounce 預設採 75ms；Enter/FocusOut/MouseRelease/part-switch/Family/Intent/Save/Export/DXF/NC 由 caller 使用 `flush_now()`。
- [ ] debounce job 被 `flush_now()` 取消後必須執行最後 state，不得遺失 final mutation。
- [ ] 加 scheduler counter seam，避免 production profiler 依賴 monkeypatch 私有函式。
- [ ] 跑 T01/T02 targeted tests 至 scheduler 核心綠。

**Acceptance:**
- transaction 同批 geometry mutation：calculation<=1、scene<=1、render<=1。
- display/camera：calculation=0、manufacturing=0。
- 75ms 可被壓力測試調整但範圍只能 50–100ms。
- scheduler 是 executor；Transaction Guard 不藏第二套 calculate。

**Worker report contract:**
```text
Task: T02
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T03: GUI Mutation Bypass 清除 + Commit Flush

**Lane:** A / Scheduler  
**Depends on:** T02

**Files:**
- Modify: `gui.py`（以 T01 gate 列出的 direct bypass 為精確清單）
- Priority lines: `gui.py:1091-1155`, `1843`, `1967`, `2297`, `2348`, `2371`, `2842`, `2862`, `2924`, `2942`, `3374`, `4125-4149`, `4402-4429`, `5304-5349`, `5734-5738`, `7158`
- Test: T01/T02 tests + existing GUI transaction tests

**Objective:**  
把一般 mutation callback 從直接 `update_calculations()` / `draw_preview()` 改成 canonical delta → `mark_dirty()` → `request_flush()`；Save/Export/DXF/NC/返回 2D 前使用 `flush_now()`。清除已確認 double-preview。

**Interfaces:**
**Consumes:** T02 scheduler API。

**Produces:** GUI mutation contract：handler 只寫 canonical input state 與 dirty reason；commit seam 只呼叫 `flush_now()` 後讀 authoritative committed result。

**Steps:**
- [ ] 以 T01 AST gate 輸出逐一處理 direct bypass，不做全域 search/replace。
- [ ] `_on_door_layout_value_changed()` 移除 calculation 後的第二次 `draw_preview()` ownership；由 scheduler 統一決定 render。
- [ ] combobox/trace/canvas configure 分類 dirty reason；純 resize/display/camera 不得標 geometry。
- [ ] `_apply_fold_designer_live_settings()` 保留 actual-delta compare；scheduler fallback 只允許 bootstrap 明確例外。
- [ ] Save/Save As/Export/DXF/NC/batch/返回2D commit seam 在讀 manufacturing result 前 `flush_now()`。
- [ ] 新增測試：pending dirty 後立即 Save/Export，輸出 fingerprint 必須等於最後輸入，不可 stale。
- [ ] 跑：`pytest -q tests/test_phase6_update_executor_conformance.py tests/test_phase6_gui_performance_contract.py tests/test_gui_corner_transaction_apply.py tests/test_phase6_left_global_transaction.py tests/test_gui_fold_designer_transaction_contract.py`。

**Acceptance:**
- T01 conformance gate 綠。
- 一般 mutation handler direct full calculation = 0（allowlist 之外）。
- double-preview path 消失。
- Save/Export/DXF/NC 前一定 flush 最後值。

**Worker report contract:**
```text
Task: T03
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T04: Sync Envelope + Actual Delta / Anti-Echo

**Lane:** B / Sync  
**Depends on:** T03

**Files:**
- Modify: `gui.py:1070-1160` 與 Fold Designer live-sync adapter
- Modify: `fold_designer_bridge.py:1850-1870`, `6009-6040`
- Create/Test: `tests/test_phase6_sync_envelope.py`
- Reuse: `tests/test_phase6_live_canonical_sync.py`

**Objective:**  
把 Main GUI ↔ 3D live-sync 從「payload 相同才不送」深化成正式 `origin + revision + transaction_id + actual delta/fingerprint` envelope；等價 state 不寫 Tk vars、不升 revision、不回送。

**Interfaces:**
**Produces neutral sync envelope（可用 dataclass 或 mapping，但只能一個 owner）：**
```python
{
  "origin": "main_gui" | "fold_designer",
  "revision": int,
  "transaction_id": str,
  "delta": {...},
  "fingerprint": str,
}
```
Revision 只在 authoritative actual delta commit 時增加。

**Steps:**
- [ ] 寫 red tests：Main→3D 等價 ingest publish=0；3D 真實 edit 只 publish 一個新 revision；stale revision reject。
- [ ] canonical compare 在 `var.set()` 前執行，相同值完全不 write Tk variable。
- [ ] persistence mirror / compatibility field 不得建立新 revision。
- [ ] 同 transaction 多欄位 change 共用 transaction_id，只形成一個 committed revision。
- [ ] Main GUI 收到自己 transaction 的等價 payload：echo=0、recalc=0。
- [ ] 跑：`pytest -q tests/test_phase6_sync_envelope.py tests/test_phase6_live_canonical_sync.py tests/test_gui_fold_designer_transaction_contract.py`。

**Acceptance:**
- equivalent sync echo=0。
- stale revision 無法覆蓋新 state。
- actual delta 才 `var.set()`。
- revision 與 transaction semantics 可由測試直接觀察。

**Worker report contract:**
```text
Task: T04
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T05: 3D Atomic Initialization / Stale Revision Guard

**Lane:** B / Sync  
**Depends on:** T04

**Files:**
- Modify: `fold_designer_bridge.py:6009-6165`（初始化）
- Modify: live ingest/publish seam around `1850-1870`
- Test: `tests/test_phase6_sync_envelope.py`
- Reuse: `tests/test_original_fold_designer_gui_integration.py`, `tests/test_phase6_gui_3d_integrity_20260830.py`

**Objective:**  
建立 `INITIALIZING → READY` 原子初始化：只 ingest authoritative current state，不 publish default/intermediate，不讓 persisted stale value 蓋掉主 GUI 最新輸入。

**Interfaces:**
**Consumes:** T04 sync envelope/revision。

**Produces initialization rule:**
`使用者目前輸入 > authoritative application state > persisted state > 3D default`。
READY 時若 fingerprint 等價，publish count 必須 0。

**Steps:**
- [ ] red test：主 GUI 先輸入新 W/H/D，再開 3D；初始化過程不得回寫舊 snapshot。
- [ ] 初始化期間所有 legacy `do_update()`/trace callback 只可 ingest/mark dirty，不得 publish intermediate。
- [ ] READY 前保存最新 authoritative revision；收到較舊 revision 直接 reject。
- [ ] READY 比對等價 state，等價就不 publish。
- [ ] 驗證初始化不產生多輪 manufacturing/render。
- [ ] 跑 targeted Xvfb integration，確認開/關 3D 不殘留 Tk grab。

**Acceptance:**
- initialization default/intermediate publish=0。
- 主 GUI 最新輸入不被 3D stale state 蓋回。
- 開啟 3D 的 manufacturing/render 次數符合單 transaction 上限。

**Worker report contract:**
```text
Task: T05
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T06: Fold Designer Orchestration Seam + Part Switch

**Lane:** B / Bridge  
**Depends on:** T05

**Files:**
- Modify: `fold_designer_bridge.py:751-754`, `1146-1195`, `1850-1895`, `2140-2170`, `2500-2605`, `6294-6845`, `7054-7171`
- Do not create a new orchestration module in this task; first deepen the orchestration seam inside `fold_designer_bridge.py`. Extraction is a separate future decision after deletion test.
- Tests: `tests/test_phase6_part_switch_external_callback.py`, `tests/test_original_fold_designer_bridge.py`, `tests/test_phase6_bridge_domain_ownership.py`

**Objective:**  
把多層 `do_update` / queue / preview-aware wrapper 的最終效果收斂為一個 orchestration seam；legacy wrapper 可留，但只提交 intent，不再擁有 calculation/render ownership。快速 part switch 若 canonical geometry 沒變，不得 full manufacturing solve。

**Interfaces:**
**Consumes:** T02 scheduler、T04 sync、T05 init guard。

**Produces orchestration operations（實際名稱可沿現有 class，但責任必須集中）：**
- `submit_update_intent(reason, *, commit=False)`
- `apply_settings_delta(delta, transaction_id)`
- `switch_active_part(part_key, *, commit=True)`
- `publish_if_changed()`

Compatibility wrapper 只能呼叫上述 seam。

**Steps:**
- [ ] 列出目前所有 `Phase6FoldDesignerApp.do_update` wrapper，先寫 conformance test 讓 wrapper 取得 executor ownership 時 fail。
- [ ] 將 `_phase6_flush_pending_settings`, `_phase6_preview_aware_do_update`, `_fix11_do_update` 的真正更新順序集中。
- [ ] settings snapshot 按 schema/key normalize，禁止「非 bool 一律 float」。
- [ ] part switch 僅 active view/annotation 改變時標 display/annotation；canonical geometry 未改不得 manufacturing solve。
- [ ] Head↔Tail 連切 10 次，global D/final material/unfolded blank fingerprint 不漂移。
- [ ] Family switch 以一個 transaction 原子更新 family topology、workspace state、live globals、GUI vars。
- [ ] 跑 Bridge/part-switch/family targeted tests。

**Acceptance:**
- Bridge compatibility 還在，但 executor ownership 只有 scheduler/orchestration seam。
- equivalent part switch full manufacturing solve=0。
- Head/Tail 快速切換不漂移。
- 不因 7k 行 Bridge 而任意拆小檔。

**Worker report contract:**
```text
Task: T06
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T07: Derived Geometry Cache Owner + Invalidation Matrix

**Lane:** C / Cache  
**Depends on:** T03（可與 T04-T06 並行）

**Files:**
- Modify: `gui.py:768, 1345-1350, 1748-1749, 2088-2090, 2287, 2339-2370, 3421, 4715-4724, 5295, 5700-5707`
- Reuse: `ae_engine/ae.py:1409-1465` immutable source cache
- Modify: `gui.py` to add a single `_Phase6DerivedCacheOwner`; do not create a new cache module in this task.
- Create/Test: `tests/test_phase6_derived_cache_owner.py`
- Reuse: `tests/test_phase6_baseline_source_cache.py`

**Objective:**  
保留既有 DXF source fingerprint，將 `_door_layout_baseline_cache`、`_authoritative_part_render_cache` 等 derived cache 的 dependency key/invalidation 從 GUI handlers 收斂到單一 owner。

**Interfaces:**
**Consumes:** `ae_engine.ae` immutable parsed source cache。

**Produces:** `invalidate(reason, changed_keys)` 與 per-product dependency declaration。W/H/D/FW 只能失效相依 derived product，不得 `clear_baseline_dxf_source_cache()`。

**Steps:**
- [ ] 建 dependency matrix test：geometry / family-structure / assembly-joint / baseline / display / camera 對每個 derived product 的 invalidation。
- [ ] 相同 DXF fingerprint + W/H/D/FW change：source disk reread additional=0。
- [ ] 將 GUI 零散 `cache = {}` 改為 owner API；禁止用一個全域 `cache.clear()` 代替精準失效。
- [ ] derived key = source fingerprint + 該 product 真 dependency subset。
- [ ] parser/schema/reload_generation 屬 source cache；dimension/joint 只屬 derived。
- [ ] 跑 baseline source cache + new derived cache tests。

**Acceptance:**
- ordinary geometry edit source reread=0。
- invalidation 由單一 owner 決定。
- display/camera 不清 source/derived manufacturing cache。
- 不引入第二套 baseline parser。

**Worker report contract:**
```text
Task: T07
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T08: Force Reload + SOURCE_UNVERIFIED 網路來源安全

**Lane:** C / Cache  
**Depends on:** T07

**Files:**
- Modify: `ae_engine/ae.py:1409-1465`
- Modify: GUI baseline source consumer around `gui.py:4715-4724` 及正式 export commit seam
- Test: `tests/test_phase6_baseline_source_cache.py`
- Test: `tests/test_phase6_derived_cache_owner.py`

**Objective:**  
補齊 source verification 狀態：Force Reload 必須在相同 stat 下重讀；網路磁碟 stat/read 暫敗時 preview 可用 LKG + `SOURCE_UNVERIFIED`，正式 Save authoritative manufacturing result / Export / DXF / NC / batch 必須 fail closed。

**Interfaces:**
**Produces source status:** `VERIFIED | SOURCE_UNVERIFIED`（名稱可用 enum/constant，但不得只藏在 UI 文案）。

**Commit rule:** 正式製造輸出前先 `flush_now()`，再要求 fresh source verification；未驗證不得當 fresh truth。

**Steps:**
- [ ] red test：相同 path/size/mtime 但 Force Reload generation+1 時 disk read 必須增加。
- [ ] red test：stat/read failure + 有 LKG → preview 可回傳資料但 status=SOURCE_UNVERIFIED。
- [ ] red test：SOURCE_UNVERIFIED 下 Export/DXF/NC/batch 拒絕或要求重新 verify。
- [ ] 網路 I/O 不得在 GUI 全域 transaction 大鎖中同步卡住 render ownership。
- [ ] source recovery 後 status 回 VERIFIED，derived cache 依新 fingerprint 正確失效。
- [ ] 跑 cache targeted suite。

**Acceptance:**
- Force Reload 真正繞過 fingerprint。
- preview/LKG 與正式製造權限分離。
- 網路失聯不會把 stale source 冒充 fresh authoritative。

**Worker report contract:**
```text
Task: T08
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T09: 中立 Final Material / Collision Contract

**Lane:** D / Manufacturing  
**Depends on:** T06 + T08

**Files:**
- Modify: `ae_engine/contracts.py`
- Modify: `ae_engine/assembly_collision.py`（僅改資料輸入/輸出邊界，不改機械公式）
- Test: `tests/test_manufacturing_policy_boundary.py`
- Create/Test: `tests/test_manufacturing_collision_dependency.py`

**Objective:**  
建立 Manufacturing 與 Collision 共用的 GUI-independent neutral contract，使 solver 不需知道 manufacturing orchestration 內部 helper/PartRenderData 建構細節。只搬資料契約，不改 Certified/Collision 機械演算法。

**Interfaces:**
**Produces contract 至少描述：** physical part id、final material polygon/holes/relief、fold topology、true thickness、piece transform/UV owner、resolved AssemblyJoint、legal contact semantics、solver constraints、diagnostic metadata。

Collision result 要能分：legal contact、illegal penetration、pre-solve evidence、candidate relief、post-solve zero penetration。

**Steps:**
- [ ] 先寫 import-boundary red test：`assembly_collision.py` 不得 import `manufacturing_api`。
- [ ] 在 `contracts.py` 加 immutable neutral DTO；禁止把 GUI callback 或 manufacturing orchestrator 塞進 contract。
- [ ] 增 adapter：manufacturing 將 committed render/material 投影成 neutral contract。
- [ ] collision solver 純吃 neutral contract / geometry，不需要反向拿 `PartRenderData` helper。
- [ ] Registry HIT/MISS semantic tests 不變：HIT 仍 canonical；MISS candidate 不能冒充 Certified。
- [ ] 跑 manufacturing/collision targeted tests。

**Acceptance:**
- neutral contract 可獨立建立與單測。
- 未改任何 relief 常數/registry rule。
- import-boundary test 可防止 cycle 回歸。

**Worker report contract:**
```text
Task: T09
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T10: Manufacturing → Collision 單向化 / 移除雙向 Import

**Lane:** D / Manufacturing  
**Depends on:** T09

**Files:**
- Modify: `ae_engine/manufacturing_api.py:1437-1605`
- Modify: `ae_engine/assembly_collision.py:278, 1269` 等反向 import seam
- Modify: `ae_engine/contracts.py`（只補 T09 必要 adapter）
- Tests: `tests/test_manufacturing_api.py`, `tests/test_assembly_collision.py`, `tests/test_assembly_collision_integration.py`, `tests/test_manufacturing_collision_dependency.py`

**Objective:**  
移除 `assembly_collision -> manufacturing_api` 反向依賴；依賴固定成 Manufacturing Orchestration 可呼叫 Collision Solver，solver 只依賴中立 contract/geometry helper。禁止複製 solver logic。

**Interfaces:**
**Consumes:** T09 neutral contract。

**Produces dependency:**
`contracts/geometry -> manufacturing_api -> assembly_collision`（或 manufacturing 與 collision 都只依賴更低層 contract，且 collision 絕不反向 import manufacturing orchestration）。

**Steps:**
- [ ] 移除 `assembly_collision.py` 中對 `PartRenderData`, `material_polygon_from_final_scene` 的 runtime import；以 T09 adapter/result 重建。
- [ ] `_scene_with_replaced_primary_cutting` 若是通用 scene/material helper，搬到中立低層且 deletion test 證明至少兩個 caller；否則改 solver 回傳 data，讓 manufacturing 自己組 PartRenderData。
- [ ] `manufacturing_api.py` 保持 stable headless boundary，不把 solver private helper 暴露給 GUI。
- [ ] 跑 import cycle scanner，`manufacturing_api ↔ assembly_collision` SCC 必須消失。
- [ ] 跑 collision zero-penetration、true thickness、Head/Tail integration tests。

**Acceptance:**
- Manufacturing→Collision 單向。
- solver 可不 import manufacturing_api 單獨測。
- 2D/3D/export final material fingerprint 不變。
- 無 solver logic duplication。

**Worker report contract:**
```text
Task: T10
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T11: 整合 Targeted Regression + Assembly Registry Matrix

**Lane:** E / 總控  
**Depends on:** T03,T06,T08,T10

**Files:**
- 不新增機械規則；必要時只新增 regression tests/evidence
- Run existing tests covering scheduler/sync/cache/manufacturing/registry/3D

**Objective:**  
總控把四條工作流整合到同一乾淨工作樹後，先跑中型 targeted regression，確認效能架構變更沒有污染 Assembly Intent、Certified Registry、2D/3D、保存/重載與輸出。

**Interfaces:**
**Consumes:** T03/T06/T08/T10 reviewed commits。

**Produces:** `logs/deep_module_targeted_20260903.json` 或等價 durable evidence，含 collection、passed/failed、counter summary、final fingerprints。

**Steps:**
- [ ] 整合前逐工單 review：spec compliance + code quality；不得只看各自 self-test。
- [ ] 跑 scheduler/sync/cache targeted suite。
- [ ] 跑 registry/assembly matrix：`test_phase6_assembly_intent_registry_matrix.py`, `test_assembly_joint_registry_matrix.py`, `test_certified_relief_registry*.py`。
- [ ] 跑 Head/Tail、INSERT/OVERLAY/INSERT_OVERLAY/包覆貼外、Receiving 相關 2D/3D/Joint tests。
- [ ] 跑 save/reload/DXF/NC canonical consumer tests。
- [ ] 若紅燈，先 root-cause；不得更新 oracle 或縮 gate。

**Acceptance:**
- targeted regression 0 failed。
- Registry HIT canonical answer/fingerprint 未變。
- 求解前 evidence 與求解後零 penetration gate 未退化。
- 2D/單板3D/組合3D/DXF/NC 共用 committed final material。

**Worker report contract:**
```text
Task: T11
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T12: 真 GUI Burst Stress + Counter Gate

**Lane:** E / 總控效能  
**Depends on:** T11

**Files:**
- Create or extend: `tools/phase6_gui_perf_stress.py`
- Reuse tests: `tests/test_phase6_gui_performance_contract.py`, `tests/test_phase6_head_tail_close_perf.py`, `tests/test_phase6_outside_advanced_perf.py`
- Evidence under `logs/` + durable checkpoint under `/mnt/data`

**Objective:**  
執行規格指定的真 GUI 壓力，不以一般 pytest 全綠代替；每段保存 wall-time 和各工作 counter，抓短時間 burst、part switch、3D 開關與 cache/network 行為。

**Interfaces:**
**Produces stress evidence per segment:** wall_time, calculation, dxf_disk_read, manufacturing_resolve, scene_rebuild, render, publish, echo, final_state_fp, final_scene_fp。

**Steps:**
- [ ] W/H/D/T 各 20 次 burst；最後值立即 commit。
- [ ] FW 連續修改。
- [ ] box_body→head→tail→box_body 快速循環；Head↔Tail ≥10 次。
- [ ] Vault↔Receiving Family 快速切換。
- [ ] INSERT/OVERLAY/INSERT_OVERLAY/正式包覆貼外 intent/joint 切換。
- [ ] 3D 開/關、camera rotate/zoom、連續返回2D。
- [ ] warm-cache baseline：普通尺寸 edit DXF reread=0。
- [ ] Force Reload：disk read 增加且 source generation 更新。
- [ ] 每段檢查無 Tk grab/pytest/Xvfb orphan。

**Acceptance:**
- 單一 geometry edit calc<=1、manufacturing<=1、scene<=1、render<=1、echo=0、same-source reread=0。
- display/camera calc=0、manufacturing=0。
- 最終 state/scene fingerprint 正確且無事件暴增。

**Worker report contract:**
```text
Task: T12
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T13: Headless + Xvfb Full Suite Durable Release Runner

**Lane:** E / 總控回歸  
**Depends on:** T12

**Files:**
- Reuse: `tools/phase6_release_test_runner.py`
- Separate journals: `logs/deep_module_headless_20260903.*`, `logs/deep_module_xvfb_20260903.*`
- Durable checkpoint: `/mnt/data/PHASE6_DEEP_MODULE_RELEASE_CHECKPOINT_20260903.json`

**Objective:**  
用 resumable release runner 完成 Headless 與 Xvfb 全套，兩份 evidence 不混用；外層 timeout/exit75 只作 checkpoint，禁止重頭跑或誤判 fail。

**Interfaces:**
**Produces:** collection SHA/count、completed/pending/failed、journal paths、batch timeout classifications、orphan cleanup result。

**Steps:**
- [ ] 先 collect tests，鎖 collection SHA/count。
- [ ] Headless 用獨立 journal 續跑至 pending=0。
- [ ] Xvfb 用另一 journal 續跑至 pending=0。
- [ ] aggregate timeout 自動縮批；單顆 failure/timeout 才 root-cause。
- [ ] complete teardown timeout 按既有 runner 契約分類；process group 必須全消失。
- [ ] 每個時間片更新 durable checkpoint，不從聊天猜進度。
- [ ] 最終掃 orphan pytest/python/Xvfb/Tk grab。

**Acceptance:**
- Headless full suite 0 fail。
- Xvfb full suite 0 fail。
- pending=0、collection SHA 一致。
- 無 orphan process / stale journal 冒用。

**Worker report contract:**
```text
Task: T13
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


### T14: 技能／踩坑庫同步 + FULL/UPDATE Fresh Package Gate

**Lane:** E / 總控交付  
**Depends on:** T13

**Files:**
- Modify when confirmed lessons exist: `.agents/skills/engineering/phase6-gui-performance-integrity/SKILL.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- Modify release docs/evidence as required
- Do NOT modify/package: `config.ini`
- Produce FULL + UPDATE with same Asia/Taipei timestamp

**Objective:**  
把本輪真正確認的新坑同步到 Skill/踩坑庫，然後依既有 Phase6 release policy 建 FULL/UPDATE；在兩個 pristine fresh extraction 驗 CRC/SHA、mandatory files、UPDATE overlay 與回歸，不拿跑過 pytest 的目錄做封包比對。

**Interfaces:**
**Consumes:** T13 full green evidence。

**Produces:** FULL zip、UPDATE zip（同時間戳）、package evidence、fresh-extraction verification evidence、final changelog。

**Steps:**
- [ ] 只把已被 red/green 證明的新坑寫入 Skill/踩坑庫，不把猜測寫成規則。
- [ ] `config.ini` 前後 SHA256 必須相同，且 UPDATE 不含 `config.ini`。
- [ ] FULL/UPDATE 用同一 Asia/Taipei `YYYYMMDD_HHMMSS`。
- [ ] ZIP CRC 驗證。
- [ ] 各自 fresh extract；逐檔 SHA256、mandatory files、AI/skills tree 檢查。
- [ ] UPDATE overlay 對既定累積基準檢查；比較目錄不得先跑 Python/pytest。
- [ ] fresh extraction 再跑必要 smoke/preflight/package gate。
- [ ] 生成最終交付報告：規格→工單→commit→tests→stress→full suite→package 對照。

**Acceptance:**
- 所有規格 Acceptance Criteria 全打勾才可出包。
- FULL/UPDATE 非空、CRC/SHA 正確、fresh extraction gate 綠。
- `config.ini` SHA 不變且 UPDATE 不含該檔。
- 任何 regression failure 未 root-cause 則禁止交付。

**Worker report contract:**
```text
Task: T14
Preflight evidence: 填入本工單實際 evidence 檔完整路徑
Base/commit: 填入實際 commit/hash；無 Git 時明寫 NO_GIT
Changed files: 逐行列出實際變更檔案，不可寫「同上」
Tests: 逐條列出實際命令與 passed/failed/skipped 數量
Counters before/after: 寫出本工單適用的 calculation/manufacturing/scene/render/publish/echo/DXF read 前後值
Spec deviations: 無偏離時寫 NONE；有偏離時寫實際 ruling、理由與風險
Residual risks: 無殘留時寫 NONE；否則逐項列實際風險與後續 gate
```


---

# 總控 Review / Merge Protocol

1. 每張 T01～T10 工單完成後，總控先做 **spec compliance review**，再做 **code quality review**；兩者任一未過，退回同一工單修正，不把缺陷推給 T11。
2. T04-T06 與 T07-T08 若都改到 `gui.py`，總控以「sync ownership vs cache invalidation ownership」逐 hunk review；禁止同一 handler 同時偷偷恢復 direct calculation 或 cache clear。
3. 每個整合點重跑 Knowledge Preflight；新增 changed-file 必須補跑，不能沿用舊範圍 evidence。
4. 發現規格沒有涵蓋但會影響機械真值的問題時，**停止該機械變更**並另立幾何規格；本計畫不得越權改 Certified/Assembly semantics。
5. Git 不可用時可跳過 commit/worktree，但不得跳過隔離副本、preflight、測試、durable evidence 與總控 review。

# 最終 Definition of Done

只有下列全部成立才算完成：

```text
唯一 executor
+ transaction coalescing
+ anti-echo
+ atomic 3D initialization
+ precise derived cache invalidation
+ SOURCE_UNVERIFIED fail-safe
+ Manufacturing→Collision 單向依賴
+ canonical geometry / registry 不變
+ 真 GUI stress
+ Headless full green
+ Xvfb full green
+ durable evidence
+ config.ini SHA unchanged
+ fresh FULL/UPDATE verification
```

任一項未完成：**不得正式出包。**
