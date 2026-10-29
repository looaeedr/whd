---
whd_doc_role: CURRENT
whd_contract: receiving-direct-3d-inner-door-nfb-confirm-all
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 受電箱 3D 雙擊內門：第二 NFB 主孔的實體提交

## 原生操作路徑

主程式 → 受電箱 → 上層內門門板 → 雙擊 3D → 受電箱頁籤 → 士林 3P125SN ＋加入 → 確定 → 回主開孔頁籤有雙孔 → 確定全部。**不經過多連候選套用。**

## 實際失敗原因

原始專案一顆士林 2P400。舊版 3D 直接入口的 settings_mode=None，在 Hole Editor 暫存選型和 CUTTING 特徵皆為兩筆，但內門 confirm_settings 只呼叫 workspace.stash_features，不保存原生 staged_config；實體 receiving_layout 的 NFBConfig 仍一顆，FinalScene 的內門板材仍僅一個孔。

## 修復契約

- 主「確定全部」時，對現有實體連由原生 CSV Features 和 staged_config 一次性校驗，再用 ReceivingSetBayAdapter 原子寫入該連的層數、型號、原生 Features 和兩個 NFBConfig 孔位；不可只保存主畫面暫存。
- 數量模式則保存到當前數量版本的 NFBConfig 和共用箱體狀態，不依賴合成展示別名。
- 按受電箱子頁籤「確定」仍只是草稿，主頁籤「取消全部」不得改動物理孔、候選版或專案。不能影響其他連。
- 製造 X 安裝基準仍為 UNVERIFIED_BASIS；3D 兩孔不表示製造放行。
- 驗收以真實 3D inner_door:upper:panel.render_data.material.interiors == 2、NFBConfig.holes == 2、不同物理孔 ID 為準，不單計 Canvas 上的兩個矩形。

## 重現與驗收

R5-2600 使用上傳的受電箱.p6fold 副本。修正前：在主編輯器 2 個 NFB_CSV_SOURCE，但按「確定全部」後實體 NFBConfig 1、3D material.interiors 1。修正後同一路徑提交 2 筆 NFBConfig，實際 3D 有 2 個內孔。

回歸：tests/test_receiving_direct_3d_inner_nfb_confirm_all.py。需在 CI 與 Windows 真實 Tk 操作驗證；不得用原有單只設定／多連候選的通過結果替代。

正式 X 不發佈；localX 合併需 CI 全綠，保留現有 config.ini、驗收日誌和原專案。