# 04 — Development Rules

## 禁止
- per-part hardcoded main outline vertex arrays
- exporter 自行重算 CUTTING/BEND
- GUI 自行重算製造 geometry
- 將 Canvas pixel 當 feature manufacturing coordinate
- 恢復 `geom['polylines'/'lines'/'circles']`
- 新增第二套 DXF serializer
- 用 task bbox / view bbox 比例縮放 Feature 座標
- 用展開總料中心取代 finished-face center

## 必須
- geometry/feature behavior 先寫 failing test
- `sheetmetal_geometry.py` 不 import ezdxf/tkinter
- `sheetmetal_features.py` 不 import ezdxf/tkinter
- `sheetmetal_drawing.py` 不 import ezdxf/tkinter
- `ae.py` 透過 DrawingScene serialize

新增盤型允許建立新的 Adapter / Factory Policy 模組，
例如 `RO.py`。

但：
1. 共用幾何仍進 `sheetmetal_geometry.py`
2. 特定製造差異進 Factory Policy
3. 不得因盤名建立獨立 hardcoded geometry
4. 每個新零件必須提供 finished-face
5. Feature 座標以 finished-face 為穩定接口
6. 自動拆圖只產生 Feature，不直接計算展開座標
7. Feature manufacturing coordinate 一律為成品面上的 1:1 mm 實體座標
8. 成品面 → 展開圖的座標轉換必須由該零件既有 resolver / reference guide 負責

## 最低驗證
```bash
pytest -q
python -m py_compile ae.py gui.py sheetmetal_geometry.py sheetmetal_features.py sheetmetal_part_adapters.py sheetmetal_drawing.py

若 ezdxf 可用，代表性零件必須 export + readfile round-trip。
