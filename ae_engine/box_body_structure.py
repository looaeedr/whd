# -*- coding: utf-8 -*-
"""Resolved box-body multi-structure geometry.

This is the public geometry seam for box-body structure modes.  It deliberately
keeps the legacy integral path intact and returns independent flat pieces for
multi-piece modes.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from phase6_box_body_structure import (
    BoxBodyStructureType,
    normalize_box_body_structure_state,
    resolve_two_piece_widths,
    resolve_three_piece_widths,
    side_rear_bend_material_length,
)
from .contracts import FoldProfileSegment
from .sheetmetal_geometry import (
    BendLine,
    FoldSegment,
    StripFoldChain,
    Vec2,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    CornerDirection,
    corner_selection_residual,
    build_strip_bend_segments,
    build_strip_outline,
    box_body_height_from_corner_policies,
)
from .sheetmetal_part_adapters import StructuralGeometryResult, build_box_body_result_from_fold_profile


from .box_body_structure_core import (
    BoxBodyStructureWarning,
    ResolvedBoxBodyPiece,
    ResolvedBoxBodyStructure,
    _canonical_cross_retain_mm,
)

def _value(row, name, default=None):
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _copy_profile_rows(profile):
    rows = []
    for row in profile or ():
        copied = {
            "len": float(_value(row, "length", _value(row, "len", 0.0))),
        }
        angle = _value(row, "angle")
        if angle is not None:
            copied["angle"] = float(angle)
        core = _value(row, "core")
        if core:
            copied["core"] = str(core)
        key = _value(row, "phase6_key")
        if key:
            copied["phase6_key"] = str(key)
        ui_add = _value(row, "ui_len_add")
        if ui_add is not None:
            copied["ui_len_add"] = float(ui_add)
        formed_length = _value(row, "formed_length")
        if formed_length is not None:
            copied["formed_length"] = float(formed_length)
        rows.append(copied)
    return rows


def _core_indexes(rows):
    d_indexes = [i for i, row in enumerate(rows) if row.get("core") == "D"]
    w_indexes = [i for i, row in enumerate(rows) if row.get("core") == "W"]
    if len(d_indexes) != 2 or len(w_indexes) != 1 or not (d_indexes[0] < w_indexes[0] < d_indexes[1]):
        raise ValueError("箱身 Fold Chain 必須保留單一 D-W-D 核心")
    return d_indexes[0], w_indexes[0], d_indexes[1]


def _to_contract(rows) -> tuple[FoldProfileSegment, ...]:
    def formed_length(row):
        explicit = row.get("formed_length")
        if explicit is not None:
            return float(explicit)
        ui_add = row.get("ui_len_add")
        if ui_add is None or row.get("core"):
            return None
        return float(row.get("len", 0.0)) + abs(float(ui_add))

    return tuple(FoldProfileSegment(
        length=float(row.get("len", 0.0)),
        angle=(float(row["angle"]) if "angle" in row else None),
        core=(str(row["core"]) if row.get("core") else None),
        phase6_key=(str(row["phase6_key"]) if row.get("phase6_key") else None),
        formed_length=formed_length(row),
    ) for row in rows)


def _generic_strip_result(rows, *, height) -> StructuralGeometryResult:
    segments = []
    for index, row in enumerate(rows):
        name = str(row.get("phase6_key") or row.get("core") or f"fold_{index}")
        segments.append(FoldSegment(name, float(row.get("len", 0.0)), 0.0))
    chain = StripFoldChain(tuple(segments), float(height))
    return StructuralGeometryResult(
        tuple(build_strip_outline(chain)),
        tuple(build_strip_bend_segments(chain)),
        chain.total_width,
        chain.height,
        chain,
    )


def _material_w_span(formed_width: float, thickness: float) -> float:
    """W 子段兩側皆為 90° bend，沿用既有 W-2T 成型/材料關係。"""
    value = float(formed_width) - 2.0 * float(thickness)
    if value <= 0:
        raise ValueError("W 分件成型寬不足以形成有效材料段")
    return value


def _formed_depth_from_profile(profile, *, thickness: float, explicit_depth=None) -> float:
    """Resolve the side-panel formed D without treating material D as package D."""
    if explicit_depth is not None:
        depth = float(explicit_depth)
        if depth <= 0:
            raise ValueError("箱身成形 D 必須大於 0")
        return depth
    rows = list(profile or ())
    d_rows = [row for row in rows if str(_value(row, "core", "") or "") == "D"]
    if not d_rows:
        raise ValueError("箱身 Fold Chain 缺少 D 核心，無法解析側板包外尺寸")
    row = d_rows[0]
    material = abs(float(_value(row, "length", _value(row, "len", 0.0))))
    ui_add = _value(row, "ui_len_add")
    compensation = abs(float(ui_add)) if ui_add is not None else 2.0 * float(thickness)
    depth = material + compensation
    if depth <= 0:
        raise ValueError("箱身成形 D 計算後必須大於 0")
    return depth


def _two_piece_rows(profile, *, left_w, right_w, t, seam_bend):
    rows = _copy_profile_rows(profile)
    left_d, w_index, right_d = _core_indexes(rows)

    left = deepcopy(rows[:w_index])
    # D_left already owns the bend into W.  W_left owns the bend into seam flange.
    left.append({
        "len": _material_w_span(left_w, t),
        "angle": -90.0,
        "core": "W_PART",
        "phase6_key": "w_left",
    })
    left.append({"len": float(seam_bend), "phase6_key": "seam_bend_left"})

    right = [{"len": float(seam_bend), "angle": -90.0, "phase6_key": "seam_bend_right"}]
    right.append({
        "len": _material_w_span(right_w, t),
        "angle": float(rows[w_index].get("angle", -90.0)),
        "core": "W_PART",
        "phase6_key": "w_right",
    })
    right.extend(deepcopy(rows[right_d:]))
    return left, right



def _with_multiple_seam_end_reliefs(
    result: StructuralGeometryResult,
    *,
    seams,
    bottom_depth: float,
    top_depth: float,
    meat: float,
) -> StructuralGeometryResult:
    """Apply one or more left/right seam-flange end reliefs to a strip piece."""
    from shapely.geometry import Polygon, box as shapely_box

    width = float(result.width)
    height = float(result.height)
    bottom = float(bottom_depth)
    top = float(top_depth)
    if bottom < 0 or top < 0 or bottom + top >= height:
        raise ValueError("中央接合折邊上下避讓深度超出箱身有效高度")
    material = Polygon([(float(p.x), float(p.y)) for p in result.outline])
    seam_names = {}
    for seam in seams:
        side = str(seam["side"])
        flange = float(seam["width"])
        name = str(seam["bend_name"])
        if meat < 0 or meat >= flange:
            raise ValueError("十字截角單邊留肉必須小於接合折邊寬度")
        if side == "left":
            cut_x1, cut_x2 = 0.0, flange - meat
        elif side == "right":
            cut_x1, cut_x2 = width - flange + meat, width
        else:
            raise ValueError("seam side must be left or right")
        if bottom > 0:
            material = material.difference(shapely_box(cut_x1, 0.0, cut_x2, bottom))
        if top > 0:
            material = material.difference(shapely_box(cut_x1, height - top, cut_x2, height))
        seam_names[name] = side
    if material.geom_type != "Polygon" or material.is_empty:
        raise ValueError("中央接合折邊十字截角產生無效 CUTTING 幾何")
    outline = tuple(Vec2(float(x), float(y)) for x, y in material.exterior.coords)
    bends = []
    found = set()
    for bend in result.bends:
        if bend.name in seam_names:
            found.add(bend.name)
            bends.append(BendLine(
                bend.name,
                Vec2(float(bend.p1.x), bottom),
                Vec2(float(bend.p2.x), height - top),
            ))
        else:
            bends.append(bend)
    missing = set(seam_names) - found
    if missing:
        raise ValueError("找不到中央接合折線：" + ", ".join(sorted(missing)))
    return StructuralGeometryResult(outline, tuple(bends), width, height, result.topology)


def _three_piece_rows(profile, *, left_w, middle_w, right_w, t, seam_bend):
    rows = _copy_profile_rows(profile)
    _left_d, w_index, right_d = _core_indexes(rows)
    left = deepcopy(rows[:w_index])
    left.append({
        "len": _material_w_span(left_w, t), "angle": -90.0,
        "core": "W_PART", "phase6_key": "w_left",
    })
    left.append({"len": float(seam_bend), "phase6_key": "seam_bend_left_outer"})

    middle = [
        {"len": float(seam_bend), "angle": -90.0, "phase6_key": "seam_bend_middle_left"},
        {"len": _material_w_span(middle_w, t), "angle": -90.0, "core": "W_PART", "phase6_key": "w_middle"},
        {"len": float(seam_bend), "phase6_key": "seam_bend_middle_right"},
    ]

    right = [
        {"len": float(seam_bend), "angle": -90.0, "phase6_key": "seam_bend_right_outer"},
        {"len": _material_w_span(right_w, t), "angle": float(rows[w_index].get("angle", -90.0)),
         "core": "W_PART", "phase6_key": "w_right"},
    ]
    right.extend(deepcopy(rows[right_d:]))
    return left, middle, right


def _flat_panel_result(*, width: float, height: float) -> StructuralGeometryResult:
    width = float(width)
    height = float(height)
    if width <= 0 or height <= 0:
        raise ValueError("平板尺寸必須大於 0")
    outline = (
        Vec2(0.0, 0.0), Vec2(width, 0.0), Vec2(width, height),
        Vec2(0.0, height), Vec2(0.0, 0.0),
    )
    return StructuralGeometryResult(outline, (), width, height, None)


def _side_back_rows(profile, *, rear_bend):
    rows = _copy_profile_rows(profile)
    _left_d, w_index, right_d = _core_indexes(rows)
    left = deepcopy(rows[:w_index])
    if not left or left[-1].get("core") != "D":
        raise ValueError("側背分離左側板缺少 D 核心")
    left[-1]["angle"] = -90.0
    left.append({"len": float(rear_bend), "phase6_key": "side_rear_bend_left"})

    # Mirror the left rear fold in panel-local geometry so both the rear support
    # flange and the existing front folds point toward the enclosure interior.
    right = [{"len": float(rear_bend), "angle": -90.0, "phase6_key": "side_rear_bend_right"}]
    right.extend(deepcopy(rows[right_d:]))
    return left, right


def _merge_side_back_piece_override(base_rows, override_rows, *, shared_keys):
    """Keep piece-local topology while rebasing shared cabinet dimensions."""
    if not override_rows:
        return deepcopy(list(base_rows or ()))
    base_by_key = {
        str(row.get("phase6_key") or ""): row
        for row in tuple(base_rows or ())
        if str(row.get("phase6_key") or "")
    }
    result = []
    for raw in tuple(override_rows or ()):
        row = deepcopy(dict(raw))
        key = str(row.get("phase6_key") or "")
        base = base_by_key.get(key)
        if key in set(shared_keys or ()) and base is not None:
            # Length/core are shared physical dimensions. Angle/topology remain
            # piece-local so the three Fold editors are genuinely independent.
            row["len"] = float(base.get("len", row.get("len", 0.0)))
            if base.get("ui_len_add") is not None:
                row["ui_len_add"] = float(base["ui_len_add"])
            else:
                row.pop("ui_len_add", None)
            if base.get("formed_length") is not None:
                row["formed_length"] = float(base["formed_length"])
            else:
                row.pop("formed_length", None)
            if base.get("core") is not None:
                row["core"] = base.get("core")
            else:
                row.pop("core", None)
        result.append(row)
    return result

def resolve_box_body_structure(
    profile,
    *,
    w,
    h,
    t,
    d=None,
    structure_state=None,
    back_panel_contract=None,
    head_corner_policy=None,
    tail_corner_policy=None,
    head_ybottom1=15.0,
    tail_ybottom1=15.0,
) -> ResolvedBoxBodyStructure:
    """Resolve one canonical box Fold Chain into physical box-body pieces."""
    state = normalize_box_body_structure_state(structure_state)
    type_id = BoxBodyStructureType(state["active_type"])

    if type_id is BoxBodyStructureType.INTEGRAL:
        structural = build_box_body_result_from_fold_profile(
            profile,
            h=h,
            t=t,
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        )
        return ResolvedBoxBodyStructure(
            type_id,
            (ResolvedBoxBodyPiece(
                "box_body", "integral", 0.0, float(w), _to_contract(_copy_profile_rows(profile)), structural,
                formed_outer_width=float(w), formed_outer_height=float(structural.height),
            ),),
        )

    if type_id is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
        cfg = state["configs"][type_id.value]
        rear_bend = side_rear_bend_material_length(state, float(t))
        comp_t = float(cfg.get("back_width_comp_t", 0.5))
        if rear_bend <= 0:
            raise ValueError("側板後折必須大於 0")
        if comp_t < 0:
            raise ValueError("後面板寬補償不可小於 0T")
        height = box_body_height_from_corner_policies(
            h, t,
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        )
        left_rows, right_rows = _side_back_rows(profile, rear_bend=rear_bend)
        back_width = float(w) - comp_t * float(t)
        if back_width <= 0:
            raise ValueError("側背分離後面板寬度計算後必須大於 0")
        back_contract = dict(back_panel_contract or {})
        if back_contract:
            contract_width = float(back_contract.get("panel_width", back_width))
            if abs(contract_width - back_width) > 1e-6:
                raise ValueError("後面板 contract 寬度與 canonical structure 不一致")
            back_height = float(back_contract.get("material_height", height))
            back_y_offset = float(back_contract.get("formed_y_offset", 0.0))
            if back_height <= 0.0 or back_height > float(height) + 1e-6:
                raise ValueError("後面板 contract 高度超出 canonical structure")
        else:
            back_height = float(height)
            back_y_offset = 0.0
        back_rows = [{"len": back_width, "core": "W_BACK", "phase6_key": "back_panel"}]

        piece_overrides = dict(cfg.get("piece_profiles") or {})
        left_rows = _merge_side_back_piece_override(
            left_rows, piece_overrides.get("left_side"),
            shared_keys={"zl1", "zl2", "fw_left", "d_left"},
        )
        back_rows = _merge_side_back_piece_override(
            back_rows, piece_overrides.get("back"),
            shared_keys={"back_panel"},
        )
        right_rows = _merge_side_back_piece_override(
            right_rows, piece_overrides.get("right_side"),
            shared_keys={"d_right", "fw_right", "zr2"},
        )

        offset = (float(w) - back_width) / 2.0
        formed_depth = _formed_depth_from_profile(profile, thickness=float(t), explicit_depth=d)
        back_result = (
            _flat_panel_result(width=back_width, height=back_height)
            if len(back_rows) == 1 and not back_rows[0].get("angle")
            else _generic_strip_result(back_rows, height=back_height)
        )
        pieces = (
            ResolvedBoxBodyPiece(
                "box_body_left_side", "left_side", 0.0, 0.0,
                _to_contract(left_rows), _generic_strip_result(left_rows, height=height),
                formed_outer_width=formed_depth, formed_outer_height=height,
            ),
            ResolvedBoxBodyPiece(
                "box_body_back", "back", offset, offset + back_width,
                _to_contract(back_rows), back_result,
                formed_outer_width=back_width, formed_outer_height=back_height,
                formed_y_offset=back_y_offset,
            ),
            ResolvedBoxBodyPiece(
                "box_body_right_side", "right_side", float(w), float(w),
                _to_contract(right_rows), _generic_strip_result(right_rows, height=height),
                formed_outer_width=formed_depth, formed_outer_height=height,
            ),
        )
        return ResolvedBoxBodyStructure(type_id, pieces, ())

    if type_id not in {BoxBodyStructureType.TWO_PIECE_W_SPLIT, BoxBodyStructureType.THREE_PIECE_W_SPLIT}:
        raise NotImplementedError(f"box body structure geometry not implemented yet: {type_id.value}")

    cfg = state["configs"][type_id.value]
    seam = float(cfg.get("seam_bend", 12.0))
    if seam < 12.0:
        raise ValueError("中央接合折邊不得小於 12 mm")

    height = box_body_height_from_corner_policies(
        h, t,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    )
    extra_relief = float(cfg.get("endcap_extra_relief", 5.0))
    meat = _canonical_cross_retain_mm(
        amount_t=float(cfg.get("endcap_single_side_meat_t", 0.5)),
        thickness=float(t),
        direction=CornerDirection.WIDTH,
    )
    if extra_relief < 0:
        raise ValueError("封頭尾十字截角額外避讓不可小於 0")
    bottom_depth = float(tail_ybottom1) + extra_relief
    top_depth = float(head_ybottom1) + extra_relief

    if type_id is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
        left_w, right_w = resolve_two_piece_widths(state, float(w))
        left_rows, right_rows = _two_piece_rows(
            profile, left_w=left_w, right_w=right_w, t=t, seam_bend=seam,
        )
        left_structural = _with_multiple_seam_end_reliefs(
            _generic_strip_result(left_rows, height=height),
            seams=({"side": "right", "width": seam, "bend_name": "w_left"},),
            bottom_depth=bottom_depth, top_depth=top_depth, meat=meat,
        )
        right_structural = _with_multiple_seam_end_reliefs(
            _generic_strip_result(right_rows, height=height),
            seams=({"side": "left", "width": seam, "bend_name": "seam_bend_right"},),
            bottom_depth=bottom_depth, top_depth=top_depth, meat=meat,
        )
        pieces = (
            ResolvedBoxBodyPiece("box_body_left", "left", 0.0, left_w, _to_contract(left_rows), left_structural, left_w, height),
            ResolvedBoxBodyPiece("box_body_right", "right", left_w, float(w), _to_contract(right_rows), right_structural, right_w, height),
        )
    else:
        left_w, middle_w, right_w = resolve_three_piece_widths(state, float(w))
        left_rows, middle_rows, right_rows = _three_piece_rows(
            profile, left_w=left_w, middle_w=middle_w, right_w=right_w, t=t, seam_bend=seam,
        )
        left_structural = _with_multiple_seam_end_reliefs(
            _generic_strip_result(left_rows, height=height),
            seams=({"side": "right", "width": seam, "bend_name": "w_left"},),
            bottom_depth=bottom_depth, top_depth=top_depth, meat=meat,
        )
        middle_structural = _with_multiple_seam_end_reliefs(
            _generic_strip_result(middle_rows, height=height),
            seams=(
                {"side": "left", "width": seam, "bend_name": "seam_bend_middle_left"},
                {"side": "right", "width": seam, "bend_name": "w_middle"},
            ),
            bottom_depth=bottom_depth, top_depth=top_depth, meat=meat,
        )
        right_structural = _with_multiple_seam_end_reliefs(
            _generic_strip_result(right_rows, height=height),
            seams=({"side": "left", "width": seam, "bend_name": "seam_bend_right_outer"},),
            bottom_depth=bottom_depth, top_depth=top_depth, meat=meat,
        )
        first = left_w
        second = left_w + middle_w
        pieces = (
            ResolvedBoxBodyPiece("box_body_left", "left", 0.0, first, _to_contract(left_rows), left_structural, left_w, height),
            ResolvedBoxBodyPiece("box_body_middle", "middle", first, second, _to_contract(middle_rows), middle_structural, middle_w, height),
            ResolvedBoxBodyPiece("box_body_right", "right", second, float(w), _to_contract(right_rows), right_structural, right_w, height),
        )

    warnings = ()
    if seam >= 50.0:
        warnings = (BoxBodyStructureWarning(
            "seam_bend_large",
            f"中央接合折邊 {seam:g} mm 已達 50 mm 以上，請確認尺寸是否合理。",
        ),)
    return ResolvedBoxBodyStructure(type_id, pieces, warnings)


from .box_body_piece_features import (
    _merge_intervals,
    _split_horizontal_bend,
    box_body_seam_positions,
    apply_base_plate_structure_reliefs,
    _feature_finished_bounds,
    _piece_w_context,
    _resolve_feature_at_local_center,
    _resolved_feature_shape,
    _polygon_parts,
    _line_parts,
    _profile_from_coords,
    _clip_one_resolved_feature,
    _clip_resolved_feature_to_piece,
    _clip_layered_profile_feature,
    resolve_box_body_piece_face_features,
)
