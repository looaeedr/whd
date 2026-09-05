# 最終板件幾何唯一所有權設計

## 目的

本設計延續既有：

- `2026-08-21-corner-type-semantic-assembly-design.md`
- `2026-08-22-shared-final-part-geometry-design.md`

不重做 CornerType，也不建立第二套幾何模型。目標是把目前已存在的 `PartSpec → PartRenderData` 路徑真正收斂成**唯一製造幾何入口**，消除 GUI、Fold Designer Bridge、AE 在進入 `PartRenderData` 前仍各自推導折邊、裝配與 structural blank 的重複責任。

核心原則：

> UI 可以保存語意與草稿；AE 可以解析製造幾何；2D、3D、DXF/NC 只能消費已解析結果。任何下游不得重新解讀 CornerType 或重新計算板件結構尺寸。

---

## 已確認的現況

目前專案其實已經有很好的基礎：

1. `CornerTypeSelection` 已是正式 CornerType 語意模型，會正規化舊 `C01~C04`、驗證 `CROSS / OVERLAY / INSERT / INSERT_OVERLAY` 的參數。
2. `manufacturing_api.build_part_render_data()` 已會建立同一份 `PartRenderData(scene, material, fold_guides)`。
3. GUI 的 `_authoritative_render_data()` 已讓 2D 與 3D 共用同一份快取。
4. `save_part_render_data_dxf()` 已能直接序列化同一份 Final Scene，不必再次重建幾何。

因此本輪**不新增另一個 `ResolvedPanelGeometry` 來與 `PartRenderData` 競爭**。`PartRenderData` 繼續是最後的已解析幾何真值。

真正還沒收斂的是 `PartSpec` 之前與 `PartSpec` 內部的「幾何預先推導」。例如封頭／封尾現在仍可能同時帶：

- `fold_left / fold_right / fold_top / fold_bottom`
- `fold_profile_x / fold_profile_y`
- `corner_policy`
- box assembly mirror

而 GUI／Bridge 還會依 `OVERLAY`、Fold Profile 再計算一次折邊長度或拓撲。這讓同一份機械意義存在多個可互相矛盾的表示方式。

`W=400, T=2, OVERLAY` 曾出現 structural blank 仍為 `422`，就是這種 seam leakage 的實際案例。

---

## 架構決策 1：保留 `CornerTypeSelection`，不再新增第二套 CornerProfile

原先可考慮新增 `CornerProfile`，但檢查現有程式後確認 `CornerTypeSelection` 已經承擔：

- 正式 type ID
- 十字模式
- 方向
- xT 量
- 嵌入貼外第二級留肉與深度
- 舊資料正規化
- 基本合法性驗證

因此再建立一個平行的 `CornerProfile` 會形成新的 mirror，反而違反本輪目的。

### 改採「衍生機械語意」

在 `ae_engine/sheetmetal_geometry.py` 增加**純函式／不可變結果**，由 `CornerTypeSelection` 推導裝配需要的機械語意。例如：

```python
@dataclass(frozen=True)
class EndCapAssemblySemantics:
    type_id: CornerTypeId
    outer_thickness_factor: float
    x_topology: Literal["folded", "flat"]
    has_box_side_outer_fold: bool


def resolve_endcap_assembly_semantics(
    top_selection: CornerTypeSelection,
) -> EndCapAssemblySemantics:
    ...
```

這個物件不是新狀態，不保存回專案檔，也不允許 GUI 修改；它只是 CornerType 的**唯讀衍生結果**。

### 必須區分的兩類規則

**CornerType 固有機械語意**可放入 resolver：

- `OVERLAY` 封頭／封尾的 X topology 為 flat。
- `OVERLAY` 無左右 X 折邊。
- `INSERT / INSERT_OVERLAY` 對外高占用規則。
- Corner relief 幾何。

**使用者明確操作時才套用的交易預設**不能放入 resolver：

- 使用者「再次明確選擇 OVERLAY」時，下方 CornerType 預設成 `CROSS + EXTRA_CUT + WIDTH + 1.5T`。

這是 UI transaction default，不是 OVERLAY 的不可變物理屬性。普通 redraw、load、cache refresh 不得重新套用。

---

## 架構決策 2：`PartSpec` 只表達請求語意，不在 GUI 預先解幾何

### 現況問題

`gui.py::_end_cap_part_spec_from_values()` 現在會讀 `fold_profile_x/y`，再自行計算：

- `fold_left`
- `fold_right`
- `fold_top`
- `fold_bottom`

這使 GUI 已經在做一部分 AE 應負責的幾何解析。

### 新責任

GUI 的 PartSpec adapter 只允許：

- 數值型使用者／專案輸入直接映射。
- CornerType state → `FourCornerTypePolicy`。
- Fold Designer rows → `FoldProfileSegment`。
- Feature state → Feature contract。
- 舊資料相容欄位原樣帶入。

GUI **不得**根據 Fold Profile 或 CornerType 再推導 structural width/height、折邊總長、blank span。

