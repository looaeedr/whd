---
whd_doc_role: REFERENCE
whd_contract: reference-performance-issue1818-navigation-sync
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1818：純板件選取仍觸發主視窗完整更新

## 重現與原因

來源 PR #1867 HEAD `3b12a61697f3d3e3b557ec098e849c0fe4e4bb64`。真實三連 Tk benchmark 的 `issue1818_rapid_2d_3d_final_state` 仍有 `calculation_flushes=1`，即使 manufacturing_solve=0。

以觀測包裝記錄 Scheduler.submit 呼叫鏈：`activate_part → execute_fold_designer_update_reasons → publish_live_state → _apply_fold_designer_live_snapshot → mark_dirty("designer_live_snapshot")`。逐一比對完整 incoming/previous payload，只變更頂層與 workspace 的 active_part，以及 revision/transaction_id/delta/fingerprint。原主視窗仍重套 settings、existing_parts 並排程一次完整更新。

## 修正邊界

`navigation_only_change` 比較完整雙向 payload；僅忽略明確的傳輸 metadata 與兩處 active_part。必須有前次 payload、兩處 active_part 一致且屬於 existing_parts、選取確實有改變。任一其他欄位新增、刪除、變更都不符合，包括尺寸、孔位、折彎與未知欄位。

主視窗對已證明的純選取只設定 canonical workspace.active_part、更新截角面板上下文、擷取 committed project snapshot 並更新同步版本／fingerprint。不中斷選取保存，也不修改真正幾何變更的原有同步、失效與 Scheduler 路徑。

benchmark 將 display-only 的 0 calculation／0 manufacturing／0 DXF gate 移至 row validation 內。失敗必須寫入 failed JSONL，不能再出現 worker exit=1 但 FAILED_SAMPLES=0 的誤導摘要。規則數值未放寬。

## 雲端目標驗證

同機、相同三連程序操作、各一筆診斷樣本（不是穩定延遲分布）：

| 指標 | 修正前 | 修正後 |
|---|---:|---:|
| calculation_flushes | 1 | 0 |
| manufacturing_solve | 0 | 0 |
| manufacturing_cache_hit | 14 | 14 |
| scene_render | 7 | 7 |
| authoritative_render_cache_miss | 2 | 0 |
| material_factory_calls | 2 | 0 |
| wall_ms | 1408.65 | 1264.31 |

最後選取箱身、真 3D 非空、製造簽章有效、legacy 2D axes 隱藏的原 gate 均保留。兩項新增契約測試先 RED，再 GREEN；正式交付以 PR 最新 exact HEAD 的 Product Regression 與六個真實 Tk workers（1/3 Bay × 3 samples，每個 5 cycles）為準，不能沿用舊 HEAD GREEN。Windows UAT 與正式 X 發布不包含於本次雲端結果。
