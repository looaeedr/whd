---
whd_doc_role: CURRENT
whd_contract: primary-phase6-left-drag-and-multi-nfb-list-removal
whd_schema: WHD_DOC_META_V1
---
# Phase6 主視窗左欄與多連內門清理（2026-10-28 台北）

## 操作決策
- 主視窗是 Phase6 折彎／3D 設計（phase6_workspace_shell.py）的組合體／板件欄，不是舊 gui.py 的外層控制欄，也不是多連設定的左欄。主視窗左欄寬度以當前文字比例之舊基準乘 0.90，Windows 中原 430px → 初始 387px，支援用可見 9px 拖曳柄左右調整。
- 拖曳不能讓 3D renderer viewport 小於 760px；左欄最小 190px；拖曳後的使用者寬度不受後續文字大小或設定同步重設。關閉重開恢復預設 90%，不用持久寫入專案或 config.ini。
- 保留先前 PR #2359 的「多連設定」自己的左側 90% 可拖曳 Panedwindow。不把主視窗與多連設定的左欄混為一談。
- 多連設定的內門頁移除『NFB 板件清單（唯讀）』整個顯示區；既有不可見舊交易控件由歷史回歸保護。原 NFB 確認、複製、還原、Undo、CSV V5 來源、實體 manufacturing manifest、DXF 出圖所有服務與規則保持不變。正式操作歸 NFB 設定／編輯器與原選取 DXF。

## 檢查
- 新 Windows 真 Tk 測試 tests/test_phase6_main_sidebar_sash_and_no_multi_nfb_list_20261028.py 直接建立 gui.Phase6PrimaryApplication，確認主視窗寬度縮減、<ButtonPress-1>/<B1-Motion> 拖曳與 3D >=760px、使用者寬度留存；建立 multi modal 確認沒有 NFB 清單，而 source manifest `NFB_WORLD_X_RECONFIRM_REQUIRED` 仍可讀。
- 原 #1500 native Tk 測試繼續查 CSV 每筆 NFB、實體板件與 NFB 源 SHA；顯示清單從 operator view 移除後，改在真正的 manifest projection 查內容，避免以隱藏 UI 假裝通過。
- #343 既有 CJK 字型／左欄文字縮放契約保留原 baseline 338／430／480，主視窗 user-facing width 乘 90%；Windows 字型 msjh.ttc 正式辨識為 Microsoft JhengHei。
- 原生 GUI 與 Canonical Product Regression 必須對新的 exact SHA 全部通過才合 GitHub localX。正式 X 不准更新，Windows 目前的 Z:\localX、config.ini、logs 與開啟中的程序不覆寫、不強制結束。
