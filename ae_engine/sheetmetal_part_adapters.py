# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Pure adapters from WHD legacy/UI parameters to structural geometry results.

This module contains no Tkinter or ezdxf dependencies.  It is the shared
translation layer used by both GUI preview and DXF serialization.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from .sheetmetal_features import RectGuide

from .sheetmetal_geometry import (
    BendLine,
    EndCapGeometry,
    FoldSegment,
    FourSideBendExtentPolicy,
    FourSideFlangeGeometry,
    RectCornerReliefPolicy,
    FourCornerTypePolicy,
    CornerTypeSelection,
    ReliefConfig,
    StripFoldChain,
    Vec2,
    build_endcap_bend_segments,
    build_endcap_outline,
    build_endcap_bend_segments_from_corner_types,
    build_endcap_outline_from_corner_types,
    build_four_side_bend_segments,
    build_four_side_outline,
    build_strip_bend_segments,
    build_strip_outline,
    box_body_height_from_corner_policies,
)


@dataclass(frozen=True)
class DoorFrameEdges:
    """Enclosure-frame edges surrounding one Door start-size cell.

    These flags affect only the conversion from cell start W/H to the finished
    Door size.  They do not remove any fold from the Door panel itself.
    """
    left: bool = True
    right: bool = True
    top: bool = True
    bottom: bool = True


@dataclass(frozen=True)
class DoorLayoutCell:
    column_index: int
    row_index: int
    start_width: float
    start_height: float
    edges: DoorFrameEdges


@dataclass(frozen=True)
class PartitionCompletion:
    """Completed one ordered W/H partition with an optional generated remainder."""
    values: tuple[float, ...]
    auto_index: int | None
    valid: bool
    excess: float = 0.0


def _finite_float(value, name="value") -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must not be bool")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def complete_partition(fixed_values, total, *, tolerance=1e-9) -> PartitionCompletion:
    """Append one positive remainder to fixed values when space remains.

    ``fixed_values`` contains only user-owned values.  The returned auto cell is
    deliberately not folded back into that list, so editing it can promote it to
    a fixed value before this helper is called again.
    """
    total = _finite_float(total, "partition total")
    tolerance = _finite_float(tolerance, "partition tolerance")
    if tolerance < 0:
        raise ValueError("partition tolerance must be >= 0")
    if total <= 0:
        raise ValueError("partition total must be > 0")
    fixed = tuple(_finite_float(value, "partition entry") for value in fixed_values)
    if any(value <= 0 for value in fixed):
        raise ValueError("partition values must be > 0")

    used = sum(fixed)
    remainder = total - used
    if remainder > tolerance:
        return PartitionCompletion(fixed + (remainder,), len(fixed), True, 0.0)
    if remainder < -tolerance:
        return PartitionCompletion(fixed, None, False, -remainder)
    return PartitionCompletion(fixed, None, True, 0.0)


def derive_door_layout_cells(columns) -> tuple[DoorLayoutCell, ...]:
    """Expand ``[(column_width, [top..bottom heights]), ...]`` into cells."""
    normalized = []
    for column_index, column in enumerate(columns):
        if len(column) != 2:
            raise ValueError("each door layout column must be (width, heights)")
        width, heights = column
        width = _finite_float(width, "door column width")
        heights = tuple(_finite_float(value, "door row height") for value in heights)
        if width <= 0:
            raise ValueError("door layout column width must be > 0")
        if not heights or any(value <= 0 for value in heights):
            raise ValueError("door layout column heights must contain positive values")
        normalized.append((width, heights))
    if not normalized:
        raise ValueError("door layout must contain at least one column")

    cells = []
    last_column = len(normalized) - 1
    for column_index, (width, heights) in enumerate(normalized):
        last_row = len(heights) - 1
        for row_index, height in enumerate(heights):
            cells.append(DoorLayoutCell(
                column_index=column_index,
                row_index=row_index,
                start_width=width,
                start_height=height,
                edges=DoorFrameEdges(
                    left=True,
                    right=(column_index == last_column),
                    top=True,
                    bottom=(row_index == last_row),
                ),
            ))
    return tuple(cells)


