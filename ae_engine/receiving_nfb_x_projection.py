# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

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
    # Assembly placement subtracts snapshot["w"]/2 from accumulated columns.
    # An inconsistent cabinet W silently shifts every NFB shadow in later
    # columns, even when the target W800 panel itself is geometrically valid.
    total_columns_w = sum(float(column[0]) for column in columns)
    cabinet_w = float(data.get("w", 0.0))
    if (not isfinite(cabinet_w) or not isfinite(total_columns_w)
            or abs(total_columns_w - cabinet_w) > 1e-6):
        raise ValueError("OPEN-X-W800x3 column widths do not equal cabinet world width")
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
    # Vault 門.dxf also carries inner CUTTING apertures. Only the unique
    # perimeter with the certified full blank W/H can define the X datum.
    # Never confuse a real internal aperture with a second physical sheet.
    outlines = [p for p in render.scene.primitives if isinstance(p, PolylinePrimitive)
                and p.closed and p.layer.upper() == "CUTTING"]
    outer = [
        shape for shape in outlines
        if abs(max(float(p.x) for p in shape.points)
               - min(float(p.x) for p in shape.points)
               - panel.unfolded_width) <= 1e-6
        and abs(max(float(p.y) for p in shape.points)
                - min(float(p.y) for p in shape.points)
                - panel.unfolded_height) <= 1e-6
    ]
    if len(outer) != 1:
        raise ValueError("OPEN-X-W800x3 unresolved unique manufactured outer CUTTING")
    xs = [float(p.x) for p in outer[0].points]
    blank_min, blank_max = min(xs), max(xs)
    if (not all(isfinite(x) and x > 0 for x in (lower_fold, core, upper_fold))
            or abs(blank_max-blank_min-723.0)>1e-6
            or abs(topo.width-723.0)>1e-6
            or abs(core-(panel.width-2*panel.thickness))>1e-6
            or abs(lower_fold-19.0)>1e-6
            or abs(upper_fold-19.0)>1e-6
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
    canonical = resolve_w800_three_whd_x(
        snapshot, inner_door_id, slot_index=slot_index,
    )
    source_x = centers[slot_index]
    if abs((source_x - source_left) - canonical.blank_x_from_cutting_left_mm) > 1e-6:
        raise ValueError("OPEN-X-W800x3 source does not match WHD canonical blank X")
    # Source only corroborates; actual CUTTING and assembly set the datum.
    cell = canonical.cell_key
    uv_x = canonical.blank_uv_x_mm
    blank_min = canonical.blank_cutting_left_x_mm
    core = canonical.folded_core_width_mm
    return NfbW800ThreeXShadow(
        rule_id="RECEIVING-NFB-OPEN-X-800-3",
        revision=RULE_REVISION,
        status=SHADOW_ONLY,
        source_dxf_sha256=_SOURCE_SHA,
        closed_reference_sha256=_CLOSED_SHA,
        source_aperture_handles=tuple(original_source["aperture_side_handles"][slot_index]),
        part_id=canonical.part_id, cell_key=cell, slot_index=slot_index,
        source_center_x_mm=source_x,
        source_left_x_mm=source_left,
        source_right_x_mm=source_left+723.0,
        blank_uv_x_mm=uv_x,
        finished_face_x_from_left_mm=canonical.finished_face_x_from_left_mm,
        candidate_box_world_x_mm=canonical.box_world_x_mm,
        blank_cutting_min_x_mm=blank_min,
        unfolded_blank_width_mm=canonical.unfolded_blank_width_mm,
        folded_core_width_mm=core,
    )


def reverse_shadow_w800_three_source_x(
    snapshot: Mapping[str, object], inner_door_id: str,
    *, candidate_world_x_mm: float, original_source: Mapping[str, object],
    closed_cutting_reference: Mapping[str, object],
) -> float:
    """Reconstruct source X under the SAME unapproved, positive-X assumption."""
    source_left, centers = _source_three_centers(original_source, closed_cutting_reference)
    x = float(candidate_world_x_mm)
    if not isfinite(x):
        raise ValueError("OPEN-X shadow world X must be finite")
    matches = []
    for slot in range(3):
        candidate = resolve_w800_three_whd_x(
            snapshot, inner_door_id, slot_index=slot,
        )
        if abs(x - candidate.box_world_x_mm) <= 1e-6:
            matches.append(slot)
    if len(matches) != 1:
        raise ValueError("OPEN-X shadow world X does not match a canonical slot")
    slot = matches[0]
    offset = reverse_w800_three_whd_x(
        snapshot, inner_door_id, slot_index=slot, box_world_x_mm=x,
    )
    if abs((centers[slot]-source_left)-offset)>1e-6:
        raise ValueError("OPEN-X source does not match WHD canonical inverse")
    return source_left+offset


# A W800x3 datum is derived from WHD's OWN manufactured CUTTING and
# physical placement. The customer DXF is neither a width nor an origin authority.
W800_THREE_DATUM_REVISION = "WHD-NFB-OPEN-X-800-3-WHD-DATUM-V1"
WHD_PART_DATUM_VERIFIED = "WHD_PANEL_X_DATUM_VERIFIED_NOT_NFB_CUTTING"
_W800_THREE_BLANK_CENTERS = (181.5, 361.5, 541.5)


@dataclass(frozen=True)
class NfbW800ThreeCanonicalX:
    rule_id: str
    revision: str
    status: str
    part_id: str
    cell_key: str
    slot_index: int
    x_direction: str
    blank_cutting_left_x_mm: float
    blank_x_from_cutting_left_mm: float
    blank_uv_x_mm: float
    finished_face_x_from_left_mm: float
    box_world_x_mm: float
    box_world_panel_center_x_mm: float
    unfolded_blank_width_mm: float
    folded_core_width_mm: float
    manufacturing_ready: bool = False
    certified_x_revision: None = None


def resolve_w800_three_whd_x(
    snapshot: Mapping[str, object], inner_door_id: str, *, slot_index: int,
) -> NfbW800ThreeCanonicalX:
    """WHD canonical CUTTING-left -> formed face -> cabinet X, source DXF independent.

    The *X datum mapping* is witnessed for W800/T2/1100 with three slots.
    No NFB model-specific CUTTING, Y placement, or manufacturing release is
    granted by this result.  Geometry must come from the live physical part.
    """
    if type(slot_index) is not int or slot_index not in (0, 1, 2):
        raise ValueError("OPEN-X-W800x3 slot index must be 0/1/2")
    panel, placement, cell, blank_left, fold_left, core = _physical_w800_basis(
        snapshot, inner_door_id
    )
    blank_from_left = _W800_THREE_BLANK_CENTERS[slot_index]
    # Actual unfold: each fold starts outside the formed face core; the
    # CUTTING min X (not customer's A1) is the positive-X blank origin.
    blank_x = blank_left + blank_from_left
    center_of_core = blank_left + fold_left + core / 2.0
    local_x = blank_x - center_of_core
    panel_cx = float(placement.world_offset[0])
    if (not isfinite(panel_cx)
            or not (blank_left + fold_left < blank_x < blank_left + fold_left + core)
            or abs(float(panel.unfolded_width) - 723.0) > 1e-6):
        raise ValueError("OPEN-X-W800x3 canonical panel X datum invalid")
    face_x = float(panel.width) / 2.0 + local_x
    if not (0.0 < face_x < float(panel.width)):
        raise ValueError("OPEN-X-W800x3 canonical finished face X invalid")
    return NfbW800ThreeCanonicalX(
        rule_id="RECEIVING-NFB-OPEN-X-800-3",
        revision=W800_THREE_DATUM_REVISION,
        status=WHD_PART_DATUM_VERIFIED,
        part_id=panel.stable_id, cell_key=cell, slot_index=slot_index,
        x_direction="WHD_CUTTING_POSITIVE_X_EQUALS_BOX_WORLD_POSITIVE_X",
        blank_cutting_left_x_mm=blank_left,
        blank_x_from_cutting_left_mm=blank_from_left,
        blank_uv_x_mm=blank_x,
        finished_face_x_from_left_mm=face_x,
        box_world_x_mm=panel_cx+local_x,
        box_world_panel_center_x_mm=panel_cx,
        unfolded_blank_width_mm=float(panel.unfolded_width),
        folded_core_width_mm=core,
    )


def reverse_w800_three_whd_x(
    snapshot: Mapping[str, object], inner_door_id: str,
    *, slot_index: int, box_world_x_mm: float,
) -> float:
    """Inverse WHD box world X to this slot's CUTTING-left offset.

    Reject an arbitrary X posing as the requested NFB slot; do not snap,
    silently infer an X, or transfer witness to another topology.
    """
    expected = resolve_w800_three_whd_x(
        snapshot, inner_door_id, slot_index=slot_index,
    )
    world = float(box_world_x_mm)
    if not isfinite(world):
        raise ValueError("OPEN-X-W800x3 canonical world X must be finite")
    _panel, _placement, _cell, blank_left, fold, core = _physical_w800_basis(
        snapshot, inner_door_id
    )
    uv = blank_left + fold + core / 2.0 + (
        world - expected.box_world_panel_center_x_mm
    )
    distance = uv - blank_left
    if abs(distance - expected.blank_x_from_cutting_left_mm) > 1e-6:
        raise ValueError("OPEN-X-W800x3 world X does not match this canonical slot")
    return distance
