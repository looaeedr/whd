# WHD 板金展開自動化系統 (Sheet-Metal Unfolding Geometry Engine)

WHD 鈑金展開自動化系統是一套專為鈑金箱體加工設計的 2D 自動展開與 DXF 生成引擎。本系統已全面揚棄傳統「硬編碼頂點陣列 (Hardcoded Vertex Arrays)」與「單一零件獨立座標演算法」的舊式做法，採用現代幾何拓撲 (Topology) 與布林運算 (Shapely Polygon Boolean) 的核心架構。

---

## 💡 核心設計理念與架構宣告

> **「告別『新增零件 = 新寫一套外框公式』的傳統思維！」**

在全新幾何引擎中，所有零件外形皆收斂為以下核心公式：

Material Polygon = Base Polygon - Relief Polygon

1. **Topology (拓撲結構) 與 Factory Policy (製造規範) 徹底分離**：
   - **Topology**：定義板材的物理折彎結構（如四邊折彎 FourSideFlange、連續展開條帶 StripFoldChain）。
   - **Factory Policy**：定義各廠牌或特定箱體類型的裝配退讓（Relief）、過切 clearance 與缺角規則（如金庫型封頭尾裝配插入退讓）。
2. **新增零件極簡化**：
   - 未來新增任何新零件類型時，**嚴禁**重新手算 12 點、16 點或 17 點頂點陣列。
   - 只要既有的 Topology 與 Factory Policy 能描述該結構，新零件**僅需傳入折邊尺寸與裝配扣量**即可自動計算出 100% 精準的 2D 展開幾何。
3. **Geometry 是唯一真相來源 (Single Source of Truth)**：
   - GUI 預覽（Canvas）與 DXF 檔案導出統一呼叫 sheetmetal_geometry.py 幾何結果，確保「畫面所見即為 DXF 所出」。

---

## 🛠️ 系統分層架構

- **Layer A (sheetmetal_geometry.py)**：純 2D 板金幾何引擎。獨立於 DXF 與 GUI，只負責 Polygon 算術與 Bend 計算。
- **Layer B (ae.py)**：參數轉接層。讀取 config.ini / CSV 並呼叫幾何引擎生成各加工圖層（CUTTING, BEND, MARKING, CHECK 等）。
- **Layer C (gui.py / batch_unfolder.py)**：GUI 操作介面與自動化批次處理產線。

---

## 📦 目前已涵蓋的零件拓撲

- Door / Stretched Door (門板 / 延伸門板)
- Box Body / Stretched Box Body (箱身 / 延伸箱身)
- End Cap / Tail (金庫型封頭 / 封尾)
- Indicator Box (指示燈盒子 / 小門)
- Base Plate (底板)

---

## 🚀 快速開始

### 環境需求
- Python 3.8+
- Shapely
- ezdxf

### 安裝依賴
`ash
pip install -r requirements.txt
`

### 執行 GUI 計算器
`ash
python gui.py
`

### 執行完整測試套件 (TDD Baseline)
`ash
pytest
`

---

## 📖 系統文件與交接指南

更詳細的開發規格與金庫型製造規範請參考專案文件：

- AGENTS.md — 專案核心精神與 AI 開發總覽。
- handoff/ 目錄：
  - 00_AI_HANDOFF_README.md — 快速接手說明
  - 01_ARCHITECTURE.md — 幾何與拓撲分層架構
  - 02_VAULT_FACTORY_RULES.md — 金庫型製造規範細節
  - 03_PART_TOPOLOGY_MAP.md — 零件與拓撲對照表
  - 04_DEVELOPMENT_RULES.md — 開發規範與 TDD 驗證

---

## 📄 授權與維護
© WHD Sheet Metal Automation System. All rights reserved.