def door_layout_part_key(cell: DoorLayoutCell) -> str:
    """Stable one-based identity shared by Fold Designer and DXF export."""
    return f"door_c{cell.column_index + 1}_r{cell.row_index + 1}"


def door_layout_export_filename(cell: DoorLayoutCell) -> str:
    return f"{door_layout_part_key(cell)}.dxf"


def door_layout_feature_map_to_part_features(columns, feature_map) -> dict[str, list]:
    """Project legacy ``col:row`` Door feature stores to formal part identities."""
    source = dict(feature_map or {})
    result = {}
    for cell in derive_door_layout_cells(columns):
        legacy_key = f"{cell.column_index}:{cell.row_index}"
        result[door_layout_part_key(cell)] = list(source.get(legacy_key, ()) or ())
    return result


def door_part_features_to_layout_feature_map(columns, part_features) -> dict[str, list]:
    """Project formal Door part features back to the main 2D layout store."""
    source = dict(part_features or {})
    result = {}
    for cell in derive_door_layout_cells(columns):
        part_key = door_layout_part_key(cell)
        result[f"{cell.column_index}:{cell.row_index}"] = list(source.get(part_key, ()) or ())
    return result


def validate_door_layout_dimensions(columns, *, total_width, total_height, tolerance=1e-6) -> tuple[DoorLayoutCell, ...]:
    """Validate layout start dimensions against the enclosure WHD face size."""
    target_width = _finite_float(total_width, "total_width")
    target_height = _finite_float(total_height, "total_height")
    tol = _finite_float(tolerance, "door layout tolerance")
    if tol < 0:
        raise ValueError("door layout tolerance must be >= 0")
    normalized = []
    for column in columns:
        if len(column) != 2:
            raise ValueError("each door layout column must be (width, heights)")
        width, heights = column
        normalized.append((
            _finite_float(width, "door column width"),
            tuple(_finite_float(v, "door row height") for v in heights),
        ))
    cells = derive_door_layout_cells(normalized)
    width_sum = sum(width for width, _ in normalized)
    if abs(width_sum - target_width) > tol:
        raise ValueError(f"door layout column widths sum to {width_sum:g}, expected W={target_width:g}")
    for index, (_width, heights) in enumerate(normalized, start=1):
        height_sum = sum(heights)
        if abs(height_sum - target_height) > tol:
            raise ValueError(
                f"door layout column {index} heights sum to {height_sum:g}, expected H={target_height:g}"
            )
    return cells


def calculate_door_finished_size(*, w, h, t, fw, gap_w, gap_h, frame_edges: DoorFrameEdges | None = None):
    """Convert one Door cell start size to finished Door W/H.

    A present enclosure-frame edge consumes one ``FW + 2T`` span.  Door gap is
    still applied on both sides of each axis.
    """
    edges = frame_edges or DoorFrameEdges()
    w = _finite_float(w, "w")
    h = _finite_float(h, "h")
    t = _finite_float(t, "t")
    fw = _finite_float(fw, "fw")
    gap_w = _finite_float(gap_w, "gap_w")
    gap_h = _finite_float(gap_h, "gap_h")
    if t <= 0 or fw < 0 or gap_w < 0 or gap_h < 0:
        raise ValueError("door thickness must be positive; FW and gaps nonnegative")
    frame_span = fw + 2.0 * t
    finished_w = w - frame_span * (int(edges.left) + int(edges.right)) - 2.0 * gap_w
    finished_h = h - frame_span * (int(edges.top) + int(edges.bottom)) - 2.0 * gap_h
    if finished_w <= 0 or finished_h <= 0:
        raise ValueError("door finished dimensions must be > 0")
    return finished_w, finished_h


@dataclass(frozen=True)
class StructuralGeometryResult:
    outline: tuple[Vec2, ...]
    bends: tuple[BendLine, ...]
    width: float
    height: float
    topology: object | None = None


def _result(outline, bends, width: float, height: float, topology=None) -> StructuralGeometryResult:
    return StructuralGeometryResult(tuple(outline), tuple(bends), _finite_float(width), _finite_float(height), topology)



