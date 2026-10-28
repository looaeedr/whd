# 多連設定 NFB 品牌下拉入口移除（2026-10-28）

此變更補上前一批 PR #2366 在實際 Windows 操作時發現的遺漏：多連設定視窗左上角還有「NFB／士林」品牌下拉選單。使用者指定整個多連設定不再需要重複的 NFB 操作／清單入口。

- receiving_multi_settings_window.py 的 brand_row 不再 pack 進可見的 Set／Bay 左欄。操作介面不顯示 NFB 品牌下拉；不是隱藏內門元件或刪掉真正的 NFB 編輯器。
- 原 brand_var、Combobox、apply_brand callback 暫作未映射的歷史交易測試相容掛鉤，不影響舊 #1504 AC-01/20/21 的品牌合法性／確認／取消／Undo 規則。未映射的控制項不會對操作者顯示或接受滑鼠操作。
- 保留先前主 Phase6 左欄 90%／可拖曳和「多連設定」本身的拖曳左欄、內門 NFB 按鈕與板件清單隱藏；不動 NFB 尺寸、孔、幾何、CSV V5 來源、實體製造或 DXF。
- R5-2600 原生 Windows GUI 包含 #1504 AC-01、AC-20、AC-21、原多連布局及主 Phase6 左欄：39/39 PASS。新版 test_phase6_main_sidebar_sash_and_no_multi_nfb_list_20261028.py 額外明確斷言 brand_selector.winfo_ismapped() 為 False；原多連控制項可見文字不再包括 NFB。
- 此修正以新的 exact-head Product CI 全綠為 GitHub localX 合併條件；未經 /推推 不碰正式 X。使用者正在執行的 Windows Z:\localX 不強制關閉或丟棄資料。
