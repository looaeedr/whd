# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""Bounded render-data orchestration for canonical manufacturing output."""
from __future__ import annotations

from .contracts import BoxBodyPartSpec, EndCapPartSpec, BasePlatePartSpec


def build_part_render_data(
    spec,
    context=None,
    *,
    render_data_type,
    build_box_body_result_from_fold_profile,
    build_part_scene,
    box_body_face_contexts_from_strip,
    material_polygon_from_final_scene,
    fold_guides_from_final_scene,
    unfolded_topology_for_spec,
    endcap_scalar,
    default_fold_left,
    default_fold_right,
    replace_receiving_bottom_relief_from_registry,
    resolve_endcap_request,
    scene_with_authoritative_fold_profiles,
    recursive_build_part_render_data,
):
    """Build final render data without owning geometry formulas or UI state."""
    box_body_result = None
    box_body_contexts = None
    if isinstance(spec, BoxBodyPartSpec):
        if not tuple(spec.fold_profile or ()):
            raise ValueError('canonical Box Body Fold Profile is required for manufacturing')
        box_body_result = build_box_body_result_from_fold_profile(
            spec.fold_profile,
            h=float(spec.height),
            t=float(spec.thickness),
            head_corner_policy=spec.head_corner_policy,
            tail_corner_policy=spec.tail_corner_policy,
        )
        scene = build_part_scene(
            spec, context, _box_body_structural_result=box_body_result
        )
        box_body_contexts = box_body_face_contexts_from_strip(
            box_body_result.topology,
            w=float(spec.width),
            h=float(spec.height),
            d=float(spec.depth),
            t=float(spec.thickness),
            head_corner_policy=spec.head_corner_policy,
            tail_corner_policy=spec.tail_corner_policy,
        )
    else:
        scene = build_part_scene(spec, context)

    metadata = {}
    if isinstance(spec, BasePlatePartSpec):
        is_receiving = str(spec.model_name or "").strip() in {"受電箱", "RECEIVING"}
        if spec.receiving_bend_pattern is not None:
            metadata = {
                "stable_id": str(spec.physical_id or "base_plate"),
                "receiving_bend_pattern": str(spec.receiving_bend_pattern),
                "receiving_nfb_base_mfg2_release_approved": False,
            }
        elif is_receiving:
            # Legacy preview is non-manufacturing: never sell its ordinary
            # four-side contour as the Receiving physical bottom plate.
            metadata = {
                "stable_id": str(spec.physical_id or "base_plate"),
                "receiving_base_plate_unconfigured": True,
            }
    if isinstance(spec, EndCapPartSpec):
        metadata = {
            'nominal_fold_left': endcap_scalar(spec.fold_left, default_fold_left),
            'nominal_fold_right': endcap_scalar(spec.fold_right, default_fold_right),
        }
    render_data = render_data_type(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata=metadata,
        unfolded_topology=unfolded_topology_for_spec(spec),
        box_body_face_contexts=box_body_contexts,
    )
    if isinstance(spec, EndCapPartSpec):
        render_data = replace_receiving_bottom_relief_from_registry(render_data, spec)

    if isinstance(spec, EndCapPartSpec) and tuple(
        getattr(spec, 'resolved_assembly_relief_cuts', ()) or ()
    ):
        from shapely.geometry import Polygon
        from .assembly_collision import (
            _scene_with_replaced_primary_cutting,
            apply_verified_endcap_relief_material,
        )

        cut_polygons = []
        for coords in tuple(spec.resolved_assembly_relief_cuts or ()):
            if len(coords) < 3:
                continue
            polygon = Polygon([(float(x), float(y)) for x, y in coords])
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if not polygon.is_empty and float(polygon.area) > 1e-9:
                cut_polygons.append(polygon)
        if cut_polygons:
            solved_material = apply_verified_endcap_relief_material(
                render_data.material, cut_polygons
            )
            if solved_material.is_empty:
                raise ValueError('verified EndCap assembly relief removed all material')
            solved_scene = _scene_with_replaced_primary_cutting(
                render_data.scene, solved_material
            )
            resolved = resolve_endcap_request(spec)
            solved_scene = scene_with_authoritative_fold_profiles(
                solved_scene, resolved.fold_profile_x, resolved.fold_profile_y
            )
            render_data = render_data_type(
                scene=solved_scene,
                material=material_polygon_from_final_scene(solved_scene),
                fold_guides=fold_guides_from_final_scene(solved_scene),
                metadata=dict(getattr(render_data, 'metadata', {}) or {}),
                unfolded_topology=getattr(render_data, 'unfolded_topology', None),
            )

    request = getattr(spec, 'assembly_relief', None)
    if request is not None and getattr(request, 'enabled', True):
        from .assembly_collision import solve_boxbody_endcap_relief

        if isinstance(spec, EndCapPartSpec):
            box_render = recursive_build_part_render_data(request.box_body, context)
            solution = solve_boxbody_endcap_relief(
                box_body_render_data=box_render,
                endcap_render_data=render_data,
                clearance=float(request.clearance),
            )
            if not solution.verified:
                raise ValueError('EndCap assembly collision relief failed verification')
            render_data = solution.solved_render_data
    return render_data
