# 全類型 Sheet-Metal Topology 遷移設計

**日期:** 2026-08-10

## 目標

把目前 `ae.py` 中依零件類型各自手工組裝 CUTTING/BEND 的邏輯，收斂成共用的 2D sheet-metal topology engine。

重點不是消滅每一種製造規則，而是消滅「依盤型/零件名稱硬寫座標」。引擎只認：

- blank / panel face
- bend
- flange / fold chain
- corner
- assembly relation
- relief policy

零件名稱只負責建立 topology，不參與 relief 幾何判斷。

---

## 現況盤點

| 現有路徑 | 現況外框 | 現況 BEND | 可歸類拓撲 | 遷移策略 |
|---|---|---|---|---|
| `export_end_cap_dxf()` | 已改成 relief polygon subtraction | 已由 material clipping 產生 | 四邊折板 + 上方二折 + assembly relation | 已完成第一版，保留為 assembly relief regression case |
| `get_stretched_end_cap_data()` | 已使用 end-cap geometry engine | 已使用 engine bend segments | 同上 | 已完成第一版 |
| `export_door_dxf()` | 12 點十字形，角落 X=`side_fold-T`、Y=`top/bottom_fold` | 4 條手工線 | 四邊單折板 | 改用通用 FourSideFlange topology + corner policy |
| `get_stretched_door_data()` | 重新生成與門相同的十字形，再映射基準檔圖元 | 4 條手工線 | 四邊單折板 | 和 direct door 共用同一 geometry builder，基準檔只負責非結構圖元映射 |
| `get_indicator_box_data()` | 固定 12 點，硬寫 47/49 | 固定 49 的 4 條線 | 四邊單折板 | 直接併入 Door 同一 rule；49=fold，47=fold-T (T=2) |
| `export_base_plate_dxf()` | 12 點十字形，角落 `bend × bend` | 4 條手工線 | 四邊單折板 | 共用 FourSideFlange topology，但使用不同 corner policy |
| `export_box_body_dxf()` | 純矩形 | 8 條垂直折彎線 | 一維多折鏈 | 新增 StripFoldChain topology；無 corner relief |
| `get_stretched_box_body_data()` | 純矩形 | 基準檔偵測 7/8 條垂直折彎線 | 一維多折鏈 | 和 direct box body 共用 StripFoldChain builder；基準檔只負責 feature mapping |

---

## 最重要的收斂結果

### 拓撲族 A：FourSideFlangePart

適用：

- Door
- Indicator Box
- Base Plate
- End Cap / Tail（加上 top chain + assembly relation）

統一描述：

```python
FourSideFlangePart(
    blank_width=...,
    blank_height=...,
    thickness=T,
    left=Flange(...),
    right=Flange(...),
    top=Flange(...),
    bottom=Flange(...),
)
```

角落 relief 不用知道「門 / 指示燈盒 / 底板」。

它只吃 `CornerReliefPolicy`。

### Door / Indicator Box 共用 policy

現有 Door：

- 左右 corner X = `side_fold - T`
- 上下 corner Y = `top/bottom_fold`

Indicator Box 目前：

- fold = 49
- X = 47
- Y = 49

在 T=2 時：

- `49 - 2 = 47`

所以兩者是同一個物理/幾何 policy，只是 Indicator Box 把值寫死。

### Base Plate policy

Base Plate 目前：

- corner X = `bend`
- corner Y = `bend`

它和 Door 有相同 topology，但 relief policy 不同。

因此應該是：

```python
RectCornerReliefPolicy(
    left_trim=...,
    right_trim=...,
    top_trim=...,
    bottom_trim=...,
)
```

而不是：

```python
if part_type == "BASE_PLATE":
    ...
```

### End Cap policy

End Cap 是 FourSideFlange 的擴充：

- top 是二折 chain
- 有 assembly insertion relation
- top primary relief = flush-front requirement
- top secondary relief = insertion clearance

它仍然走同一個 OutlineBuilder，只是 ReliefEngine 多一條 assembly rule。

---

## 拓撲族 B：StripFoldChainPart

適用：

- Box Body
- Stretched Box Body
- 未來任何只沿單一方向連續折彎的箱身/槽體展開

統一描述：

```python
StripFoldChainPart(
    height=...,
    segments=[
        Segment(length=...),
        Segment(length=...),
        ...
    ],
)
```

bend 位置由 segment 累加動態產生。

目前箱身的：

```text
zl1
zl2
FW
D-2T
W-2T
D-2T
FW
zr2
zr1
```

應該被轉成 segment chain，而不是保留 `x1 ... x8` 手算。

`z_comp` 也應作為 chain compensation policy，而不是 exporter 內分散計算。

Box Body 沒有 corner relief，所以不應硬塞進 CornerReliefEngine；它使用相同 topology framework，但走 `StripOutlineBuilder`。

---

## 通用資料模型

建議在 `sheetmetal_geometry.py` 擴充：

```python
@dataclass(frozen=True)
class FoldSegment:
    name: str
    length: float
    compensation: float = 0.0


@dataclass(frozen=True)
class StripFoldChain:
    segments: tuple[FoldSegment, ...]
    height: float


@dataclass(frozen=True)
class FourSideFlangeGeometry:
    total_width: float
    total_height: float
    thickness: float
    left_fold: float
    right_fold: float
    top_fold: float
    bottom_fold: float


@dataclass(frozen=True)
class RectCornerRelief:
    left_bottom_x: float
    right_bottom_x: float
    left_top_x: float
    right_top_x: float
    bottom_y: float
    top_y: float
```

核心 builder：

```python
build_four_side_outline(...)
build_four_side_bend_segments(...)
build_strip_bend_segments(...)
build_strip_outline(...)
clip_bends_to_material(...)
```

---

## Rule 層

ReliefEngine 不應包含 part name。

推薦 rule：

1. `RectangularCornerReliefRule`
   - 通用四角矩形 cut
   - Door / Indicator Box / Base Plate 都可使用
   - 尺寸由 policy 提供

2. `AssemblyInsertionReliefRule`
   - End Cap/Tail
   - 只看 `assembly relation + inserting flange + mating panel`

3. `NoCornerReliefRule`
   - Strip fold chain / Box Body

後續如果真的出現新的物理關係，例如：

- flange overlap
- hem
- tab/slot
- 三折相撞

才新增 rule。

新增新盤名不應新增 rule。

---

## Baseline DXF 的角色重新定義

目前 stretched functions 同時做：

- 結構外框
- BEND
- 孔位/標記映射

遷移後必須拆開：

```text
Geometry Engine
  → 決定 CUTTING 外框
  → 決定 BEND

Baseline Mapper
  → 只映射孔、MARKING、局部 CUTTING feature
  → 不再決定主外框與主 BEND
```

如此 direct export 與 stretched export 的結構幾何必然一致。

---

## 成功標準

1. `ae.py` 不再有 Door/BasePlate/Indicator 的 12 點主外框 literal。
2. `ae.py` 不再有 BoxBody 的 `x1...x8` 作為唯一 bend 幾何來源。
3. direct 與 stretched 同類零件共用同一 topology builder。
4. Indicator Box 在 T=2 時保持目前 47/49 幾何；T 改為 1.5 時 corner X 自動變為 47.5，而不是繼續固定 47。
5. Door / Base Plate / Box Body / End Cap 都有純幾何 regression tests，不需 ezdxf 即可驗證。
6. DXF exporter 只負責把 engine result 寫到 layer，不再推導主 CUTTING/BEND。
7. 新零件如果 topology/rule 已存在，只新增 topology assembly code，不新增新的 outline builder。
