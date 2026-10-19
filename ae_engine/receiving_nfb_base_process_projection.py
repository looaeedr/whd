# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

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
class NfbNativeFixingAlias:
    """Two native handles proven to describe ONE screw on ONE physical NFB."""
    source_sha256: str
    owner_hole_id: str
    upper_handle: str
    lower_handle: str
    center_uv_mm: tuple[float, float]
    radius_mm: float


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
    native_fixing_aliases: tuple[NfbNativeFixingAlias, ...] = ()
    verified_hole_locations: tuple[tuple[str, float, int, int, int], ...] = ()

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
    # Work faces may already contain EAR mounting slots. Their voids are
    # intentional holes, not evidence that the surrounding face is absent.
    # Compare the face against the EXISTING structural exterior envelope;
    # the individual NFB contours are checked against actual remaining
    # material below, so an NFB circle may never re-cut an EAR hole.
    from shapely.geometry import Polygon as _Polygon
    faces = getattr(render.material, "geoms", (render.material,))
    exterior = unary_union(tuple(
        _Polygon(piece.exterior) for piece in faces
        if hasattr(piece, "exterior")
    ))
    if exterior.is_empty or not exterior.buffer(_TOL).covers(face_poly):
        raise ValueError("NFB base work face outside actual plate exterior")
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



def _native_fixing_alias_pairs(upper, lower, pivot):
    """Require a full bijection before collapsing a repeated native quartet.

    Comparison is in the original groups' relative coordinates, before any
    placement or rotation. No cross-unit, cross-source or proximity dedupe.
    Partial matches remain unsafe instead of silently dropping process holes.
    """
    center = _xy(lower.screw_group_center_xy_mm, "native screw centroid")
    pairs = []
    for circle in upper.base_cutting_circles:
        matches = tuple(screw for screw in lower.circles if
            abs(circle.radius_mm - screw.radius_mm) <= _TOL
            and all(abs((a-b) - (c-d)) <= _TOL for a,b,c,d in
                    zip(circle.center_xy_mm, pivot, screw.center_xy_mm, center)))
        if len(matches) > 1:
            raise ValueError("NFB native fixing quartet alias ambiguous")
        if matches:
            pairs.append((circle, matches[0]))
    if not pairs:
        return ()
    if (len(upper.base_cutting_circles) != 4 or len(pairs) != 4
            or len({s.source_handle for _, s in pairs}) != 4
            or len({u.source_handle for u, _ in pairs}) != 4
            or any(u.source_handle == s.source_handle for u, s in pairs)):
        raise ValueError("NFB native fixing quartet alias incomplete")
    return tuple(pairs)

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
    aliases = []
    alias_pairs = _native_fixing_alias_pairs(native_source, lower_fixing, pivot)
    aliased_upper = {upper.source_handle for upper, _ in alias_pairs}
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
            if shape.source_handle in aliased_upper:
                continue
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
        for upper, screw in alias_pairs:
            aliases.append(NfbNativeFixingAlias(
                source_sha256=native_source.source_sha256,
                owner_hole_id=physical_id,
                upper_handle=upper.source_handle,
                lower_handle=screw.source_handle,
                center_uv_mm=move(upper.center_xy_mm),
                radius_mm=upper.radius_mm,
            ))
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
            marking.add_polyline(pts, layer="MARKING", closed=mark.source_closed, color=212)
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
        native_fixing_aliases=tuple(aliases),
        verified_hole_locations=placements,
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
        "nfb_native_fixing_aliases": projection.native_fixing_aliases,
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





