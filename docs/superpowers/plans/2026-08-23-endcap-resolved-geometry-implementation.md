# 封頭／封尾最終幾何唯一所有權實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 將 EndCap 的 CornerType、Fold Profile 與 legacy scalar folds 在 AE 邊界一次解析，讓 structural outline、Final Scene、2D／3D／DXF 共用同一份已解析幾何，並移除 GUI 對 Fold Profile 的預先幾何推導。

**Architecture:** 保留既有 `CornerTypeSelection` 與 `PartRenderData`，不新增平行狀態模型。`ae_engine.sheetmetal_geometry` 提供 CornerType → `EndCapAssemblySemantics` 的純語意 resolver；`ae_engine.manufacturing_api` 提供 `resolve_endcap_request()`，集中 Fold Profile precedence、OVERLAY flat-X、legacy scalar fallback，再由 `build_part_scene()` 唯一消費。GUI 只打包原始 scalar 值與 Fold Profile；Bridge 只建立／讀回編輯狀態。

**Tech Stack:** Python 3、dataclasses、pytest、Tk/Xvfb、Shapely、ezdxf。

**Spec:** `docs/superpowers/specs/2026-08-23-resolved-part-geometry-ownership-design.md`

## Global Constraints

- 本輪只處理封頭／封尾 EndCap，不拆 `gui.py`／`fold_designer_bridge.py` 大檔。
- Head/Tail 上方 CornerType 是裝配機械語意 Source of Truth；`assembly_type` 只能是 UI／舊檔 mirror。
- Fold Profile 存在時優先於 scalar folds；scalar folds 只作 legacy fallback。
- `PartRenderData` 維持 2D／3D／DXF 的唯一已解析幾何物件。
- Renderer／Exporter 不得重新解 CornerType 或自行重算 structural span。
- `OVERLAY W=400` 的 X material span 從 AE resolver 到 Final Scene／DXF 必須維持 400。
- 使用者明確選擇 OVERLAY 才能套用下方 CROSS + EXTRA_CUT + WIDTH + 1.5T 預設；重繪／重載不得再次覆寫。
- 不修改 `config.ini`。
- 此交付副本沒有 `.git`；不偽造 Git commit，改以檔案差異、測試輸出與 ZIP 驗證作為交付證據。

---

### Task 1: 建立 EndCap 裝配語意純 resolver

**Files:**
- Modify: `ae_engine/sheetmetal_geometry.py`
- Create: `tests/test_endcap_resolved_geometry_ownership.py`

**Interfaces:**
- Consumes: `CornerTypeSelection`, `FourCornerTypePolicy`, `normalize_corner_selection()`。
- Produces: `EndCapAssemblySemantics`、`resolve_endcap_assembly_semantics(selection)`、`resolve_endcap_policy_assembly_semantics(policy)`。

- [x] **Step 1: 寫失敗測試**

```python
import pytest
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    FourCornerTypePolicy,
    GeometryError,
    resolve_endcap_assembly_semantics,
    resolve_endcap_policy_assembly_semantics,
)

@pytest.mark.parametrize(
    ("type_id", "x_topology", "has_outer_fold", "factor"),
    [
        (CornerTypeId.INSERT, "folded", True, 0.0),
        (CornerTypeId.OVERLAY, "flat", False, 1.0),
        (CornerTypeId.INSERT_OVERLAY, "folded", True, 1.0),
    ],
)
def test_endcap_assembly_semantics_are_derived_from_corner_type(
    type_id, x_topology, has_outer_fold, factor,
):
    got = resolve_endcap_assembly_semantics(CornerTypeSelection(type_id))
    assert got.type_id is type_id
    assert got.x_topology == x_topology
    assert got.has_box_side_outer_fold is has_outer_fold
    assert got.outer_thickness_factor == pytest.approx(factor)


def test_endcap_policy_rejects_mixed_top_assembly_types():
    policy = FourCornerTypePolicy(
        bottom_left=CornerTypeSelection(CornerTypeId.CROSS),
        bottom_right=CornerTypeSelection(CornerTypeId.CROSS),
        top_left=CornerTypeSelection(CornerTypeId.OVERLAY),
        top_right=CornerTypeSelection(CornerTypeId.INSERT),
        fw=25.0,
    )
    with pytest.raises(GeometryError):
        resolve_endcap_policy_assembly_semantics(policy)
```

- [x] **Step 2: 跑測試確認 RED**

Run: `env -u DISPLAY python -m pytest tests/test_endcap_resolved_geometry_ownership.py -q`

Expected: collection/import FAIL，因 resolver 尚不存在。

