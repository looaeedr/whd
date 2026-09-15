# 折彎診斷存檔與封尾原生方向設計

## 目標

1. 封尾在 3D 中使用基準/製造 final scene 的原生 Y 方向，不再套用封頭正規化後的 Y profile 順序。
2. 3D 工作區新增「存檔」功能，輸出可直接交給除錯者閱讀的 JSON，完整保存折彎方法、尺寸、目前板件與 authoritative final geometry 摘要。
3. 門把問題不再靠猜測座標或孔型修補；JSON 必須能證明 CUTTING 是否已存在於 final scene/material。

## 資料流

- 製造來源仍是 `PartSpec -> manufacturing_api.build_part_render_data()`。
- 3D 只折 `PartRenderData.material`，scene 僅作 BEND/MARKING 顯示與診斷。
- 存檔從 3D draft 匯出，不改主 GUI transaction，不等同「確定」。

## 封尾方向

- `head`：沿用目前正規化後的 Y profile：`ytop1 -> fw -> core -> ybottom1`。
- `tail`：final scene 不鏡像，因此 Y profile 必須保持原生由 minY 到 maxY：`ybottom1 -> core -> fw -> ytop1`。
- 不修改 AE 的 `is_tail` scene normalization 契約；只修 3D/editor profile 對 final scene 的對應。

## JSON 存檔格式

頂層包含：
- `schema`: 固定版本字串。
- `saved_at`: ISO 時間。
- `model`, `active_part`。
- `settings`: W/H/D/T/FW 與目前製造設定。
- `workspace`: 所有板件的 X/Y profiles，逐段保存 `len`, `ui_len_add`, `angle`, `phase6_key`, `core`。
- `active_part_payload`: 目前送往 canonical PartSpec adapter 的 draft payload。
- `final_geometry.scene`: final scene 的 primitives（type/layer/座標）。
- `final_geometry.material`: bounds/area/geometry type/interior count/GeoJSON mapping。
- `render_error`: 若 final geometry 無法建立，保存錯誤字串而不是阻止存檔。

## 門把驗證規則

- JSON 的 `final_geometry.scene` 若有門把 CUTTING，但 material 沒洞：修 manufacturing material boundary。
- scene 已沒有門把：修 baseline reader/operation ownership。
- material 有洞但 3D 看不到：只修 3D tessellation/render，不回頭重建孔。

## UI

- 板件設定 footer 新增「存檔」按鈕。
- 使用 `asksaveasfilename`，預設 `.json`。
- 存檔成功顯示狀態文字；取消選檔不改任何狀態。
