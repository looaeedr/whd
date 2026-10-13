---
whd_doc_role: REFERENCE
whd_contract: ai-library-reference
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# 📐 05. CAD 批次拆圖與特徵萃取規範

> **REFERENCE／歷史拆圖方案，不是目前 WHD 執行入口。** 本檔記載的 Windows 專案路徑與 Adapter 是舊方案留存；現行 repository／施工位置及製造 API 由正式 X 的 `AGENTS.md`、`09_WHD_Canonical_Authority_Map.md`、`04_WHD鈑金展開幾何引擎規範.md` 和當次 production 原始碼確定，不得據此轉用本機或建立第二套 domain authority。
>
> 歷史專案路徑：`Z:\Ollama-整合whd\`（非現行工作根目錄；本次正式 X tree 沒有 `modules/ae_adapter.py`）。

---

## 🔍 拆圖管線核心模組

1. **大圖框感應與廢圖過濾**
   - 辨識 `A$C784A6902` 標準圖框塊，或 3000~6000 × 2500~5000 獨立矩形框。
   - 掃描洋紅色（Color 6）打叉劃線，自動剔除作廢圖框。
   - 支援大框內多盤體（Multi-PANEL）X 軸自動切分。

2. **雙軸氣切視圖分離（Gas-Cut View Segmentation）**
   - 分離「正視圖」、「配置圖」、「側視圖」、「左視圖」。
   - 歸屬「箱身」、「封頭」、「封尾」等子區塊。
   - 跨框搜尋：主框缺乏配置圖時，自動向右側鄰框抓取補全。

3. **底座獨立拆分 (`detect_child_bottom_base`)**
   - 以幾何 + DXF 尺寸交叉驗證，不依盤名、不寫死 50mm。
   - 確認底座後：`高` 自動扣除底座改為箱體實際高度，`底座高度` 獨立欄位。
   - 產出獨立 `底座.dxf`。

4. **後端展開整合 (`ae_engine`，以下為歷史方案／不可直接當作現行 API)**
   - 拆圖完成後透過 `modules/ae_adapter.py` 將 finalized info_data 與 features 轉為 `CabinetJob` / `PartSpec`。
   - 直接調用 `ae_engine.manufacturing_api` 產出加工展開圖。

5. **成果導出標準**
   - DXF：乾淨獨立視圖圖面（加工圖跟隨 GUI 設定的輸出根目錄）。
   - JPG：自動快照（含指示燈盒 / 指示燈小門）。
   - CSV：盤體總表、排版座標表、尺寸明細表（支援同名盤體尺寸補全）。