- [x] **Step 3: 實作最小純 resolver**

在 `sheetmetal_geometry.py` 匯入 `Literal`，新增：

```python
@dataclass(frozen=True)
class EndCapAssemblySemantics:
    type_id: CornerTypeId
    outer_thickness_factor: float
    x_topology: Literal["folded", "flat"]
    has_box_side_outer_fold: bool


def resolve_endcap_assembly_semantics(selection: CornerTypeSelection) -> EndCapAssemblySemantics:
    normalized = normalize_corner_selection(selection)
    if normalized.type_id is CornerTypeId.INSERT:
        return EndCapAssemblySemantics(normalized.type_id, 0.0, "folded", True)
    if normalized.type_id is CornerTypeId.OVERLAY:
        return EndCapAssemblySemantics(normalized.type_id, 1.0, "flat", False)
    if normalized.type_id is CornerTypeId.INSERT_OVERLAY:
        return EndCapAssemblySemantics(normalized.type_id, 1.0, "folded", True)
    raise GeometryError("封頭尾上方截角必須使用箱體裝配 CornerType")


def resolve_endcap_policy_assembly_semantics(policy: FourCornerTypePolicy) -> EndCapAssemblySemantics:
    left = resolve_endcap_assembly_semantics(policy.top_left)
    right = resolve_endcap_assembly_semantics(policy.top_right)
    if left.type_id is not right.type_id:
        raise GeometryError("封頭尾上方左右 CornerType 的裝配類型必須一致")
    return left
```

- [x] **Step 4: 跑測試確認 GREEN**

Run: `env -u DISPLAY python -m pytest tests/test_endcap_resolved_geometry_ownership.py -q`

Expected: 4 passed。

---

### Task 2: 建立 AE 唯一 EndCap request resolver

**Files:**
- Modify: `ae_engine/manufacturing_api.py`
- Modify: `tests/test_endcap_resolved_geometry_ownership.py`

**Interfaces:**
- Consumes: `EndCapPartSpec`、Task 1 的 `EndCapAssemblySemantics`、`FoldProfileSegment`。
- Produces: `ResolvedEndCapRequest`、`resolve_endcap_request(spec)`；`build_part_scene()` 的 EndCap branch 只讀 resolved request。

- [x] **Step 1: 寫 profile precedence、legacy fallback、flat-X 失敗測試**

在測試檔加入 helper：

```python
from ae_engine.contracts import EndCapPartSpec, FoldProfileSegment
from ae_engine.manufacturing_api import resolve_endcap_request


def _seg(length, angle=None, core=None, key=None):
    return FoldProfileSegment(length=float(length), angle=angle, core=core, phase6_key=key)


def test_resolved_endcap_request_uses_profile_before_scalar_folds():
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=91, fold_right=92, fold_top=93, fold_bottom=94,
        fold_profile_x=(
            _seg(10, -90, key="left"),
            _seg(392, -90, core="W-2T", key="endcap_w_core"),
            _seg(20, key="right"),
        ),
        fold_profile_y=(
            _seg(7, -90, key="front_extra"),
            _seg(25, -90, key="fw"),
            _seg(244, -90, core="D-T", key="endcap_d_core"),
            _seg(13, key="ybottom1"),
        ),
    )
    got = resolve_endcap_request(spec)
    assert (got.fold_left, got.fold_right, got.fold_top, got.fold_bottom) == pytest.approx((10, 20, 7, 13))


def test_resolved_endcap_request_uses_legacy_scalars_without_profiles():
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=11, fold_right=12, fold_top=13, fold_bottom=14,
    )
    got = resolve_endcap_request(spec)
    assert (got.fold_left, got.fold_right, got.fold_top, got.fold_bottom) == pytest.approx((11, 12, 13, 14))


def test_flat_x_profile_forces_zero_effective_side_folds_without_guessing_corner_type():
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(_seg(400, key="endcap_w_flat"),),
    )
    got = resolve_endcap_request(spec)
    assert got.assembly is None
    assert got.fold_left == pytest.approx(0)
    assert got.fold_right == pytest.approx(0)
```

- [x] **Step 2: 跑測試確認 RED**

Run: `env -u DISPLAY python -m pytest tests/test_endcap_resolved_geometry_ownership.py -q`

Expected: import FAIL，因 `resolve_endcap_request` 尚不存在。

- [x] **Step 3: 實作 resolved request 與 parser**

在 `manufacturing_api.py` 新增不可變 `ResolvedEndCapRequest`。欄位固定為：