def build_box_body_result_from_fold_profile(
    profile, *, h, t,
    head_corner_policy: FourCornerTypePolicy | None = None,
    tail_corner_policy: FourCornerTypePolicy | None = None,
):
    """Build a flat Box Body directly from an arbitrary semantic Fold Chain.

    The profile must retain the structural D-W-D core anchors, but the material
    before/after that core may contain any practical number of user folds.
    Segment count is never interpreted.
    """
    rows = list(profile or ())
    if len(rows) < 3:
        raise ValueError("box body fold profile requires D-W-D core")

    def value(row, name, default=None):
        if isinstance(row, Mapping):
            current = row.get(name, default)
        else:
            current = getattr(row, name, default)
        return default if current is None else current

    d_indexes = [i for i, row in enumerate(rows) if value(row, "core") == "D"]
    w_indexes = [i for i, row in enumerate(rows) if value(row, "core") == "W"]
    if len(d_indexes) != 2 or len(w_indexes) != 1 or not (d_indexes[0] < w_indexes[0] < d_indexes[1]):
        raise ValueError("box body fold profile must contain ordered D-W-D core")

    left_d, right_d = d_indexes
    w_index = w_indexes[0]
    segments = []
    for index, row in enumerate(rows):
        length = _finite_float(
            value(row, "length", value(row, "len", 0.0)), "fold segment length"
        )
        if index == left_d:
            name = "depth_left"
        elif index == w_index:
            name = "front"
        elif index == right_d:
            name = "depth_right"
        else:
            name = str(value(row, "phase6_key") or f"fold_{index}")
        segments.append(FoldSegment(name, length, 0.0))

    chain = StripFoldChain(
        segments=tuple(segments),
        height=box_body_height_from_corner_policies(
            h, t,
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        ),
    )
    return _result(
        build_strip_outline(chain), build_strip_bend_segments(chain),
        chain.total_width, chain.height, chain,
    )

def build_box_body_result(
    *, w, h, d, t, fw, zl1, zl2, zr1, zr2, z_comp, include_right_fw=True,
    head_corner_policy: FourCornerTypePolicy | None = None,
    tail_corner_policy: FourCornerTypePolicy | None = None,
):
    lengths = [
        ("zl1", abs(_finite_float(zl1))),
        ("zl2", _finite_float(zl2)),
        ("fw_left", _finite_float(fw)),
        ("depth_left", _finite_float(d) - 2.0 * _finite_float(t)),
        ("front", _finite_float(w) - 2.0 * _finite_float(t)),
        ("depth_right", _finite_float(d) - 2.0 * _finite_float(t)),
    ]
    if include_right_fw:
        lengths.append(("fw_right", _finite_float(fw)))
    lengths.extend([("zr2", _finite_float(zr2)), ("zr1", abs(_finite_float(zr1)))])
    comp = _finite_float(z_comp) / len(lengths)
    chain = StripFoldChain(
        segments=tuple(FoldSegment(name, length, comp) for name, length in lengths),
        height=box_body_height_from_corner_policies(
            h, t,
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        ),
    )
    outline = build_strip_outline(chain)
    bends = build_strip_bend_segments(chain)
    width = sum(seg.length + seg.compensation for seg in chain.segments)
    return _result(outline, bends, width, chain.height, chain)


def build_door_result(*, w, h, t, fw, gap_w, gap_h, fold_left, fold_right, fold_top, fold_bottom, frame_edges: DoorFrameEdges | None = None):
    t = _finite_float(t)
    finished_w, finished_h = calculate_door_finished_size(
        w=w, h=h, t=t, fw=fw, gap_w=gap_w, gap_h=gap_h, frame_edges=frame_edges,
    )
    blank_w = finished_w - 2.0 * t + _finite_float(fold_left) + _finite_float(fold_right)
    blank_h = finished_h - 2.0 * t + _finite_float(fold_top) + _finite_float(fold_bottom)
    geometry = FourSideFlangeGeometry(
        total_width=blank_w,
        total_height=blank_h,
        thickness=t,
        left_fold=_finite_float(fold_left),
        right_fold=_finite_float(fold_right),
        top_fold=_finite_float(fold_top),
        bottom_fold=_finite_float(fold_bottom),
    )
    from .certified_relief_registry import certified_corner_policy_for_part
    policy = certified_corner_policy_for_part("金庫型", "door", fw=_finite_float(fw))
    return _result(
        build_four_side_outline(geometry, policy),
        build_four_side_bend_segments(geometry, policy),
        blank_w,
        blank_h,
        geometry,
    )


