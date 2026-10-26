# -*- coding: utf-8 -*-
"""#1502/#1503: resolve Receiving inner-door NFB Z datum from TRUE folded skins.

This module reads the SAME manufactured Inner Door panel and finite BEND guides
as the 3D viewer. It intentionally never calls assembly placement's old rear
wall-centered Base Plate offset (-D/2+T+BEND/2) and never equates the
inner-door placement centre to its physical face.

The verified datum is suitable for deriving selected NFB/base working faces.
Its reference-depth fixing-plate face is a *virtual arithmetic witness* only;
actual fixed-ear Z must use the entire brand CSV maximum via
receiving_tier_ear_z_targets, NEVER a tier's selected NFB depth.
It is NOT welding or DXF manufacturing certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class ReceivingNfbWorldSkinDatum:
    inner_door_outer_skin_world_z_mm: float
    inner_door_inner_skin_world_z_mm: float
    base_nfb_face_world_z_mm: float
    base_back_skin_world_z_mm: float
    fixing_plate_contact_skin_world_z_mm: float
    fixing_plate_back_skin_world_z_mm: float
    shallow_nfb_face_world_z_mm: float | None = None
    shallow_base_back_skin_world_z_mm: float | None = None

    @property
    def deep_nfb_net_clearance_mm(self) -> float:
        """Actual inner-door INSIDE skin to base NFB mounting FRONT skin."""
        return self.inner_door_inner_skin_world_z_mm - self.base_nfb_face_world_z_mm


def receiving_inner_door_real_world_skins(
    snapshot: Mapping[str, object], inner_door_id: str,
) -> tuple[float, float]:
    """Outward(+Z), inward(-Z) true folded INNER DOOR CORE physical skins.

    Source authority: Receiving inner-door FinalScene material, actual 19-mm
    four-side profiles/BEND guides, and resolve_inner_door_panel_placement.
    Use mapped flat UV on the *core face* rather than taking folded envelope
    outermost Z (which belongs to the return folds, not the NFB opening).
    Surface midlines and app placement offsets are never called clearances.
    """
    from .cabinet_types import policy as family
    from .inner_door_panels import inner_door_panel_part_profiles
    from .manufacturing_scene_orchestration import build_inner_door_panel_render_data
    from .assembly_placement import resolve_inner_door_panel_placement
    from .assembly_geometry import (
        folded_mesh_with_flat_uv_from_polygon, world_skin_with_flat_uv,
    )
    if not isinstance(snapshot, Mapping):
        raise TypeError("Receiving inner-door geometry snapshot must be a mapping")
    if str(snapshot.get("model") or "") not in ("受電箱", "RECEIVING"):
        raise ValueError("NFB Z skin datum requires Receiving cabinet")
    panels = [p for p in family.derive_inner_door_panels(snapshot)
              if str(p.inner_door_id) == str(inner_door_id)]
    if len(panels) != 1:
        raise ValueError("NFB datum must have exactly one physical inner door")
    panel = panels[0]
    render = build_inner_door_panel_render_data(panel)
    profiles = inner_door_panel_part_profiles([panel])[panel.stable_id]
    mapped = folded_mesh_with_flat_uv_from_polygon(
        render.material, profiles["X"], profiles["Y"],
        fold_guides=tuple(render.fold_guides or ()),
    )
    if not mapped:
        raise ValueError("NFB inner-door actual folded material is empty")
    placement = resolve_inner_door_panel_placement(snapshot, inner_door_id)
    world = world_skin_with_flat_uv(
        mapped, placement.placement_kind,
        (float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
        offset=placement.world_offset,
        sheet_thickness=float(panel.thickness),
    )
    tol = 1e-6
    xmin, xmax = float(panel.fold_left), float(panel.unfolded_width - panel.fold_right)
    ymin, ymax = float(panel.fold_bottom), float(panel.unfolded_height - panel.fold_top)
    # Clipped by exact fold stations; triangles with all three UV vertices in
    # the core belong to the NFB mounting face rather than one of four legs.
    inside = [
        row for row in world
        if all(xmin-tol <= float(x) <= xmax+tol and
               ymin-tol <= float(y) <= ymax+tol
               for x, y in row.flat)
    ]
    if not inside:
        raise ValueError("NFB inner-door folded central physical face missing")
    zs = [float(p[2]) for tri in inside for p in tri.world]
    if not all(isfinite(v) for v in zs):
        raise ValueError("NFB inner-door skin has nonfinite world Z")
    inward, outward = min(zs), max(zs)
    if abs(outward-inward-float(panel.thickness))>tol:
        raise ValueError("NFB central panel skins are not one true material T apart")
    # No formula here assumes the operator's 80 mm is a physical skin Z.
    return outward, inward


def resolve_receiving_nfb_world_skin_datums(
    snapshot: Mapping[str, object], *, inner_door_id: str,
    reference_nfb_depth_mm: float, secondary_nfb_depth_mm: float | None = None,
    fixing_plate_thickness_mm: float = 3.0,
) -> ReceivingNfbWorldSkinDatum:
    """Project true inner-door physical surfaces to base/ear TARGET faces.

    Cabinet world +Z is outward. This produces an ideal reference-depth
    base/ear skin chain for comparisons. It does NOT move the installed ears.
    Fixed-ear Z is independently locked to brand CSV maximum depth in the
    active Set/Bay's ear-target resolver; a shallower selected model may
    leave a base/ear gap until verified depth compensation is installed.
    Side-panel weld MARKING is a separate acceptance gate.
    """
    from .receiving_nfb_depth_surface_policy import receiving_nfb_second_side_fold_mm
    outer, inner = receiving_inner_door_real_world_skins(snapshot, inner_door_id)
    deep=float(reference_nfb_depth_mm)
    base_t=float(snapshot.get("t",0))
    ear_t=float(fixing_plate_thickness_mm)
    if not all(isfinite(v) and v>0 for v in (deep,base_t,ear_t)):
        raise ValueError("NFB depth/base/fixing thickness must be positive finite")
    shallow_front = shallow_back = None
    if secondary_nfb_depth_mm is not None:
        shallow=float(secondary_nfb_depth_mm)
        receiving_nfb_second_side_fold_mm(
            reference_nfb_depth_mm=deep,
            secondary_nfb_depth_mm=shallow,
            base_plate_thickness_mm=base_t,
        )
        shallow_front = inner-shallow
        shallow_back = shallow_front-base_t
    front = inner-deep
    back = front-base_t
    return ReceivingNfbWorldSkinDatum(
        inner_door_outer_skin_world_z_mm=outer,
        inner_door_inner_skin_world_z_mm=inner,
        base_nfb_face_world_z_mm=front,
        base_back_skin_world_z_mm=back,
        fixing_plate_contact_skin_world_z_mm=back,
        fixing_plate_back_skin_world_z_mm=back-ear_t,
        shallow_nfb_face_world_z_mm=shallow_front,
        shallow_base_back_skin_world_z_mm=shallow_back,
    )