```python
@dataclass(frozen=True)
class ResolvedEndCapRequest:
    width: float
    depth: float
    thickness: float
    frame_width: float
    height: float | None
    model_name: str | None
    is_tail: bool
    fold_left: float
    fold_right: float
    fold_top: float
    fold_bottom: float
    fold_profile_x: tuple
    fold_profile_y: tuple
    corner_policy: object | None
    assembly: EndCapAssemblySemantics | None
    holes: tuple
```

`resolve_endcap_request(spec)` 規則：

1. scalar `None` 轉為 AE 既有預設值前，不在 GUI 猜；resolver 使用 `ae.yl1_def/yr1_def/ytop1_def/ybottom1_def` 作 legacy default。
2. X profile 有 `phase6_key="endcap_w_flat"` → left/right = 0。
3. 否則 X profile 有 `core="W-2T"` → core 前總長 = left、core 後總長 = right。
4. Y profile 非空 → `phase6_key="ybottom1"` 總長 = bottom；排除 `fw/endcap_d_core/ybottom1` 後總長 = top。
5. `corner_policy` 非空 → `resolve_endcap_policy_assembly_semantics()`；assembly 為 OVERLAY 時無條件 left/right = 0。
6. 未提供 `corner_policy` 時不推測 CornerType，`assembly=None`。

- [x] **Step 4: 修改 `build_part_scene()` EndCap branch**

```python
resolved = resolve_endcap_request(spec)
common = dict(
    w=resolved.width,
    d=resolved.depth,
    t=resolved.thickness,
    fw=resolved.frame_width,
    yl1=resolved.fold_left,
    yr1=resolved.fold_right,
    ytop1=resolved.fold_top,
    ybottom1=resolved.fold_bottom,
    draw_stock=ctx.draw_stock,
    is_tail=resolved.is_tail,
    holes=_legacy_endcap_holes(spec),
)
```

baseline／unknown／factory scene builder 都使用 `resolved`，`_scene_with_authoritative_fold_profiles()` 也使用 `resolved.fold_profile_x/y`。

- [x] **Step 5: 跑 ownership 測試確認 GREEN**

Run: `env -u DISPLAY python -m pytest tests/test_endcap_resolved_geometry_ownership.py -q`

Expected: 7 passed。

---

### Task 3: 移除 GUI 的 Fold Profile → scalar 幾何預解析

**Files:**
- Modify: `gui.py`
- Modify: `tests/test_endcap_resolved_geometry_ownership.py`

**Interfaces:**
- Consumes: GUI canonical `val`、Bridge Fold Profile raw rows。
- Produces: `EndCapPartSpec`；scalar folds 保留 canonical／legacy 原值，profile 原樣轉成 `FoldProfileSegment`。

- [x] **Step 1: 寫 GUI adapter 失敗測試**

```python
import gui


def test_gui_endcap_adapter_does_not_pre_resolve_profile_into_scalar_folds():
    app = object.__new__(gui.BoxCalculatorGUI)
    spec = app._end_cap_part_spec_from_values(
        {
            "w": 400, "h": 600, "d": 250, "t": 2, "fw": 25,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "zl1": 20, "zr1": 21,
        },
        model_name=None,
        is_tail=False,
        holes=(),
        fold_profiles={
            "X": [
                {"len": 10, "angle": -90, "phase6_key": "left"},
                {"len": 392, "angle": -90, "core": "W-2T", "phase6_key": "endcap_w_core"},
                {"len": 20, "phase6_key": "right"},
            ],
            "Y": [
                {"len": 7, "angle": -90, "phase6_key": "front_extra"},
                {"len": 25, "angle": -90, "phase6_key": "fw"},
                {"len": 244, "angle": -90, "core": "D-T", "phase6_key": "endcap_d_core"},
                {"len": 13, "phase6_key": "ybottom1"},
            ],
        },
    )
    assert (spec.fold_left, spec.fold_right, spec.fold_top, spec.fold_bottom) == pytest.approx((15, 15, 16, 15))
    assert len(spec.fold_profile_x) == 3
    assert len(spec.fold_profile_y) == 4
```

- [x] **Step 2: 跑測試確認 RED**

Run: `env -u DISPLAY python -m pytest tests/test_endcap_resolved_geometry_ownership.py::test_gui_endcap_adapter_does_not_pre_resolve_profile_into_scalar_folds -q`

Expected: FAIL，現況會得到 10/20/7/13。

- [x] **Step 3: 最小修改 GUI adapter**

刪除 `_end_cap_part_spec_from_values()` 裡依 X/Y profile 聚合 `fold_left/right/top/bottom` 的程式，只保留：

