# #1817｜單連快取與完整求解的同機對照（2026-10-17）

> 狀態：此文件定義量測協議；**不預先宣稱任何成功樣本或改善幅度**。實際成功與統計以本 PR 的 GitHub Actions 真 Tk 原始 artifact 為準。

## 正式來源和比較範圍

- 基準：GitHub `localX` 已完成 PR #1838～#1841，進入此 PR 前 HEAD `48937c186b31364dc13f3eeb95ff8c66f58a3fda`。
- 使用原有 `tools/whd_performance_baseline.py`、原有「WHD Performance Baseline Evidence」GitHub Runner、Linux Xvfb Tk、真 `Phase6PrimaryApplication` 與 Fold Designer UI，不使用 DC/RC/Windows，不造假組裝模型、不改幾何精度。
- 既有 1／3 連冷暖 benchmark 保留，另在 **3 連 topology** 完成初次設定與 modal 關閉後，執行每 worker 一次配對的 #1817 項目。
- 同一 GitHub Runner、同一 Python process、同一已載入的原始資源，比較 **單連預覽取回已完成結果** vs **只清除該單連預覽快取並用原始權威 API 重新製造求解**。這是 `receiving_bay_preview_request()` 的節省，不等同整個操作／Windows 顯示器的端到端加速。

## 實際 GUI 操作與紀錄

| Operation key | 現行 GUI 操作／量測對象 |
|---|---|
| `issue1817_bay0_first_full_solve` | 3 連真 GUI，第一次建立第 1 連的 `FinalSceneViewRequest` |
| `issue1817_bay0_cached` | 相同權威快照取回同一份結果；正式 solve 次數預期為 0 |
| `issue1817_bay0_forced_full_comparison` | 在相同狀態下僅移除第 1 連預覽 cache，重新呼叫**真正製造／FinalScene**，正式 solve 次數預期大於等於 1 |
| `issue1817_append_tail_bay4_actual_ui` | 真 `＋連` Tk 按鈕、套用、關閉，變成 4 連（*不*直接改測試用假資料） |
| `issue1817_bay0_after_tail_append` | 真實拓樸修改後重取第 1 連，需是原物件、solve=0、板件鍵／偏移及原材質一致 |
| `issue1817_remove_tail_bay4_actual_ui` | 真 `－連` Tk 按鈕、套用、關閉，回到原 3 連 |
| `issue1817_bay0_after_tail_remove` | 恢復拓樸後再取第 1 連，必須仍為原物件、solve=0、板件鍵／偏移及原材質一致 |

原 `record()` 必須採集 `wall_ms`、`counts.manufacturing_solve`、`counts.part_materialization`、`materialized_parts`（逐 Part Key）、`material_factory_rebuild_calls`、真 GUI `calculation_flushes`、`scene_render`、`dxf_readfile` 與 RSS；統計使用同一份 raw journal `summary` 的 median/P95，不可混入另一版本 runner 時間當絕對收益。

## 幾何與失效條件

第一連真製造結果的 assembly part keys、逐 part offsets、可比較的原始平片材料 `equals` 必須與同來源強制完整重算一致。尾端增減後第一連必須保有相同 preview object identity。任何缺少來源、geometry resolve 例外、GUI callback 錯誤、空物理件、變更時 unintended manufacturing solve 或誤重用均讓 benchmark run 失敗，**不把失敗列刪掉**。

最終完整驗收仍包括 Windows `Z:\localX` 使用者實機 GUI、DXF 匯出與存檔重開的內容 parity；Linux 雲端樣本不可冒稱已完成 Windows UAT。本文件／測試工具不修改 `cleanup/2d-3d-sync` 正式 `X`。

## 真 Tk 已完成實測（2026-10-17）

