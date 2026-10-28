---
whd_doc_role: CURRENT
whd_contract: receiving-no-base-edge-shrink-lock-close
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 受電箱底板取消「縮」／參數面板可關閉（2026-10-28）

## 問題來源

之前僅移除 `phase6_settings_panel_owned_render.py` 受電箱專屬縮邊欄位；真正殘留在 3D 圖面四邊的是 `gui_modules/application/fold_designer_composition_registry_edges.py` 的 `render_base_plate_edge_controls`，即使參數鎖定也照常顯示，造成操作員仍看見「上／下／左／右縮」。

另外 3D 畫布右上角「參數鎖定」在展開板件設定／組合體診斷時，畫布可能被版面推到可視區域外，原按鈕雖可由測試程式 `.invoke()` 操作，真實滑鼠卻無法收合。

## 改善契約

- `model=受電箱/RECEIVING` 的底板**不建立**四邊縮邊輸入，且直接呼叫既有 `commit_base_plate_edge_shrink` 也必須拒絕；不刪不改內部保存的 `shrink_*` 幾何來源，防止展開、孔位、NFB 墊高片、3D/製造資料漂移。
- 非受電箱的底板仍保留舊有四邊縮邊輸入及更新功能。
- 展開板件設定與組合體診斷時，在可見的面板自身加入「收合參數」，直接呼叫同一個 `toggle_parameter_panel`，不得新增另一套鎖定狀態；再開／再關、切換零件仍要正常。
- 未更改專案 `.p6fold`、`config.ini`、DXF 或正式 X；使用者目前正在執行的 Python 視窗需重新啟動才能載入更新程式。
- GUI 合格須驗證真實 Tk `winfo_manager()/winfo_ismapped()` 與點擊 `invoke()`，而非只檢查程式字串。

## 測試

`tests/test_receiving_base_no_shrink_and_lock_reclose_gui.py`：受電箱無四邊縮、直接改值拒絕且數值不變、設定及組合體兩種面板都可收合且再次切換。

原有 `tests/test_phase6_receiving_edge_controls_gui.py` 的非受電箱四邊縮輸入仍須通過。