```python
fold_left=float(val["yl1"])
fold_right=float(val["yr1"])
fold_top=float(val["ytop1"])
fold_bottom=float(val["ybottom1"])
fold_profile_x=profile_to_fold_segments(x_rows)
fold_profile_y=profile_to_fold_segments(y_rows)
```

- [x] **Step 4: 跑 GUI adapter 與 resolver 測試確認 GREEN**

Run: `env -u DISPLAY python -m pytest tests/test_endcap_resolved_geometry_ownership.py -q`

Expected: 8 passed。

---

### Task 4: 建立 OVERLAY W=400 全資料鏈契約

**Files:**
- Modify: `tests/test_endcap_resolved_geometry_ownership.py`
- Modify: `ae_engine/manufacturing_api.py` only when the new test proves a remaining EndCap boundary bug

**Interfaces:**
- Consumes: `EndCapPartSpec` + OVERLAY policy + W-FLAT profile。
- Produces: width 400 through resolver → Final Scene → `PartRenderData` → serialized DXF。

- [x] **Step 1: 寫完整資料鏈測試**

```python
import ezdxf
from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import build_part_render_data, save_part_render_data_dxf
from ae_engine.sheetmetal_geometry import CornerDirection, CrossCornerMode


def _overlay_policy():
    top = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.0)
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.WIDTH,
        amount_t=1.5,
    )
    return FourCornerTypePolicy(bottom, bottom, top, top, 25.0)


@pytest.mark.parametrize("is_tail", [False, True])
def test_overlay_400_span_is_identical_from_resolver_to_dxf(tmp_path, is_tail):
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        is_tail=is_tail,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(_seg(400, key="endcap_w_flat"),),
        corner_policy=_overlay_policy(),
    )
    resolved = resolve_endcap_request(spec)
    assert (resolved.fold_left, resolved.fold_right) == pytest.approx((0, 0))
    render = build_part_render_data(spec, ManufacturingContext(draw_stock=False))
    minx, miny, maxx, maxy = map(float, render.material.bounds)
    assert maxx - minx == pytest.approx(400)
    vertical_bends = [
        primitive for primitive in render.scene.primitives
        if str(getattr(primitive, "layer", "")).upper() == "BEND"
        and hasattr(primitive, "p1") and hasattr(primitive, "p2")
        and abs(float(primitive.p1.x) - float(primitive.p2.x)) < 1e-9
    ]
    assert vertical_bends == []

    output = tmp_path / ("tail.dxf" if is_tail else "head.dxf")
    save_part_render_data_dxf(render, output, overwrite=True)
    doc = ezdxf.readfile(output)
    cutting = [
        ent for ent in doc.modelspace()
        if str(ent.dxf.layer).upper() == "CUTTING" and ent.dxftype() == "LWPOLYLINE"
    ]
    assert cutting
    points = [(float(x), float(y)) for x, y, *_ in cutting[0].get_points()]
    xs = [p[0] for p in points]
    assert max(xs) - min(xs) == pytest.approx(400)
```

- [x] **Step 2: 跑測試**

Run: `env -u DISPLAY python -m pytest tests/test_endcap_resolved_geometry_ownership.py -q`

Expected: 10 passed。若出現失敗，只能修 `resolve_endcap_request()` 或 EndCap scene boundary，禁止在 GUI／Bridge 加尺寸補丁。

---

### Task 5: 驗證 Bridge 仍只是 UI request/profile 層

**Files:**
- Verify only: `fold_designer_bridge.py`
- Verify: `tests/test_phase6_shared_assembly_and_dimensions.py`
- Verify: `tests/test_phase6_linked_fold_chain_and_parts.py`

**Interfaces:**
- Consumes: raw snapshot／CornerType mirror。
- Produces: Fold editor profile／tab state；不產生 Final Scene 或 `PartRenderData`。

- [x] **Step 1: source guard**

Run:

```bash
python - <<'PY'
from pathlib import Path
src = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
for forbidden in ("ResolvedEndCapRequest(", "PartRenderData(", "build_part_render_data("):
    assert forbidden not in src, forbidden
print("bridge ownership guard: OK")
PY
```

Expected: `bridge ownership guard: OK`。

- [x] **Step 2: 保留既有 OVERLAY editor 行為**

Run: `env -u DISPLAY python -m pytest tests/test_phase6_shared_assembly_and_dimensions.py tests/test_phase6_linked_fold_chain_and_parts.py -q`

Expected: 0 failures；OVERLAY X editor 仍只有 `endcap_w_flat`，Fold tabs 仍只有 `Y`，load/redraw 不重設 bottom CornerType。

