# CornerType / 未知類型設計規格

## 目標

在 **Phase6 Clean-Break `ae_engine/` 架構**內，把截角公式從折彎尺寸中分離，同時維持既有金庫型製造結果完全不變；只有使用者選擇「未知類型」時，才允許手動指定角型。

## 不可破壞條件

- 專案根目錄不得恢復 `ae.py`、`sheetmetal_geometry.py`、`sheetmetal_features.py`、`sheetmetal_part_adapters.py`、`sheetmetal_drawing.py`、`hole_catalog.py`、`contracts.py`、`manufacturing_api.py` 等 Phase5 compatibility shims。
- 共用核心固定位於 `ae_engine/`。
- `gui.py` 使用 `import ae_engine.ae as ae` 與 `ae_engine.manufacturing_api`。
- 金庫型目前的 CUTTING/BEND 與 stretched baseline 行為不得改變。
- GUI 不自行重算製造幾何；預覽與 DXF 仍共用 authoritative geometry / headless manufacturing API。

## 核心模型

```text
Fold Geometry + CornerType = Final Corner
```

`CornerType` 只描述從折彎基準扣除後，角本身的殘差規則，不保存「折幾彎」或「每一彎多大」。

### C01 — 標準截角

```text
U = 0
V = 0
```

### C02 — 單邊留肉 1T

```text
U = -1T
V = 0
```

旋轉 90° 後變成：

```text
U = 0
V = -1T
```

X 留肉與 Y 留肉是同一個 C02，不新增類型。

### C03 — 雙向多切 0.5T

```text
U = +0.5T
V = +0.5T
```

### C04 — 雙段截角

```text
Primary U = FW
Primary V = FW - T
Secondary U = +0.5T
Secondary Depth = 2T
```

## 金庫型固定映射

金庫型不顯示 CornerType 選擇器，也不能由使用者改型：

```text
Door / Indicator Box / Indicator Door -> C02
Base Plate                              -> C01
EndCap/Tail Bottom                      -> C03
EndCap/Tail Top                         -> C04
```

這些映射只是把既有公式改寫成「折彎基準 + 角型殘差」，輸出幾何必須與 Phase6 母版相同。

## 未知類型

基準型號清單新增：

```text
未知類型
```

選到未知類型後：

- 不讀取任何 baseline DXF。
- 支援 Head、Tail、Door、Base Plate、Indicator Box、Indicator Door 各自保存四角設定。
- 四個角可分別選 C01～C04。
- C02 可選 0° / 90°，用同一類型表達 X/Y 留肉。
- 每個 Cxx 顯示小圖，並提供目前選取角的放大預覽。
- 最終 export 仍透過 `manufacturing_api.generate_part()`，不從 GUI 直接呼叫 DXF exporter。

## 檔案責任

- `ae_engine/sheetmetal_geometry.py`：CornerType 純幾何、殘差與 fold-base 組合。
- `ae_engine/sheetmetal_part_adapters.py`：金庫固定映射與 unknown structural builders。
- `ae_engine/corner_type_ui.py`：未知類型名稱、四角狀態與 policy 組裝；無 Tkinter。
- `ae_engine/contracts.py`：PartSpec 可選 `corner_policy`。
- `ae_engine/manufacturing_api.py`：unknown PartSpec 路由至 unknown exporter，既有 Vault/baseline 路徑不變。
- `ae_engine/ae.py`：DrawingScene 組裝與 DXF serialize；Door/head mirror 規則維持 Phase6。
- `gui.py`：unknown-only 選角 UI、小圖與預覽；出口仍走 headless API。

## 驗證標準

1. Phase6 clean-break layout tests 必須通過，根目錄不得重新出現舊 core。
2. 全部 pytest 在 Xvfb 下通過。
3. `py_compile` 必須通過。
4. Unknown C01～C04 必須能透過 headless API 輸出可被 ezdxf 讀回的 DXF。
5. 與 Phase6 母版比較，Vault direct/stretched 代表 DXF 必須逐 entity 相同。

## FIX3 — CornerType 預覽與多門輸入防呆（2026-08-17）

### CornerType 小圖必須使用 authoritative geometry

FIX2 的小圖雖然呼叫 `resolve_corner_relief()` 取得數值，但 GUI 仍自行拼接 CUTTING 線段，因此畫面可能與真正材料輪廓語意不一致。FIX3 禁止這種做法。

新的規則：

```text
CornerTypeSelection
→ build_four_side_outline()
→ 取得真正 Material Polygon
→ 裁切單一角落
→ GUI 只做 world → canvas 縮放與繪製
```

因此：

- C01/C02/C03/C04 小圖來自正式 FourSideFlange CUTTING。
- C02 0° / 90° 的 X/Y 留肉直接由正式 geometry rotation 產生。
- GUI 不得重新推導 `fold-T`、`fold+0.5T`、`fold+FW` 或雙段階梯座標。
- 小圖以材料區域呈現；切除區保持空白，BEND 只作藍色參考線。

### 多門輸入防呆

多門 Canvas 上的寬/高 Entry 是製造尺寸輸入，不得只在輸入後顯示「超出」狀態。

欄寬輸入必須滿足：

```text
目前欄寬 > 0
目前欄寬 <= W - 其他固定欄寬總和
```

同欄高度輸入必須滿足：

```text
目前層高 > 0
目前層高 <= H - 同欄其他固定層高總和
```

違反時：

1. 拒絕 commit。
2. Entry 回復上一個合法值。
3. 顯示「多門尺寸錯誤」警告，明確列出 W/H、其他固定尺寸合計與本格最大允許值。
4. 不建立負數 remainder、不保留 invalid cell、不進入 export。
5. 非數字、0、負數同樣拒絕並回復。