### 相容欄位優先權

`EndCapPartSpec` 暫時保留 scalar folds，避免一次破壞舊呼叫端：

- `fold_profile_x/y` 非空時：它是 topology／fold length 的權威來源。
- `fold_profile_x/y` 為空時：才使用 `fold_left/right/top/bottom` 作 legacy fallback。

這個優先權只在 AE resolver 實作一次，不得由 GUI／Bridge 各自再實作。

---

## 架構決策 3：AE 增加「PartSpec 正規化／解析邊界」

新增 AE 內部 resolver，概念介面：

```python
@dataclass(frozen=True)
class ResolvedEndCapRequest:
    width: float
    depth: float
    thickness: float
    frame_width: float
    is_tail: bool
    fold_profile_x: tuple[FoldProfileSegment, ...]
    fold_profile_y: tuple[FoldProfileSegment, ...]
    fold_left: float
    fold_right: float
    fold_top: float
    fold_bottom: float
    assembly: EndCapAssemblySemantics
    corner_policy: FourCornerTypePolicy | None
    holes: tuple[FeatureLike, ...]
```

名稱可以在實作時依現有命名調整，但責任固定：

1. 接受 `EndCapPartSpec`。
2. 正規化 legacy／新欄位。
3. 從上方 CornerType 推導裝配機械語意。
4. 決定有效 Fold Profile 與有效 scalar fold。
5. 產生 structural result 與 Final Scene 所需的**同一份解析結果**。

`build_part_scene()`、structural result builder、Final Scene builder 不得各自再解一次。

### `PartRenderData` 仍是最後幾何真值

流程固定：

```text
GUI / 專案檔 / Fold Designer 草稿
        ↓
      PartSpec
        ↓
AE Resolver（唯一正規化／機械解析）
        ↓
Structural Result + Final DrawingScene
        ↓
PartRenderData(scene, material, fold_guides)
        ↓
2D / 3D / DXF / NC
```

不另外建立與 `PartRenderData` 平行的 render model。

---

## 架構決策 4：Fold Designer Bridge 降級為狀態轉換器

Bridge 可以：

- snapshot ↔ Fold Designer raw state。
- 將 UI 草稿轉回 GUI canonical PartSpec callback 所需資料。
- 顯示／隱藏不存在的折彎頁面。
- 對舊檔的 `assembly_type` 做 mirror 相容。

Bridge 不可以：

- 決定 structural blank 寬高。
- 因 `OVERLAY` 自己改 manufacturing span。
- 自己重新建立 Corner relief。
- 建立第二份 Final Scene。
- 用 `assembly_type` 反向覆寫已有的 Head/Tail 上方 CornerType。

`resolve_box_assembly_type()` 若保留，定位必須是 **UI／舊檔相容 query**，不能再成為製造幾何的 source of truth。

---

## 架構決策 5：GUI 只保留一個 authoritative render provider

既有：

```python
_authoritative_render_data(spec, context)
```

繼續保留，並視為 GUI 唯一幾何 provider。

所有支援的 2D 預覽、3D、單件 DXF、批次 DXF 都必須符合：

```text
canonical state → PartSpec → _authoritative_render_data() → consumer
```

禁止 consumer 旁路回：

- `build_unknown_*_result()`
- `_build_*_scene()`
- 自己拼 CUTTING/BEND
- 自己重新解析 CornerType

特殊 hit-zone 若只用來編輯導航，可以使用 structural topology，但不能成為顯示尺寸或輸出幾何的真值。

---

## 第一輪實作範圍

為降低風險，第一輪只收斂 **封頭／封尾（EndCap）**，不一次改所有 PartSpec。

原因：

1. 目前 `OVERLAY 400 → 422` 的真實漂移就發生在 EndCap。
2. EndCap 同時涉及 CornerType、X/Y Fold Profile、Head/Tail、2D/3D/DXF，是最好的完整資料鏈驗證案例。
3. Door／BoxBody 已有較多穩定基準，先不要一起擴大變更面。

### 第一輪預計涉及

- `ae_engine/sheetmetal_geometry.py`
- `ae_engine/contracts.py`（只有必要 contract 註解／內部型別；避免破 API）
- `ae_engine/manufacturing_api.py`
- `gui.py`
- `fold_designer_bridge.py`
- EndCap／Corner／FinalScene 相關 tests

### 第一輪不處理

- 不拆 `gui.py` 大檔。
- 不拆 `fold_designer_bridge.py` 大檔。
- 不改 `fold_designer_original.py` 製造幾何。
- 不重做 Door／BoxBody/BasePlate/IndicatorBox。
- 不改既有 CornerType UI 外觀。
- 不改基準 DXF。
- 不引入新的 project file schema。

---

## 遷移順序

### 階段 A：先補完整資料鏈測試

先建立失敗測試／契約測試，再改 production code。

至少覆蓋：