---

### Task 6: 完整回歸、修改日誌與交付

**Files:**
- Modify: `修改日誌/20260823.md`
- Verify only: `config.ini`
- Create: FULL/UPDATE ZIP

**Interfaces:**
- Consumes: Tasks 1-5 全部變更。
- Produces: 綠燈專案、繁體中文修改日誌、共同 Asia/Taipei 時間戳的 FULL／UPDATE。

- [x] **Step 1: 記錄 `config.ini` SHA256**

Run: `sha256sum config.ini > /tmp/phase6_config_before.sha256`

- [x] **Step 2: 跑聚焦回歸**

Run:

```bash
xvfb-run -a python -m pytest \
  tests/test_endcap_resolved_geometry_ownership.py \
  tests/test_corner_semantics.py \
  tests/test_corner_parameter_lock.py \
  tests/test_phase6_shared_assembly_and_dimensions.py \
  tests/test_phase6_linked_fold_chain_and_parts.py \
  tests/test_phase6_3d_single_source_renderer.py \
  tests/test_phase6_ui_state_regressions.py -q
```

Expected: 0 failures。

- [x] **Step 3: 跑完整測試**

Run: `xvfb-run -a python -m pytest -q`

Expected: 0 failures。

- [x] **Step 4: Python 語法編譯**

Run: `python -m py_compile gui.py fold_designer_bridge.py ae_engine/sheetmetal_geometry.py ae_engine/manufacturing_api.py tests/test_endcap_resolved_geometry_ownership.py`

Expected: exit 0。

- [x] **Step 5: 驗證 `config.ini` 未改**

Run: `sha256sum -c /tmp/phase6_config_before.sha256`

Expected: `config.ini: OK`。

- [x] **Step 6: 更新繁體中文修改日誌**

追加本輪根因、唯一所有權設計、實際修改檔、測試總數、OVERLAY 400 契約、`config.ini` 未修改證據。

- [x] **Step 7: 建立 UPDATE／FULL**

使用 `TZ=Asia/Taipei date +%Y%m%d_%H%M%S` 取得一次時間戳；FULL 與 UPDATE 共用該值。UPDATE 至少包含本輪修改的 production/test/spec/plan/修改日誌；FULL 包含完整專案。

- [x] **Step 8: 驗證 ZIP**

Run: `python -m zipfile -t <FULL.zip>` 與 `python -m zipfile -t <UPDATE.zip>`。

Expected: 兩包都輸出 `Done testing`。

---

## 自我檢查

- 規格中的語意 resolver、profile precedence、GUI 去預解析、OVERLAY 400、PartRenderData/DXF、Bridge boundary、完整回歸都有對應工作項目。
- 文件沒有未決占位內容。
- 型別／函式名稱一致：`EndCapAssemblySemantics` → `resolve_endcap_assembly_semantics()` → `resolve_endcap_policy_assembly_semantics()`；`ResolvedEndCapRequest` → `resolve_endcap_request()` → `build_part_scene()`。
- 第一輪不擴張 Door／BoxBody/BasePlate，也不拆大檔。


## 2026-08-23 實際執行結果

- 實作過程依 TDD 逐項 RED → GREEN；最終 ownership 契約為 `20 passed`。
- 額外在 code review 發現並修正四個原計畫未充分展開但屬同一資料鏈的 seam：
  1. `endcap_outer_thickness_factor()` 原本仍有第二套 CornerType 解讀。
  2. unknown／baseline structural builder 原本仍自行判斷 `OVERLAY`，現在明確接收 AE resolver 的 `x_topology`。
  3. 基準檔拉伸器原本用 polygon vertex index 配對不同 CornerType 外框，OVERLAY 會因頂點數不同 `IndexError`；改為 X/Y 一維座標層級映射。
  4. `INSERT / INSERT_OVERLAY + stale endcap_w_flat` 原本可反向蓋掉 CornerType；現在 resolver 丟棄不相容 profile。
- Bridge ownership source guard：`OK`。
- 聚焦回歸（排除 4 個硬編碼缺件 fixture）：`161 passed, 2 skipped, 4 deselected`。
- 全套原始回歸：`259 passed, 2 skipped, 4 failed`；四個 failure 與修改前完全相同，唯一原因是環境缺少 `/mnt/data/自訂.p6fold`。
- 全套排除上述 4 個已知缺件 fixture：`259 passed, 2 skipped, 4 deselected`，0 failure。
- `py_compile`：通過。
- `config.ini` SHA256 維持 `5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`。
- 此副本無 `.git`，因此沒有 commit／merge／PR 步驟。
