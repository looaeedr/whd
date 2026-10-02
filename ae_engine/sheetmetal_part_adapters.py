"""Pure adapters from WHD legacy/UI parameters to structural geometry results.

This module contains no Tkinter or ezdxf dependencies.  It is the shared
translation layer used by both GUI preview and DXF serialization.
"""
from __future__ import annotations

from dataclasses import dataclass

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


def complete_partition(fixed_values, total, *, tolerance=1e-9) -> PartitionCompletion:
    """Append one positive remainder to fixed values when space remains.

    ``fixed_values`` contains only user-owned values.  The returned auto cell is
    deliberately not folded back into that list, so editing it can promote it to
    a fixed value before this helper is called again.
    """
    total = float(total)
    tolerance = float(tolerance)
    if total <= 0:
        raise ValueError("partition total must be > 0")
    fixed = tuple(float(value) for value in fixed_values)
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
        width = float(width)
        heights = tuple(float(value) for value in heights)
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
    normalized = []
    for width, heights in columns:
        normalized.append((float(width), tuple(float(v) for v in heights)))
    cells = derive_door_layout_cells(normalized)
    width_sum = sum(width for width, _ in normalized)
    if abs(width_sum - float(total_width)) > float(tolerance):
        raise ValueError(f"door layout column widths sum to {width_sum:g}, expected W={float(total_width):g}")
    for index, (_width, heights) in enumerate(normalized, start=1):
        height_sum = sum(heights)
        if abs(height_sum - float(total_height)) > float(tolerance):
            raise ValueError(
                f"door layout column {index} heights sum to {height_sum:g}, expected H={float(total_height):g}"
            )
    return cells


def calculate_door_finished_size(*, w, h, t, fw, gap_w, gap_h, frame_edges: DoorFrameEdges | None = None):
    """Convert one Door cell start size to finished Door W/H.

    A present enclosure-frame edge consumes one ``FW + 2T`` span.  Door gap is
    still applied on both sides of each axis.
    """
    edges = frame_edges or DoorFrameEdges()
    w = float(w)
    h = float(h)
    t = float(t)
    fw = float(fw)
    gap_w = float(gap_w)
    gap_h = float(gap_h)
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
    return StructuralGeometryResult(tuple(outline), tuple(bends), float(width), float(height), topology)



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
        if isinstance(row, dict):
            return row.get(name, default)
        return getattr(row, name, default)

    d_indexes = [i for i, row in enumerate(rows) if value(row, "core") == "D"]
    w_indexes = [i for i, row in enumerate(rows) if value(row, "core") == "W"]
    if len(d_indexes) != 2 or len(w_indexes) != 1 or not (d_indexes[0] < w_indexes[0] < d_indexes[1]):
        raise ValueError("box body fold profile must contain ordered D-W-D core")

    left_d, right_d = d_indexes
    w_index = w_indexes[0]
    segments = []
    for index, row in enumerate(rows):
        length = float(value(row, "length", value(row, "len", 0.0)))
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
        ("zl1", abs(float(zl1))),
        ("zl2", float(zl2)),
        ("fw_left", float(fw)),
        ("depth_left", float(d) - 2.0 * float(t)),
        ("front", float(w) - 2.0 * float(t)),
        ("depth_right", float(d) - 2.0 * float(t)),
    ]
    if include_right_fw:
        lengths.append(("fw_right", float(fw)))
    lengths.extend([("zr2", float(zr2)), ("zr1", abs(float(zr1)))])
    comp = float(z_comp) / len(lengths)
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
    t = float(t)
    finished_w, finished_h = calculate_door_finished_size(
        w=w, h=h, t=t, fw=fw, gap_w=gap_w, gap_h=gap_h, frame_edges=frame_edges,
    )
    blank_w = finished_w - 2.0 * t + float(fold_left) + float(fold_right)
    blank_h = finished_h - 2.0 * t + float(fold_top) + float(fold_bottom)
    geometry = FourSideFlangeGeometry(
        total_width=blank_w,
        total_height=blank_h,
        thickness=t,
        left_fold=float(fold_left),
        right_fold=float(fold_right),
        top_fold=float(fold_top),
        bottom_fold=float(fold_bottom),
    )
    from .certified_relief_registry import certified_corner_policy_for_part
    policy = certified_corner_policy_for_part("金庫型", "door", fw=float(fw))
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
    t = float(t)
    finished_w, finished_h = calculate_door_finished_size(
        w=w, h=h, t=t, fw=fw, gap_w=gap_w, gap_h=gap_h, frame_edges=frame_edges,
    )
    blank_w = finished_w - 2.0 * t + float(fold_left) + float(fold_right)
    blank_h = finished_h - 2.0 * t + float(fold_top) + float(fold_bottom)
    geometry = FourSideFlangeGeometry(
        total_width=blank_w, total_height=blank_h, thickness=t,
        left_fold=float(fold_left), right_fold=float(fold_right),
        top_fold=float(fold_top), bottom_fold=float(fold_bottom),
    )
    return _result(
        build_four_side_outline(geometry, corner_policy),
        build_four_side_bend_segments(geometry, corner_policy),
        blank_w, blank_h, geometry,
    )