def build_unknown_door_result(
    *, w, h, t, fw, gap_w, gap_h,
    fold_left, fold_right, fold_top, fold_bottom, corner_policy: FourCornerTypePolicy,
    frame_edges: DoorFrameEdges | None = None,
):
    """Manual/unknown Door: same fold topology, caller-selected CornerType policy."""
    t = _finite_float(t)
    finished_w, finished_h = calculate_door_finished_size(
        w=w, h=h, t=t, fw=fw, gap_w=gap_w, gap_h=gap_h, frame_edges=frame_edges,
    )
    blank_w = finished_w - 2.0 * t + _finite_float(fold_left) + _finite_float(fold_right)
    blank_h = finished_h - 2.0 * t + _finite_float(fold_top) + _finite_float(fold_bottom)
    geometry = FourSideFlangeGeometry(
        total_width=blank_w, total_height=blank_h, thickness=t,
        left_fold=_finite_float(fold_left), right_fold=_finite_float(fold_right),
        top_fold=_finite_float(fold_top), bottom_fold=_finite_float(fold_bottom),
    )
    return _result(
        build_four_side_outline(geometry, corner_policy),
        build_four_side_bend_segments(geometry, corner_policy),
        blank_w, blank_h, geometry,
    )


def build_base_plate_result(*, w, h, t, shrink_top, shrink_bottom, shrink_left, shrink_right, bend):
    total_width = _finite_float(w) - _finite_float(shrink_left) - _finite_float(shrink_right) + 2.0 * _finite_float(bend)
    total_height = _finite_float(h) - _finite_float(shrink_top) - _finite_float(shrink_bottom) + 2.0 * _finite_float(bend)
    geometry = FourSideFlangeGeometry(
        total_width=total_width,
        total_height=total_height,
        thickness=_finite_float(t),
        left_fold=_finite_float(bend),
        right_fold=_finite_float(bend),
        top_fold=_finite_float(bend),
        bottom_fold=_finite_float(bend),
    )
    from .certified_relief_registry import certified_corner_policy_for_part
    policy = certified_corner_policy_for_part("金庫型", "base_plate", fw=0.0)
    return _result(
        build_four_side_outline(geometry, policy),
        build_four_side_bend_segments(geometry, policy),
        total_width,
        total_height,
        geometry,
    )


def build_unknown_base_plate_result(
    *, w, h, t, shrink_top, shrink_bottom, shrink_left, shrink_right, bend,
    corner_policy: FourCornerTypePolicy,
):
    total_width = _finite_float(w) - _finite_float(shrink_left) - _finite_float(shrink_right) + 2.0 * _finite_float(bend)
    total_height = _finite_float(h) - _finite_float(shrink_top) - _finite_float(shrink_bottom) + 2.0 * _finite_float(bend)
    geometry = FourSideFlangeGeometry(
        total_width=total_width, total_height=total_height, thickness=_finite_float(t),
        left_fold=_finite_float(bend), right_fold=_finite_float(bend), top_fold=_finite_float(bend), bottom_fold=_finite_float(bend),
    )
    return _result(
        build_four_side_outline(geometry, corner_policy),
        build_four_side_bend_segments(geometry, corner_policy),
        total_width, total_height, geometry,
    )


def build_indicator_box_result(*, total_width, total_height, t, fold=49.0):
    fold = _finite_float(fold)
    t = _finite_float(t)
    geometry = FourSideFlangeGeometry(
        total_width=_finite_float(total_width),
        total_height=_finite_float(total_height),
        thickness=t,
        left_fold=fold,
        right_fold=fold,
        top_fold=fold,
        bottom_fold=fold,
    )
    from .certified_relief_registry import certified_corner_policy_for_part
    policy = certified_corner_policy_for_part("金庫型", "indicator_box", fw=0.0)
    extent = FourSideBendExtentPolicy(horizontal_to_blank_edges=True)
    return _result(
        build_four_side_outline(geometry, policy),
        build_four_side_bend_segments(geometry, policy, extent),
        _finite_float(total_width),
        _finite_float(total_height),
        geometry,
    )


