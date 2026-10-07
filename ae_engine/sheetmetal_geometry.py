# -*- coding: utf-8 -*-
"""Pure 2D sheet-metal geometry primitives and relief generation.

This module deliberately has no ezdxf dependency.  DXF exporters consume the
closed exterior point list produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Iterable, Literal

try:
    from shapely.geometry import Polygon, box, LineString, Point
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
except Exception:  # pragma: no cover - exercised only on minimal deployments
    Polygon = None
    box = None
    LineString = None
    Point = None
    orient = None
    unary_union = None


from .sheetmetal_geometry_core import (
    DEFAULT_TOLERANCE,
    GeometryError,
    Vec2,
    BendLine,
    Flange,
    Corner,
    ReliefPolygon,
    ReliefConfig,
    CornerTypeResidual,
    CornerTypeId,
    CrossCornerMode,
    CornerDirection,
    EDITABLE_CORNER_TYPE_IDS,
    CORNER_TYPE_LABELS,
    CornerTypeSelection,
    ResolvedCornerRelief,
)

from .sheetmetal_corner_policy import (
    normalize_corner_selection,
    _directional_delta,
    corner_selection_residual,
    corner_type_residual,
    compose_corner_residual,
    resolve_corner_relief,
    FourCornerTypePolicy,
    EndCapAssemblySemantics,
    resolve_endcap_assembly_semantics,
    resolve_endcap_policy_assembly_semantics,
    VAULT_C01,
    VAULT_C02,
    VAULT_C03,
    VAULT_C04,
    VAULT_ENDCAP_CORNER_POLICY,
    corner_outer_thickness_factor,
    endcap_outer_thickness_factor,
    box_body_vertical_offsets,
    box_body_height_from_corner_policies,
)

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
class RectCornerReliefPolicy:
    bottom_left_x: float
    bottom_right_x: float
    top_left_x: float
    top_right_x: float
    bottom_y: float
    top_y: float

@dataclass(frozen=True)
class FourSideBendExtentPolicy:
    horizontal_to_blank_edges: bool = False


def _validate_four_side_geometry(g: FourSideFlangeGeometry) -> None:
    if g.total_width <= 0 or g.total_height <= 0:
        raise GeometryError("blank dimensions must be greater than zero")
    if g.thickness <= 0:
        raise GeometryError("板厚必須大於 0")
    if any(v < 0 for v in (g.left_fold, g.right_fold, g.top_fold, g.bottom_fold)):
        raise GeometryError("fold dimensions must not be negative")


def _validate_four_side(g: FourSideFlangeGeometry, policy: RectCornerReliefPolicy) -> None:
    _validate_four_side_geometry(g)
    values = (
        policy.bottom_left_x, policy.bottom_right_x,
        policy.top_left_x, policy.top_right_x,
        policy.bottom_y, policy.top_y,
    )
    if any(v < 0 for v in values):
        raise GeometryError("relief dimensions must not be negative")
    if policy.bottom_left_x + policy.bottom_right_x >= g.total_width:
        raise GeometryError("bottom corner reliefs consume blank width")
    if policy.top_left_x + policy.top_right_x >= g.total_width:
        raise GeometryError("top corner reliefs consume blank width")
    if policy.bottom_y + policy.top_y >= g.total_height:
        raise GeometryError("corner reliefs consume blank height")


def _local_cross_slot_polygon(relief: ResolvedCornerRelief):
    """Build an optional rounded-end slot in canonical +U/+V corner coordinates."""
    if relief.slot_width is None:
        return None
    if relief.slot_straight_depth is None or relief.slot_radius is None:
        raise GeometryError("十字截角槽參數不完整")
    width = float(relief.slot_width)
    straight = float(relief.slot_straight_depth)
    radius = float(relief.slot_radius)
    u0 = float(relief.primary_u) - width
    u1 = float(relief.primary_u)
    tangent_v = float(relief.primary_v) + straight
    if u0 < -DEFAULT_TOLERANCE:
        raise GeometryError("十字截角槽超出主截角U範圍")
    rectangle = box(max(0.0, u0), float(relief.primary_v), u1, tangent_v)
    axis_left = u0 + radius
    axis_right = u1 - radius
    if axis_right < axis_left - DEFAULT_TOLERANCE:
        raise GeometryError("十字截角槽R與槽寬不相容")
    if abs(axis_right - axis_left) <= DEFAULT_TOLERANCE:
        cap = Point(((axis_left + axis_right) / 2.0, tangent_v)).buffer(radius)
    else:
        cap = LineString(((axis_left, tangent_v), (axis_right, tangent_v))).buffer(
            radius, cap_style=1, join_style=1
        )
    cap = cap.intersection(box(u0, tangent_v, u1, tangent_v + radius + DEFAULT_TOLERANCE))
    return unary_union((rectangle, cap))


def _mirror_local_corner_polygon(poly, *, corner_name: str, width: float, height: float):
    from shapely.affinity import scale, translate
    if corner_name == "bottom_left":
        return poly
    if corner_name == "bottom_right":
        return translate(scale(poly, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0)), xoff=float(width))
    if corner_name == "top_left":
        return translate(scale(poly, xfact=1.0, yfact=-1.0, origin=(0.0, 0.0)), yoff=float(height))
    if corner_name == "top_right":
        mirrored = scale(poly, xfact=-1.0, yfact=-1.0, origin=(0.0, 0.0))
        return translate(mirrored, xoff=float(width), yoff=float(height))
    raise GeometryError(f"unknown physical corner: {corner_name}")


def _placed_corner_cut_polygons(
    *,
    corner_name: str,
    relief: ResolvedCornerRelief,
    width: float,
    height: float,
):
    """Place a canonical inward +U/+V corner cut at one physical blank corner."""
    pu, pv = relief.primary_u, relief.primary_v
    if corner_name == "bottom_left":
        primary = box(0.0, 0.0, pu, pv)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(0.0, pv, relief.secondary_u, pv + relief.secondary_depth)
        )
    elif corner_name == "bottom_right":
        primary = box(width - pu, 0.0, width, pv)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(width - relief.secondary_u, pv, width, pv + relief.secondary_depth)
        )
    elif corner_name == "top_left":
        primary = box(0.0, height - pv, pu, height)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(0.0, height - pv - relief.secondary_depth, relief.secondary_u, height - pv)
        )
    elif corner_name == "top_right":
        primary = box(width - pu, height - pv, width, height)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(
                width - relief.secondary_u,
                height - pv - relief.secondary_depth,
                width,
                height - pv,
            )
        )
    else:
        raise GeometryError(f"unknown physical corner: {corner_name}")
    slot_local = _local_cross_slot_polygon(relief)
    slot = (
        None if slot_local is None
        else _mirror_local_corner_polygon(
            slot_local, corner_name=corner_name, width=width, height=height
        )
    )
    return [
        poly for poly in (primary, secondary, slot)
        if poly is not None and not poly.is_empty
    ]


def placed_corner_cut_polygons(
    *,
    corner_name: str,
    relief: ResolvedCornerRelief,
    width: float,
    height: float,
):
    """Public geometry seam for placing one already-resolved CornerType cut."""
    return _placed_corner_cut_polygons(
        corner_name=corner_name, relief=relief, width=width, height=height
    )


def _four_side_type_cut_polygons(g: FourSideFlangeGeometry, policy: FourCornerTypePolicy):
    _validate_four_side_geometry(g)
    specs = {
        "bottom_left": (policy.bottom_left, g.left_fold, g.bottom_fold),
        "bottom_right": (policy.bottom_right, g.right_fold, g.bottom_fold),
        "top_left": (policy.top_left, g.left_fold, g.top_fold),
        "top_right": (policy.top_right, g.right_fold, g.top_fold),
    }
    cuts = []
    for name, (selection, fold_u, fold_v) in specs.items():
        relief = resolve_corner_relief(
            selection, fold_u=fold_u, fold_v=fold_v, thickness=g.thickness,
            fw=policy.fw_for(name),
        )
        if relief.primary_u > g.total_width or relief.primary_v > g.total_height:
            raise GeometryError("corner relief exceeds blank dimensions")
        if relief.secondary_u is not None and relief.secondary_u > g.total_width:
            raise GeometryError("secondary corner relief exceeds blank dimensions")
        if relief.secondary_depth is not None and relief.primary_v + relief.secondary_depth > g.total_height:
            raise GeometryError("secondary corner relief exceeds blank dimensions")
        cuts.extend(_placed_corner_cut_polygons(
            corner_name=name, relief=relief, width=g.total_width, height=g.total_height
        ))
    return cuts


def _four_side_material_polygon(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
):
    _require_shapely()
    w, h = g.total_width, g.total_height
    blank = box(0.0, 0.0, w, h)
    if isinstance(policy, RectCornerReliefPolicy):
        _validate_four_side(g, policy)
        cuts = [
            box(0.0, 0.0, policy.bottom_left_x, policy.bottom_y),
            box(w - policy.bottom_right_x, 0.0, w, policy.bottom_y),
            box(0.0, h - policy.top_y, policy.top_left_x, h),
            box(w - policy.top_right_x, h - policy.top_y, w, h),
        ]
    elif isinstance(policy, FourCornerTypePolicy):
        cuts = _four_side_type_cut_polygons(g, policy)
    else:
        raise TypeError(f"unsupported corner policy: {type(policy).__name__}")
    cut_union = unary_union(cuts) if cuts else None
    result = blank if cut_union is None else blank.difference(cut_union)
    if result.geom_type != "Polygon" or result.is_empty or not result.is_valid:
        raise GeometryError("invalid four-side flange outline")
    return orient(result, sign=1.0)


def build_four_side_outline(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
) -> list[Vec2]:
    result = _four_side_material_polygon(g, policy)
    return _normalize_ring(result.exterior.coords)


def _clip_axis_bend(name: str, line: LineString, material, vertical: bool) -> BendLine:
    clipped = material.intersection(line)
    if clipped.is_empty:
        raise GeometryError(f"bend {name} does not intersect material")
    if clipped.geom_type == "MultiLineString":
        clipped = max(clipped.geoms, key=lambda geom: geom.length)
    if clipped.geom_type != "LineString":
        raise GeometryError(f"bend {name} did not clip to a line")
    coords = list(clipped.coords)
    a = Vec2(float(coords[0][0]), float(coords[0][1]))
    b = Vec2(float(coords[-1][0]), float(coords[-1][1]))
    if vertical:
        if a.y > b.y:
            a, b = b, a
    elif a.x > b.x:
        a, b = b, a
    return BendLine(name, a, b)


def build_four_side_bend_segments(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
    extent: FourSideBendExtentPolicy = FourSideBendExtentPolicy(),
) -> list[BendLine]:
    _require_shapely()
    material = _four_side_material_polygon(g, policy)
    w, h = g.total_width, g.total_height
    vertical = [
        _clip_axis_bend("left", LineString([(g.left_fold, 0.0), (g.left_fold, h)]), material, True),
        _clip_axis_bend("right", LineString([(w - g.right_fold, 0.0), (w - g.right_fold, h)]), material, True),
    ]
    if extent.horizontal_to_blank_edges:
        horizontal = [
            BendLine("bottom", Vec2(0.0, g.bottom_fold), Vec2(w, g.bottom_fold)),
            BendLine("top", Vec2(0.0, h - g.top_fold), Vec2(w, h - g.top_fold)),
        ]
    else:
        horizontal = [
            _clip_axis_bend("bottom", LineString([(0.0, g.bottom_fold), (w, g.bottom_fold)]), material, False),
            _clip_axis_bend("top", LineString([(0.0, h - g.top_fold), (w, h - g.top_fold)]), material, False),
        ]
    return vertical + horizontal


@dataclass(frozen=True)
class EndCapGeometry:
    total_width: float
    total_depth: float
    thickness: float
    fw: float
    left_fold: float
    right_fold: float
    top_first_fold: float
    bottom_fold: float


@dataclass(frozen=True)
class EndCapReliefDimensions:
    top_primary_left: float
    top_primary_right: float
    top_primary_height: float
    top_secondary_left: float
    top_secondary_right: float
    top_secondary_depth_left: float
    top_secondary_depth_right: float
    bottom_left: float
    bottom_right: float
    bottom_height: float


@dataclass(frozen=True)
class EndCapTopology:
    left_bend: BendLine
    right_bend: BendLine
    bottom_bend: BendLine
    top_chain_bend_1: BendLine
    top_chain_bend_2: BendLine
    bottom_left: Corner
    bottom_right: Corner
    top_chain_left_1: Corner
    top_chain_right_1: Corner
    top_chain_left_2: Corner
    top_chain_right_2: Corner


def _cross(a: Vec2, b: Vec2) -> float:
    return a.x * b.y - a.y * b.x


def _normalized(v: Vec2, tol: float = DEFAULT_TOLERANCE) -> Vec2:
    length = v.length()
    if length <= tol:
        raise GeometryError("zero-length direction vector")
    return Vec2(v.x / length, v.y / length)


def line_intersection(
    a: BendLine,
    b: BendLine,
    tol: float = DEFAULT_TOLERANCE,
) -> Vec2:
    """Return the intersection of the two infinite bend lines."""
    p = a.p1
    r = a.p2 - a.p1
    q = b.p1
    s = b.p2 - b.p1
    denominator = _cross(r, s)
    if abs(denominator) <= tol:
        raise GeometryError("bend lines are parallel or degenerate")
    t = _cross(q - p, s) / denominator
    return Vec2(p.x + t * r.x, p.y + t * r.y)


def _validate_endcap(g: EndCapGeometry) -> None:
    if g.thickness <= 0:
        raise GeometryError("板厚必須大於 0")
    if g.total_width <= 0 or g.total_depth <= 0:
        raise GeometryError("blank dimensions must be greater than zero")
    if g.fw < 0:
        raise GeometryError("FW must not be negative")


def _factor_or_override(
    override: float | None,
    factor: float,
    thickness: float,
    name: str,
) -> float:
    value = override if override is not None else factor * thickness
    if value < 0:
        raise GeometryError(f"{name} must not be negative")
    return float(value)


def calculate_endcap_relief_dimensions(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> EndCapReliefDimensions:
    """Resolve the fixed Vault EndCap mapping through CornerType composition.

    Vault is intentionally not user-selectable: bottom corners are C03 and top
    corners are C04.  ReliefConfig remains a narrow Factory Policy override for
    the C03/C04 residual clearances; fold dimensions stay outside the type rule.
    """
    _validate_endcap(g)
    left = abs(g.left_fold)
    right = abs(g.right_fold)
    top = abs(g.top_first_fold)
    bottom = abs(g.bottom_fold)

    left_secondary_extra = _factor_or_override(
        cfg.top_secondary_x_left,
        cfg.top_secondary_x_factor,
        g.thickness,
        "top_secondary_x_left",
    )
    right_secondary_extra = _factor_or_override(
        cfg.top_secondary_x_right,
        cfg.top_secondary_x_factor,
        g.thickness,
        "top_secondary_x_right",
    )
    left_secondary_depth = _factor_or_override(
        cfg.top_secondary_depth_left,
        cfg.top_secondary_depth_factor,
        g.thickness,
        "top_secondary_depth_left",
    )
    right_secondary_depth = _factor_or_override(
        cfg.top_secondary_depth_right,
        cfg.top_secondary_depth_factor,
        g.thickness,
        "top_secondary_depth_right",
    )
    left_bottom_extra = _factor_or_override(
        cfg.bottom_x_left,
        cfg.bottom_x_factor,
        g.thickness,
        "bottom_x_left",
    )
    right_bottom_extra = _factor_or_override(
        cfg.bottom_x_right,
        cfg.bottom_x_factor,
        g.thickness,
        "bottom_x_right",
    )
    bottom_y_extra = _factor_or_override(
        cfg.bottom_y,
        cfg.bottom_y_factor,
        g.thickness,
        "bottom_y",
    )

    # 舊 C04 現在會轉成「嵌入貼外型」。UI 仍以「嵌入留肉」表達，
    # 但實際二級 CUTTING 必須維持原本 C04 幾何：側折 + xT，深度 2T。
    # FW - xT 是兩級切線之間剩下的材料寬度，不是第二級 CUTTING 座標。
    c04 = corner_selection_residual(VAULT_C04, thickness=g.thickness, fw=g.fw)
    top_left = compose_corner_residual(
        CornerTypeResidual(
            c04.primary,
            left_secondary_extra,
            left_secondary_depth,
        ),
        fold_u=left, fold_v=top,
    )
    top_right = compose_corner_residual(
        CornerTypeResidual(
            c04.primary,
            right_secondary_extra,
            right_secondary_depth,
        ),
        fold_u=right, fold_v=top,
    )

    # C03 intrinsic rule is (+0.5T, +0.5T). ReliefConfig can override those
    # residual clearances while the actual fold sizes remain topology data.
    bottom_left = compose_corner_residual(
        CornerTypeResidual((left_bottom_extra, bottom_y_extra)),
        fold_u=left, fold_v=bottom,
    )
    bottom_right = compose_corner_residual(
        CornerTypeResidual((right_bottom_extra, bottom_y_extra)),
        fold_u=right, fold_v=bottom,
    )

    dims = EndCapReliefDimensions(
        top_primary_left=top_left.primary_u,
        top_primary_right=top_right.primary_u,
        top_primary_height=top_left.primary_v,
        top_secondary_left=top_left.secondary_u or 0.0,
        top_secondary_right=top_right.secondary_u or 0.0,
        top_secondary_depth_left=top_left.secondary_depth or 0.0,
        top_secondary_depth_right=top_right.secondary_depth or 0.0,
        bottom_left=bottom_left.primary_u,
        bottom_right=bottom_right.primary_u,
        bottom_height=bottom_left.primary_v,
    )
    for name, value in dims.__dict__.items():
        if value < 0:
            raise GeometryError(f"relief dimension {name} must not be negative")
    if dims.top_primary_height <= 0:
        raise GeometryError("top primary relief height must be greater than zero")
    return dims


def _corner(name: str, a: BendLine, b: BendLine) -> Corner:
    point = line_intersection(a, b)
    u = _normalized(a.p2 - a.p1)
    v = _normalized(b.p2 - b.p1)
    return Corner(name=name, point=point, u=u, v=v, bends=(a, b))


def build_endcap_topology(g: EndCapGeometry) -> EndCapTopology:
    """Build fold/bend topology without assigning a panel-type-specific outline."""
    _validate_endcap(g)
    left_x = abs(g.left_fold)
    right_x = g.total_width - abs(g.right_fold)
    bottom_y = abs(g.bottom_fold)

    # Existing flat-pattern chain:
    # total_depth = bottom + body_depth_minus_3T + FW + top_first_fold
    top_chain_y1 = g.total_depth - abs(g.top_first_fold) - g.fw
    top_chain_y2 = g.total_depth - abs(g.top_first_fold)

    left_bend = BendLine("left", Vec2(left_x, 0.0), Vec2(left_x, g.total_depth))
    right_bend = BendLine("right", Vec2(right_x, 0.0), Vec2(right_x, g.total_depth))
    bottom_bend = BendLine("bottom", Vec2(0.0, bottom_y), Vec2(g.total_width, bottom_y))
    top_1 = BendLine("top_chain_1", Vec2(0.0, top_chain_y1), Vec2(g.total_width, top_chain_y1))
    top_2 = BendLine("top_chain_2", Vec2(0.0, top_chain_y2), Vec2(g.total_width, top_chain_y2))

    return EndCapTopology(
        left_bend=left_bend,
        right_bend=right_bend,
        bottom_bend=bottom_bend,
        top_chain_bend_1=top_1,
        top_chain_bend_2=top_2,
        bottom_left=_corner("bottom_left", left_bend, bottom_bend),
        bottom_right=_corner("bottom_right", right_bend, bottom_bend),
        top_chain_left_1=_corner("top_chain_left_1", left_bend, top_1),
        top_chain_right_1=_corner("top_chain_right_1", right_bend, top_1),
        top_chain_left_2=_corner("top_chain_left_2", left_bend, top_2),
        top_chain_right_2=_corner("top_chain_right_2", right_bend, top_2),
    )



def _endcap_manual_material_polygon(
    g: EndCapGeometry,
    policy: FourCornerTypePolicy,
    *,
    relief_left_fold: float | None = None,
    relief_right_fold: float | None = None,
    bottom_relief_left_fold: float | None = None,
    bottom_relief_right_fold: float | None = None,
):
    """Material polygon for manual/unknown EndCap using CornerType selections."""
    _require_shapely()
    _validate_endcap(g)
    left_basis = abs(g.left_fold if relief_left_fold is None else float(relief_left_fold))
    right_basis = abs(g.right_fold if relief_right_fold is None else float(relief_right_fold))
    bottom_left_basis = abs(
        left_basis if bottom_relief_left_fold is None else float(bottom_relief_left_fold)
    )
    bottom_right_basis = abs(
        right_basis if bottom_relief_right_fold is None else float(bottom_relief_right_fold)
    )
    specs = {
        "bottom_left": (policy.bottom_left, bottom_left_basis, abs(g.bottom_fold)),
        "bottom_right": (policy.bottom_right, bottom_right_basis, abs(g.bottom_fold)),
        "top_left": (policy.top_left, left_basis, abs(g.top_first_fold)),
        "top_right": (policy.top_right, right_basis, abs(g.top_first_fold)),
    }
    cuts = []
    for name, (selection, fold_u, fold_v) in specs.items():
        relief = resolve_corner_relief(
            selection,
            fold_u=fold_u,
            fold_v=fold_v,
            thickness=g.thickness,
            fw=policy.fw_for(name),
        )
        cuts.extend(_placed_corner_cut_polygons(
            corner_name=name,
            relief=relief,
            width=g.total_width,
            height=g.total_depth,
        ))
    blank = box(0.0, 0.0, g.total_width, g.total_depth)
    result = blank.difference(unary_union(cuts)) if cuts else blank
    if result.is_empty or result.geom_type != "Polygon" or not result.is_valid:
        raise GeometryError("invalid manual EndCap corner reliefs")
    return orient(result, sign=1.0)


def build_endcap_outline_from_corner_types(
    g: EndCapGeometry,
    policy: FourCornerTypePolicy,
    *,
    relief_left_fold: float | None = None,
    relief_right_fold: float | None = None,
    bottom_relief_left_fold: float | None = None,
    bottom_relief_right_fold: float | None = None,
) -> list[Vec2]:
    """Build unknown/manual EndCap CUTTING from fold geometry + CornerType only."""
    material = _endcap_manual_material_polygon(
        g, policy,
        relief_left_fold=relief_left_fold,
        relief_right_fold=relief_right_fold,
        bottom_relief_left_fold=bottom_relief_left_fold,
        bottom_relief_right_fold=bottom_relief_right_fold,
    )
    return _normalize_ring(material.exterior.coords)


def build_endcap_bend_segments_from_corner_types(
    g: EndCapGeometry,
    policy: FourCornerTypePolicy,
    *,
    relief_left_fold: float | None = None,
    relief_right_fold: float | None = None,
    bottom_relief_left_fold: float | None = None,
    bottom_relief_right_fold: float | None = None,
) -> list[BendLine]:
    """Clip EndCap bends against CornerType material using an optional nominal relief basis."""
    material = _endcap_manual_material_polygon(
        g, policy,
        relief_left_fold=relief_left_fold,
        relief_right_fold=relief_right_fold,
        bottom_relief_left_fold=bottom_relief_left_fold,
        bottom_relief_right_fold=bottom_relief_right_fold,
    )
    topo = build_endcap_topology(g)
    return [
        _clip_axis_bend(
            "left",
            LineString([(topo.left_bend.p1.x, 0.0), (topo.left_bend.p1.x, g.total_depth)]),
            material,
            True,
        ),
        _clip_axis_bend(
            "right",
            LineString([(topo.right_bend.p1.x, 0.0), (topo.right_bend.p1.x, g.total_depth)]),
            material,
            True,
        ),
        _clip_axis_bend(
            "bottom",
            LineString([(0.0, topo.bottom_bend.p1.y), (g.total_width, topo.bottom_bend.p1.y)]),
            material,
            False,
        ),
        _clip_axis_bend(
            "top_chain_1",
            LineString([(0.0, topo.top_chain_bend_1.p1.y), (g.total_width, topo.top_chain_bend_1.p1.y)]),
            material,
            False,
        ),
        _clip_axis_bend(
            "top_chain_2",
            LineString([(0.0, topo.top_chain_bend_2.p1.y), (g.total_width, topo.top_chain_bend_2.p1.y)]),
            material,
            False,
        ),
    ]


def build_endcap_bend_segments(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> list[BendLine]:
    """Return the five physical bend segments clipped to remaining material."""
    topo = build_endcap_topology(g)
    dims = calculate_endcap_relief_dimensions(g, cfg)

    left_x = topo.left_bend.p1.x
    right_x = topo.right_bend.p1.x
    bottom_y = topo.bottom_bend.p1.y
    top_1_y = topo.top_chain_bend_1.p1.y
    top_2_y = topo.top_chain_bend_2.p1.y

    top_primary_bottom = g.total_depth - dims.top_primary_height
    left_top = top_primary_bottom - dims.top_secondary_depth_left
    right_top = top_primary_bottom - dims.top_secondary_depth_right

    return [
        BendLine("left", Vec2(left_x, dims.bottom_height), Vec2(left_x, left_top)),
        BendLine("right", Vec2(right_x, dims.bottom_height), Vec2(right_x, right_top)),
        BendLine(
            "bottom",
            Vec2(dims.bottom_left, bottom_y),
            Vec2(g.total_width - dims.bottom_right, bottom_y),
        ),
        BendLine(
            "top_chain_1",
            Vec2(dims.top_secondary_left, top_1_y),
            Vec2(g.total_width - dims.top_secondary_right, top_1_y),
        ),
        BendLine(
            "top_chain_2",
            Vec2(dims.top_primary_left, top_2_y),
            Vec2(g.total_width - dims.top_primary_right, top_2_y),
        ),
    ]


def _validate_reliefs_fit_blank(
    g: EndCapGeometry,
    dims: EndCapReliefDimensions,
) -> None:
    if (
        dims.bottom_left > g.total_width
        or dims.bottom_right > g.total_width
        or dims.top_primary_left > g.total_width
        or dims.top_primary_right > g.total_width
        or dims.top_secondary_left > g.total_width
        or dims.top_secondary_right > g.total_width
        or dims.bottom_height > g.total_depth
        or dims.top_primary_height > g.total_depth
        or dims.top_primary_height + dims.top_secondary_depth_left > g.total_depth
        or dims.top_primary_height + dims.top_secondary_depth_right > g.total_depth
    ):
        raise GeometryError("relief exceeds blank dimensions")

    # Opposing reliefs must leave some material at each affected level.
    if (
        dims.bottom_left + dims.bottom_right >= g.total_width
        or dims.top_primary_left + dims.top_primary_right >= g.total_width
        or dims.top_secondary_left + dims.top_secondary_right >= g.total_width
    ):
        raise GeometryError("relief exceeds blank dimensions")


def _require_shapely() -> None:
    if Polygon is None or box is None or unary_union is None:
        raise GeometryError(
            "Shapely is required for boolean outline generation in this build"
        )


def build_endcap_reliefs(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> list[ReliefPolygon]:
    """Return material-removal polygons for the current assembly rule."""
    _require_shapely()
    dims = calculate_endcap_relief_dimensions(g, cfg)
    _validate_reliefs_fit_blank(g, dims)
    w, h = g.total_width, g.total_depth
    top_primary_y = h - dims.top_primary_height

    specs = [
        ("bottom_left", "assembly_bottom", box(0, 0, dims.bottom_left, dims.bottom_height)),
        (
            "bottom_right",
            "assembly_bottom",
            box(w - dims.bottom_right, 0, w, dims.bottom_height),
        ),
        (
            "top_primary_left",
            "flush_front_primary",
            box(0, top_primary_y, dims.top_primary_left, h),
        ),
        (
            "top_primary_right",
            "flush_front_primary",
            box(w - dims.top_primary_right, top_primary_y, w, h),
        ),
        (
            "top_secondary_left",
            "assembly_insertion_secondary",
            box(
                0,
                top_primary_y - dims.top_secondary_depth_left,
                dims.top_secondary_left,
                top_primary_y,
            ),
        ),
        (
            "top_secondary_right",
            "assembly_insertion_secondary",
            box(
                w - dims.top_secondary_right,
                top_primary_y - dims.top_secondary_depth_right,
                w,
                top_primary_y,
            ),
        ),
    ]
    return [
        ReliefPolygon(
            rule_name=rule,
            source_corner=name,
            polygon=poly,
            metadata={"area": float(poly.area)},
        )
        for name, rule, poly in specs
    ]


def _normalize_ring(points: Iterable[tuple[float, float]]) -> list[Vec2]:
    coords = [Vec2(float(x), float(y)) for x, y in points]
    if len(coords) < 4:
        raise GeometryError("outline exterior has too few points")
    if coords[0] == coords[-1]:
        coords = coords[:-1]

    # Deterministic start: left-most surviving point on the bottom edge.
    min_y = min(p.y for p in coords)
    bottom_indices = [
        i for i, p in enumerate(coords) if math.isclose(p.y, min_y, abs_tol=DEFAULT_TOLERANCE)
    ]
    start = min(bottom_indices, key=lambda i: coords[i].x)

    rotated = coords[start:] + coords[:start]
    rotated.append(rotated[0])
    return rotated


def build_endcap_outline(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> list[Vec2]:
    """Build the final CUTTING exterior by subtracting relief polygons."""
    _require_shapely()
    _validate_endcap(g)

    blank = box(0.0, 0.0, g.total_width, g.total_depth)
    reliefs = build_endcap_reliefs(g, cfg)
    cut_union = unary_union([r.polygon for r in reliefs])
    result = blank.difference(cut_union)

    if result.is_empty:
        raise GeometryError("relief removes the entire blank")
    if result.geom_type != "Polygon":
        raise GeometryError(
            f"expected one exterior polygon after relief, got {result.geom_type}"
        )
    if not result.is_valid:
        raise GeometryError("generated outline is invalid")
    if result.area <= DEFAULT_TOLERANCE:
        raise GeometryError("generated outline has no positive area")

    # Make orientation deterministic before rotating the start vertex.
    result = orient(result, sign=1.0)
    return _normalize_ring(result.exterior.coords)

from .sheetmetal_strip_geometry import (
    FoldSegment,
    StripFoldChain,
    _validate_strip_chain,
    build_strip_outline,
    build_strip_bend_segments,
)

