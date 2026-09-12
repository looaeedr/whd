<!-- WHD_DOC_ROLE role=HISTORICAL contract=architecture-snapshot -->
> **[architecture snapshot]** 此檔保留當時 evidence / roadmap / API 盤點；**不參與 current routing**，不得以檔名中的 `CURRENT`、`目前`、`Next Steps` 或舊架構語氣覆蓋現行 authority。
> Current authority：`個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`；製造架構/API：`個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`。

# 01 — Architecture

## 單一真相來源

```text
Parameters
  ↓
sheetmetal_part_adapters.py
  ↓
StructuralGeometryResult
  ↓
Structural primitives + Resolved Features + Drawing semantics
  ↓
DrawingScene
  ├─ GUI
  └─ ae.py DXF serializer
```

`DrawingScene` 是目前 DXF/GUI 的 typed drawing contract。
`SceneData` 用於需要額外 metadata/params 的 baseline/stretched/indicator 流程。

## 分層

### Structural Geometry
`sheetmetal_geometry.py`
- Base polygon / relief boolean
- FourSideFlange
- StripFoldChain
- Bend clipping

### Features / Factory Policy
`sheetmetal_features.py`
- Circle/Rect feature
- ResolvedFeature
- End-cap finished-face mapping
- Vault EndCap policy
- Door indicator layout/interaction
- Preview guides

### Part Adapters
`sheetmetal_part_adapters.py`
- 舊 W/H/D/T/FW/yl/zl 等參數 → authoritative structural result

### Drawing semantics
`sheetmetal_drawing.py`
- `PolylinePrimitive`
- `LinePrimitive`
- `CirclePrimitive`
- `TextPrimitive`
- `DrawingScene`
- `SceneData`
- CHECK/STOCK/DATUM builders

### DXF boundary
`ae.py`
- config/resource
- scene orchestration
- `_add_drawing_scene_to_dxf()`
- save

### GUI boundary
`gui.py`
- world→canvas
- render DrawingScene / StructuralGeometryResult
- hit-test/drag through Feature/Guide APIs