合法修改仍保留既有 smart remainder 行為，例如 W=1000：400 + 自動600；把自動600改成400後，自動補200。

## FIX4 — 上下成對選角與局部 Cut Profile 預覽（2026-08-17）

### 操作預設

未知類型不再要求四個實體角逐一選擇。一般製造情境預設：

```text
上方：左上 = 右上
下方：左下 = 右下
```

因此一般情況只需要兩次選擇：一次設定上方、一次設定下方。

GUI 各自提供：

```text
上方截角  [✓ 左右相同]  [上方]
下方截角  [✓ 左右相同]  [下方]
```

取消某一列的「左右相同」後，該列才展開成左右兩個實體角：

```text
上方截角  [  左右相同]  [左上] [右上]
下方截角  [  左右相同]  [左下] [右下]
```

底層資料仍永久保存四個獨立 `CornerTypeSelection`，所以這只是操作層分組，不改 manufacturing contract。

重新勾回「左右相同」時，以左側目前值為 authority，同步到右側：

```text
top_left    -> top_right
bottom_left -> bottom_right
```

### CornerType 小圖語意

FIX3 的 Material Polygon 角落裁圖仍會呈現 L 形材料，對使用者而言無法直接辨識「切掉的是哪一種角」。FIX4 改成只畫 canonical local **Cut Profile**：

```text
Fold sample + CornerType
        ↓
ResolvedCornerRelief
        ↓
Primary cut + optional Secondary cut
        ↓
Canonical removed-material polygon
        ↓
GUI thumbnail
```

規則：

- 紅色/深色輪廓表示真正被 CUTTING 移除的材料。
- 不再畫周圍 L 形保留材料。
- 藍色虛線只表示 sample fold reference。
- C01～C04 catalog 小圖永遠使用同一 canonical 方向，不因左上/右上/左下/右下而鏡射。
- 實際零件四角方向仍由 geometry placement 自動鏡射。
- C02 的大預覽可依 0°/90° 顯示 X/Y 留肉；catalog 小圖保持 canonical 0°。

### FIX4 不變範圍

- 金庫型 Factory Policy、Vault fixed mapping 不變。
- `sheetmetal_geometry.py`、`sheetmetal_part_adapters.py`、`ae.py`、`manufacturing_api.py`、`contracts.py` 的製造行為不變。
- 多門 W/H hard guard 保留 FIX3 行為。
- Phase6 clean-break 根目錄不得重新出現 legacy core/shim。


## FIX5 — CornerType 預覽共用尺度

- C01～C04 縮圖禁止各自依自身 bbox 自動 fit；否則 C01/C02/C03 都會被放大成同樣的矩形。
- 所有類型必須使用同一組示意參數與同一 viewport scale。
- GUI 示意參數固定為 `fold_u=fold_v=12`、`T=4`、`FW=8`（僅供圖示辨識，不參與製造幾何）。
- 藍色虛線固定代表相同折彎基準；紅色 CUT profile 相對基準顯示：C02 少切 1T、C01 標準、C03 多切 0.5T、C04 雙段。
- 實際 DXF / Factory Policy / 金庫型公式不得讀取上述示意參數。

## FIX6 — Preview 直接取現有已驗證零件角（2026-08-17）

CornerType 縮圖不再建立任何 sample relief / illustrative CornerType geometry。

Canonical preview source 固定為現有 Vault 正式幾何：

```text
C01 → build_base_plate_result() → Base Plate 左下角
C02 → build_door_result()       → Door 左下角
C03 → build_endcap_result()     → EndCap 左下角
C04 → build_endcap_result()     → EndCap 左上角
```

流程：

```text
既有正式 Part Adapter
→ final StructuralGeometryResult.outline
→ Blank Rectangle - Material Polygon
→ 取指定實體角 removed-material polygon
→ 統一成 canonical 左下觀看方向
→ 共用 crop span
→ GUI thumbnail
```

約束：
- `corner_type_ui.py` 不得呼叫 `resolve_corner_relief()` 來重建縮圖。
- 不得再出現 `fold=3T`、`FW=2T` 等 preview-only CornerType 公式。
- C02 90° 只允許旋轉已從 Door 擷取出的 canonical cut，不另算一套 relief。
- 四種小圖共用同一 crop span，不 per-type auto-fit。
- 此變更只影響 preview；manufacturing core / Vault DXF 不變。


## FIX7 — 縮圖直接裁現有 CUTTING/BEND

FIX6 的錯誤是把 `Blank - Material` 的被切除面積當成縮圖，因此 C01/C02/C03 會呈現成封閉小方塊。FIX7 改為真正的「從現有零件直接截」：

- C01：Base Plate 現有左下角 final CUTTING + BEND。
- C02：Door 現有左下角 final CUTTING + BEND。
- C03：EndCap 現有左下角 final CUTTING + BEND。
- C04：EndCap 現有左上角 final CUTTING + BEND。
- 以同一個實體裁切視窗裁 `result.outline` 與 `result.bends`，只做座標正規化與 Canvas 縮放。
- GUI 只畫 linework：CUTTING 綠色、BEND 藍色虛線；禁止再把 removed-area 畫成封閉填色 polygon。
- C02 的 90° 只旋轉已裁出的 Door CUTTING/BEND linework，不重新推導 relief。

因此 C01/C02/C03 的差異直接由現有加工幾何決定：C01 CUTTING/BEND 重合；C02 CUTTING 相對 BEND 留肉；C03 CUTTING 超過 BEND；C04 顯示既有雙段階梯。
