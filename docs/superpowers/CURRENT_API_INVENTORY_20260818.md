# Phase6 / AE Engine 現行 API 盤點

日期：2026-08-18

> 本文件記錄目前專案可見且實際使用中的 API 邊界。目的不是把 `ae.py` 內所有函式都稱為 API，而是區分「正式 headless 製造 API」、「契約型別」、「盤型 registry」與「GUI 直接使用的 engine helper」。

## 1. API 邊界原則

正式製造邊界：

```text
PartSpec + ManufacturingContext
              ↓
ae_engine.manufacturing_api.generate_part()
              ↓
           ae_engine
              ↓
             DXF
```

- GUI 單門、多門、箱身、封頭、封尾、底板、指示燈盒／小門的正式 DXF 出圖應走 `manufacturing_api.generate_part()`。
- 自動拆圖也應組成相同 `PartSpec` 後進入 `generate_part()`。
- `ae_engine.ae` 仍可提供 GUI 預覽／尺寸計算與 engine 內部實作，但不應成為新的 GUI DXF export bypass。
- `fold_designer_bridge.py` / `fold_designer_original.py` 屬於「自己畫」的 UI／adapter 路線，不列為 headless manufacturing API。

---

## 2. `ae_engine` 頂層正式公開 API

目前 `ae_engine.__all__` 公開下列名稱：

### 製造入口與 helper

- `generate_part`
- `resolve_policy`
- `expected_baseline_path_for`
- `door_finished_face_size`
- `door_indicator_offset_for_finished_center`
- `indicator_box_opening_feature`
- `indicator_small_door_spec`

### 契約／Context

- `ManufacturingPolicy`
- `ManufacturingContext`
- `DoorPartSpec`
- `BoxBodyPartSpec`
- `EndCapPartSpec`
- `BasePlatePartSpec`
- `IndicatorBoxPartSpec`
- `PartExportResult`
- `PartSpec`

### Cabinet registry

- `CabinetTypeRegistration`
- `registered_cabinet_types`
- `resolve_cabinet_type`

### 模組入口

- `ae`
- `manufacturing_api`

---

## 3. `manufacturing_api` 公開函式

```python
resolve_policy(context=None) -> ManufacturingPolicy

expected_baseline_path_for(spec, context=None)

door_finished_face_size(spec: DoorPartSpec, context=None)

door_indicator_offset_for_finished_center(
    spec, groups, desired_center, context=None
)

indicator_box_opening_feature(
    groups, thickness=..., center=..., context=None
)

indicator_small_door_spec(
    groups, thickness=..., context=None
) -> DoorPartSpec

generate_part(
    spec, output_path, context=None
) -> PartExportResult
```

`generate_part()` 是正式統一 DXF 製造入口。

---

## 4. `contracts` PartSpec

目前 `PartSpec`：

```text
PartSpec
├─ DoorPartSpec
├─ BoxBodyPartSpec
├─ EndCapPartSpec
├─ BasePlatePartSpec
└─ IndicatorBoxPartSpec
```

其他正式契約：

- `ManufacturingPolicy`
- `ManufacturingContext`
- `PartExportResult`

### `ManufacturingContext` 主要責任

- `resource_root`
- `overwrite`
- `draw_stock`
- `policy`

自動拆圖可藉由 `ManufacturingContext` 指定自己的 resource root / Factory Policy，而不必由 GUI 狀態推算。

---

## 5. 多門 API 接法

目前多門不是額外建立 `MultiDoorPartSpec`，而是每一格門片都建立一個 `DoorPartSpec`：

```text
Door Layout
    ↓
DoorLayoutCell
    ↓
_door_layout_part_spec(cell, val)
    ↓
DoorPartSpec
    ↓
manufacturing_api.generate_part()
```

目前 `gui.py` 的 `export_multi_door_layout_dxfs()` 對每個 validated Door cell 執行一次：

```python
manufacturing_api.generate_part(
    self._door_layout_part_spec(cell, val),
    filepath,
    context,
)
```

每格自己的尺寸、`frame_edges`、feature ownership、指示燈狀態、offset、Unknown corner policy 由 GUI adapter 組進 `DoorPartSpec`。

多門的 Indicator Box／Indicator Small Door 也各自組 spec 後呼叫 `generate_part()`。

---

## 6. Cabinet Type Registry API

`ae_engine.cabinet_types` 公開：

- `CabinetTypeRegistration`
- `register_cabinet_type()`
- `registered_cabinet_types()`
- `resolve_cabinet_type()`
- `VAULT`
- `RO`

目前狀態：

```text
VAULT / 金庫型  → 已實作
RO / 落地盤     → registry extension point 已存在
                  不代表所有 RO 製造規則已完成
```

Registry 只負責盤型 identity / dispatch，不應自行猜製造幾何。

---

## 7. GUI 目前直接使用的 `sheetmetal_part_adapters`

目前 `gui.py` 直接 import：

- `DoorFrameEdges`
- `derive_door_layout_cells`
- `validate_door_layout_dimensions`
- `complete_partition`
- `door_layout_export_filename`
- `build_box_body_result`
- `build_door_result`
- `build_base_plate_result`
- `build_indicator_box_result`
- `build_endcap_result`
- `build_unknown_door_result`
- `build_unknown_base_plate_result`
- `build_unknown_indicator_box_result`
- `build_unknown_endcap_result`
- `build_finished_reference_guide`

