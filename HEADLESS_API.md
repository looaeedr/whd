# Headless Manufacturing API（Phase 6：AE Engine Clean Break）

目的：讓 GUI、自動拆圖、CLI 或其他 Python 程式都使用同一個 AE 出圖入口，不必建立 Tkinter GUI，也不必直接呼叫 `ae.export_xxx_dxf()`。

## 公開入口

```python
from ae_engine.contracts import ManufacturingContext, DoorPartSpec
from ae_engine.manufacturing_api import generate_part

spec = DoorPartSpec(
    width=500,
    height=600,
    thickness=2.0,
    frame_width=25.0,
    model_name="金庫型",
    features=(),  # finished-face 1:1 mm Feature / legacy feature dict
)

result = generate_part(
    spec,
    r"D:\輸出\加工圖\門-展開.dxf",
    ManufacturingContext(
        resource_root=r"D:\拆圖專案",  # 這裡底下有 基準檔\
        overwrite=True,
        draw_stock=False,
    ),
)
```

## PartSpec

目前支援：

- `DoorPartSpec`
- `BoxBodyPartSpec`
- `EndCapPartSpec(is_tail=False)`：封頭
- `EndCapPartSpec(is_tail=True)`：封尾
- `BasePlatePartSpec`
- `IndicatorBoxPartSpec`

指示燈小門沿用 `DoorPartSpec(model_name="指示燈")`，由 API 自動選 `基準檔/指示燈/小門.dxf`。

Feature 座標契約不變：**finished-face 上的 1:1 mm 實體座標**。API 不接受 Canvas pixel、normalized coordinate 或展開料座標作為來源加工座標。

## GUI Adapter（第二階段已完成）

GUI 的 DXF 出圖現在固定走：

```text
Tkinter state
→ GUI adapter helper
→ immutable PartSpec
→ manufacturing_api.generate_part()
→ existing AE exporter / resolver
→ DXF
```

`gui.py` 的出圖方法不再直接呼叫任何 `ae.export_*`。`ae` 仍可被 GUI 預覽與基準讀取邏輯使用，但**製造輸出入口只有 manufacturing_api**。

目前 GUI adapters 包含：

- Box Body（含 left/back/right face feature ownership）
- Head / Tail（完整保留 H、Y 折邊與 Z-side fold 參數）
- Single Door
- Multi-Door per-cell Door
- Base Plate
- Single / Multi Indicator Box
- Single / Multi Indicator Door

## Baseline 規則

- Door：存在 `基準檔/<model>/門.dxf` 時自動使用 stretched exporter；不存在才 formula fallback。
- `model_name="指示燈"` 的 Door 使用 `小門.dxf`。
- End Cap：存在 `封頭尾.dxf` 時使用 stretched exporter；不存在才公式 fallback。
- Box Body：主 CUTTING/BEND 永遠由 StripFoldChain 公式生成；如果存在 `箱身.dxf`，由既有 Box Body exporter 載入固定孔 / MARKING 等基準特徵。
- Base Plate / Indicator Box：目前沒有 model baseline dispatch，直接走既有 authoritative exporter。

## Resource Root

`ManufacturingContext.resource_root` 告訴 Adapter：

```text
<resource_root>/基準檔/
```

在哪裡。這讓 AE 程式放在 `modules/` 時，不需要再複製第二份 `modules/基準檔`。

GUI standalone 目前使用 `resource_root=None`，因此沿用 AE 既有 standalone / PyInstaller 資源搜尋；拆圖端未來會明確傳入拆圖專案根目錄。

## Factory Policy（第四階段）

`ManufacturingContext` 現在可攜帶 `ManufacturingPolicy`。Automatic bridge 不再 import `ae` 讀取 FW/T/gap/fold；它只透過：

```python
policy = manufacturing_api.resolve_policy(context)
```

取得同一次出圖要使用的 policy snapshot，並把 snapshot 放回 Context。Policy 目前正式包含：

- default thickness
- frame width (FW)
- Door gap W/H
- Door fold L/R/T/B
- Indicator Box fold
- Indicator small-door fold

若 caller 未注入 policy，`manufacturing_api` 才在 API 邊界從 wrapped AE Core 讀取現行 Factory Policy。外部 Adapter 不得直接讀 `ae.T` / `ae.FW` / `ae.*_def`。

製造公式也集中在 API helper：

- `door_finished_face_size()`
- `door_indicator_offset_for_finished_center()`
- `indicator_box_opening_feature()`
- `indicator_small_door_spec()`

因此 automatic bridge 只保留來源 ownership、finished-face extraction、replacement semantics 與 Feature validation。

## Atomic Overwrite

`generate_part()` 不直接覆蓋舊 DXF：

```text
export → 同目錄 temp DXF → exporter 成功 → os.replace() → 正式檔
```

若 exporter 中途失敗，舊加工圖保持不變。

## 拆圖端第三／四階段接法

拆圖端維持原責任：

```text
finalized info_data + finished-face Feature
                     ↓
              split-side Adapter
                     ↓
                  PartSpec
                     ↓
             generate_part()
                     ↓
                    DXF
```

拆圖端保留 source ownership、physical feature、selector、替換 CSV、LOG、snapshot、PermissionError 與 finalized `info_data` 等責任；不把這些搬進 AE Core。

## Phase 6：最終 Clean Break

目前正式結構只保留一份製造核心：

```text
ae_engine/
├─ ae.py
├─ contracts.py
├─ manufacturing_api.py
├─ sheetmetal_geometry.py
├─ sheetmetal_features.py
├─ sheetmetal_part_adapters.py
├─ sheetmetal_drawing.py
├─ hole_catalog.py
└─ cabinet_types/
```

不再提供任何根目錄或 `modules/` compatibility shim。`ae_engine` 內部也只允許 package-relative import。

拆圖專案自己的來源 catalog 已正式改名為：

```text
modules/automatic_hole_catalog.py
```

它持有 `開孔.csv` / `管孔尺寸清單.csv` / `自動開孔替換.csv`、source lookup、replacement parser 等拆圖責任，**不屬於 AE Core，也不得被 AE 更新覆蓋**。

未來 AE 更新唯一標準動作：

```text
AE 專案/ae_engine/
        ↓ 整個資料夾覆蓋
拆圖專案/ae_engine/
```

不再複製單一 `.py`，也不再合併 `modules/ae.py`。

`RO / 落地盤` 已保留 `ae_engine/cabinet_types/ro.py` 與 registry dispatch；目前 `implemented=False`，代表尚未加入未確認的 RO 製造幾何。


## 測試環境：Headless 與 Xvfb 不可互相替代

- `env -u DISPLAY pytest ...` 只驗證 **pure/headless contract**。需要 Tk 視窗的測試在沒有 `DISPLAY` 時必須被標記/辨識為 `SKIP`，不得把 `TclError: no display name` 計為 production failure。
- 正式 GUI release gate 必須在有效的 X display（建議 Xvfb）下執行；有 `DISPLAY` 時 `requires_tk_display` 不會 skip，Tk 測試必須真正建立 GUI 並跑完。
- 中央規則位於 `tests/conftest.py`：新 GUI 測試應使用 `@pytest.mark.requires_tk_display`；舊測試若漏 marker，只在 `DISPLAY` 未設定且錯誤明確是缺 display 的 Tk `TclError` 時相容轉為 skip。其他 Tcl/Tk 錯誤一律維持 failure。
- 因此：**headless PASS ≠ GUI PASS**；正式出包仍必跑 Xvfb GUI suite。
