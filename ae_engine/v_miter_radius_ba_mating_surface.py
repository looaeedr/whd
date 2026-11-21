# -*- coding: utf-8 -*-
"""#3317 含 R／BA 的直折段共同接合面候選；不核准加工。

沿用既有試算的 BEND=圓弧起點模型。先解兩個圓弧末端直折段
中面的交線，再解有限板厚的平分接合面，反算每側料座標與厚度位置。
不以「無交叉」代替接合，不修剪來源，不替彎曲根部宣告體積零穿透。
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Polygon

from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_ideal_mating import (
    _UNIT_Z, _add, _cross, _dot, _outside_normal, _outward_bend_axis,
    _scale, _unit,
)
from .v_miter_radius_ba_interface_trial import _bend_measurement
from .v_miter_relief_trial import project_v_miter_relief_mating_trial
from .v_miter_true_t_collision import _flange_footprint

_EPS = 1e-8


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


@dataclass(frozen=True)
class VMiterMatingMaterialPoint:
    """料面位置與厚度位置須分開；厚度位置不是平面切割補償。"""
    flat: Vec2
    normal_offset_mm: float


@dataclass(frozen=True)
class VMiterRadiusBAMatingSurfaceTrial:
    """共同面為三維 CHECK；缺料只相對呼叫時明示的兩條 BEND 料域。"""
    interface_vertices: tuple
    interface_triangles: tuple
    interface_area_mm2: float
    interface_normal: tuple
    first_material_vertices: tuple[VMiterMatingMaterialPoint, ...]
    second_material_vertices: tuple[VMiterMatingMaterialPoint, ...]
    first_missing_source_area_mm2: float
    second_missing_source_area_mm2: float
    first_axial_extension_mm: float
    second_axial_extension_mm: float
    first_neutral_axis_k: float
    second_neutral_axis_k: float
    source_remaining_outline: tuple
    source_status: str
    geometry_model: str = "R_BA_STRAIGHT_LEG_BISECTOR_FACE_TRIAL"
    bend_datum: str = "EXISTING_TRIAL_BEND_IS_ARC_START"
    root_status: str = "CURVED_ROOT_UNSOLVED"
    solid_penetration_status: str = "WHOLE_SHEET_VOLUME_NOT_VERIFIED"
    manufacturing_status: str = "V_MITER_MATING_SURFACE_UNCERTIFIED"
    stock_domain_basis: str = "DECLARED_BEND_SPANS_ONLY"


def _clip(points, a, b, limit):
    """平面凸多邊形與 a*x+b*y<=limit 的真正交集。"""
    if not points:
        return []
    result = []
    for current, following in zip(points, points[1:] + points[:1]):
        dc = a * current[0] + b * current[1] - limit
        dn = a * following[0] + b * following[1] - limit
        if dc <= 0:
            result.append(current)
        if (dc < 0 < dn) or (dn < 0 < dc):
            ratio = dc / (dc - dn)
            result.append(tuple(current[i] + ratio * (following[i] - current[i])
                                for i in range(2)))
    return result


def solve_v_miter_radius_ba_mating_surface_trial(
    scene: DrawingScene, v_edge_bend: LinePrimitive, second_bend: LinePrimitive,
    *, thickness_mm: float, first_flange_height_mm: float,
    second_flange_height_mm: float, second_fold_angle_deg: float,
    relief_mode: VMiterReliefMode | str, relief_t_factor: float | None = None,
    first_inner_radius_mm: float, second_inner_radius_mm: float,
    first_bend_allowance_mm: float, second_bend_allowance_mm: float,
) -> VMiterRadiusBAMatingSurfaceTrial:
    """求解直折段共同面及兩側逆映射，不改原本安全修整求解器。

    面的兩側可被相反半空間分開，但本函式不輸出裁後實體，不能
    據此宣稱全板件無穿透。非零接合面也不能取代來源板料檢查。
    每側只用自 V 頂點沿該明示折線方向的 [0, 折線長度] 及指定折高，
    與試作 V 剩料取交集；不讀其他 BEND 的延伸段、未納入 Factory
    找回的折線或實際 Fold 附著。SOURCE_EXTENSION_REQUIRED 只表示
    此限定料域不足，不表示實體板件必須補料。
    """
    mating = project_v_miter_relief_mating_trial(
        scene, v_edge_bend, second_bend, thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode, relief_t_factor=relief_t_factor,
    )
    q = mating.relief.source_trial.ideal.source
    t = q.thickness_mm
    angles = (math.pi / 2, math.radians(q.second_fold_angle_deg))
    measures = (
        _bend_measurement(first_inner_radius_mm, first_bend_allowance_mm,
                          angles[0], t, "first"),
        _bend_measurement(second_inner_radius_mm, second_bend_allowance_mm,
                          angles[1], t, "second"),
    )
    heights = (q.first_flange_height_mm, q.second_flange_height_mm)
    if any(ba >= h - _EPS for (_, ba, _), h in zip(measures, heights)):
        raise GeometryError("V-miter 接合面沒有剩餘直折段")
    apex = q.bend_intersection
    origin = (apex.x, apex.y, 0.0)
    axes = (_outward_bend_axis(v_edge_bend, apex),
            _outward_bend_axis(second_bend, apex))
    outsides = (_outside_normal(*axes), _outside_normal(*reversed(axes)))
    frames = []
    for axis, outside, angle, (r, ba, k), height in zip(
        axes, outsides, angles, measures, heights
    ):
        # 與既有 _formed_curved_skin 的圓弧終點完全相同。
        mid_r = r + t / 2
        tangent = _add(_scale(outside, math.cos(angle)),
                       _scale(_UNIT_Z, math.sin(angle)))
        normal = _unit(_cross(axis, tangent), label="接合面板厚法向")
        arc_end = _add(_scale(outside, mid_r * math.sin(angle)),
                       _scale(_UNIT_Z, mid_r * (1 - math.cos(angle))))
        frames.append((axis, outside, tangent, normal, arc_end, ba, height))
    n1, n2 = frames[0][3], frames[1][3]
    cosine = _dot(n1, n2)
    denominator = 1 - cosine * cosine
    if denominator <= _EPS:
        raise GeometryError("V-miter 接合面兩中面近乎平行")
    c1, c2 = _dot(n1, frames[0][4]), _dot(n2, frames[1][4])
    point = _add(_scale(n1, (c1 - cosine * c2) / denominator),
                 _scale(n2, (c2 - cosine * c1) / denominator))
    seam = _unit(_cross(n1, n2), label="R/BA 中面交線")
    if seam[2] < 0:
        seam = _scale(seam, -1)
    # 選擇朝向兩側實際 BEND 軸的平分面，不依全域 XY 象限猜測。
    chosen = None
    for sign in (1, -1):
        candidate = _add(n1, _scale(n2, sign))
        if math.hypot(*candidate) <= _EPS:
            continue
        plane_normal = _unit(candidate, label="R/BA 平分面")
        across = _unit(_cross(seam, plane_normal), label="接合面橫向")
        if _dot(across, axes[0]) < 0:
            across = _scale(across, -1)
        if min(_dot(across, axis) for axis in axes) > _EPS:
            chosen = plane_normal, across
            break
    if chosen is None:
        raise GeometryError("V-miter 沒有兩側一致的接合面內向")
    plane_normal, across = chosen
    rates = [_dot(seam, frame[2]) for frame in frames]
    if min(rates) <= _EPS:
        raise GeometryError("V-miter 接合面沒有共同向上直折段")
    width = t / (2 * max(abs(_dot(across, n)) for n in (n1, n2)))
    reach = 4 * (sum(heights) + sum(m[0] for m in measures) +
                 t + math.hypot(*point)) / min(rates)
    if not all(math.isfinite(v) for v in (*point, width, reach)):
        raise GeometryError("V-miter 接合面尺度超過有限數值範圍")
    polygon = [(-width, -reach), (width, -reach),
               (width, reach), (-width, reach)]
    # 同時保留兩側完整直折高度限制，不把較高邊改成較短邊。
    for _, _, tangent, normal, arc_end, ba, height in frames:
        for direction, low, high in ((tangent, 0.0, height - ba),
                                     (normal, -t / 2, t / 2)):
            a, b = _dot(across, direction), _dot(seam, direction)
            offset = _dot(_sub(point, arc_end), direction)
            polygon = _clip(polygon, a, b, high - offset)
            polygon = _clip(polygon, -a, -b, offset - low)
    if len(polygon) < 3:
        raise GeometryError("V-miter 有限直折段沒有共同接合面")
    face = Polygon(polygon)
    if face.is_empty or not face.is_valid or face.area <= _EPS:
        raise GeometryError("V-miter 有限直折段沒有非零共同接合面")
    polygon = tuple(face.exterior.coords)[:-1]
    relative = tuple(_add(point, _add(_scale(across, x), _scale(seam, y)))
                     for x, y in polygon)
    world = tuple(_add(origin, p) for p in relative)
    source = Polygon([(p.x, p.y) for p in mating.relief.trial_remaining_outline])
    maps, missing, extensions = [], [], []
    for frame, bend in zip(frames, (v_edge_bend, second_bend)):
        axis, outside, tangent, normal, arc_end, ba, height = frame
        span = math.hypot(bend.p2.x - bend.p1.x, bend.p2.y - bend.p1.y)
        patch, _ = _flange_footprint(
            source, apex, axis, outside, source_span=span,
            source_flange_height=height,
        )
        mapped, axial_values = [], []
        for p in relative:
            delta = _sub(p, arc_end)
            axial = _dot(p, axis)
            material_u = ba + _dot(delta, tangent)
            depth = _dot(delta, normal)
            flat = Vec2(apex.x + axis[0] * axial + outside[0] * material_u,
                        apex.y + axis[1] * axial + outside[1] * material_u)
            mapped.append(VMiterMatingMaterialPoint(flat, depth))
            axial_values.append(axial)
        footprint = Polygon([(p.flat.x, p.flat.y) for p in mapped])
        if not footprint.is_valid or footprint.area <= _EPS:
            raise GeometryError("V-miter 接合面逆映射退化")
        maps.append(tuple(mapped))
        missing.append(float(footprint.difference(patch).area))
        extensions.append(max(0.0, -min(axial_values), max(axial_values) - span))
    status = ("SOURCE_EXTENSION_REQUIRED"
              if any(v > _EPS for v in missing + extensions)
              else "STRAIGHT_FACE_SOURCE_COVERED_ROOT_UNSOLVED")
    return VMiterRadiusBAMatingSurfaceTrial(
        interface_vertices=world,
        interface_triangles=tuple((world[0], world[i], world[i + 1])
                                  for i in range(1, len(world) - 1)),
        interface_area_mm2=float(face.area), interface_normal=plane_normal,
        first_material_vertices=maps[0], second_material_vertices=maps[1],
        first_missing_source_area_mm2=missing[0],
        second_missing_source_area_mm2=missing[1],
        first_axial_extension_mm=extensions[0],
        second_axial_extension_mm=extensions[1],
        first_neutral_axis_k=measures[0][2], second_neutral_axis_k=measures[1][2],
        source_remaining_outline=mating.relief.trial_remaining_outline,
        source_status=status,
    )