def build_unknown_indicator_box_result(
    *, total_width, total_height, t, fold=49.0, corner_policy: FourCornerTypePolicy,
):
    fold = _finite_float(fold)
    geometry = FourSideFlangeGeometry(
        total_width=_finite_float(total_width), total_height=_finite_float(total_height), thickness=_finite_float(t),
        left_fold=fold, right_fold=fold, top_fold=fold, bottom_fold=fold,
    )
    extent = FourSideBendExtentPolicy(horizontal_to_blank_edges=True)
    return _result(
        build_four_side_outline(geometry, corner_policy),
        build_four_side_bend_segments(geometry, corner_policy, extent),
        _finite_float(total_width), _finite_float(total_height), geometry,
    )


def build_endcap_result(
    *, w, d, t, fw, yl1, yr1, ytop1, ybottom1,
    relief_config: ReliefConfig, x_topology="folded", depth_comp_t=3.0,
):
    t = _finite_float(t)
    if x_topology not in {"folded", "flat"}:
        raise ValueError(f"unsupported EndCap x_topology: {x_topology}")
    total_width = (
        _finite_float(w)
        if x_topology == "flat"
        else _finite_float(w) - 4.0 * t + abs(_finite_float(yl1)) + abs(_finite_float(yr1))
    )
    total_depth = _finite_float(d) - _finite_float(depth_comp_t) * t + _finite_float(ytop1) + _finite_float(fw) + _finite_float(ybottom1)
    geometry = EndCapGeometry(
        total_width=total_width,
        total_depth=total_depth,
        thickness=t,
        fw=_finite_float(fw),
        left_fold=_finite_float(yl1),
        right_fold=_finite_float(yr1),
        top_first_fold=_finite_float(ytop1),
        bottom_fold=_finite_float(ybottom1),
    )
    return _result(
        build_endcap_outline(geometry, relief_config),
        build_endcap_bend_segments(geometry, relief_config),
        total_width,
        total_depth,
        geometry,
    )


def build_unknown_endcap_result(
    *, w, d, t, fw, yl1, yr1, ytop1, ybottom1,
    corner_policy: FourCornerTypePolicy, x_topology, depth_comp_t=3.0,
    nominal_yl1=None, nominal_yr1=None,
    box_body_formed_fw_left=None, box_body_formed_fw_right=None,
):
    """手動／自訂封頭尾：AE 已解析的 X topology 決定結構寬度。"""
    t = _finite_float(t)
    if x_topology not in {"folded", "flat"}:
        raise ValueError(f"unsupported EndCap x_topology: {x_topology}")
    flat_x = x_topology == "flat"
    nominal_left = _finite_float(yl1 if nominal_yl1 is None else nominal_yl1)
    nominal_right = _finite_float(yr1 if nominal_yr1 is None else nominal_yr1)
    left_fold = 0.0 if flat_x else _finite_float(yl1)
    right_fold = 0.0 if flat_x else _finite_float(yr1)
    # flat-X removes the physical EndCap X bend, but the top STANDARD corner
    # still uses the nominal material fold evidence.  Formed Box Body FW is
    # shadow/3D evidence only and must not become the manufacturing formula.
    if flat_x:
        relief_left_fold = nominal_left
        relief_right_fold = nominal_right
    else:
        relief_left_fold = left_fold
        relief_right_fold = right_fold
    # Bottom relief follows the physical X topology.  With flat-X there is no
    # X fold to protect, so lower CROSS/EXTRA_CUT uses a zero side-fold basis.
    bottom_relief_left_fold = left_fold if flat_x else relief_left_fold
    bottom_relief_right_fold = right_fold if flat_x else relief_right_fold
    total_width = (
        _finite_float(w)
        if flat_x
        else _finite_float(w) - 4.0 * t + abs(left_fold) + abs(right_fold)
    )
    total_depth = _finite_float(d) - _finite_float(depth_comp_t) * t + _finite_float(ytop1) + _finite_float(fw) + _finite_float(ybottom1)
    geometry = EndCapGeometry(
        total_width=total_width, total_depth=total_depth, thickness=t, fw=_finite_float(fw),
        left_fold=left_fold, right_fold=right_fold,
        top_first_fold=_finite_float(ytop1), bottom_fold=_finite_float(ybottom1),
    )
    bends = build_endcap_bend_segments_from_corner_types(
        geometry, corner_policy,
        relief_left_fold=relief_left_fold,
        relief_right_fold=relief_right_fold,
        bottom_relief_left_fold=bottom_relief_left_fold,
        bottom_relief_right_fold=bottom_relief_right_fold,
    )
    if flat_x:
        bends = [bend for bend in bends if bend.name not in {"left", "right"}]
    return _result(
        build_endcap_outline_from_corner_types(
            geometry, corner_policy,
            relief_left_fold=relief_left_fold,
            relief_right_fold=relief_right_fold,
            bottom_relief_left_fold=bottom_relief_left_fold,
            bottom_relief_right_fold=bottom_relief_right_fold,
        ),
        bends,
        total_width, total_depth, geometry,
    )


