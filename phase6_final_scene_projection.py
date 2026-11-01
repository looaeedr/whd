# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""Pure Final Scene geometry/projection helpers for Phase 4 T5.

This module owns calculation and projection only. It does not mutate renderer
axes/canvas, own Tk/UI state, import the bridge, or invoke application owners.
"""
from __future__ import annotations

from ae_engine.display_dimensions import folded_outside_envelope
from ae_engine import manufacturing_api
from phase6_final_scene_contracts import AssemblySceneRenderData
from phase6_fold_profiles import _num, engine_segment_length_to_ui


def _phase6_profile_base_index(profile):
    """Compatibility: Engine selects the real physical 3D Fold base segment."""
    return manufacturing_api.fold_profile_base_index(profile)


def _phase6_profile_geometry(profile, *, enabled_folds=None):
    """Compatibility: use the same folded material chain as Engine assembly."""
    return manufacturing_api.fold_profile_geometry(profile, enabled_folds=enabled_folds)


def _phase6_fold_mask_for_cross_coordinate(profile, axis, cross_position, fold_guides, *, tol=1e-6):
    """Compatibility: Engine owns finite BEND-span fold activation."""
    return manufacturing_api.fold_profile_bend_mask(
        profile, axis, cross_position, fold_guides, tol=tol,
    )


def _phase6_profile_map_with_guides(position, cross_position, profile, *, axis, fold_guides):
    """Compatibility: fold one mesh coordinate using canonical Engine geometry."""
    return manufacturing_api.fold_profile_map_with_guides(
        position, cross_position, profile, axis=axis, fold_guides=fold_guides,
    )


def _phase6_profile_map(position, boundaries, folded):
    """Compatibility: Engine owns material-space to formed-space mapping."""
    return manufacturing_api.fold_profile_map(position, boundaries, folded)


def _phase6_profile_flat_map(position, boundaries, *, profile=None):
    """Compatibility: Engine owns the unbent semantic base datum."""
    return manufacturing_api.fold_profile_flat_map(
        position, boundaries, profile=profile,
    )


def _phase6_folded_mesh_from_polygon(
    material, x_profile, y_profile, *, fold_exemptions=(), fold_guides=()
):
    """Compatibility wrapper around shared manufacturing-space folding."""
    from ae_engine.assembly_geometry import folded_mesh_from_polygon

    return list(folded_mesh_from_polygon(
        material,
        x_profile,
        y_profile,
        fold_exemptions=fold_exemptions,
        fold_guides=fold_guides,
    ))


def _phase6_mesh_feature_segments(triangles, *, tolerance=1e-6):
    """FinalScene presentation compatibility, not a physical-edge formula."""
    return manufacturing_api.physical_solid_mesh_feature_segments(
        triangles, tolerance=tolerance,
    )


def _phase6_fitted_limits_from_vertices(vertices, padding=0.06):
    """Fit each model axis independently instead of forcing a max_b cube."""
    pts = list(vertices or ())
    if not pts:
        return ((-50.0, 50.0), (-50.0, 50.0), (-50.0, 50.0))
    axes = list(zip(*pts))
    limits = []
    largest = max(max(a) - min(a) for a in axes)
    minimum_span = max(1.0, largest * 0.01)
    for values in axes:
        lo, hi = float(min(values)), float(max(values))
        span = max(hi - lo, minimum_span)
        center = (lo + hi) / 2.0
        half = span * (0.5 + float(padding))
        limits.append((center - half, center + half))
    return tuple(limits)


def _phase6_scene_fold_boundaries(scene, material):
    """Phase6 compatibility: Engine owns physical BEND-derived boundaries."""
    return manufacturing_api.scene_fold_boundaries(scene, material)


def _phase6_profile_to_scene_boundaries(profile, boundaries):
    """Phase6 compatibility: Engine owns material profile source lengths."""
    return manufacturing_api.profile_to_scene_boundaries(profile, boundaries)


def _phase6_fold_ownership_exemptions(material, xb, yb):
    """Phase6 compatibility: Engine owns local corner fold source semantics."""
    return manufacturing_api.fold_ownership_exemptions(material, xb, yb)


def _default_number_text(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    nearest_int = round(number)
    if abs(number - nearest_int) <= 1e-9:
        return str(int(nearest_int))
    return str(number)


def _phase6_folded_outside_envelope(triangles, thickness):
    """Compatibility wrapper around the shared 2D/3D dimension provider."""
    return folded_outside_envelope(triangles, thickness)


def _phase6_profile_operator_fold_values(profile):
    out = []
    for seg in profile or ():
        if seg.get("core"):
            continue
        try:
            out.append(float(engine_segment_length_to_ui(seg)))
        except Exception:
            out.append(float(_num(seg.get("len", 0.0))))
    return out


def _phase6_contract_profile_rows(profile):
    """Compatibility: Engine owns FoldSegment material row serialization."""
    return manufacturing_api.contract_fold_profile_rows(profile)


def _phase6_box_body_piece_world_mapper(piece, *, total_w, thickness, x_profile):
    """Compatibility adapter to the shared assembly-geometry role transform."""
    from ae_engine.assembly_geometry import place_box_body_structure_points

    def world(point):
        placed = place_box_body_structure_points(
            (point,), piece, total_w=total_w, thickness=thickness, x_profile=x_profile
        )
        return placed[0]
    return world


def _phase6_box_body_piece_dimension_lines(render_data) -> tuple[str, ...]:
    """Operator text for each authoritative physical Box Body piece."""
    labels = {
        "left_side": "左側板", "back": "後面板", "right_side": "右側板",
        "left": "左箱身", "middle": "中箱身", "right": "右箱身",
    }
    rows = []
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        label = labels.get(str(getattr(piece, "role", "") or ""), "箱身板件")
        fw, fh = tuple(float(v) for v in piece.formed_outer_dimensions)
        bw, bh = tuple(float(v) for v in piece.material_dimensions)
        rows.append(
            f"{label}：成形 {_default_number_text(fw)} × {_default_number_text(fh)} mm；"
            f"展開 {_default_number_text(bw)} × {_default_number_text(bh)} mm"
        )
    return tuple(rows)



def _phase6_assembly_physical_dimension_lines(part, *, thickness):
    """Format physical dimension evidence resolved exclusively by Engine."""
    evidence = manufacturing_api.project_assembly_physical_dimension_evidence(
        part, thickness=thickness,
    )
    lines = []
    for item in evidence:
        if item.role == "divider":
            detail = []
            if item.fw_outside is not None:
                detail.append(f"FW包外 {_default_number_text(item.fw_outside)}")
            if item.core_outside is not None:
                detail.append(f"核心包外 {_default_number_text(item.core_outside)}")
            suffix = ("；" + "、".join(detail)) if detail else ""
            width, height = item.material_extent
            lines.append(
                f"中隔：展開外框 {_default_number_text(width)} × "
                f"{_default_number_text(height)} mm{suffix}"
            )
        else:
            label = "左側板" if item.role == "left_side" else "右側板"
            formatted = " / ".join(
                _default_number_text(value) for value in item.fold_outside
            )
            lines.append(f"{label}：折後各段包外 {formatted} mm（依展開順序）")
    return tuple(lines)

def _phase6_assembly_part_presentation(part_key, opacity):
    """Return shared-theme visual role and visible opacity, never edit material."""
    from whd_theme import WHD_THEME
    if str(part_key).startswith("box_body:divider:"):
        return WHD_THEME["divider_face"], WHD_THEME["divider_edge"], 1.0
    return None


def _phase6_box_body_formed_width_datum(pieces):
    """Compatibility: Engine validates actual Box Body world-width provenance."""
    return manufacturing_api.resolve_box_body_formed_width_datum(pieces)


def _phase6_box_body_true_world_piece_meshes(part, *, dimensions, thickness):
    """3D FinalScene adapter: true-T physical world skins belong to Engine."""
    return manufacturing_api.resolve_box_body_true_world_piece_meshes(
        part, dimensions=dimensions, thickness=thickness,
    )

def _phase6_box_body_structure_meshes(render_data, *, thickness):
    """Compatibility list: Engine owns physical Box Body mid-surface folding."""
    return list(manufacturing_api.resolve_box_body_structure_mid_meshes(
        render_data, thickness=thickness,
    ))

def format_operator_info_text(request, *, dimensions=None, number_text=None):
    """Format already-resolved operator display information for every View sink."""
    number_text = number_text or _default_number_text
    dims = tuple(dimensions or getattr(request, "finished_dimensions", ()) or ())
    if len(dims) < 2:
        return ""
    width, height = dims[:2]
    depth = dims[2] if len(dims) > 2 else None
    xfold = " / ".join(number_text(v) for v in _phase6_profile_operator_fold_values(request.x_profile)) or "-"
    yfold = " / ".join(number_text(v) for v in _phase6_profile_operator_fold_values(request.y_profile)) or "-"
    finished = (
        f"折後包外：W {number_text(width)} × H {number_text(height)} × D {number_text(depth)} mm"
        if depth is not None else
        f"折後包外：W {number_text(width)} × H {number_text(height)} mm"
    )
    lines = [finished, f"X折：{xfold}   Y折：{yfold}"]
    if request.corner_dimension_text:
        lines.append(request.corner_dimension_text)
    if request.unfolded_blank_text:
        lines.append(request.unfolded_blank_text)
    if str(getattr(request, "part_key", "") or "") == "box_body":
        lines.extend(_phase6_box_body_piece_dimension_lines(getattr(request, "render_data", None)))
    return "\n".join(lines)


def _phase6_triangle_bounds(triangles):
    from ae_engine.assembly_geometry import triangle_bounds

    return triangle_bounds(triangles)


def _phase6_place_assembly_triangles(triangles, placement, dimensions, offset):
    """Compatibility wrapper around the shared assembly-space transform."""
    from ae_engine.assembly_geometry import place_assembly_triangles

    return place_assembly_triangles(triangles, placement, dimensions, offset)


def make_assembly_scene_render_data(
    *,
    assembly_parts,
    visible_part_keys=None,
    visible_box_body_piece_keys=None,
    show_interference=False,
    ignore_fixed_corner_relief=False,
    interference_probe_parts=(),
    joint_diagnostics=(),
    collision_certification_diagnostics=(),
    selected_joint_id=None,
    preserve_endcap_core_origin=False,
    formed_fixing_plate_skins=(),
    show_fixing_plate_mesh=True,
    formed_nfb_pad_skins=(),
    warnings=(),
    render_data_cls=None,
):
    """Construct the UI-only assembly bundle across old/new view contracts."""
    from inspect import Parameter, signature

    cls = render_data_cls or AssemblySceneRenderData
    values = {
        "assembly_parts": tuple(part for part in assembly_parts if getattr(part,"placement","offset")!="standalone"),
        "visible_part_keys": (
            None
            if visible_part_keys is None
            else tuple(str(key) for key in visible_part_keys)
        ),
        "visible_box_body_piece_keys": (
            None
            if visible_box_body_piece_keys is None
            else tuple(str(key) for key in visible_box_body_piece_keys)
        ),
        "show_interference": bool(show_interference),
        "ignore_fixed_corner_relief": bool(ignore_fixed_corner_relief),
        "interference_probe_parts": tuple(interference_probe_parts or ()),
        "joint_diagnostics": tuple(joint_diagnostics or ()),
        "collision_certification_diagnostics": tuple(
            collision_certification_diagnostics or ()
        ),
        "selected_joint_id": (
            None if selected_joint_id is None else str(selected_joint_id)
        ),
        "preserve_endcap_core_origin": bool(preserve_endcap_core_origin),
        "formed_fixing_plate_skins": tuple(formed_fixing_plate_skins or ()),
        "show_fixing_plate_mesh": bool(show_fixing_plate_mesh),
        "formed_nfb_pad_skins": tuple(formed_nfb_pad_skins or ()),
        "warnings": tuple(warnings or ()),
    }
    try:
        params = signature(cls).parameters
    except (TypeError, ValueError):
        params = {}
    accepts_kwargs = any(
        parameter.kind is Parameter.VAR_KEYWORD
        for parameter in params.values()
    )
    if accepts_kwargs:
        kwargs = values
    else:
        if (
            "visible_part_keys" not in params
            and values["visible_part_keys"] is not None
        ):
            visible = set(values["visible_part_keys"])
            values["assembly_parts"] = tuple(
                part
                for part in values["assembly_parts"]
                if str(getattr(part, "part_key", "")) in visible
            )
        kwargs = {
            key: value
            for key, value in values.items()
            if key in params
        }
        kwargs.setdefault("assembly_parts", values["assembly_parts"])
    return cls(**kwargs)


__all__ = [
    '_phase6_profile_base_index',
    '_phase6_profile_geometry',
    '_phase6_fold_mask_for_cross_coordinate',
    '_phase6_profile_map_with_guides',
    '_phase6_profile_map',
    '_phase6_profile_flat_map',
    '_phase6_folded_mesh_from_polygon',
    '_phase6_mesh_feature_segments',
    '_phase6_fitted_limits_from_vertices',
    '_phase6_scene_fold_boundaries',
    '_phase6_profile_to_scene_boundaries',
    '_phase6_fold_ownership_exemptions',
    '_default_number_text',
    '_phase6_folded_outside_envelope',
    '_phase6_profile_operator_fold_values',
    '_phase6_contract_profile_rows',
    '_phase6_box_body_piece_world_mapper',
    '_phase6_box_body_piece_dimension_lines',
    '_phase6_box_body_structure_meshes',
    'format_operator_info_text',
    '_phase6_triangle_bounds',
    '_phase6_place_assembly_triangles',
    'make_assembly_scene_render_data'
]