def build_existing_receiving_base_with_verified_nfb(
    *,
    snapshot: Mapping[str, object],
    inner_door_id: str,
    base_spec,
    verified_inner_door: NfbValidatedInnerDoorRender,
    source_path,
    profile,
    lower_reference_handle: str,
) -> NfbComposedActualBase:
    """Assemble cabinet-X-centered Base Plate, project verified NFB screws.

    The upper Door NFB height owns the Base Plate Y placement, NOT plate
    finished height. BasePlatePartSpec retains the original physical blank
    and folded 670-mm fixing pattern, permanently cabinet X-centered. Per-
    NFB horizontal X shifts ONLY native screw CUTTING coordinates into
    that fixed plate's work-face UV. Outer Door lower compartment has no plate.
    """
    from .contracts import BasePlatePartSpec
    from .manufacturing_api import build_part_render_data
    from .sheetmetal_part_adapters import (
        RECEIVING_BASE_PATTERN_CENTER, RECEIVING_BASE_PATTERNS,
        derive_door_layout_cells,
    )
    from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    from .sheetmetal_drawing import PolylinePrimitive
    from math import isfinite

    if not isinstance(base_spec, BasePlatePartSpec):
        raise TypeError("NFB base needs original BasePlatePartSpec owner")
    if str(base_spec.model_name or "").strip() not in ("受電箱","RECEIVING"):
        raise ValueError("NFB Base Plate owner must be Receiving cabinet")
    if base_spec.receiving_bend_pattern not in RECEIVING_BASE_PATTERNS:
        raise ValueError("NFB Base Plate needs actual physical bend-pattern decision")
    stable_id = str(base_spec.physical_id or "").strip()
    if not stable_id or stable_id.startswith("base_plate_c"):
        raise ValueError("NFB Base Plate needs its own actual physical identity, not legacy Door-cell plates")
    if (abs(float(snapshot.get("w",0.)) - float(base_spec.width)) > _TOL
            or abs(float(snapshot.get("t",0.)) - float(base_spec.thickness)) > _TOL):
        raise ValueError("NFB Base Plate does not belong to current box W/T")
    inner = next((
        row for row in (snapshot.get("inner_doors") or ())
        if isinstance(row,Mapping) and
        str(row.get("stable_id") or "").strip() == str(inner_door_id).strip()
    ),None)
    if inner is None:
        raise ValueError("NFB selected inner door absent from real cabinet topology")
    try:
        column,row = (int(v) for v in str(inner.get("cell_key") or "").split(":"))
    except (TypeError,ValueError) as exc:
        raise ValueError("NFB inner door has invalid owning cell") from exc
    cells = derive_door_layout_cells(snapshot.get("door_layout_columns") or ())
    cell = next((x for x in cells if (x.column_index,x.row_index)==(column,row)),None)
    if cell is None or row != 0 or abs(float(cell.start_height)-1100.0)>_TOL:
        raise ValueError("NFB opening is not on certified upper 1100-mm cell")
    if float(base_spec.height) > float(cell.start_height) or float(base_spec.height) <= 0:
        raise ValueError("NFB actual base cannot exceed upper installation cell")

    # The NFB family supports one physical installation Y per plate.
    # For two separate switch layers the caller must supply TWO real plate
    # identities/parts: never invent two sets of ear holes on one plate.
    locations=tuple(verified_inner_door.verified_hole_locations)
    if not locations:
        raise ValueError("NFB verified installation group has no holes")
    centers=[]
    for physical_id, x, count, slot, rotation in locations:
        if not isinstance(x,(int,float)) or not isfinite(float(x)):
            raise ValueError("NFB physical X is not verified")
        yy=project_nfb_inner_door_nominal_y(
            snapshot,inner_door_id,layer_count=count,slot_index=slot,
        )
        centers.append((float(x),float(yy.box_world_y_mm)))
    if max(y for _,y in centers)-min(y for _,y in centers)>_TOL:
        raise ValueError("NFB distinct installation heights require distinct actual ear/base groups")
    # Physical Base Plate/ear mount X is invariant at the cabinet centre.
    # Only each source NFB's screw CUTTING uses its individual opening X in
    # project_one_original_nfb_into_actual_base(world_hole=...). Never
    # translate 670-mm fixed ear slots because one NFB is shifted.
    nfb_group_world_center=(
        (min(x for x,_ in centers)+max(x for x,_ in centers))/2.0,
        centers[0][1],
    )
    group_world_center=(0.0, centers[0][1])
    # The real plate must physically fit its owning upper cell. This uses
    # actual manufactured face dimensions, not the sample-DXF paper origin.
    real=build_part_render_data(base_spec)
    if real.unfolded_topology is None or real.unfolded_topology.piece_id != stable_id:
        raise ValueError("NFB existing Base Plate has no matching physical topology")
    width,height = float(real.unfolded_topology.width),float(real.unfolded_topology.height)
    from .assembly_placement import resolve_outer_door_placement
    from .sheetmetal_part_adapters import door_layout_part_key
    outer=resolve_outer_door_placement(snapshot,door_layout_part_key(cell))
    lower=float(outer.world_offset[1])-float(cell.start_height)/2.0
    upper=float(outer.world_offset[1])+float(cell.start_height)/2.0
    if (group_world_center[1]-height/2.0 < lower-_TOL
            or group_world_center[1]+height/2.0 > upper+_TOL):
        raise ValueError("NFB actual base extends outside its upper cell")
    if abs(group_world_center[0])+float(base_spec.width)/2.0 > float(snapshot["w"])/2.0+_TOL:
        raise ValueError("NFB base exterior exceeds cabinet width")

    fold_y=float(base_spec.bend)
    if base_spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_CENTER:
        # #1502: NEVER infer the mounted NFB face from the nominal 71-mm
        # unfolded side return. Original user's 受電箱底板(5).dxf has:
        # BENDING x40/73/699/732, CUTTING shoulders x74/698, T2.
        # The second BEND lines delimit the inner face with T/2 skins.
        # Consume the *actual FinalScene* finite guides for THIS part so
        # an NFB depth-pair edit also changes the mounting face.
        x_guides = sorted({
            float(guide.position)
            for guide in tuple(real.fold_guides or ())
            if str(guide.axis) == "x"
        })
        if len(x_guides) != 4:
            raise ValueError("NFB center base requires four actual side BEND guides")
        x0 = x_guides[1] + float(base_spec.thickness)/2.0
        x1 = x_guides[2] - float(base_spec.thickness)/2.0
    else:
        x0,x1=0.0,width
    y0,y1=fold_y,height-fold_y
    if x0 >= x1 or y0 >= y1:
        raise ValueError("NFB physical Base Plate has no central mounting face")
    ear_slots=tuple(x for x in real.scene.primitives
                    if isinstance(x,PolylinePrimitive)
                    and x.layer=="CUTTING" and x.closed)
    if len(ear_slots)!=5:
        raise ValueError("NFB physical base requires one exterior and four actual EAR mounts")
    target=NfbActualBaseWorkFace(
        physical_part_id=stable_id,
        actual_render=real,
        world_face_center_xy_mm=group_world_center,
        unfolded_face_center_uv_mm=((x0+x1)/2.,(y0+y1)/2.),
        face_outline_uv_mm=((x0,y0),(x1,y0),(x1,y1),(x0,y1)),
    )
    projection=project_one_original_nfb_into_actual_base(
        snapshot=snapshot,inner_door_id=inner_door_id,
        verified_inner_door=verified_inner_door,
        source_path=source_path,profile=profile,
        lower_reference_handle=lower_reference_handle,target=target,
    )
    composed=compose_projected_nfb_on_actual_base(
        target=target,projection=projection,
    )
    # Carry the SAME approved installation center into downstream 2D/3D/
    # DXF acceptance evidence. This is a world-XY mating datum, not a
    # claim that the ear's brand-dependent Z/weld face is approved.
    from dataclasses import replace
    metadata=dict(composed.render_data.metadata)
    metadata["receiving_base_ear_mount_center_world_xy_mm"]=group_world_center
    metadata["receiving_base_nfb_row_center_world_xy_mm"]=nfb_group_world_center
    metadata["receiving_base_upper_cell_key"]=f"{column}:{row}"
    metadata["receiving_base_ear_weld_z_verified"]=False
    return replace(
        composed,
        render_data=replace(composed.render_data,metadata=metadata),
    )


