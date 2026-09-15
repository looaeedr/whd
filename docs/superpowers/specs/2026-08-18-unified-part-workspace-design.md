# FIX14 統一板件工作區設計

## 目標
把 Phase6 現有的板件/截角與開孔編輯器整合到同一個主視窗工作區，共用同一個目前板件；3D 折彎設計器恢復為獨立入口，避免主工作區長時間佔用 3D 畫面。

## UI 契約
主預覽區頂部固定兩列控制：

1. 板件列：`箱身 / 封頭 / 封尾 / 門 / 底板 / 指示燈盒 / 指示燈小門 / ＋新增`。所有板件與箱身同層，空間不足可換行；不得使用板件下拉選單。
2. 功能列：`截角/板件 / 開孔`。

左側控制區另有 `開啟折彎 / 3D 設計` 獨立入口。按下才開啟原始 3D 設計器 Toplevel；主工作區不再把 3D 當第三種 mode。

目前板件仍是共享選擇；從主工作區選定板件後，打開 3D 時以該板件作為 active part。

## 資料契約
- Phase6 GUI 變數、Feature/CornerType/基準檔資料仍是正式製造來源。
- 3D 編輯器沿用 `fold_designer_original.py` 的 Renderer/BendingUI；該檔保持 byte-identical。
- 3D 由 `open_original_fold_designer()` 開啟獨立 Toplevel，關閉/套用時透過既有 snapshot bridge 回寫 Phase6 GUI；回寫後重算正式 geometry、Corner relief，並清除基準衍生 cache 讓目前基準檔以新尺寸重載。
- 開孔仍只使用 Phase6 `surface_features`；原 prototype HolesUI 不作編輯來源。

## 封頭尾 / 包外尺寸既有契約
FIX13 定義不變：
- X UI core = `W - 2T`，Renderer/正式 BEND span = `W - 4T`。
- Y UI core = `D - T`，Renderer/正式 BEND span = `D - 3T`。
- 封頭/封尾 X+Y 均存在，上邊兩折保留。
- ±90 只在 UI 邊界反號。
- 不使用 FIX12 立姿 transform，維持原 Renderer 姿態。

## 不可變條件
- 不修改 `fold_designer_original.py`。
- 不修改 `ae_engine/` 製造核心。
- 不新增第二套 CornerType 或開孔資料。
- `config.ini`、基準 DXF 不得被更新包覆寫。


## API 盤點

現行 API 邊界與多門接入方式請參考 `docs/superpowers/CURRENT_API_INVENTORY_20260818.md`。
