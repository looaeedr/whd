# FIX12 金庫型 XY 折彎 / 全域 WHD / 封頭尾立姿設計

## 目標
先把金庫型折彎設計器做正，不先加入其他類型。

## 不可變條件
- `fold_designer_original.py` 必須與使用者提供的 `mainapp.py` byte-identical。
- 不修改原 `Renderer.calc_profile()`、`Renderer.render()`、BendingUI 操作方式。
- 不修改 `ae_engine` 製造幾何、CUTTING/BEND/DXF。
- CornerType 不進折彎設計器。
- Phase6 開孔仍是唯一編輯來源；設計器只投影孔供原 Renderer 預覽。

## 金庫型板件資料模型
設計器內每個板件都使用原 Renderer 的 X/Y profile 能力；畫面不再提供「標準十字型 / 金庫型(三件)」模式切換。

### 箱身
- X profile：沿用目前箱身 FoldChain，中央固定 D-W-D。
- Y profile：只提供全域 H 作為 X profile 的 extrusion 基準，不新增製造折彎。

### 封頭 / 封尾
正式 Phase6 幾何有 5 條 BEND：X 左右各一折；Y 下邊一折、上邊兩折。

X profile（由左到右）：
`yl1 | W - 4T | yr1`

Y profile 為了配合原 `calc_profile()` 的 middle-base 規則，採由上往下的反向列示：
`ytop1 | FW | D - 3T | ybottom1`

因此仍代表正式 flat chain 的反向：
`ybottom1 | D - 3T | FW | ytop1`

預設 preview 內部 turn 皆沿用 `-90`，UI 只顯示相反符號。

## ±90 UI 契約
只翻 UI / engine 的 ±90 符號：
- engine +90 -> UI -90
- engine -90 -> UI +90
- UI +90 -> engine -90
- UI -90 -> engine +90
其他角度不改。

這不能改變原 Renderer 的 3D 幾何。

## 全域 W/H/D
設計器最上方 W/H/D 永遠代表 Phase6 全域箱體尺寸，不因切換門、底板、封頭等板件而改成局部尺寸。

連動至少包含：
- 箱身中央 D-W-D。
- 箱身 extrusion H。
- 封頭/封尾 X core = W - 4T。
- 封頭/封尾 Y core = D - 3T。

封頭/封尾若直接修改 core，反向更新全域 W/D：
- W = X core + 4T
- D = Y core + 3T

FW、yl1、yr1、ytop1、ybottom1 仍是各自既有 Phase6 參數。

## 封頭 / 封尾 3D 立姿
原 Renderer 先照原算法產生標準 X/Y 3D 幾何；bridge 在 render 完成後只對 3D artists 套 preview placement transform，把板件面由 XY 平面轉到 XZ 立面。2D 圖不旋轉，製造幾何不旋轉。

採用 X 軸 +90° 的等價座標轉換：
`(x, y, z) -> (x, -z, y)`，再只做顯示用 Z 平移讓整件落在可視正 Z 範圍。

## UI
- 隱藏原 prototype 的「標準十字型 / 金庫型(三件)」Radio controls。
- 板件 selector 保留。
- 選封頭/封尾時，BendingUI 顯示 X 軸折彎 / Y 軸折彎。
- 原折角、長度、方向鍵、新增/刪除操作不重畫。
## 3D 回寫 / 基準檔重新載入
- 封頭/封尾在 3D 設計器修改 X/Y profile 後，回寫必須更新 `W/D/FW/yl1/yr1/ytop1/ybottom1` 全部正式 Phase6 參數。
- 箱身舊 profile 不得在 export 階段覆蓋封頭/封尾剛修改的全域 `W/D/FW`。
- Apply 回主程式後，保留目前基準型號，不呼叫會重置預設值的 `on_baseline_changed()`。
- 清除主程式的 baseline 衍生 scene cache，接著 `update_calculations()` 以新尺寸重新讀取/拉伸目前基準檔。
- 原始基準 DXF、`config.ini` 均不得被更新包覆寫。