1. `OVERLAY EndCap W=400, T=2`：解析後 X structural span 必須為 `400`，不是 `422`。
2. 同一 PartSpec 的 `PartRenderData.material.bounds` 與 2D 顯示尺寸一致。
3. 3D callback 取得的是同一份 `PartRenderData`，不得重建。
4. `save_part_render_data_dxf()` 輸出的 CUTTING bbox 與 `PartRenderData.material.bounds` 一致。
5. 儲存／重新載入後，同一 Head/Tail CornerType + Fold Profile 產生相同 render bounds。
6. 明確選擇 OVERLAY 時下方 `WIDTH + 1.5T` 預設仍只套用一次；普通重繪／重載不洗掉人工修改。

### 階段 B：加入 pure semantic resolver

把 Head/Tail 上方 CornerType → EndCap 裝配機械語意集中到 AE pure function。

現有分散的 `if ... OVERLAY` 只有 UI 呈現／交易預設可以保留；製造 topology 判斷改用 resolver。

### 階段 C：移動 Fold Profile → effective folds 的解析責任

把 `_end_cap_part_spec_from_values()` 裡「由 profile 算 fold_left/right/top/bottom」移到 AE resolver。

GUI 只打包 profile。

### 階段 D：讓 structural 與 Final Scene 共吃同一 resolved request

禁止 structural builder 與 scene builder各自從原始 PartSpec 再決定拓撲。

基準檔拉伸路徑同樣受此規則約束：若 CornerType 改變外框 topology，不得再假設「基準 polygon 與新 polygon 頂點數／索引完全一致」。既有基準圖元的拉伸映射必須使用穩定的一維 X/Y 控制層級；當某軸 topology 層級數不同時，退回已知邊界／折線控制點，而不是用 polygon vertex index 強配。

### 階段 E：移除 Bridge 的幾何判斷

Bridge 只保留 UI／相容用途；所有 manufacturing span／blank 判斷刪除或改呼叫 canonical resolver。

---

## 強制不變量

完成後必須成立：

1. **一份機械語意只能有一個擁有者。**
2. Head/Tail 上方 CornerType 是裝配機械語意 source of truth。
3. `assembly_type` 僅為 UI／舊檔 mirror，不能反向覆寫 CornerType。
4. Fold Profile 存在時，它是 EndCap **折長／順序** 的 source of truth；但不得違反上方 CornerType 已決定的裝配機械拓撲。
   - `OVERLAY` 強制 X topology = flat；殘留 folded X profile 必須在 AE resolver 丟棄。
   - `INSERT / INSERT_OVERLAY` 強制 X topology = folded；殘留 `endcap_w_flat` 必須在 AE resolver 丟棄並回到 canonical scalar folds。
   - 沒有 CornerType policy 時，Fold Profile 才可自行決定 flat/folded topology。
5. scalar folds 只作舊資料 fallback。
6. structural outline 與 Final Scene 由同一 resolved request 產生。
7. `PartRenderData` 是 2D／3D／DXF 的唯一已解析幾何物件。
8. Renderer／Exporter 不得重新解 CornerType。
9. `OVERLAY W=400` 的 X span 從 AE resolver 到 DXF 必須始終為 `400`。
10. 不允許為了解決單一畫面症狀而在 GUI／Bridge 加新的補丁公式。

---

## 測試策略

### 單元測試

- CornerType → `EndCapAssemblySemantics`。
- legacy scalar folds fallback。
- profile precedence。
- head／tail orientation 不影響 physical span。

### Contract tests

- canonical state → PartSpec。
- PartSpec → resolved request。
- resolved request → PartRenderData。
- same input → equal/identical cached render data。

### 完整資料鏈測試

以至少三組 EndCap 案例：

1. `INSERT_OVERLAY` 既有金庫型基準。
2. `OVERLAY` flat X topology。
3. `OVERLAY` 後人工修改下方 CROSS 參數。

逐一驗證：

```text
Source of Truth
→ PartSpec
→ AE resolved request
→ structural outline
→ Final Scene
→ 2D 尺寸
→ 3D material
→ DXF bbox
→ 儲存／重載
→ 再解析結果
```

所有幾何尺寸必須一致。

### 回歸測試

先跑 EndCap／Corner／shared final scene 相關測試，再跑完整 pytest。Tk 測試必須使用有效 Xvfb，不使用假的 `DISPLAY=:0`。

---

## 完成定義

第一輪完成不是「程式可以跑」而已，而是同時滿足：

- EndCap manufacturing topology 的決策只存在 AE resolver 一處。
- GUI 不再從 Fold Profile 推導有效 structural fold 尺寸。
- Bridge 不再擁有 manufacturing blank 公式。
- 2D／3D／DXF 使用同一份 `PartRenderData`。
- `OVERLAY 400 → 422` 類型的跨 seam 漂移有完整資料鏈測試保護。
- 舊金庫型、既有 INSERT_OVERLAY、已保存專案均不退化。

後續若這一輪穩定，再用同一模式逐步收斂 Door、BoxBody、BasePlate；不先做大規模檔案拆分。
