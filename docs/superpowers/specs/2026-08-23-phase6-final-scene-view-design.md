# Phase6 FinalScene View 深模組設計

## 目標

把 `fold_designer_bridge.py` 中 FinalScene 的 3D 顯示實作收斂到 `phase6_final_scene_view.py`，讓 Bridge 只負責取得 `PartRenderData` 與組合顯示 request；FinalScene View 僅消費製造邊界已解析完成的 `material / scene / fold_guides`，不得重建第二份製造幾何。

## Seam 與所有權

### 製造幾何 Source of Truth

`ae_engine.manufacturing_api.PartRenderData` 擁有：

- `material`：完成 CUTTING／孔洞／截角後的最終材料面。
- `scene`：完成 BEND／MARKING／BLIND_HOLE 等操作。
- `fold_guides`：同一 FinalScene 的有限 BEND 覆蓋。

FinalScene View 可以 triangulate、fold、project operation linework，但不得呼叫 `build_part_render_data()`、`material_polygon_from_final_scene()`、CornerType resolver 或從 scene 重新建立 CUTTING material。

### Bridge 保留責任

`fold_designer_bridge.py` 保留：

- `_phase6_scene_query_payload_for_part()` 與 `_phase6_query_final_render_data()`。
- active part → X/Y Fold Profile 的 draft adapter。
- operator finished dimensions 的數值解析（因為它涉及 Settings、CornerPolicy、PartDimensions）。
- unfolded-size label 的數值解析與 Tk label 更新。
- 建立 `FinalSceneViewRequest` 所需的 adapter 資料。

### `phase6_final_scene_view.py` 擁有責任

- profile unfolded→folded cross-section 映射。
- Final material triangulation 與 finite fold-guide folding。
- material mesh boundary。
- BEND／MARKING／BLIND_HOLE 投影。
- operator 尺寸圖形繪製（只接收已解析 finished dimensions）。
- fitted axis limits、rectangular 3D viewport、zoom／scroll。
- FinalScene render install、錯誤顯示與 last-render diagnostics。

## Interface

```python
@dataclass(frozen=True)
class FinalSceneViewRequest:
    render_data: object
    x_profile: tuple[Mapping[str, object], ...]
    y_profile: tuple[Mapping[str, object], ...]
    part_key: str
    alpha_bend: float
    finished_dimensions: tuple[float, ...] | None
    thickness: float

class Phase6FinalSceneView:
    def __init__(self, renderer): ...
    def render(self, request: FinalSceneViewRequest) -> list[tuple[tuple[float, float, float], ...]]: ...
    def install(self, request_provider, *, after_render=None) -> None: ...
    def on_scroll(self, event) -> None: ...
```

Interface 只讓 caller 提供已解析的 `PartRenderData`、Fold Profiles 與 operator display values。Renderer／Matplotlib 細節、zoom state、last material／mesh／error 全部藏在 module implementation 內。

## 相容策略

既有測試／舊 caller 直接 import 的純幾何 helper，可由 `fold_designer_bridge.py` 直接 re-export `phase6_final_scene_view` 的同一函式物件；不可保留第二套 wrapper 公式。新的 production code 不得從 Bridge 取這些 View helper。

`Phase6FoldDesignerApp` 可暫時保留 `_phase6_last_cutting_mesh`、`_phase6_last_cutting_material`、`_phase6_cutting_mesh_error`、`_phase6_zoom_scale` compatibility property，但 backing state 必須只有 `Phase6FinalSceneView` 一份。

## 不做

- 不改 PartRenderData schema。
- 不改 CornerType／Fold Profile／EndCap 公式。
- 不改 2D renderer。
- 不把 scene query 或 manufacturing request 搬進 View。
- 不重新計算 CUTTING material。
- 不拆 Settings UI、diagnostics 或 Designer workspace。

## 回歸契約

1. 同一份 `PartRenderData.material` 是 View 唯一 CUTTING material；含洞 polygon 的 3D mesh 不得填回洞。
2. View module 不 import／呼叫 `build_part_render_data` 或 `material_polygon_from_final_scene`。
3. `fold_guides` 直接取自 `PartRenderData`；View 不從 scene 再推導一份 manufacturing fold guide。
4. 原本 3D BEND／MARKING／BLIND_HOLE、operator dimensions、zoom、rectangular viewport 行為保持。
5. legacy geometry renderer 仍不得被執行。
