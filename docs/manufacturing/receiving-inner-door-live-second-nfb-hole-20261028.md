---
whd_doc_role: CURRENT
whd_contract: receiving-inner-door-live-second-nfb-hole
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 內門同層新增第二顆 NFB：主孔即時預覽（2026-10-28）

## 問題與修正

內門「受電箱」頁按「＋加入」以前僅更新 NFB 清單；
第二個 CSV CUTTING 主孔必須額外按該頁「確定」才匯入原開孔
編輯器，因此使用者認為「第 2 孔沒有出現」。

現在同層按「＋加入」立即依現有 CSV V5 與
`editor_nfb_features_from_csv` 產生所有已選主孔，透過
原生 `HoleEditorAction.preview_all` 暫存並重新描繪主畫面。
此行為只更新原生 Hole Editor 暫存，**不保存至 Receiving
Set/Bay、數量版本、工作區或正式 DXF**。

## 取消／復原與提交

- 「復原 NFB」、移除、替換、層數改動都要同步原生預覽；
- 內門頁「取消」恢復進入該頁前的 NFB 主孔、先前 staged_config；
- 原主頁「確定全部」才正式提交，使用既有物理孔與 CSV 原始來源證明；
- 不合法 CSV/孔位、跨門或碰撞不得默默生成假第 2 孔；
  UI 顯示明確錯誤，保留上一次合法暫存；
- 畫面測試以**不同位置的輪廓**計數，不把同一個重疊輪廓
  重畫兩次誤認成兩個不同孔；
- 實體製造／NC 仍須遵守現行安全門檻。

## 測試

`tests/test_issue1504_live_second_nfb_main_canvas.py`
驗證 1→2 顆同層 2P400、立即出現二個不同位置孔、
Undo 回 1、取消不寫專案、重新加入後
Confirm All 才持久化兩孔和兩筆 NFBConfig。
