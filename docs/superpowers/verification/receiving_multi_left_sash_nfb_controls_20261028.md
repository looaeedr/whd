---
whd_doc_role: CURRENT
whd_contract: receiving-multi-nfb-operator-surface-single-editor-draggable-left
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Receiving 多連設定 — 內門單一操作入口及左欄寬度

## 使用者決策（2026-10-28 Asia/Taipei）

- 多連設定的「內門」頁面不顯示重複的 NFB 確認套用／複製／還原／Undo 按鈕及兩個 NFB 專屬局部 DXF 出圖按鈕。保留內門版本選取、編輯、套用、版本管理及唯讀板件清單。真正 NFB 層數與選型只在原 NFB 設定／編輯器操作。
- 不可刪除或放寬現有 NFB 交易 authority、cancel/Undo/Restore、實體 Bay identity、source verification 與製造守衛。舊 #1500/#1504 交易 UI 測試目前仍有未映射到螢幕的相容操作掛鉤；實際操作者在多連內門頁看不到這些按鈕。等歷史回歸移到統一編輯器／交易 API 後才刪除相容掛鉤，避免假冒驗收或刪測試。
- 左欄是多連設定「套／連／NFB 品牌」設定欄。Tk 實際計算的原始 requested width 首次縮為 90%，以 ttk.Panedwindow 分隔線拖曳調整，切換內門／封頭設定或 Bay 選取時不重設 sash。右側 2D 顯示區可隨剩餘寬度伸縮，模型尺寸／資料不變。
- Windows 的最大化驗收應比較 Windows WorkingArea（扣除工作列），不是全螢幕像素高度。不更動最大化行為、不動原生關閉和 modal grab。

## 驗收

- R5-2600 原生 Windows Tk：左欄 requested 313 px → 初始 282 px（90%）；手動拉到 357 px，切換設定頁仍維持 357 px。5 Bay 2D 命中盒仍存在，視窗可關閉；內門頁可見編輯／套用／版本管理，無 NFB／DXF 操作按鈕。
- 原 #1500 Tk NFB 提交／複製／還原／Undo 交易測試 33 項，加上新的可見性與拖曳測試 1 項：34/34 PASS。原 #1504 舊專案 GUI 6/6 PASS。
- 更新 test_receiving_multi_settings_stage_20261010.py 對 Panedwindow 左右關係及 Windows 可用工作區的斷言，不刪除原 Set/Bay 操作測試。
- CI 必跑：tests/test_receiving_multi_clean_nfb_draggable_sidebar_20261028.py，原 #1500/#1504 交易及 GUI 原有測試照跑。
- 合併僅限已簽 CI 的 GitHub localX，使用者目前的 Windows Z:\localX、config.ini 和 log 不覆寫，正式 X 須當次 /推推。