這些屬於 engine helper / preview adapter 層，不等同於頂層 headless export API。

---

## 8. GUI 目前直接使用的 Feature API

`ae_engine.sheetmetal_features`：

### Feature 型別

- `FeatureAnchor`
- `ReferenceAnchor`
- `CircleFeature`
- `RectFeature`
- `ProfileFeature`
- `ResolvedCircle`
- `ResolvedRect`
- `ResolvedProfile`
- `CanvasTransform`
- `RectGuide`
- `DoorIndicatorContext`

### Box Body / EndCap / Door feature resolution

- `box_body_face_dimensions`
- `box_body_face_contexts_from_strip`
- `resolve_box_body_face_features`
- `resolve_endcap_features`
- `endcap_feature_context_from_geometry`
- `resolve_endcap_finished_face_guide`
- `resolve_vault_endcap_fixed_features`
- `resolve_door_indicator_features`
- `resolve_door_indicator_layout`
- `resolve_door_indicator_dimension_guides`
- `measure_door_indicator_position`
- `door_indicator_offset_for_position`
- `door_enclosure_reference_offsets`
- `door_enclosure_reference_guide`
- `indicator_box_opening_size`

### Finished-face / placement

- `legacy_hole_to_feature`
- `feature_to_legacy_hole`
- `placement_from_finished_point`
- `feature_finished_point`
- `move_feature_to_finished_point`
- `reanchor_feature`
- `feature_with_offset`
- `build_feature_placement_guides`
- `resolve_features_in_finished_face`
- `hit_test_resolved_features`
- `feature_surface_from_rect`
- `feature_surface_from_outline`
- `feature_surface_from_structural_result`
- `feature_is_within_surface`
- `move_feature_within_surface`
- `resolve_surface_features`

### Reference / process / pattern

- `REFERENCE_ANCHOR_LABELS`
- `REFERENCE_ANCHOR_BY_LABEL`
- `feature_reference_anchor`
- `feature_with_reference_anchor`
- `feature_reference_point`
- `reference_distances`
- `move_feature_by_reference_distance`
- `feature_with_process`
- `expand_linear_pattern`
- `expand_grid_pattern`

### Round-hole helpers

- `circle_center_distance_from_gap`
- `circle_gap_from_center_distance`
- `align_circle_to_neighbor`
- `generate_round_fill`
- `generate_round_refill`

### Base plate / baseline

- `resolve_base_plate_mounting_holes`
- `resolved_circles_from_baseline`

---

## 9. CornerType API

`ae_engine.corner_type_ui`：

- `UNKNOWN_MODEL_NAME`
- `CORNER_KEYS`
- `CORNER_LABELS`
- `CORNER_PAIR_CORNERS`
- `apply_manual_corner_selection()`
- `with_unknown_model()`
- `is_unknown_model()`
- `new_manual_corner_pair_same_state()`
- `new_manual_corner_state()`
- `policy_from_corner_state()`
- `set_manual_corner_pair_same()`
- `build_corner_type_preview_geometry()`

幾何共用型別目前由 `ae_engine.sheetmetal_geometry` 提供：

- `CornerTypeId`
- `CornerTypeSelection`
- `CORNER_TYPE_LABELS`
- `Vec2`

---

## 10. Hole Catalog API

AE GUI 使用 `ae_engine.hole_catalog`：

- `load_hole_catalog()`
- `load_pipe_catalog()`
- `feature_from_definition()`
- `custom_circle_definition()`
- `custom_rectangle_definition()`

注意：自動拆圖專案的 `modules/hole_catalog.py` 仍可能包含 split-owned 的來源 catalog、替換 CSV、lookup/replace 規則；它不應被單純視為 AE Core 同步檔。

---

## 11. Drawing API（GUI 現行直接使用）

`ae_engine.sheetmetal_drawing`：

- `PolylinePrimitive`
- `LinePrimitive`
- `CirclePrimitive`
- `DrawingScene`
- `resolved_features_to_primitives()`
- `mirror_point_y()`

正式 DXF export 仍應從 `manufacturing_api.generate_part()` 進入，而不是 GUI 自行把 DrawingScene 寫檔。

---

## 12. FoldDesigner 路線

目前專案仍可維持兩條工作流：

```text
自動拆圖
→ PartSpec
→ manufacturing_api.generate_part()
→ ae_engine

自己畫
→ gui.py
→ fold_designer_bridge.py
→ fold_designer_original.py
```

FoldDesigner bridge 是 GUI adapter / 手動設計路線；只要不要再複製一套 authoritative manufacturing policy，就不必強制把 UI bridge 併進自動拆圖 API。

---

## 13. 修改時的保護規則

1. 新的正式 DXF export 優先走 `PartSpec + ManufacturingContext + generate_part()`。
2. GUI 預覽可使用 `ae` / geometry / feature helper，但不可偷偷多一條正式 export bypass。
3. 自動拆圖不要重新讀取 GUI 私有狀態來猜 Factory Policy。
4. 多門維持 per-cell `DoorPartSpec`，不要另造平行製造公式。
5. `RO / 落地盤` registry 已存在不等於規則已完成；只可依確認過的規則擴充。
6. `docs/superpowers/` 應隨相關更新包保留，避免規格／歷史邊界在 overlay 時遺失。
