# -*- coding: utf-8 -*-
"""#1494: reversible *shadow* X projection from actual W800x3 source evidence.

The nominal table contains only neighbor distances, NOT absolute centers.
W800x3 is the sole known source for three horizontal 28x58 rectangle centers.
Only actual Receiving inner-door panel/placement/topology and CUTTING outline
may define its blank-to-box shadow. Source matches never register an approved
NFB X rule or enable manufacturing CUTTING.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .assembly_placement import resolve_inner_door_panel_placement
from .cabinet_types import policy as cabinet_family_policy
from .manufacturing_api import build_inner_door_panel_render_data
from .sheetmetal_drawing import PolylinePrimitive
from .sheetmetal_part_adapters import derive_door_layout_cells

RULE_REVISION = "WHD-NFB-OPEN-X-1494-SHADOW-V1"
PREVIEW_ONLY = "PREVIEW_ONLY"
SHADOW_ONLY = "SHADOW_GEOMETRY_NOT_APPROVED_FOR_CUTTING"
_NOMINAL_PITCH: dict[tuple[int, int], tuple[float, ...] | None] = {
    (600, 1): None,
    (750, 1): None,
    (800, 1): None,
    (600, 2): (180.0,),
    (750, 2): (310.0,),
    (800, 2): (325.0,),
    (800, 3): (180.0, 180.0),
}
_SOURCE_SHA = "2e3143124a4bd81394143a12b464d78dd030f479c0da2d02279b1dd502ad4416"
_CLOSED_SHA = "f2a30d89a8127eb7296b9269fe464a3f6786674ee4ea9d6097a35cae5050604e"


@dataclass(frozen=True)
class NfbNominalXGroup:
    rule_id: str
    revision: str
    gate: str
    outer_width_mm: int
    nfb_count: int
    adjacent_distances_mm: tuple[float, ...] | None
    status: str = PREVIEW_ONLY
    certified_x_revision: None = None
    absolute_centers_mm: None = None
    manufacturing_ready: bool = False


def nominal_nfb_x_group(outer_width_mm: int, nfb_count: int) -> NfbNominalXGroup:
    """Never infer absolute X from a nominal center pitch or a one-unit W/2."""
    if type(outer_width_mm) is not int or type(nfb_count) is not int:
        raise ValueError("OPEN-X requires explicitly approved integer W and N")
    key = (outer_width_mm, nfb_count)
    if key not in _NOMINAL_PITCH:
        raise ValueError("OPEN-X unsupported combination; no default centering")
    return NfbNominalXGroup(
        rule_id=f"RECEIVING-NFB-OPEN-X-{outer_width_mm}-{nfb_count}",
        revision=RULE_REVISION, gate="OPEN-X-ONE" if nfb_count == 1 else "OPEN-X-ROW",
        outer_width_mm=outer_width_mm, nfb_count=nfb_count,
        adjacent_distances_mm=_NOMINAL_PITCH[key],
    )


@dataclass(frozen=True)
class NfbW800ThreeXShadow:
    rule_id: str
    revision: str
    status: str
    source_dxf_sha256: str
    closed_reference_sha256: str
    source_aperture_handles: tuple[str, ...]
    part_id: str
    cell_key: str
    slot_index: int
    source_center_x_mm: float
    source_left_x_mm: float
    source_right_x_mm: float
    blank_uv_x_mm: float
    finished_face_x_from_left_mm: float
    candidate_box_world_x_mm: float
    blank_cutting_min_x_mm: float
    unfolded_blank_width_mm: float
    folded_core_width_mm: float
    certified_x_revision: None = None
    manufacturing_ready: bool = False


def _source_three_centers(source: Mapping[str, object],
                          closed: Mapping[str, object]) -> tuple[float, tuple[float, ...]]:
    if (source.get("source_sha256") != _SOURCE_SHA
            or closed.get("source_sha256") != _CLOSED_SHA
            or source.get("blank_left_handle") != "A1"
            or source.get("blank_right_handle") != "A0"
            or not closed.get("source_a1_segment_identical_to_closed_cutting")
            or closed.get("physical_blank_to_face_box_transform_certified") is not False
            or closed.get("nfb_model_main_hole_certified") is not False):
        raise ValueError("OPEN-X-W800x3 original evidence identity / release gate mismatch")
    entities = {str(e["handle"]): e for e in source["entities"]}
    left, right = entities["A1"], entities["A0"]
    if (left["type"] != "LINE" or right["type"] != "LINE"
            or left["layer"] != "0" or right["layer"] != "0"
            or left["color"] != 7 or right["color"] != 7):
        raise ValueError("OPEN-X-W800x3 source horizontal authority unknown")
    left_x, right_x = float(left["start"][0]), float(right["start"][0])
    if (left["start"][0] != left["end"][0]
            or right["start"][0] != right["end"][0]
            or abs(right_x - left_x - 723.0) > 1e-6):
        raise ValueError("OPEN-X-W800x3 source boundary width mismatch")
    # Compare actual A1/A0 segments, including their *endpoints*, to the
    # customer-supplied CLOSED CUTTING reference rather than just bbox width.
    outline = tuple(closed["outer"]["vertices_xy_bulge"])
    if (closed.get("layer") != "CUTTING" or closed.get("layer_aci") != 3
            or not closed["outer"].get("closed")
            or len(outline) < 4):
        raise ValueError("OPEN-X-W800x3 closed CUTTING reference invalid")
    segments = tuple((outline[i], outline[(i+1) % len(outline)])
                     for i in range(len(outline)))
    for edge in (left, right):
        a, b = tuple(edge["start"][:2]), tuple(edge["end"][:2])
        matching = [1 for p, q in segments if p[2] == 0 and (
            (tuple(p[:2]) == a and tuple(q[:2]) == b)
            or (tuple(p[:2]) == b and tuple(q[:2]) == a)
        )]
        if len(matching) != 1:
            raise ValueError("OPEN-X-W800x3 source A1/A0 has no identical closed CUTTING side")
    centers = []
    matching_closed_holes = []
    for handles in source["aperture_side_handles"]:
        if len(handles) != 4 or len(set(handles)) != 4:
            raise ValueError("OPEN-X-W800x3 source aperture sides are ambiguous")
        sides = [entities[h] for h in handles]
        if any(e["type"] != "LINE" or e["layer"] != "0" or e["color"] != 7
               for e in sides):
            raise ValueError("OPEN-X-W800x3 source aperture side provenance differs")
        side_x = {float(e["start"][0]) for e in sides}
        if (len(side_x) != 2
                or any(e["start"][0] != e["end"][0] for e in sides)
                or abs(max(side_x) - min(side_x) - 28.0) > 1e-6):
            raise ValueError("OPEN-X-W800x3 source aperture sides are ambiguous")
        side_y = [float(p[1]) for e in sides
                  for p in (e["start"], e["end"])]
        bottom, top = min(side_y), max(side_y)
        if abs(top - bottom - 58.0) > 1e-6:
            raise ValueError("OPEN-X-W800x3 source aperture height mismatch")
        # The customer drawing has three apertures, while the closed reference
        # has two rows of three. Match the actual XY hole footprint, not only
        # the common X columns (which could hide a different Y/physical hole).
        source_bbox = (min(side_x), bottom, max(side_x), top)
        matched = [i for i, hole in enumerate(closed["rectangular_holes"])
                   if len(hole["bbox"]) == 4 and all(
                       abs(float(a) - float(b)) <= 1e-6
                       for a, b in zip(hole["bbox"], source_bbox))]
        if len(matched) != 1:
            raise ValueError("OPEN-X-W800x3 source aperture has no identical closed CUTTING hole")
        matching_closed_holes.append(matched[0])
        centers.append((min(side_x) + max(side_x)) / 2.0)
    if len(matching_closed_holes) != 3 or len(set(matching_closed_holes)) != 3:
        raise ValueError("OPEN-X-W800x3 source apertures do not uniquely match closed CUTTING")
    if len(centers) != 3 or any(abs(v - expect) > 1e-6 for v, expect in zip(
        (v-left_x for v in centers), (181.5, 361.5, 541.5)
    )):
        raise ValueError("OPEN-X-W800x3 source centers mismatch")
    # Independently require the closed reference to contain each 28-mm-wide
    # hole center, without conflating other six inner contours with NFB holes.
    observed = {round((float(r["bbox"][0])+float(r["bbox"][2]))/2, 6)
                for r in closed["rectangular_holes"]}
    if (len(closed["rectangular_holes"]) != 6 or
            {round(v, 6) for v in centers} != observed):
        raise ValueError("OPEN-X-W800x3 closed reference aperture center mismatch")
    return left_x, tuple(centers)


def _physical_w800_basis(snapshot: Mapping[str, object], inner_door_id: str):
    data = dict(snapshot or {})
    if data.get("model") != "受電箱" or not data.get("multi_door_enabled"):
        raise ValueError("OPEN-X-W800x3 requires enabled Receiving inner door")
    columns = data.get("door_layout_columns") or ()
    cells = derive_door_layout_cells(columns)
    owners = [r for r in data.get("inner_doors", ()) if isinstance(r, dict)
              and r.get("stable_id") == inner_door_id]
    if len(owners) != 1:
        raise ValueError("OPEN-X-W800x3 requires unique inner-door owner")
    cell_key = owners[0].get("cell_key")
    cell = next((c for c in cells if f"{c.column_index}:{c.row_index}" == cell_key), None)
    if (cell is None or abs(float(cell.start_width)-800.0) > 1e-7
            or cell.row_index != 0 or abs(float(cell.start_height)-1100.0) > 1e-7
            or abs(float(data["t"])-2.0) > 1e-7):
        raise ValueError("OPEN-X-W800x3 only witnessed W800 T2 top 1100 cell")
    panels = [p for p in cabinet_family_policy.derive_inner_door_panels(data)
              if p.inner_door_id == inner_door_id and p.cell_key == cell_key]
    if len(panels) != 1:
        raise ValueError("OPEN-X-W800x3 cannot resolve unique physical panel")
    panel = panels[0]
    placement = resolve_inner_door_panel_placement(data, inner_door_id)
    if (panel.stable_id != placement.stable_id
            or placement.anchor != f"inner_door_frame_opening:{inner_door_id}"
            or tuple(placement.rotation) != (0.0, 0.0, 0.0)):
        raise ValueError("OPEN-X-W800x3 physical part/rotation authority mismatch")
    render = build_inner_door_panel_render_data(panel)
    topo = render.unfolded_topology
    if topo is None or topo.piece_id != panel.stable_id:
        raise ValueError("OPEN-X-W800x3 manufacturing topology absent")
    segments = topo.x_segments
    if tuple(s.name for s in segments) != (
        "inner_door_fold_left", "inner_door_face_width", "inner_door_fold_right",
    ):
        raise ValueError("OPEN-X-W800x3 unexpected manufactured X segments")
    lower_fold, core, upper_fold = [float(s.length) for s in segments]
    outlines = [p for p in render.scene.primitives if isinstance(p, PolylinePrimitive)
                and p.closed and p.layer.upper() == "CUTTING"]
    if len(outlines) != 1:
        raise ValueError("OPEN-X-W800x3 unresolved actual manufactured outer CUTTING")
    xs = [float(p.x) for p in outlines[0].points]
    blank_min, blank_max = min(xs), max(xs)
    if (not all(isfinite(x) and x > 0 for x in (lower_fold, core, upper_fold))
            or abs(blank_max-blank_min-723.0)>1e-6
            or abs(topo.width-723.0)>1e-6
            or abs(core-(panel.width-2*panel.thickness))>1e-6
            or abs(panel.width-689.0)>1e-6
            or abs(lower_fold+core+upper_fold-723.0)>1e-6):
        raise ValueError("OPEN-X-W800x3 real part core/blank conflict")
    return panel, placement, cell_key, blank_min, lower_fold, core


def shadow_w800_three_source_x(
    snapshot: Mapping[str, object], inner_door_id: str,
    *, slot_index: int, original_source: Mapping[str, object],
    closed_cutting_reference: Mapping[str, object],
) -> NfbW800ThreeXShadow:
    """Conditional positive-X source->blank->face->world translation (NOT approval).

    A1 in the closed CUSTOMER reference is proven; A1 identity with WHD's
    GENERATED manufacturing blank and box-world axis direction is NOT signed.
    Result is strictly preview evidence for this W800/T2 three-hole case.
    """
    if type(slot_index) is not int or slot_index not in (0, 1, 2):
        raise ValueError("OPEN-X-W800x3 slot index must be 0/1/2")
    source_left, centers = _source_three_centers(original_source, closed_cutting_reference)
    panel, placement, cell, blank_min, fold, core = _physical_w800_basis(snapshot, inner_door_id)
    source_x = centers[slot_index]
    uv_x = blank_min + (source_x-source_left)
    actual_core_mid_x = blank_min+fold+core/2.0
    from_center = uv_x-actual_core_mid_x
    if not (blank_min+fold < uv_x < blank_min+fold+core):
        raise ValueError("OPEN-X-W800x3 shadow center outside formed core")
    return NfbW800ThreeXShadow(
        rule_id="RECEIVING-NFB-OPEN-X-800-3",
        revision=RULE_REVISION,
        status=SHADOW_ONLY,
        source_dxf_sha256=_SOURCE_SHA,
        closed_reference_sha256=_CLOSED_SHA,
        source_aperture_handles=tuple(original_source["aperture_side_handles"][slot_index]),
        part_id=panel.stable_id, cell_key=cell, slot_index=slot_index,
        source_center_x_mm=source_x,
        source_left_x_mm=source_left,
        source_right_x_mm=source_left+723.0,
        blank_uv_x_mm=uv_x,
        finished_face_x_from_left_mm=float(panel.width)/2.0+from_center,
        candidate_box_world_x_mm=float(placement.world_offset[0])+from_center,
        blank_cutting_min_x_mm=blank_min,
        unfolded_blank_width_mm=float(panel.unfolded_width),
        folded_core_width_mm=core,
    )


def reverse_shadow_w800_three_source_x(
    snapshot: Mapping[str, object], inner_door_id: str,
    *, candidate_world_x_mm: float, original_source: Mapping[str, object],
    closed_cutting_reference: Mapping[str, object],
) -> float:
    """Reconstruct source X under the SAME unapproved, positive-X assumption."""
    source_left, _ = _source_three_centers(original_source, closed_cutting_reference)
    _, placement, _, _, fold, core = _physical_w800_basis(snapshot, inner_door_id)
    x = float(candidate_world_x_mm)
    if not isfinite(x):
        raise ValueError("OPEN-X shadow world X must be finite")
    from_center = x-float(placement.world_offset[0])
    if not (-core/2.0 < from_center < core/2.0):
        raise ValueError("OPEN-X shadow world X outside physical door core")
    return source_left+(fold+core/2.0+from_center)