def build_base_plate_result(*, w, h, t, shrink_top, shrink_bottom, shrink_left, shrink_right, bend):
    total_width = float(w) - float(shrink_left) - float(shrink_right) + 2.0 * float(bend)
    total_height = float(h) - float(shrink_top) - float(shrink_bottom) + 2.0 * float(bend)
    geometry = FourSideFlangeGeometry(
        total_width=total_width,
        total_height=total_height,
        thickness=float(t),
        left_fold=float(bend),
        right_fold=float(bend),
        top_fold=float(bend),
        bottom_fold=float(bend),
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
    total_width = float(w) - float(shrink_left) - float(shrink_right) + 2.0 * float(bend)
    total_height = float(h) - float(shrink_top) - float(shrink_bottom) + 2.0 * float(bend)
    geometry = FourSideFlangeGeometry(
        total_width=total_width, total_height=total_height, thickness=float(t),
        left_fold=float(bend), right_fold=float(bend), top_fold=float(bend), bottom_fold=float(bend),
    )
    return _result(
        build_four_side_outline(geometry, corner_policy),
        build_four_side_bend_segments(geometry, corner_policy),
        total_width, total_height, geometry,
    )


def build_indicator_box_result(*, total_width, total_height, t, fold=49.0):
    fold = float(fold)
    t = float(t)
    geometry = FourSideFlangeGeometry(
        total_width=float(total_width),
        total_height=float(total_height),
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
        float(total_width),
        float(total_height),
        geometry,
    )


def build_unknown_indicator_box_result(
    *, total_width, total_height, t, fold=49.0, corner_policy: FourCornerTypePolicy,
):
    fold = float(fold)
    geometry = FourSideFlangeGeometry(
        total_width=float(total_width), total_height=float(total_height), thickness=float(t),
        left_fold=fold, right_fold=fold, top_fold=fold, bottom_fold=fold,
    )
    extent = FourSideBendExtentPolicy(horizontal_to_blank_edges=True)
    return _result(
        build_four_side_outline(geometry, corner_policy),
        build_four_side_bend_segments(geometry, corner_policy, extent),
        float(total_width), float(total_height), geometry,
    )


def build_endcap_result(
    *, w, d, t, fw, yl1, yr1, ytop1, ybottom1,
    relief_config: ReliefConfig, x_topology="folded", depth_comp_t=3.0,
):
    t = float(t)
    if x_topology not in {"folded", "flat"}:
        raise ValueError(f"unsupported EndCap x_topology: {x_topology}")
    total_width = (
        float(w)
        if x_topology == "flat"
        else float(w) - 4.0 * t + abs(float(yl1)) + abs(float(yr1))
    )
    total_depth = float(d) - float(depth_comp_t) * t + float(ytop1) + float(fw) + float(ybottom1)
    geometry = EndCapGeometry(
        total_width=total_width,
        total_depth=total_depth,
        thickness=t,
        fw=float(fw),
        left_fold=float(yl1),
        right_fold=float(yr1),
        top_first_fold=float(ytop1),
        bottom_fold=float(ybottom1),
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
    t = float(t)
    if x_topology not in {"folded", "flat"}:
        raise ValueError(f"unsupported EndCap x_topology: {x_topology}")
    flat_x = x_topology == "flat"
    nominal_left = float(yl1 if nominal_yl1 is None else nominal_yl1)
    nominal_right = float(yr1 if nominal_yr1 is None else nominal_yr1)
    left_fold = 0.0 if flat_x else float(yl1)
    right_fold = 0.0 if flat_x else float(yr1)
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
        float(w)
        if flat_x
        else float(w) - 4.0 * t + abs(left_fold) + abs(right_fold)
    )
    total_depth = float(d) - float(depth_comp_t) * t + float(ytop1) + float(fw) + float(ybottom1)
    geometry = EndCapGeometry(
        total_width=total_width, total_depth=total_depth, thickness=t, fw=float(fw),
        left_fold=left_fold, right_fold=right_fold,
        top_first_fold=float(ytop1), bottom_fold=float(ybottom1),
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
    fw = float(finished_width)
    fh = float(finished_height)
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
