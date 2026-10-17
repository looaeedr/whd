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
