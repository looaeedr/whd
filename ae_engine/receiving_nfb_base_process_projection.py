# -*- coding: utf-8 -*-
"""#1502: project NFB source Color30/212 onto an ACTUAL base work face.

The inner-door verified physical hole is the sole installation-center owner.
The actual base part/mating face must be supplied by the existing assembly
and manufacturing scene. No CAD drawing origin, guessed W/2 or ear hole may
replace that center. This module projects exact upper-source NFB process
geometry; it does not manufacture a new base outline or release a DXF.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians, sin
from typing import Mapping

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .manufacturing_render_data import PartRenderData
from .receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)
from .receiving_nfb_upper_base_source import (
    NfbUpperBaseSourceProcess, OBSERVED,
)
from .receiving_nfb_lower_fixing_source import NfbVerifiedLowerFixingGroup
from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from .sheetmetal_drawing import DrawingScene

_TOL = 1e-6
_ANGLES = (0, 90, 180, 270)
_STATUS = "BASE_PROCESS_PROJECTED_ACTUAL_FACE_NOT_RELEASED"


@dataclass(frozen=True)
class NfbActualBaseWorkFace:
    """An existing physical base's *flat* face, expressed in unfolded UV.

    The owner derives these facts from the CURRENT assembly/part geometry.
    An illustrative DXF cannot create this interface. The face center and
    material polygon are not new editable NFB coordinates.
    """
    physical_part_id: str
    actual_render: PartRenderData
    world_face_center_xy_mm: tuple[float, float]
    unfolded_face_center_uv_mm: tuple[float, float]
    face_outline_uv_mm: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class NfbProjectedBaseProcess:
    physical_part_id: str
    source_sha256: str
    source_model: str
    owner_hole_ids: tuple[str, ...]
    cutting: tuple[object, ...]
    marking: tuple[object, ...]
    status: str = _STATUS
    manufacturing_ready: bool = False

    def source_process_scene(self) -> DrawingScene:
        """Process overlay for the existing scene composer; never a full blank."""
        scene = DrawingScene()
        scene.extend(self.cutting)
        scene.extend(self.marking)
        return scene


def _xy(raw, label):
    try:
        result = tuple(float(v) for v in raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(label + " has invalid coordinates") from exc
    if len(result) != 2 or not all(isfinite(v) for v in result):
        raise ValueError(label + " needs finite XY")
    return result


def _work_face(face: NfbActualBaseWorkFace):
    if not isinstance(face, NfbActualBaseWorkFace):
        raise TypeError("NFB base projection needs real physical work face")
    if not isinstance(face.physical_part_id, str) or not face.physical_part_id.strip():
        raise ValueError("NFB base physical identity missing")
    render = face.actual_render
    if not isinstance(render, PartRenderData):
        raise ValueError("NFB base needs existing manufactured render data")
    if render.unfolded_topology is None:
        raise ValueError("NFB base real unfolded topology missing")
    if render.unfolded_topology.piece_id != face.physical_part_id:
        raise ValueError("NFB base actual topology/physical identity mismatch")
    if str(render.metadata.get("stable_id", "")) != face.physical_part_id:
        raise ValueError("NFB base render has no matching stable ID")
    if render.material is None or not hasattr(render.material, "covers"):
        raise ValueError("NFB base final material missing")
    face_poly = Polygon(face.face_outline_uv_mm)
    if not face_poly.is_valid or face_poly.is_empty or face_poly.area <= _TOL:
        raise ValueError("NFB base real work face invalid")
    if not render.material.buffer(_TOL).covers(face_poly):
        raise ValueError("NFB base work face outside actual cut material")
    world = _xy(face.world_face_center_xy_mm, "base assembly face world center")
    uv = _xy(face.unfolded_face_center_uv_mm, "base unfolded flat face center")
    if not face_poly.buffer(_TOL).covers(Point(*uv)):
        raise ValueError("NFB base UV center outside actual face")
    return face_poly, world, uv


def _projection(point, *, pivot, world_hole, face_world, face_uv, rotation_deg):
    x, y = _xy(point, "native NFB source point")
    dx, dy = x - pivot[0], y - pivot[1]
    angle = radians(rotation_deg)
    rotated_x = cos(angle) * dx - sin(angle) * dy
    rotated_y = sin(angle) * dx + cos(angle) * dy
    return (
        face_uv[0] + world_hole[0] + rotated_x - face_world[0],
        face_uv[1] + world_hole[1] + rotated_y - face_world[1],
    )


def project_verified_nfb_base_process(
    *,
    snapshot: Mapping[str, object],
    inner_door_id: str,
    verified_inner_door: NfbValidatedInnerDoorRender,
    native_source: NfbUpperBaseSourceProcess,
    lower_fixing: NfbVerifiedLowerFixingGroup,
    target: NfbActualBaseWorkFace,
) -> NfbProjectedBaseProcess:
    """Map the SAME real NFB source onto one independently built base.

    Uses verified door world-X, canonical door Y and source pivot/rotation.
    Requires existing target structural scene + physical topology + material
    and rejects any cut outside the base flat face or into existing holes.
    EAR-to-box/plate mounting holes are neither generated nor relocated here.
    """
    if not isinstance(verified_inner_door, NfbValidatedInnerDoorRender):
        raise TypeError("NFB base requires real inner-door manufacturing proof")
    door = verified_inner_door
    if (door.manufacturing_ready is not True
            or door.render_data.metadata.get("nfb_trial_status") != VALIDATED
            or door.render_data.metadata.get("nfb_trial_export_approved") is not True):
        raise ValueError("NFB inner-door actual CUTTING must be verified first")
    if not isinstance(native_source, NfbUpperBaseSourceProcess):
        raise TypeError("NFB base requires typed original source geometry")
    if (native_source.status != OBSERVED
            or native_source.manufacturing_ready is not False
            or native_source.source_sha256 != door.source_sha256
            or native_source.indexed_filename != door.indexed_model_key[1]):
        raise ValueError("NFB base source differs from approved inner-door NFB")
    if (not isinstance(lower_fixing, NfbVerifiedLowerFixingGroup)
            or lower_fixing.manufacturing_ready is not False
            or lower_fixing.source_sha256 != door.source_sha256
            or lower_fixing.indexed_filename != door.indexed_model_key[1]
            or len(lower_fixing.circles) != 4):
        raise ValueError("NFB native lower screw group not matched to verified door")
    from .assembly_placement import resolve_inner_door_panel_placement
    resolved_door = resolve_inner_door_panel_placement(snapshot, inner_door_id)
    if door.part_id != resolved_door.stable_id:
        raise ValueError("NFB source-verified door belongs to another physical part")
    placements = tuple(door.verified_hole_locations)
    if (not placements or len(placements) != len(door.physical_hole_ids)
            or {row[0] for row in placements} != set(door.physical_hole_ids)
            or len(set(door.physical_hole_ids)) != len(door.physical_hole_ids)):
        raise ValueError("NFB verified hole ID/position identity incomplete")
    face_poly, face_world, face_uv = _work_face(target)
    pivot = _xy(native_source.upper_color150_center_xy_mm, "NFB upper main opening center")
    if not native_source.base_cutting_circles and not native_source.base_cutting_closed_loops:
        raise ValueError("NFB base source has no native CUTTING")
    cutting = DrawingScene()
    marking = DrawingScene()
    cuts = []
    for physical_id, world_x, layers, slot, angle in placements:
        if (not isinstance(physical_id, str) or not physical_id.strip()
                or type(angle) is not int or angle not in _ANGLES
                or type(world_x) not in (int, float) or not isfinite(world_x)):
            raise ValueError("NFB base hole owner/rotation/position invalid")
        y = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id, layer_count=layers, slot_index=slot,
        )
        if y.part_id != door.part_id:
            raise ValueError("NFB base Y not on source-verified inner-door owner")
        world_hole = (float(world_x), float(y.box_world_y_mm))

        def move(point):
            return _projection(
                point, pivot=pivot, world_hole=world_hole,
                face_world=face_world, face_uv=face_uv, rotation_deg=angle,
            )

        for shape in native_source.base_cutting_circles:
            if shape.radius_mm <= 0 or not isfinite(shape.radius_mm):
                raise ValueError("NFB source native circle radius invalid")
            center = move(shape.center_xy_mm)
            geom = Point(*center).buffer(shape.radius_mm, quad_segs=32)
            cuts.append(geom)
            cutting.add_circle(center, shape.radius_mm, layer="CUTTING",
                               color=30, source_type="NFB_COLOR30",
                               source_id=f"{physical_id}:{shape.source_handle}")
        # Only four LOWER-group CIRCLEs are NFB fixing screws. Their
        # native quartet centroid (not its schematic drawing Y) is placed
        # under the SAME verified main-opening center as the upper group.
        lower_center = _xy(lower_fixing.screw_group_center_xy_mm,
                           "NFB native lower screw quartet center")
        for screw in lower_fixing.circles:
            if not isfinite(screw.radius_mm) or screw.radius_mm <= 0:
                raise ValueError("NFB native screw hole radius invalid")
            center = _projection(
                screw.center_xy_mm, pivot=lower_center,
                world_hole=world_hole, face_world=face_world,
                face_uv=face_uv, rotation_deg=angle,
            )
            cuts.append(Point(*center).buffer(screw.radius_mm, quad_segs=32))
            cutting.add_circle(
                center, screw.radius_mm, layer="CUTTING", color=30,
                source_type="NFB_LOWER_NATIVE_FIXING_CIRCLE",
                source_id=f"{physical_id}:{screw.source_handle}",
            )
        for shape in native_source.base_cutting_closed_loops:
            points = tuple(move(xy) for xy in shape.vertices_xy_mm)
            geom = Polygon(points)
            if not geom.is_valid or geom.area <= _TOL:
                raise ValueError("NFB projected Color30 closed CUTTING invalid")
            cuts.append(geom)
            cutting.add_polyline(points, layer="CUTTING", closed=True, color=30)
        for mark in native_source.base_marking_entities:
            if any(abs(float(b)) > _TOL for b in mark.bulges):
                raise ValueError("NFB Color212 marking curved source unsupported")
            pts = tuple(move(point) for point in mark.vertices_xy_mm)
            if len(pts) < 2:
                raise ValueError("NFB source Color212 marking path invalid")
            marking.add_polyline(pts, layer="MARKING", closed=False, color=212)
    if not cuts:
        raise ValueError("NFB base cannot have empty generated holes")
    # Existing material already includes any ear-mount holes. The new NFB
    # contours must fit undamaged face material, not overwrite ear mounting.
    for contour in cuts:
        if (not face_poly.buffer(_TOL).covers(contour)
                or not target.actual_render.material.buffer(_TOL).covers(contour)):
            raise ValueError("NFB fixing hole crosses actual base face/ear mounting material")
    if len(cuts) > 1 and sum(x.area for x in cuts) > unary_union(cuts).area + _TOL:
        raise ValueError("NFB base has overlapping NFB CUTTING groups")
    for m in marking.primitives:
        coords = tuple((float(p.x), float(p.y)) for p in m.points)
        if not face_poly.buffer(_TOL).covers(LineString(coords)):
            raise ValueError("NFB marking outside actual base face")
    return NfbProjectedBaseProcess(
        physical_part_id=target.physical_part_id,
        source_sha256=native_source.source_sha256,
        source_model=native_source.indexed_filename,
        owner_hole_ids=door.physical_hole_ids,
        cutting=tuple(cutting.primitives),
        marking=tuple(marking.primitives),
    )



def project_one_original_nfb_into_actual_base(
    *,
    snapshot: Mapping[str, object],
    inner_door_id: str,
    verified_inner_door: NfbValidatedInnerDoorRender,
    source_path,
    profile,
    lower_reference_handle: str,
    target: NfbActualBaseWorkFace,
) -> NfbProjectedBaseProcess:
    """ONE original SHA and ONE verified door for both native source groups.

    This is the callable MFG-2 preparation boundary for a real base face.
    Both upper process contours and lower four NFB fixing circles are
    extracted from the same original operator-indexed DXF in one operation,
    then projected together. Source-only/geometry-only results are NOT a
    finished factory base plate or an authorization to export DXF.
    """
    from .receiving_nfb_upper_base_source import inspect_nfb_upper_base_native_process
    from .receiving_nfb_lower_fixing_source import inspect_nfb_lower_four_fixing_circles
    if (verified_inner_door.source_sha256 != profile.source_sha256
            or verified_inner_door.indexed_model_key !=
                (profile.brand, profile.indexed_filename)):
        raise ValueError("NFB source and verified inner door do not match")
    upper = inspect_nfb_upper_base_native_process(
        source_path, profile=profile,
        lower_reference_handle=lower_reference_handle,
    )
    lower = inspect_nfb_lower_four_fixing_circles(
        source_path, profile=profile,
        lower_reference_handle=lower_reference_handle,
    )
    return project_verified_nfb_base_process(
        snapshot=snapshot, inner_door_id=inner_door_id,
        verified_inner_door=verified_inner_door,
        native_source=upper, lower_fixing=lower, target=target,
    )



@dataclass(frozen=True)
class NfbComposedActualBase:
    """Real existing structural base plus NFB process on its FinalScene.

    Never silently promote a source-only adapter to full MFG-2 release.
    """
    projection: NfbProjectedBaseProcess
    render_data: PartRenderData
    manufacturing_ready: bool = False


def compose_projected_nfb_on_actual_base(
    *, target: NfbActualBaseWorkFace,
    projection: NfbProjectedBaseProcess,
) -> NfbComposedActualBase:
    """Merge one NFB process onto ONE already manufactured base part scene.

    The outer base blank, fold guides and EAR attachment cuts remain owned by
    the existing part. The NFB native circles/closed loops are added as real
    CUTTING, marking as real MARKING, and material is recomputed from the
    shared final scene: preview/3D/export all can consume one geometry result.
    The per-physical-part readiness/export policy still blocks whole MFG-2
    until actual formed EAR/plate manufacturing validation is completed.
    """
    from .manufacturing_render_data import material_polygon_from_final_scene
    if (not isinstance(projection, NfbProjectedBaseProcess)
            or projection.manufacturing_ready is not False
            or projection.physical_part_id != target.physical_part_id):
        raise ValueError("NFB overlay does not match actual base geometry owner")
    face_poly, _, _ = _work_face(target)
    actual = target.actual_render
    if not isinstance(actual.scene, DrawingScene):
        raise ValueError("NFB real base requires shared DrawingScene source")
    scene=DrawingScene()
    scene.extend(actual.scene.primitives)
    scene.extend(projection.cutting)
    scene.extend(projection.marking)
    material=material_polygon_from_final_scene(scene)
    if material.is_empty or material.area >= actual.material.area - _TOL:
        raise ValueError("NFB composite base did not produce actual material CUTTING")
    if not face_poly.buffer(_TOL).covers(
        material.intersection(face_poly)
    ):
        raise ValueError("NFB composited material invalid for base face")
    metadata={
        **dict(actual.metadata),
        "nfb_source_sha256": projection.source_sha256,
        "nfb_source_model": projection.source_model,
        "nfb_physical_hole_ids": projection.owner_hole_ids,
        "nfb_base_process_status": projection.status,
        "nfb_base_mfg2_release_approved": False,
    }
    return NfbComposedActualBase(
        projection=projection,
        render_data=PartRenderData(
            scene=scene, material=material,
            fold_guides=actual.fold_guides,
            metadata=metadata,
            unfolded_topology=actual.unfolded_topology,
            box_body_face_contexts=actual.box_body_face_contexts,
        ),
    )