def validate_nfb_base_part_cutting(
    render_data: PartRenderData, *, physical_part_id: str,
) -> None:
    """Validate one actual NFB Base Plate CUTTING result, not its EAR assembly.

    Called at the production PART_ONLY boundary before the DXF is written.
    This uses the source-bound FinalScene and real unfolded part, never a
    caller-supplied approval boolean. Assembly/weld Z remains independent.
    """
    from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
    import re

    if not isinstance(render_data, PartRenderData):
        raise ValueError("NFB_BASE_PART_CUTTING_EVIDENCE_MISSING")
    metadata = render_data.metadata
    identity = str(physical_part_id or "").strip()
    topology = render_data.unfolded_topology
    if (not identity or identity.startswith("base_plate_c")
            or metadata.get("stable_id") != identity
            or topology is None or topology.piece_id != identity
            or str(metadata.get("receiving_bend_pattern") or "") not in (
                "LEFT_FLAT_SIDE", "RIGHT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD"
            )):
        raise ValueError("NFB_BASE_PART_PHYSICAL_ID_OR_BEND_PATTERN_UNVERIFIED")
    if (metadata.get("nfb_base_process_status") != _STATUS
            or not re.fullmatch(r"[0-9a-f]{64}", str(metadata.get("nfb_source_sha256") or ""))
            or not str(metadata.get("nfb_source_model") or "").lower().endswith(".dxf")):
        raise ValueError("NFB_BASE_PART_SOURCE_EVIDENCE_MISSING")
    hole_ids = metadata.get("nfb_physical_hole_ids")
    if (not isinstance(hole_ids, (tuple, list)) or not hole_ids
            or any(not isinstance(v, str) or not v for v in hole_ids)
            or len(hole_ids) != len(set(hole_ids))):
        raise ValueError("NFB_BASE_PART_HOLE_OWNERS_UNVERIFIED")
    if (render_data.material is None or render_data.material.is_empty
            or render_data.material.area <= _TOL
            or not isinstance(render_data.scene, DrawingScene)
            or topology.width <= 0 or topology.height <= 0):
        raise ValueError("NFB_BASE_PART_ACTUAL_GEOMETRY_MISSING")
    try:
        ear_center = _xy(metadata["receiving_base_ear_mount_center_world_xy_mm"], "EAR")
        nfb_center = _xy(metadata["receiving_base_nfb_row_center_world_xy_mm"], "NFB")
    except (KeyError, ValueError) as exc:
        raise ValueError("NFB_BASE_PART_MATING_XY_UNVERIFIED") from exc
    # The base/ear X MUST stay at the cabinet centre. NFB source-group X
    # is a screw-hole machining offset, not the physical plate centre, so
    # it MAY differ. Only the owning tier's Y must agree for the same plate.
    # Remaining native screw outlines are independently checked below.
    if (abs(ear_center[0]) > _TOL
            or abs(ear_center[1]-nfb_center[1]) > _TOL):
        raise ValueError("NFB_BASE_PART_MATING_XY_UNVERIFIED")

    primitives = render_data.scene.primitives
    screws = tuple(p for p in primitives
                   if isinstance(p, CirclePrimitive)
                   and p.layer == "CUTTING"
                   and p.source_type == "NFB_LOWER_NATIVE_FIXING_CIRCLE")
    uppers = tuple(p for p in primitives
                   if isinstance(p, CirclePrimitive)
                   and p.layer == "CUTTING"
                   and p.source_type == "NFB_COLOR30")
    if len(screws) != 4 * len(hole_ids):
        raise ValueError("NFB_BASE_PART_SOURCE_CUTTING_INCOMPLETE")
    screw_ids = tuple(str(getattr(p, "source_id", "") or "") for p in screws)
    if (len(set(screw_ids)) != len(screw_ids)
            or any(sum(s.startswith(hole + ":") for s in screw_ids) != 4
                   for hole in hole_ids)):
        raise ValueError("NFB_BASE_PART_SOURCE_HOLE_MAPPING_UNVERIFIED")
    aliases = metadata.get("nfb_native_fixing_aliases", ())
    if not isinstance(aliases, tuple):
        raise ValueError("NFB_BASE_PART_NATIVE_ALIAS_UNVERIFIED")
    alias_ids = set()
    upper_ids = set()
    for alias in aliases:
        if (not isinstance(alias, NfbNativeFixingAlias)
                or alias.source_sha256 != metadata["nfb_source_sha256"]
                or alias.owner_hole_id not in hole_ids
                or not alias.upper_handle or not alias.lower_handle
                or alias.upper_handle == alias.lower_handle):
            raise ValueError("NFB_BASE_PART_NATIVE_ALIAS_UNVERIFIED")
        lower_id = alias.owner_hole_id + ":" + alias.lower_handle
        upper_id = alias.owner_hole_id + ":" + alias.upper_handle
        if lower_id in alias_ids or upper_id in upper_ids:
            raise ValueError("NFB_BASE_PART_NATIVE_ALIAS_UNVERIFIED")
        alias_ids.add(lower_id)
        upper_ids.add(upper_id)
        matches = tuple(p for p in screws if p.source_id == lower_id)
        if (len(matches) != 1
                or abs(matches[0].radius - alias.radius_mm) > _TOL
                or not isfinite(alias.radius_mm) or alias.radius_mm <= 0
                or any(abs(a-b) > _TOL for a,b in zip(
                    (matches[0].center.x, matches[0].center.y),
                    _xy(alias.center_uv_mm, "native alias UV")))):
            raise ValueError("NFB_BASE_PART_NATIVE_ALIAS_UNVERIFIED")
    for hole in hole_ids:
        owned_aliases = tuple(a for a in aliases if a.owner_hole_id == hole)
        owned_uppers = tuple(p for p in uppers if
                             str(p.source_id or "").startswith(hole + ":"))
        if ((owned_aliases and (len(owned_aliases) != 4 or owned_uppers))
                or (not owned_aliases and not owned_uppers)):
            raise ValueError("NFB_BASE_PART_SOURCE_HOLE_MAPPING_UNVERIFIED")
    contours = tuple(p for p in primitives
                     if isinstance(p, PolylinePrimitive)
                     and p.layer == "CUTTING" and p.closed)
    marks = tuple(p for p in primitives
                  if isinstance(p, PolylinePrimitive) and p.layer == "MARKING")
    if len(contours) < 5 or not marks:
        raise ValueError("NFB_BASE_PART_EAR_AND_MARKING_GEOMETRY_MISSING")
    # Does NOT require the independent physical EAR bend/weld-Z certification;
    # this authorizes only the verified Base Plate CUTTING DXF, not an assembly.
