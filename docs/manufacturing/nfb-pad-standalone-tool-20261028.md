---
whd_doc_role: CURRENT
whd_contract: nfb-pad-standalone-draft-preview
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# NFB 墊高片獨立工具 — 規格與使用方式（2026-10-28）

## 入口

從 WHD 專案根目錄執行 `python nfb_pad_standalone.py`。Python 必須具備
Tkinter；「草稿 DXF」功能另需已安裝 `ezdxf`。這是獨立於 WHD 受電箱
GUI 的視窗，**目前仍需同一份 WHD 原始碼、CSV V5 與加工規則資料夾**，
不是獨立封裝的 EXE，也不會修改原 WHD 專案或 `config.ini`。

## 操作

1. 指定實體層（1–32）、廠牌與 NFB 型號，按「加入 NFB」。型號只讀取
   `基準檔/開孔/NFB/數值規格/<廠牌>/NFB數值規格.csv`。
2. 可跨層加入多顆 NFB，每層獨立按最深者計算墊高量；兩顆同深度不用 PAD。
   板厚預設 2 mm，**可修改，不是任何 NFB 型號的硬編碼規則**。
3. 按「計算墊高片」，切換 2D 展開與 3D 折彎**示意**。畫面尺寸與折線
   來自 `generate_nfb_pad_patterns`；3D 示意不宣稱實際貼合、折彎半徑、
   底板碰撞或焊接已驗證。
4. 「輸出草稿 DXF」建立全新資料夾（禁止覆寫），圖層為
   `DRAFT_OUTLINE`、`DRAFT_BEND`、`DRAFT_SCREWS`、
   `DRAFT_WARNING`，並寫入 `DRAFT_NOT_FOR_MANUFACTURING.json`。
   不輸出正式 `CUTTING`、`BEND`、`CHECK/Q` 或 NC 檔案。

## 單一規則與製造權限

計算核心、原始 CSV V5、共用加工 JSON **直接重用 WHD 既有模組**：
`ae_engine.receiving_nfb_numeric_catalog`、
`ae_engine.receiving_nfb_pad_generator`。獨立 UI 只能新增選型、
分層、預覽及明確標示的草稿匯出；不可另寫另一套 PAD 幾何，
不可複製公式、猜測未填 CSV、跨層共用最深深度。

正式加工須回到 WHD，使用原始 Hole Editor 實際提交的 X/Y、認證
底板來源、PAD 與底板方孔接觸、裝配 3D、CHECK/Q及 NC 製造程序驗收。
本工具的 `PadPattern.manufacturing_ready` 一律為 false；
單獨草稿 **不可當作已核准的工廠輸出**。

## 測試

`python -m pytest tests/test_receiving_nfb_pad_standalone.py -q`

測試涵蓋 107/68 的 39 mm、雙層隔離、相同深度不產生、
錯誤資料 fail-closed 與草稿 DXF 非製造圖層、禁覆寫。
正式 X 無使用者 `/推推` 不發布。
