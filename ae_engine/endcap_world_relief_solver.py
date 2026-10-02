"""Bounded EndCap world-relief solver orchestration.

Shared collision/backprojection primitives, public result types and mechanical
authority are injected by the assembly_collision facade. This module therefore
does not reverse-import the facade or manufacture a second generic solver path.
"""
from __future__ import annotations


def solve_world_backprojected_endcap_relief(
    *,
    box_body_render_data,
    endcap_render_data,
    box_body_x_profile,
    endcap_x_profile,
    endcap_y_profile,
    finished_dimensions,
    endcap_placement="top",
    sheet_thickness=0.0,
    clearance=0.0,
    max_iterations=8,
    assembly_intent=None,
    cabinet_family="ANY",
    allow_3d_fallback=True,
    assembly_joint=None,
    assembly_graph=None,
    endcap_part=None,
    certified_result_override=None,
    _deps=None,
):
    if _deps is None:
        raise RuntimeError("EndCap world-relief solver dependencies are required")
    AssemblyBackprojectedReliefSolution = _deps["AssemblyBackprojectedReliefSolution"]
    BackprojectedCornerRelief = _deps["BackprojectedCornerRelief"]
    FlatInterferenceProjection = _deps["FlatInterferenceProjection"]
    _build_box_body_world_solid = _deps["_build_box_body_world_solid"]
    _canonical_corner_geometry = _deps["_canonical_corner_geometry"]
    _corner_name_for_component = _deps["_corner_name_for_component"]
    _expand_orthogonal_corner_cut_with_clearance = _deps["_expand_orthogonal_corner_cut_with_clearance"]
    _folded_profile_is_mirror_symmetric = _deps["_folded_profile_is_mirror_symmetric"]
    _measure_canonical_corner_cut = _deps["_measure_canonical_corner_cut"]
    _normalize_corner_cut_to_component_topology = _deps["_normalize_corner_cut_to_component_topology"]
    _physical_corner_geometry = _deps["_physical_corner_geometry"]
    _polygon_parts = _deps["_polygon_parts"]
    _project_probe_material = _deps["_project_probe_material"]
    _project_probe_mid_surface = _deps["_project_probe_mid_surface"]
    _projection_within_material_boundary_band = _deps["_projection_within_material_boundary_band"]
    _render_data_rebuilt_from_material = _deps["_render_data_rebuilt_from_material"]
    _snap_single_stage_cut_to_structural_contact = _deps["_snap_single_stage_cut_to_structural_contact"]
    apply_verified_endcap_relief_material = _deps["apply_verified_endcap_relief_material"]
    derive_corner_relief_from_flat_interference = _deps["derive_corner_relief_from_flat_interference"]
    joint_relief_ownership = _deps["joint_relief_ownership"]
    projection_has_material_penetration = _deps["projection_has_material_penetration"]
    """Replace fixed relief with a converged, world-verified 3D-derived cut."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    from .assembly_geometry import (
        folded_mesh_with_flat_uv_from_polygon,
        restore_unrelieved_endcap_material,
        restored_endcap_relief_delta,
    )

    t = max(0.0, float(sheet_thickness or 0.0))
    # The receiving cabinet's asymmetric EndCap fold profile uses the core
    # datum as the authoritative assembly-depth origin. Existing vault/generic
    # solver contracts retain historical envelope centering until migrated and
    # certified independently, so this opt-in must stay family-scoped.
    family_key = str(cabinet_family or "").strip().upper()
    preserve_endcap_core_origin = family_key in {"受電箱", "RECEIVING"}
    restored = restore_unrelieved_endcap_material(endcap_render_data.material)
    delta = restored_endcap_relief_delta(endcap_render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return AssemblyBackprojectedReliefSolution(None, (), (), endcap_render_data, False, None)

    body_world_surface, body_world_solid = _build_box_body_world_solid(
        box_body_render_data, box_body_x_profile, finished_dimensions, t
    )
    full_mapped = folded_mesh_with_flat_uv_from_polygon(
        restored, endcap_x_profile, endcap_y_profile,
        fold_guides=tuple(getattr(endcap_render_data, "fold_guides", ()) or ()),
    )
    full_reference_local = tuple(mapped.local for mapped in full_mapped)
    blank_bounds = tuple(map(float, restored.bounds))
    minx, miny, maxx, maxy = blank_bounds
    components = []
    for component in _polygon_parts(delta):
        name = _corner_name_for_component(component, blank_bounds)
        if name is not None:
            components.append((name, component))

    # Certified formulas have priority over 3D discovery.  Once a resolved
    # AssemblyJoint graph exists it is the assembly source of truth; the legacy
    # high-level assembly_intent mirror is ignored for rule selection.
    if assembly_graph is not None or assembly_intent is not None or certified_result_override is not None:
        from .certified_relief_registry import (
            CertifiedReliefStatus,
            lookup_certified_endcap_relief,
            lookup_certified_endcap_relief_from_graph,
        )
        certified = certified_result_override
        if certified is None and assembly_graph is not None:
            part_key = str(endcap_part or ("tail" if str(endcap_placement).lower() == "bottom" else "head"))
            certified = lookup_certified_endcap_relief_from_graph(
                graph=assembly_graph,
                endcap_part=part_key,
                endcap_render_data=endcap_render_data,
                box_body_x_profile=box_body_x_profile,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                sheet_thickness=t,
                cabinet_family=cabinet_family,
            )
        elif certified is None and assembly_intent is not None:
            signature_relations = None
            if assembly_joint is not None:
                # Legacy compatibility only: one explicit Joint augments the
                # high-level mirror when no resolved graph is available.
                signature_relations = (
                    str(getattr(assembly_intent, "value", assembly_intent)),
                    str(getattr(getattr(assembly_joint, "relation", None), "value", getattr(assembly_joint, "relation", ""))),
                )
            certified = lookup_certified_endcap_relief(
                assembly_intent=assembly_intent,
                endcap_render_data=endcap_render_data,
                box_body_x_profile=box_body_x_profile,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                sheet_thickness=t,
                cabinet_family=cabinet_family,
                joint_signature_relations=signature_relations,
            )
        if certified is not None:
            certified_corner_names = {
                str(getattr(relief, "corner_name", "") or "")
                for relief in tuple(getattr(certified, "corner_reliefs", ()) or ())
            }
            certified_components = tuple(
                (name, component) for name, component in components
                if not certified_corner_names or str(name) in certified_corner_names
            )
            certified_projections = []
            for _corner_name, component in certified_components:
                probe = restored.intersection(component)
                certified_projections.append(_project_probe_material(
                    probe_material=probe,
                    box_body_world_surface=body_world_surface,
                    box_body_world_solid=body_world_solid,
                    endcap_reference_local=full_reference_local,
                    endcap_x_profile=endcap_x_profile,
                    endcap_y_profile=endcap_y_profile,
                    endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                    endcap_placement=endcap_placement,
                    sheet_thickness=t,
                    preserve_core_origin=preserve_endcap_core_origin,
                ))

            final_cuts = tuple(certified.cut_polygons or ())
            cut_polygon = unary_union(final_cuts) if final_cuts else None
            solved_material = apply_verified_endcap_relief_material(
                endcap_render_data.material, final_cuts
            )
            if solved_material.is_empty:
                return AssemblyBackprojectedReliefSolution(
                    cut_polygon, tuple(certified.corner_reliefs), tuple(certified_projections),
                    endcap_render_data, False, FlatInterferenceProjection((), (), 0),
                    trust_level=CertifiedReliefStatus.ENGINE_CONFLICT.value,
                    rule_id=certified.rule_id,
                    rule_revision=certified.rule_revision,
                    joint_signature=tuple(dict(item) for item in tuple(certified.rule.joint_signature or ())),
                    shadow_validation={
                        "reason": "certified rule removed all material",
                        "geometry_inputs": list(getattr(certified.rule, "geometry_inputs", ()) or ()),
                        "geometry_evidence": dict(getattr(certified, "geometry_evidence", {}) or {}),
                    },
                )
            solved_render = _render_data_rebuilt_from_material(endcap_render_data, solved_material)

            verify_segments = []
            verify_points = []
            verify_pairs = 0
            has_material_penetration = False
            verification_tolerance = 1e-5
            for _corner_name, component in certified_components:
                probe = solved_render.material.intersection(component)
                projection = _project_probe_material(
                    probe_material=probe,
                    box_body_world_surface=body_world_surface,
                    box_body_world_solid=body_world_solid,
                    endcap_reference_local=full_reference_local,
                    endcap_x_profile=endcap_x_profile,
                    endcap_y_profile=endcap_y_profile,
                    endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                    endcap_placement=endcap_placement,
                    sheet_thickness=t,
                    preserve_core_origin=preserve_endcap_core_origin,
                )
                penetrates = projection_has_material_penetration(
                    projection, probe, tolerance=verification_tolerance
                )
                if penetrates:
                    mid_projection = _project_probe_mid_surface(
                        probe_material=probe,
                        box_body_world_surface=body_world_surface,
                        box_body_world_solid=body_world_solid,
                        endcap_reference_local=full_reference_local,
                        endcap_x_profile=endcap_x_profile,
                        endcap_y_profile=endcap_y_profile,
                        endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                        endcap_placement=endcap_placement,
                        sheet_thickness=t,
                    )
                    mid_clear = not projection_has_material_penetration(
                        mid_projection, probe, tolerance=verification_tolerance
                    )
                    if mid_clear:
                        # Certified structural-contact rules intentionally end
                        # exactly at a mating line.  Physical +/-T/2 skins can
                        # still intersect as surface contact, but the certified
                        # answer remains authoritative when the semantic
                        # mid-surface is clear.
                        penetrates = False
                    elif _projection_within_material_boundary_band(
                        projection, probe, tolerance=max(0.02, t * 0.01 if t > 0.0 else 0.02)
                    ):
                        penetrates = False
                verify_segments.extend(projection.segments_2d)
                verify_points.extend(projection.points_2d)
                verify_pairs += projection.pair_count
                if penetrates:
                    has_material_penetration = True
            final_residual = FlatInterferenceProjection(
                tuple(verify_segments), tuple(verify_points), verify_pairs
            )
            verified = not has_material_penetration
            trust = (
                certified.trust_level.value if verified
                else CertifiedReliefStatus.ENGINE_CONFLICT.value
            )
            return AssemblyBackprojectedReliefSolution(
                cut_polygon_2d=cut_polygon,
                corner_reliefs=tuple(certified.corner_reliefs),
                projections=tuple(certified_projections),
                solved_render_data=solved_render,
                verified=verified,
                residual_projection=final_residual,
                trust_level=trust,
                rule_id=certified.rule_id,
                rule_revision=certified.rule_revision,
                joint_signature=tuple(dict(item) for item in tuple(certified.rule.joint_signature or ())),
                shadow_validation={
                    "policy": certified.rule.solver_shadow_policy,
                    "verified": bool(verified),
                    "residual_pair_count": int(final_residual.pair_count),
                    "geometry_inputs": list(getattr(certified.rule, "geometry_inputs", ()) or ()),
                    "geometry_evidence": dict(getattr(certified, "geometry_evidence", {}) or {}),
                },
            )

    if assembly_joint is not None:
        from .assembly_joint import AssemblyJointRelation
        relation = getattr(assembly_joint, "relation", None)
        try:
            relation = relation if isinstance(relation, AssemblyJointRelation) else AssemblyJointRelation(str(relation))
        except Exception:
            relation = None
        if relation is AssemblyJointRelation.WRAP:
            ownership = joint_relief_ownership(assembly_joint)
            # Current EndCap fallback can only remove EndCap material.  For WRAP
            # the outer subject must be preserved and the wrapped target owns
            # relief. Refuse an unsafe subject cut until the generalized target
            # flat-mapper path handles this Joint.
            return AssemblyBackprojectedReliefSolution(
                cut_polygon_2d=None, corner_reliefs=(), projections=(),
                solved_render_data=endcap_render_data, verified=False,
                residual_projection=FlatInterferenceProjection((), (), 0),
                trust_level="FAILED", rule_id=None, rule_revision=None,
                shadow_validation={
                    "reason": "WRAP_RELIEF_OWNER_IS_TARGET",
                    "preserve_part": ownership.preserve_part,
                    "relief_part": ownership.relief_part,
                    "joint_id": str(assembly_joint.joint_id),
                },
            )

    if not bool(allow_3d_fallback):
        return AssemblyBackprojectedReliefSolution(
            cut_polygon_2d=None,
            corner_reliefs=(),
            projections=(),
            solved_render_data=endcap_render_data,
            verified=False,
            residual_projection=FlatInterferenceProjection((), (), 0),
            trust_level="FAILED",
            rule_id=None,
            rule_revision=None,
            shadow_validation={"reason": "NO_CERTIFIED_RULE_AND_3D_FALLBACK_DISABLED"},
        )

    raw_cuts = {}
    all_projections = []
    current_material = restored
    residual_projection = FlatInterferenceProjection((), (), 0)

    for _iteration in range(max(1, int(max_iterations))):
        changed = False
        residual_segments = []
        residual_points = []
        residual_pairs = 0
        for corner_name, component in components:
            probe = current_material.intersection(component)
            projection = _project_probe_material(
                probe_material=probe,
                box_body_world_surface=body_world_surface,
                box_body_world_solid=body_world_solid,
                endcap_reference_local=full_reference_local,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                endcap_placement=endcap_placement,
                sheet_thickness=t,
            )
            all_projections.append(projection)
            # Solve with a stricter interior tolerance than final refold
            # verification.  Otherwise a few-micron crossing can be accepted too
            # early, then topology/replay leaves a visible retained boundary
            # crossing (自訂(10) Tail).
            if not projection_has_material_penetration(
                projection, probe, tolerance=1e-6
            ):
                continue
            residual_segments.extend(projection.segments_2d)
            residual_points.extend(projection.points_2d)
            residual_pairs += projection.pair_count
            result = derive_corner_relief_from_flat_interference(
                relief_component=component,
                segments_2d=projection.segments_2d,
                blank_bounds=blank_bounds,
                corner_name=corner_name,
                clearance=0.0,
            )
            if result is None:
                continue
            previous = raw_cuts.get(corner_name)
            combined = result.cut_polygon_2d if previous is None else unary_union([previous, result.cut_polygon_2d])
            if previous is None or float(combined.area) > float(previous.area) + 1e-7:
                raw_cuts[corner_name] = combined
                changed = True
        residual_projection = FlatInterferenceProjection(
            tuple(residual_segments), tuple(residual_points), residual_pairs
        )
        if not residual_projection.has_interference:
            break
        if not changed:
            break
        raw_union = unary_union(list(raw_cuts.values())) if raw_cuts else None
        current_material = restored if raw_union is None else restored.difference(raw_union)
        if not current_material.is_valid:
            current_material = current_material.buffer(0)

    # Numerical triangle intersections can leave mirror-equivalent corner cuts
    # a few microns apart.  When the canonical cut shapes are already within a
    # tight manufacturing tolerance, harmonize them by taking the shared union.
    # This removes triangulation noise without forcing genuinely asymmetric
    # geometry to become symmetric.
    mirror_pairs = (("bottom_left", "bottom_right"), ("top_left", "top_right"))
    mirror_tolerance = max(0.01, min(0.05, t * 0.01 if t > 0.0 else 0.01))
    x_geometry_is_symmetric = (
        _folded_profile_is_mirror_symmetric(box_body_x_profile, tolerance=1e-6)
        and _folded_profile_is_mirror_symmetric(endcap_x_profile, tolerance=1e-6)
    )
    component_lookup = {name: component for name, component in components}
    for left_name, right_name in mirror_pairs:
        left_cut = raw_cuts.get(left_name)
        right_cut = raw_cuts.get(right_name)
        if left_cut is None or right_cut is None:
            continue
        left_canonical = _canonical_corner_geometry(left_cut, blank_bounds, left_name)
        right_canonical = _canonical_corner_geometry(right_cut, blank_bounds, right_name)

        force_structural_mirror = False
        if x_geometry_is_symmetric:
            left_component = component_lookup.get(left_name)
            right_component = component_lookup.get(right_name)
            if left_component is not None and right_component is not None:
                left_component_canonical = _canonical_corner_geometry(
                    left_component, blank_bounds, left_name
                )
                right_component_canonical = _canonical_corner_geometry(
                    right_component, blank_bounds, right_name
                )
                force_structural_mirror = (
                    float(left_component_canonical.hausdorff_distance(
                        right_component_canonical
                    )) <= 1e-6
                )

        if (
            not force_structural_mirror
            and float(left_canonical.hausdorff_distance(right_canonical)) > mirror_tolerance
        ):
            continue
        # Symmetric physical geometry must have symmetric collision evidence.
        # Union is conservative: if triangulation misses one mirrored crossing,
        # retain the evidence seen on the opposite, physically identical side.
        common = unary_union([left_canonical, right_canonical])
        raw_cuts[left_name] = _physical_corner_geometry(common, blank_bounds, left_name)
        raw_cuts[right_name] = _physical_corner_geometry(common, blank_bounds, right_name)

    # Apply clearance A once, after the physical collision envelope has converged.
    a = max(0.0, float(clearance or 0.0))
    blank = box(minx, miny, maxx, maxy)
    corner_reliefs = []
    final_cuts = []
    structural_contact_snaps = set()
    topology_normalized_corners = set()
    component_by_name = {name: component for name, component in components}
    topology_snap_tolerance = max(0.01, t * 0.005 if t > 0.0 else 0.01)
    # Dynamic 3D solving owns the size, but the existing corner component owns
    # the legal manufacturing topology (single-stage vs two-stage).  This rule
    # also applies to flat-X OVERLAY parts: skipping normalization there lets
    # triangle-skin intersection noise invent a tiny second stage.
    for corner_name, raw_cut in raw_cuts.items():
        component = component_by_name.get(corner_name)
        if component is not None:
            raw_cut = _normalize_corner_cut_to_component_topology(
                raw_cut, component, corner_name, blank_bounds,
                snap_tolerance=topology_snap_tolerance,
            )
            topology_normalized_corners.add(corner_name)
            raw_cut, contact_snapped = _snap_single_stage_cut_to_structural_contact(
                raw_cut,
                corner_name,
                blank_bounds,
                box_body_x_profile=box_body_x_profile,
                endcap_x_profile=endcap_x_profile,
                sheet_thickness=t,
            )
            if contact_snapped:
                structural_contact_snaps.add(corner_name)
        final_cut = _expand_orthogonal_corner_cut_with_clearance(
            raw_cut, corner_name, blank_bounds, a
        ) if a > 0.0 else raw_cut
        if not final_cut.is_valid:
            final_cut = final_cut.buffer(0)
        measurement = _measure_canonical_corner_cut(
            final_cut, corner_name, blank_bounds, a
        )
        corner_reliefs.append(BackprojectedCornerRelief(
            corner_name=corner_name, cut_polygon_2d=final_cut, measurement=measurement
        ))
        final_cuts.append(final_cut)

    cut_polygon = unary_union(final_cuts) if final_cuts else None

    # Production replay uses the exact same corner-scoped helper as
    # Manufacturing API.  The probe may restore the whole blank, but only
    # corners with verified replacement cuts are restored into final material.
    solved_material = apply_verified_endcap_relief_material(
        endcap_render_data.material, final_cuts
    )
    if solved_material.is_empty:
        return AssemblyBackprojectedReliefSolution(
            cut_polygon, tuple(corner_reliefs), tuple(all_projections),
            endcap_render_data, False, residual_projection
        )
    solved_render = _render_data_rebuilt_from_material(endcap_render_data, solved_material)

    # Fresh verification after clearance: every remaining piece in each legacy
    # corner domain must be free of non-coplanar physical crossings.
    verify_segments = []
    verify_points = []
    verify_pairs = 0
    has_material_penetration = False
    # Final refold verification works on independently triangulated physical
    # skins. Coincident cut/mating edges can therefore land a few nanometres
    # inside retained material. Treat only this numerical boundary band as
    # contact; the iterative solver itself still uses the stricter default.
    verification_tolerance = 1e-5
    for _corner_name, component in components:
        probe = solved_render.material.intersection(component)
        projection = _project_probe_material(
            probe_material=probe,
            box_body_world_surface=body_world_surface,
            box_body_world_solid=body_world_solid,
            endcap_reference_local=full_reference_local,
            endcap_x_profile=endcap_x_profile,
            endcap_y_profile=endcap_y_profile,
            endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
            endcap_placement=endcap_placement,
            sheet_thickness=t,
        )
        penetrates = projection_has_material_penetration(
            projection, probe, tolerance=verification_tolerance
        )
        if penetrates and (
            _corner_name in structural_contact_snaps
            or _corner_name in topology_normalized_corners
        ):
            mid_projection = _project_probe_mid_surface(
                probe_material=probe,
                box_body_world_surface=body_world_surface,
                box_body_world_solid=body_world_solid,
                endcap_reference_local=full_reference_local,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                endcap_placement=endcap_placement,
                sheet_thickness=t,
            )
            mid_clear = not projection_has_material_penetration(
                mid_projection, probe, tolerance=verification_tolerance
            )
            if _corner_name in structural_contact_snaps and mid_clear:
                # Exact structural contact is legal.  Keep physical skins as the
                # primary evidence, but reject their T/2 contact-band crossing when
                # the semantic mid-surface confirms no retained-material penetration.
                penetrates = False
            elif (
                _corner_name in topology_normalized_corners
                and mid_clear
                and _projection_within_material_boundary_band(
                    projection, probe, tolerance=topology_snap_tolerance
                )
            ):
                # Topology normalization may replace a micron-scale triangle-skin
                # stair step with the approved single/two-stage manufacturing edge.
                # Forgive only a boundary-band crossing when the semantic mid-surface
                # is also clear; deeper retained-material penetration still fails.
                penetrates = False
        verify_segments.extend(projection.segments_2d)
        verify_points.extend(projection.points_2d)
        verify_pairs += projection.pair_count
        if penetrates:
            has_material_penetration = True
    final_residual = FlatInterferenceProjection(
        tuple(verify_segments), tuple(verify_points), verify_pairs
    )
    return AssemblyBackprojectedReliefSolution(
        cut_polygon_2d=cut_polygon,
        corner_reliefs=tuple(sorted(corner_reliefs, key=lambda item: item.corner_name)),
        projections=tuple(all_projections),
        solved_render_data=solved_render,
        verified=not has_material_penetration,
        residual_projection=final_residual,
    )