def build_finished_reference_guide(part_key, result: StructuralGeometryResult, *, finished_width, finished_height) -> RectGuide:
    """Map authoritative assembled dimensions into the unfolded world coordinates.

    The guide is a user-facing dimension/reference frame only.  It deliberately
    does not replace the result outline or FeatureSurface containment polygon.
    """
    key = str(part_key).lower()
    fw = _finite_float(finished_width)
    fh = _finite_float(finished_height)
    if fw <= 0 or fh <= 0:
        raise ValueError("finished reference dimensions must be > 0")

    topology = result.topology
    if key == "box_body" and isinstance(topology, StripFoldChain):
        segments = topology.segments
        front_index = next((i for i, seg in enumerate(segments) if seg.name == "front"), None)
        if front_index is None:
            raise ValueError("box body topology has no front segment")
        start = sum(seg.length + seg.compensation for seg in segments[:front_index])
        span = segments[front_index].length + segments[front_index].compensation
        cx = start + span / 2.0
        cy = result.height / 2.0
    elif key in {"door", "base_plate", "indicator_box", "indicator_door"} and isinstance(topology, FourSideFlangeGeometry):
        cx = (topology.left_fold + (result.width - topology.right_fold)) / 2.0
        cy = (topology.bottom_fold + (result.height - topology.top_fold)) / 2.0
    elif key in {"head", "tail", "endcap", "end_cap"}:
        return RectGuide(Vec2(0.0, 0.0), Vec2(fw, fh), "finished_boundary")
    else:
        cx = result.width / 2.0
        cy = result.height / 2.0

    return RectGuide(
        Vec2(cx - fw / 2.0, cy - fh / 2.0),
        Vec2(cx + fw / 2.0, cy + fh / 2.0),
        "finished_boundary",
    )



RECEIVING_BASE_PATTERN_LEFT = "LEFT_FLAT_SIDE"
RECEIVING_BASE_PATTERN_CENTER = "CENTER_DOUBLE_SIDE_FOLD"
RECEIVING_BASE_PATTERN_RIGHT = "RIGHT_FLAT_SIDE"
RECEIVING_BASE_PATTERNS = frozenset((
    RECEIVING_BASE_PATTERN_LEFT,
    RECEIVING_BASE_PATTERN_CENTER,
    RECEIVING_BASE_PATTERN_RIGHT,
))


