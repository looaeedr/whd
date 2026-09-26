"""Bounded render-data orchestration for canonical manufacturing output."""
from __future__ import annotations

from .contracts import BoxBodyPartSpec, EndCapPartSpec


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