**測試證據：** 工具 PR [#1842](https://github.com/looaeedr/whd/pull/1842)，真實量測 exact HEAD `cedafed8a659369845cca7cfa0d52ddddc5d2830`，合併 GitHub `localX` `2e865fe9277f053a29d9b8428baca031ac1f5cdc`。同 HEAD 的 [WHD Product Regression #38993576295](https://github.com/looaeedr/whd/actions/runs/38993576295) 與 [WHD Performance Baseline Evidence #38993576310](https://github.com/looaeedr/whd/actions/runs/38993576310) 均 completed/success。原始 artifact [#12085947541](https://github.com/looaeedr/whd/actions/runs/38993576310/artifacts/12085947541)（保留 14 日），含原始 `baseline.json`、6 worker JSONL／log、環境與工具 SHA。**243 筆完整真 GUI 操作，0 失敗；包含原先 222 筆 #1816 基準操作及 21 筆 #1817 特別操作。**

### Linux Xvfb 同 Runner 配對數據

各列均為三個獨立 fresh-process 的三連箱體真 Tk 操作，`n=3`，毫秒為 Tk update/settled，非顯示器 scan-out。強制完整重算只**移除本次第 1 連 preview cache**，仍經現行正式製造 API，不是測試替代 geometry。

| 操作 | median ms | P95 ms | 每筆 `manufacturing_solve` | 每筆 `part_materialization` | 五主要工廠成功建材 | Scene render | DXF disk read |
|---|---:|---:|---:|---:|---:|---:|---:|
| 第 1 連第一次完整預覽 | 683.55 | 697.39 | 1 | 13 | 7 | 0 | 0 |
| 第 1 連已暖快取 | **1.68** | 1.79 | **0** | **0** | **0** | 0 | 0 |
| 同狀態強制真實完整重算 | **654.49** | 718.88 | **1** | **13** | **7** | 0 | 0 |
| 真 UI 增加第 4 連並關閉 | 1361.29 | 1369.78 | 1 | 13 | 15 | 1 | 0 |
| 增連後重取第 1 連 | **1.65** | 1.65 | **0** | **0** | **0** | 0 | 0 |
| 真 UI 移除第 4 連並關閉 | 1343.96 | 1410.38 | 1 | 13 | 15 | 1 | 0 |
| 減連後重取第 1 連 | **1.61** | 1.90 | **0** | **0** | **0** | 0 | 0 |

上述 13 個真正製造物件輸入（每次 forced full solve／每次尾端增減 GUI 提交中均已觀測到）：`box_body`、`head`、`tail`、`base_plate`、`door_c1_r1`、`door_c1_r2`、`box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1`、`inner_door:upper:panel`、`inner_door:upper:top_frame`、`inner_door:upper:left_frame`、`inner_door:upper:right_frame`、`base_plate:fixing_plate:left`、`base_plate:fixing_plate:right`。**這是 13 個 key 的 materialization，不等於 13 塊獨立鈑金實體。**此外 `world_skin_physical_rematerializations=15`，也是另一層不可與 13 相加的計數。

**準確結論：** 無關尾端增減後第 1 連會返還**同一份**已認證預覽物件，0 次求解、0 次重新建材，且程序會檢查 world offsets、各 Part Key 以及可比較平片 `equals`，確定不是快取到 stale 幾何；強制完整重算則確實呼叫製造引擎 1 次並 materialize 13 個 key。這是**單連預覽路徑**的配對數據，不能推論全部 GUI 操作縮短 `654/1.68` 倍或任何固定百分比；n=3 也不能當成 Windows 機台穩態。

### 還要修的實際瓶頸與安全界線

真 `＋連／－連` 操作本身仍需約 **1.3 秒**：各 1 次正式製造求解、1 次場景 render、13 個輸入 materialize、15 次五工廠 successful builds。其 `calculation_flushes=2` 是**兩個 GUI owner 的 Scheduler metrics 合計**，不是兩次製造求解，不能擅自刪除 executor。產品後續要追查對本來未改動的板件，在 **Set/Bay/Joint、共用設定與完整成品輸出**依賴下能否安全跨交易重用；不能只把現行全局 manufacturing cache key 裡的 `receiving_layout` 刪掉，否則可能漏算相鄰接合與碰撞、下料／DXF。

剩餘 #1817 完成條件：同機比較有無局部重算在整個 GUI 提交的作用、真製造可保留件 vs 真需重算件，以及完整 save/reload、2D／3D、DXF 製造成品一致性與 Windows 實機 UAT。正式 `X` 未經使用者當次 `/推推` 不發布；本項仍只是 GitHub `localX` 雲端驗證證據。
