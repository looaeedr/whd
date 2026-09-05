---
name: phase6-gui-performance-integrity
description: Use when Phase6 GUI/3D feels slow, freezes, stutters, recalculates repeatedly, reloads DXF unexpectedly, or when changing Tk trace/live-sync, 3D initialization, cache invalidation, debounce, render scheduling, or GUI performance tests.
---

# Phase6 GUI / 3D 效能完整性 Gate

## 核心原則

GUI 效能修正不能靠「少算、延遲不更新、降低幾何精度」製造假快。每次互動必須維持 canonical state → geometry → 2D/3D → save/export 一致，同時消除重複計算與重複 I/O。

## 更新管線唯一權責

**Scheduler 是唯一 calculation executor。** Tk trace、Transaction Guard、live callback、3D callback 都只能 `mark_dirty()` / `request_flush()`，不得直接呼叫完整 calculation、FinalScene build、manufacturing resolve 或 render。

- Transaction Guard 只管理 nesting/批次邊界；`end_sync()` 不自行 calculation，只通知 Scheduler flush。
- Dirty reason 至少區分 geometry / assembly / baseline / display / annotation / camera；Scheduler 合併同一 transaction，最多一次 calculation、一次 scene update、一次 render。
- Slider/Spinbox/camera drag 可由 Scheduler 做短 trailing debounce；最後一筆必須執行。Enter / FocusOut / MouseRelease 必須立即 flush。
- **Save / Export / DXF / NC 前**必須 `flush_now()`，禁止輸出 stale state。
- 測試若用 `SimpleNamespace`、`__new__` 或其他 partial GUI fixture 直接呼叫 production handler，fixture 必須實作該 handler 的正式 Scheduler seam（目前至少 `_request_phase6_update(...)`）；**禁止為了遷就缺介面的 test double，在 production handler 加回 direct `update_calculations()` / `do_update()` fallback**，否則會破壞唯一 executor。
- 等價的 part switch / display-only 切換只允許 render/display dirty；若 canonical geometry/assembly 沒變，正式契約是 full calculation = 0，而不是為相容舊測試硬做一次完整 update。

## GUI ↔ 3D Anti-Echo

同步 envelope 至少保留 `origin + revision + transaction_id`，並以 actual delta 判斷是否回送。

- Main GUI → 3D 的等價 state 禁止再原封不動 publish 回 Main GUI。
- 3D 真正由使用者修改才建立新 revision 並 publish。
- 批次套 settings 必須使用 `set_var_if_changed` 或等價 canonical compare；值相同不得再 `var.set()` 觸發 Tk trace。

## 3D Atomic Initialization

初始化期間只 ingest current authoritative state，不 publish default/intermediate state。優先級固定：

`使用者目前輸入 > authoritative application state > persisted state > 3D default`

初始化完成時若結果與 Main GUI 一致，publish=0；較舊 revision 一律拒絕覆蓋較新 state。

## DXF / Geometry Cache

Cache 必須分兩層：

1. immutable DXF source cache：path + size + mtime_ns + parser/schema version + reload generation。
2. derived geometry cache：依 W/H/D/FW/Joint 等真 dependency 精準失效。

普通尺寸修改不得清 parsed source cache。網路磁碟暫時失聯時，GUI preview 可使用 last-known-good 並標記 `SOURCE_UNVERIFIED`；manufacturing / Save authoritative result / Export / DXF / NC 禁止把未驗證來源當 fresh truth。Force Reload 必須能繞過相同 path/mtime/size。

## 效能驗證不是只跑 pytest

每次相關修改至少量：

- `recalculation` 次數
- `DXF disk read` 次數
- FinalScene/manufacturing resolve 次數
- `render` 次數
- 單步 wall time

單一 geometry edit 的結構目標：`recalculation <= 1`、相同 DXF disk reread = 0、FinalScene rebuild <= 1、render <= 1、live-state echo = 0。

除了自動 regression，必須跑**真 GUI 壓力**：連續 W/H/D/T burst、箱身/封頭/封尾快速切換、Family/Assembly Intent 切換、3D 開關與連續互動。每段驗證最終 state/scene 一致、無事件暴增、無 Tk grab/Xvfb/pytest orphan、無 stale cache。

## Durable evidence

長時間 profiling / stress / release 驗證不得只存在對話或臨時工作樹。建立 **durable checkpoint**，至少保存來源包、工作樹/patch hash、collection SHA、completed/pending/failed、journal 路徑、效能計數與下一步命令。任何續跑先讀 durable state，不從聊天文字猜進度。

## 禁止事項

- 禁止用大型 debounce 掩蓋單一 transaction 內的重算風暴。
- 禁止 display-only 變更觸發 manufacturing solve 或 DXF reload。
- 禁止全域 `cache.clear()` 取代 dependency invalidation。
- 禁止只看 callback/state 已變就宣稱同步；必須驗最終 geometry/scene。
- 禁止只跑 headless 或一般 regression 就宣稱 GUI 順暢；真 GUI 壓力 gate 不可省略。