def build_receiving_base_plate_result(
    *, w, h, t, shrink_top, shrink_bottom, shrink_left, shrink_right,
    bend, pattern, nfb_depth_pair_mm=None,
) -> StructuralGeometryResult:
    """Reuse the Base Plate part owner for the three drawn Receiving patterns.

    The supplied drawing is the SHAPE/BEND reference, not a manufacturing
    world-coordinate or a second NFB location owner. The part spec owns
    actual enclosure/plate dimensions; these offsets are always local UV.

    LEFT/RIGHT: straight side edges, TOP and BOTTOM material fold 20 mm.
    CENTER: upper/lower material folds match the NFB face depth step
    (35 for 107/72), and their outside lengths match the X second-return
    outside lengths. First side fold -40 is fixed; second side return is
    inferred from the real NFB depth pair when supplied. Historic previews
    used 40/33 for Shihlin 107/72 T2; this MUST NOT become a universal
    manufacturing rule. The central straight span is W-shrink_left-
    shrink_right; original W800 shrinks85/85 gives 630+2*(40+33-2)=772.
    The user inferred 33 from deep NFB FRONT to shallow plate BACK, i.e.
    107-(72+2)=33, not by counting two T deductions or assuming that
    33 is the formed outside-to-outside Z step (the NFB face step is 35).

    User supplied center source has 35-mm upper/lower material BEND offsets
    for 107/72 (not 20 mm). No drawing's absolute X/Y, holes
    or cut profile may become an installation coordinate by itself.
    """
    from .sheetmetal_geometry import BendLine

    values=(w,h,t,shrink_top,shrink_bottom,shrink_left,shrink_right,bend)
    # Check all source dimensions before derived geometry is built.
    values = tuple(_finite_float(v) for v in values)
    w,h,t,st,sb,sl,sr,bend=map(float,values)
    if pattern not in RECEIVING_BASE_PATTERNS:
        raise ValueError("Receiving Base Plate needs a known left/center/right bend pattern")
    if t<=0 or min(st,sb,sl,sr)<0 or w-sl-sr<=0 or h-st-sb<=0:
        raise ValueError("Receiving Base Plate dimensions cannot resolve valid material")
    if pattern in (RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT) and abs(bend-20.0)>1e-6:
        raise ValueError("Receiving LEFT/RIGHT top/bottom material bend is 20 mm")
    core_w=w-sl-sr
    blank_h=h-st-sb
    if pattern in (RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT):
        if blank_h<=2*bend:
            raise ValueError("Receiving Base Plate face height insufficient for upper/lower folds")
        blank_w=core_w
        outline=(Vec2(0.,0.),Vec2(blank_w,0.),
                 Vec2(blank_w,blank_h),Vec2(0.,blank_h))
        bends=(
            BendLine("receiving_bottom_20",Vec2(0.,bend),Vec2(blank_w,bend)),
            BendLine("receiving_top_20",Vec2(0.,blank_h-bend),
                     Vec2(blank_w,blank_h-bend)),
        )
        return _result(outline,bends,blank_w,blank_h,(
            "RECEIVING_BASE",pattern,core_w,blank_h,bend,t,
        ))

    if abs(t-2.0)>1e-6:
        raise ValueError("Receiving center double-side bend drawing is T2 only")
    first, second = 40.0, 33.0  # historical preview-only Shihlin 107/72, T2
    if nfb_depth_pair_mm is not None:
        # #1502/#1503: compute from the selected brand/model CSV depths.
        # User's NON-FOLDED thought experiment: reference NFB front face
        # minus shallow NFB BACK face; never deduct T twice.
        #   deep 107 / shallow 72, T2 => front-to-front 35, 2nd return 33.
        # This length is a face-datum TARGET, not measured 3D face parity.
        if (not isinstance(nfb_depth_pair_mm, (tuple, list))
                or len(nfb_depth_pair_mm) != 2):
            raise ValueError("Receiving depth pair requires (deep, shallow)")
        from .receiving_nfb_depth_surface_policy import receiving_nfb_second_side_fold_mm
        second = receiving_nfb_second_side_fold_mm(
            reference_nfb_depth_mm=nfb_depth_pair_mm[0],
            secondary_nfb_depth_mm=nfb_depth_pair_mm[1],
            base_plate_thickness_mm=t,
        )
    # The unfolded BLANK return and the two BEND station locations are
    # DIFFERENT measured values. The user's 受電箱底板(5).dxf has W772,
    # BENDING left stations x=(40,73) and right x=(699,732), measured
    # relative to the center example's cutting min-X. So their physical
    # station-to-station spacing is 33, NOT 31. The blank return is still
    # 40 + 33 - T2 = 71 on each side; that is NOT the 2nd BEND station.
    # For variable selected NFB depth second, preserve this distinction.
    # This does not certify the 3D folded skins or release manufacturing.
    # Outside-length parity is the CENTER contract, not the LEFT/RIGHT
    # 20-mm flat-source fold: X second material=second, outside=second+2T;
    # Y upper/lower material=second+T, outside=(second+T)+T.
    center_y_fold = second + t
    # A two-tier assembly can pass a shared, source-selected bend while
    # each tier owns a DIFFERENT selected NFB depth step. For CENTER,
    # only the tier's actual second-return geometry determines Y BEND;
    # legacy bend=20 must not override it or trigger a false conflict.
    if blank_h<=2*center_y_fold:
        raise ValueError("Receiving CENTER upper/lower folds consume physical sheet")
    side_fold=first+second-t
    second_bend_station=first+second
    blank_w=core_w+2*side_fold
    shoulder=center_y_fold
    corner_chamfer=5.0
    # Physical source CUTTING (受電箱底板(5).dxf, SHA256 cccf060c...4160d29b)
    # for W772/T2 has inner shoulder x=74 and 698 (20 polygon vertices).
    # IMPORTANT: unfolded topology's material side return=71 differs from:
    # 2nd BEND station=73 and CUTTING shoulder=74. The latter is 1 mm
    # beyond the BEND station for this certified T2 geometry. Do not
    # project 71 to all three geometrically different reference points.
    cutting_shoulder=second_bend_station+t/2.0
    if (blank_h <= 2*(shoulder+corner_chamfer)
            or cutting_shoulder+corner_chamfer>=blank_w/2.0
            or core_w<=0):
        raise ValueError("Receiving center base shoulders consume the physical core")
    x0,x1=cutting_shoulder,blank_w-cutting_shoulder
    y0,y1=shoulder,blank_h-shoulder
    c=corner_chamfer
    outline=(
        Vec2(x0+c,blank_h),Vec2(x1-c,blank_h),
        Vec2(x1,blank_h-c),Vec2(x1,y1),
        Vec2(blank_w-c,y1),Vec2(blank_w,y1-c),
        Vec2(blank_w,y0+c),Vec2(blank_w-c,y0),
        Vec2(x1,y0),Vec2(x1,c),
        Vec2(x1-c,0.),Vec2(x0+c,0.),
        Vec2(x0,c),Vec2(x0,y0),
        Vec2(c,y0),Vec2(0.,y0+c),
        Vec2(0.,y1-c),Vec2(c,y1),
        Vec2(x0,y1),Vec2(x0,blank_h-c),
    )
    bends=(
        # Stable legacy BEND identifiers end in _20; CENTER coordinates do
        # NOT mean 20 mm. Real Y BEND stations come from center_y_fold.
        BendLine("receiving_bottom_20",Vec2(x0,center_y_fold),Vec2(x1,center_y_fold)),
        BendLine("receiving_top_20",
                 Vec2(x0,blank_h-center_y_fold),Vec2(x1,blank_h-center_y_fold)),
        BendLine("receiving_left_40",Vec2(first,y0),Vec2(first,y1)),
        BendLine("receiving_left_33",Vec2(second_bend_station,y0),Vec2(second_bend_station,y1)),
        BendLine("receiving_right_40",
                 Vec2(blank_w-first,y0),Vec2(blank_w-first,y1)),
        BendLine("receiving_right_33",
                 Vec2(blank_w-second_bend_station,y0),Vec2(blank_w-second_bend_station,y1)),
    )
    # Keep topology/fingerprint sensitive to an actual source-selected
    # NFB depth pair. Reusing the old fixed-33 topology key for a changed
    # 2nd return could incorrectly retain cached manufacturing geometry.
    identity = ("RECEIVING_BASE", pattern, core_w, blank_h, bend, t)
    if nfb_depth_pair_mm is not None:
        identity += ("NFB_DEPTH_RETURN", _finite_float(second))
    return _result(outline,bends,blank_w,blank_h,identity)
