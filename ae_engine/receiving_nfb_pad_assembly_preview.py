# -*- coding: utf-8 -*-
"""Display-only true-sheet PAD skins projected onto committed real NFB bases.

All inputs come from the current selected Bay, per-model V5 CSV, common PAD
tooling file, and the already cut actual Base Plate FinalScene. Never add
these trial skins to manufacturing parts, CNC/DXF exports, or certified BOM.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from .receiving_nfb_pad_part import build_nfb_pad_draft_part
from .receiving_nfb_pad_generator import (
    generate_nfb_pad_patterns, read_pad_tooling_rule,
)


@dataclass(frozen=True)
class NfbPadDisplaySkin:
    part_id: str
    parent_base_id: str
    owner_hole_id: str
    world_triangles: tuple
    base_front_world_z_mm: float
    pad_front_world_z_mm: float
    rise_mm: float
    source_flat_and_bend_verified: bool = True
    actual_base_squares_present: bool = True
    four_tab_mesh_mating_verified: bool = False
    base_slab_collision_verified: bool = False
    manufacturing_ready: bool = False
    assembly_contact_certified: bool = False


def pad_physical_preview_world_mesh(pattern, *, parent_base_id,
                                    owner_hole_id, world_x, world_y,
                                    base_front_world_z_mm,rotation_deg=0):
    """Draw full T sheet from the common unfolded CUTTING & signed BENDs.

    The material's center NFB web is at local Z=0. Four small tabs extend
    two mm below each regular leg tip and enter the BASE's matching squares.
    Base Plate front skin (physical, not a DXF plane) is the anchor.
    """
    from .assembly_geometry import folded_mesh_from_polygon, thicken_triangle_surface
    from .assembly_geometry_primitives import (
        triangle_bounds, place_assembly_triangles,
    )
    tooling = read_pad_tooling_rule()
    draft = build_nfb_pad_draft_part(
        pattern,parent_base_id=parent_base_id,owner_hole_id=owner_hole_id,
    )
    # A rule for two-mm tab engagement is only certified in the native T2
    # source. The generic calculator still supports different thickness,
    # but must not pretend a non-matching tab physically fits a T3 base.
    if not isclose(pattern.plate_thickness_mm, tooling.tab_projection_mm, abs_tol=1e-7):
        raise ValueError("PAD_TABS_MUST_MATCH_PHYSICAL_BASE_SHEET_T")
    folded = folded_mesh_from_polygon(
        draft.render_data.material, draft.x_profile,draft.y_profile,
        fold_guides=draft.render_data.fold_guides,
    )
    bounds = triangle_bounds(folded)
    if bounds is None:
        raise ValueError("PAD_FOLDED_FINALSCENE_MESH_EMPTY")
    zmin,zmax=map(float,bounds[2])
    if (not isclose(zmax,0.,abs_tol=1e-5)
            or not isclose(
                zmin,-pattern.rise_mm-pattern.plate_thickness_mm/2,
                abs_tol=1e-5)):
        raise ValueError("PAD_SIGNED_REAL_FOLD_NOT_INTO_BASE")
    # The sheet's front physical skin, not its zero-thickness mid-surface,
    # must meet the smaller NFB's mounting face at depth rise from the base.
    target_core_mid_z = (float(base_front_world_z_mm) +
                         pattern.rise_mm-pattern.plate_thickness_mm/2)
    mesh_mid_z=(zmin+zmax)/2
    placed = place_assembly_triangles(
        folded,"offset",None,
        (float(world_x),float(world_y),target_core_mid_z+mesh_mid_z),
    )
    # Rotate the REAL folded 3D mesh about its selected NFB installation
    # centre using the EXACT V5 axes that also rotated the Base squares.
    from .receiving_nfb_v5_configured_inner_door import AXES
    if type(rotation_deg) is not int or rotation_deg not in AXES:
        raise ValueError("PAD_SELECTED_NFB_ROTATION_INVALID")
    ux,uy=AXES[rotation_deg]
    cx,cy=float(world_x),float(world_y)
    rotated=tuple(tuple((
        cx + (float(pt[0])-cx)*ux[0] + (float(pt[1])-cy)*uy[0],
        cy + (float(pt[0])-cx)*ux[1] + (float(pt[1])-cy)*uy[1],
        float(pt[2]),
    ) for pt in face) for face in placed)
    solids=tuple(thicken_triangle_surface(rotated,pattern.plate_thickness_mm))
    if not solids:
        raise ValueError("PAD_FOLDED_PHYSICAL_SHEET_EMPTY")
    return solids


def build_committed_pad_assembly_display(snapshot, assembly_parts):
    """Read-only assembled PAD skins, only when real bottom square cuts exist."""
    from collections.abc import Mapping
    if (not isinstance(snapshot,Mapping)
            or snapshot.get("model") not in ("受電箱","RECEIVING")
            or snapshot.get("nfb_config_submitted") is not True):
        return ()
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes
    from .receiving_nfb_numeric_catalog import model_spec
    from .receiving_base_plate_config import receiving_base_plate_values
    from .receiving_nfb_world_skin_datums import resolve_receiving_nfb_world_skin_datums
    from .receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
    from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    from .sheetmetal_part_adapters import (
        RECEIVING_BASE_PATTERN_LEFT,RECEIVING_BASE_PATTERN_RIGHT,
    )
    sourced=_submitted_csv_holes(snapshot)
    if not sourced:
        return ()
    door_id, holes = sourced
    physical=receiving_base_plate_values(snapshot)
    if physical is None or physical["receiving_bend_pattern"] not in (
            RECEIVING_BASE_PATTERN_LEFT,RECEIVING_BASE_PATTERN_RIGHT):
        return ()  # existing CENTER double-fold already solves depth.
    parts=tuple(assembly_parts or ())
    by_key={str(part.part_key):part for part in parts}
    if len(by_key)!=len(parts):
        raise ValueError("PAD_DUPLICATE_BASE_SOURCE_PART")
    raw_t=snapshot.get("t")
    if isinstance(raw_t,bool):
        raise ValueError("PAD_INVALID_PLATE_THICKNESS")
    count=holes[0].layer_count
    result=[]
    for tier in range(count):
        entries=tuple(h for h in holes if h.slot_index==tier)
        if not entries:
            continue
        parent=("base_plate" if count==1 else f"base_plate:nfb_layer:{tier}")
        base=by_key.get(parent)
        if base is None:
            raise ValueError("PAD_REAL_PARENT_BASE_MISSING")
        meta=dict(base.render_data.metadata or {})
        if (meta.get("receiving_bend_pattern") not in (
                RECEIVING_BASE_PATTERN_LEFT,RECEIVING_BASE_PATTERN_RIGHT)
                or meta.get("nfb_v5_trial_status") is None):
            return ()  # normal editor has not published an actual cut trial
        source_specs=[]
        for entry in entries:
            from .receiving_nfb_model_identity import parse_numeric_model_ref
            identity=parse_numeric_model_ref(entry.model_ref)
            if identity is None or identity[0]!=entry.brand:
                raise ValueError("PAD_COMMITTED_CSV_IDENTITY_DRIFT")
            source=model_spec(*identity)
            if source is None or not source.dimensionally_complete:
                raise ValueError("PAD_COMMITTED_CSV_MISSING_GEOMETRY")
            source_specs.append(source)
        patterns=generate_nfb_pad_patterns(
            source_specs,plate_thickness_mm=float(snapshot["t"]),
            tooling=read_pad_tooling_rule(),
        )
        if not patterns:
            continue
        squares=dict(meta.get("nfb_v5_pad_square_owners") or ())
        if (set(squares)!={entries[p.switch_index].physical_hole_id for p in patterns}
                or any(count!=4 for count in squares.values())):
            raise ValueError("PAD_BASE_LOCATOR_SQUARES_NOT_SAME_OWNER")
        # Ownership count is only metadata. Recheck every actual 6x6
        # CUTTING polygon against this NFB's four selected CSV screw centres
        # and its rotated source geometry before any 3D skin may appear.
        from .receiving_nfb_pad_base_mating import (
            verify_real_pad_base_square_cuts,
            verify_real_pad_mesh_tab_engagement,
            verify_pad_solid_inside_real_base_cutouts,
        )
        real_square_uv_by_owner={}
        for candidate in patterns:
            selected=entries[candidate.switch_index]
            real_square_uv_by_owner[selected.physical_hole_id] = (
                verify_real_pad_base_square_cuts(
                    base.render_data,candidate,
                    owner_hole_id=selected.physical_hole_id,
                    rotation_deg=selected.rotation_deg,
                )
            )
        world=resolve_receiving_nfb_world_skin_datums(
            snapshot,inner_door_id=door_id,
            reference_nfb_depth_mm=max(s.depth_mm for s in source_specs),
        )
        local_front, shallow=receiving_base_actual_local_nfb_skins(
            snapshot,physical,
        )
        if (shallow is not None
                or not isclose(
                    float(base.offset[2])+local_front,
                    world.base_nfb_face_world_z_mm,abs_tol=1e-5
                )):
            raise ValueError("PAD_BASE_FRONT_REAL_SKIN_Z_DRIFT")
        for pattern in patterns:
            entry=entries[pattern.switch_index]
            y=project_nfb_inner_door_nominal_y(
                snapshot,door_id,layer_count=count,slot_index=tier,
            )
            if not isclose(float(base.offset[1]),float(y.box_world_y_mm),abs_tol=1e-5):
                raise ValueError("PAD_NFB_Y_DOES_NOT_MATCH_BASE_TIER")
            triangles=pad_physical_preview_world_mesh(
                pattern,parent_base_id=parent,owner_hole_id=entry.physical_hole_id,
                world_x=entry.world_x_mm,world_y=y.box_world_y_mm,
                base_front_world_z_mm=world.base_nfb_face_world_z_mm,
                rotation_deg=entry.rotation_deg,
            )
            # The real solid-skin tab tips must each ENTER its own physical
            # selected-CSV square, at the actual Base Plate world Z. A render
            # with a shifted or upside-down PAD is now refused, not displayed
            # on the strength of four source square counts alone.
            real_squares_world=verify_real_pad_mesh_tab_engagement(
                triangles,pattern,
                real_square_uv_by_owner[entry.physical_hole_id],
                world_x_mm=entry.world_x_mm,
                world_y_mm=y.box_world_y_mm,
                base_front_world_z_mm=world.base_nfb_face_world_z_mm,
                rotation_deg=entry.rotation_deg,
            )
            verify_pad_solid_inside_real_base_cutouts(
                triangles,real_squares_world,
                base_front_world_z_mm=world.base_nfb_face_world_z_mm,
                thickness_mm=pattern.plate_thickness_mm,
            )
            result.append(NfbPadDisplaySkin(
                part_id=f"nfb_pad:{entry.physical_hole_id}",
                parent_base_id=parent,
                owner_hole_id=entry.physical_hole_id,
                world_triangles=triangles,
                base_front_world_z_mm=world.base_nfb_face_world_z_mm,
                pad_front_world_z_mm=world.base_nfb_face_world_z_mm+pattern.rise_mm,
                rise_mm=pattern.rise_mm,
                four_tab_mesh_mating_verified=True,
                base_slab_collision_verified=True,
            ))
    return tuple(result)
