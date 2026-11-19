# -*- coding: utf-8 -*-
"""#3317 V-miter trial source save/reload, never a CornerType authorization.

Only save operator *inputs*, exact source geometry fingerprint and BEND
references.  Rebuild every V notch, R/hole and formed contact from CURRENT
canonical DrawingScene after reloading the project.  Never serialize a
computed CUTTING polygon / 3D mesh as saved truth.  A valid preview remains
V_MITER_RELIEF_FORMED_CONTACT_UNCERTIFIED after any roundtrip.

Can be embedded as optional project snapshot metadata by a source-owning
GUI/worker caller; no automatic fifth type or manufacturing publication.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

from .sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_bend_marking import project_v_miter_bend_markings
from .v_miter_true_t_collision import (
    VMiterTrueThicknessCollisionShadow,
    diagnose_v_miter_true_thickness_collision,
)
from .v_miter_relief_trial import (
    VMiterReliefMatingTrial,
    build_v_miter_relief_trial_check_scene,
    project_v_miter_relief_mating_trial,
)
from .v_miter_radius_ba_interface_trial import (
    VMiterRadiusCompensatedInterfaceTrial,
    solve_v_miter_radius_ba_interface_trial,
    build_v_miter_radius_ba_full_sheet_check_scene,
)

_TRIAL_CONTRACT = "V_MITER_RELIEF_TRIAL_SOURCE_V1"
_UNCERTIFIED = "V_MITER_RELIEF_FORMED_CONTACT_UNCERTIFIED"
_R_BA_TRIAL_CONTRACT = "V_MITER_RADIUS_BA_SOURCE_V2"
_R_BA_UNCERTIFIED = "V_MITER_RADIUS_BA_INTERFACE_UNCERTIFIED"
_INPUT_KEYS = frozenset({
    "thickness_mm", "first_flange_height_mm", "second_flange_height_mm",
    "second_fold_angle_deg", "relief_mode", "relief_t_factor",
})
_R_BA_MEASUREMENT_KEYS = frozenset({
    "first_inner_radius_mm", "second_inner_radius_mm",
    "first_bend_allowance_mm", "second_bend_allowance_mm",
    "max_permitted_edge_trim_mm",
})
_R_BA_INPUT_KEYS = _INPUT_KEYS | _R_BA_MEASUREMENT_KEYS
_SNAPSHOT_KEYS = frozenset({
    "contract", "manufacturing_status", "source_geometry_sha256",
    "first_bend_index", "second_bend_index", "parameters",
})


def _source_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GeometryError("V-miter snapshot source coordinates must be numeric, not bool")
    number = float(value)
    if not math.isfinite(number):
        raise GeometryError("V-miter snapshot source coordinates must be finite")
    return number


def _point_row(point) -> list[float]:
    return [_source_float(point.x), _source_float(point.y)]


def _physical_sources(scene: DrawingScene) -> tuple[list, list]:
    """Return the same ordered CUTTING/BEND records and their original owners.

    CHECK/DATUM/MARKING are intentionally excluded, so an operator's drawing
    annotations cannot readdress a physical BEND after project reload.
    """
    if not isinstance(scene, DrawingScene):
        raise GeometryError("V-miter snapshot needs DrawingScene source")
    rows, physical = [], []
    for item in scene.primitives:
        if item.layer == "CUTTING":
            if not isinstance(item, PolylinePrimitive) or not isinstance(item.closed, bool):
                raise GeometryError("V-miter snapshot CUTTING source must be a closed polyline")
            rows.append(["CUTTING", item.closed, [_point_row(p) for p in item.points]])
            physical.append(item)
        elif item.layer == "BEND":
            if not isinstance(item, LinePrimitive):
                raise GeometryError("V-miter snapshot BEND source must be a LinePrimitive")
            rows.append(["BEND", _point_row(item.p1), _point_row(item.p2)])
            physical.append(item)
    if sum(row[0] == "CUTTING" for row in rows) != 1 or sum(
        row[0] == "BEND" for row in rows
    ) < 2:
        raise GeometryError("V-miter snapshot missing physical CUTTING/BEND source")
    return rows, physical


def _source_geometry_sha256(
    scene: DrawingScene, *, selected_physical_indices: tuple[int, int] | None = None,
) -> str:
    """Source-only SHA; newly captured records additionally bind BEND roles.

    Legacy V1/V2 files used SHA256(ordered physical rows) but persisted
    ABSOLUTE scene indices, so moving a nonphysical CHECK/DATUM row could
    silently select different BENDs. New captures hash the selected physical
    source ordinals as well: source geometry and role ordering are both
    invariant under cosmetic row changes. Old two-BEND files are decoded
    unambiguously by _resolve_saved_trial_source, without upgrading status.
    Neither digest is an HMAC or manufacturing certification.
    """
    rows, physical = _physical_sources(scene)
    payload = rows
    if selected_physical_indices is not None:
        first, second = selected_physical_indices
        if (type(first) is not int or type(second) is not int or
                first == second or min(first, second) < 0 or
                max(first, second) >= len(physical) or
                any(not isinstance(physical[i], LinePrimitive)
                    or physical[i].layer != "BEND" for i in (first, second))):
            raise GeometryError("V-miter saved BEND source roles are invalid")
        payload = {
            "revision": "V_MITER_SELECTED_PHYSICAL_BENDS_SHA256_V1",
            "sources": rows,
            "selected_bend_roles": [first, second],
        }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _owned_index(scene: DrawingScene, bend: LinePrimitive) -> int:
    _, physical = _physical_sources(scene)
    for i, item in enumerate(physical):
        if item is bend and isinstance(item, LinePrimitive) and item.layer == "BEND":
            return i
    raise GeometryError("V-miter saved BEND must belong to original physical source scene")


def _validate_snapshot(
    payload: Mapping, *,
    contract: str = _TRIAL_CONTRACT,
    status: str = _UNCERTIFIED,
    input_keys: frozenset = _INPUT_KEYS,
) -> tuple[int, int, dict]:
    if not isinstance(payload, Mapping) or set(payload) != _SNAPSHOT_KEYS:
        raise GeometryError("V-miter saved trial record has invalid fields")
    if payload["contract"] != contract:
        raise GeometryError("V-miter saved trial contract revision is unsupported")
    if payload["manufacturing_status"] != status:
        raise GeometryError("V-miter saved trial cannot claim certified manufacture")
    fingerprint = payload["source_geometry_sha256"]
    if (not isinstance(fingerprint, str) or len(fingerprint) != 64 or
            any(ch not in "0123456789abcdef" for ch in fingerprint)):
        raise GeometryError("V-miter saved source fingerprint is invalid")
    first, second = payload["first_bend_index"], payload["second_bend_index"]
    if (type(first) is not int or type(second) is not int or
            first < 0 or second < 0 or first == second):
        raise GeometryError("V-miter saved BEND references are invalid")
    raw = payload["parameters"]
    if not isinstance(raw, Mapping) or set(raw) != input_keys:
        raise GeometryError("V-miter saved source parameter fields are invalid")
    # Both saved CHECK revisions originate from the same validated physical
    # two-bend source. Open must not accept corrupt inputs merely because it
    # has no DrawingScene to replay yet. No saved metadata certifies CUTTING.
    for field in (
        "thickness_mm", "first_flange_height_mm",
        "second_flange_height_mm", "relief_t_factor",
    ):
        value = raw[field]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise GeometryError(f"V-miter saved physical source {field} is invalid")
    angle = raw["second_fold_angle_deg"]
    if (type(angle) not in (int, float) or not math.isfinite(angle) or
            not 0 < angle < 180):
        raise GeometryError("V-miter saved physical source second_fold_angle_deg is invalid")
    mode = raw["relief_mode"]
    if type(mode) is not str or mode not in tuple(item.value for item in VMiterReliefMode):
        raise GeometryError("V-miter saved physical source relief_mode is invalid")
    if contract == _R_BA_TRIAL_CONTRACT:
        for field in _R_BA_MEASUREMENT_KEYS:
            value = raw[field]
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise GeometryError(f"V-miter saved measured R/BA source {field} is invalid")
    return first, second, dict(raw)


def capture_v_miter_relief_trial_snapshot(
    scene: DrawingScene,
    v_edge_bend: LinePrimitive,
    second_bend: LinePrimitive,
    *,
    thickness_mm: float,
    first_flange_height_mm: float,
    second_flange_height_mm: float,
    second_fold_angle_deg: float,
    relief_mode: str,
    relief_t_factor: float | None = None,
) -> dict[str, object]:
    """Capture validated operator source only, excluding computed geometry."""
    trial = project_v_miter_relief_mating_trial(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    q = trial.relief.source_trial.ideal.source
    first_role = _owned_index(scene, v_edge_bend)
    second_role = _owned_index(scene, second_bend)
    return {
        "contract": _TRIAL_CONTRACT,
        "manufacturing_status": _UNCERTIFIED,
        "source_geometry_sha256": _source_geometry_sha256(
            scene, selected_physical_indices=(first_role, second_role),
        ),
        "first_bend_index": first_role,
        "second_bend_index": second_role,
        "parameters": {
            "thickness_mm": q.thickness_mm,
            "first_flange_height_mm": q.first_flange_height_mm,
            "second_flange_height_mm": q.second_flange_height_mm,
            "second_fold_angle_deg": q.second_fold_angle_deg,
            "relief_mode": q.relief_mode.value,
            "relief_t_factor": q.relief_t_factor,
        },
    }


def _resolve_saved_trial_source(
    scene: DrawingScene,
    snapshot: Mapping,
    *,
    contract: str = _TRIAL_CONTRACT,
    status: str = _UNCERTIFIED,
    input_keys: frozenset = _INPUT_KEYS,
) -> tuple[LinePrimitive, LinePrimitive, dict]:
    first_idx, second_idx, parameters = _validate_snapshot(
        snapshot, contract=contract, status=status, input_keys=input_keys,
    )
    fingerprint = snapshot["source_geometry_sha256"]
    _, physical = _physical_sources(scene)
    modern = _source_geometry_sha256(
        scene, selected_physical_indices=(first_idx, second_idx),
    ) if max(first_idx, second_idx) < len(physical) else None
    if fingerprint == modern:
        first, second = physical[first_idx], physical[second_idx]
    elif fingerprint == _source_geometry_sha256(scene):
        # Original V1/V2 payloads used absolute DrawingScene indices and
        # did not bind selected role geometry. If the scene has >2 BENDs,
        # moving/removing a CHECK row can make both old indices alias OTHER
        # physical BEND lines while its source SHA still matches. There is
        # no information in the legacy envelope to recover which two were
        # originally chosen: fail closed instead of guessing from a corner.
        bends = tuple(item for item in physical if isinstance(item, LinePrimitive))
        if len(bends) != 2:
            raise GeometryError(
                "V-miter legacy saved BEND source roles are ambiguous; recapture required"
            )
        first, second = (
            (bends[0], bends[1]) if first_idx < second_idx
            else (bends[1], bends[0])
        )
    else:
        raise GeometryError("V-miter saved source geometry has changed since capture")
    if (not isinstance(first, LinePrimitive) or first.layer != "BEND" or
            not isinstance(second, LinePrimitive) or second.layer != "BEND" or
            first is second):
        raise GeometryError("V-miter saved source BEND references have changed roles")
    return first, second, parameters


def replay_v_miter_relief_trial_snapshot(
    scene: DrawingScene,
    snapshot: Mapping,
) -> VMiterReliefMatingTrial:
    """Recreate original 2D relief and 3D ideal seam after a source reload."""
    first, second, parameters = _resolve_saved_trial_source(scene, snapshot)
    return project_v_miter_relief_mating_trial(
        scene, first, second, **parameters,
    )


def _append_saved_bend_alignment_check(
    preview: DrawingScene,
    first: LinePrimitive,
    second: LinePrimitive,
    *,
    include_alignment_check: bool,
) -> DrawingScene:
    """Opt-in press-brake alignment *visualization*, NOT a MARKING toolpath.

    Uses only the existing Engine 20-mm stroke / 50-mm blank-gap rule and
    actual SHA-replayed BEND sources. Re-layering the marks to CHECK is
    intentional: no engraving or CUTTING can be released from a V trial.
    """
    if type(include_alignment_check) is not bool:
        raise GeometryError("V-miter CHECK alignment flag must be bool")
    if not include_alignment_check:
        return preview
    result = DrawingScene(list(preview.primitives))
    for bend in (first, second):
        for stroke in project_v_miter_bend_markings(bend):
            result.add(LinePrimitive(
                stroke.p1, stroke.p2, layer="CHECK", color=211,
            ))
    return result


def build_saved_v_miter_relief_trial_check_scene(
    scene: DrawingScene,
    snapshot: Mapping,
    *,
    include_alignment_check: bool = False,
) -> DrawingScene:
    """Saved V1 source recreates CHECK/DATUM and optional CHECK alignment."""
    first, second, parameters = _resolve_saved_trial_source(scene, snapshot)
    preview = build_v_miter_relief_trial_check_scene(
        scene, first, second, **parameters,
    )
    return _append_saved_bend_alignment_check(
        preview, first, second,
        include_alignment_check=include_alignment_check,
    )



def replay_v_miter_true_thickness_collision_snapshot(
    scene: DrawingScene,
    snapshot: Mapping,
) -> VMiterTrueThicknessCollisionShadow:
    """Rebuild full local T-thick sharp-fold collision from saved REAL source.

    All cut polygons, 3D surfaces, thickness meshes and collision segments
    are rederived from the canonical DrawingScene after project reload.
    No persisted collision result can certify an untested manufacturing DXF.
    The 60-degree unresolved physical BEND extension still fails closed.
    """
    first, second, parameters = _resolve_saved_trial_source(scene, snapshot)
    return diagnose_v_miter_true_thickness_collision(
        scene, first, second, **parameters,
    )


def capture_v_miter_radius_ba_trial_snapshot(
    scene: DrawingScene,
    v_edge_bend: LinePrimitive,
    second_bend: LinePrimitive,
    *,
    thickness_mm: float,
    first_flange_height_mm: float,
    second_flange_height_mm: float,
    second_fold_angle_deg: float,
    relief_mode: str,
    relief_t_factor: float | None = None,
    first_inner_radius_mm: float,
    second_inner_radius_mm: float,
    first_bend_allowance_mm: float,
    second_bend_allowance_mm: float,
    max_permitted_edge_trim_mm: float,
) -> dict[str, object]:
    """Store verified operator R/BA source, never the computed mesh/CUTTING.

    Existing V1 source-only snapshots are unchanged. This V2 CHECK contract
    additionally preserves measured R/BA and the *maximum* permitted trim,
    all explicitly supplied by the operator. Geometry still must be fully
    re-solved from original physical CUTTING/BEND after .p6fold reload.
    """
    basic = {
        "thickness_mm": thickness_mm,
        "first_flange_height_mm": first_flange_height_mm,
        "second_flange_height_mm": second_flange_height_mm,
        "second_fold_angle_deg": second_fold_angle_deg,
        "relief_mode": relief_mode,
        "relief_t_factor": relief_t_factor,
    }
    old = capture_v_miter_relief_trial_snapshot(
        scene, v_edge_bend, second_bend, **basic,
    )
    measured = {
        "first_inner_radius_mm": first_inner_radius_mm,
        "second_inner_radius_mm": second_inner_radius_mm,
        "first_bend_allowance_mm": first_bend_allowance_mm,
        "second_bend_allowance_mm": second_bend_allowance_mm,
        "max_permitted_edge_trim_mm": max_permitted_edge_trim_mm,
    }
    # Inputs must be genuine typed shop measurements before any potential
    # normalization; strings/bools never become an apparent measured R.
    for field, value in measured.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise GeometryError(f"V-miter measured R/BA source {field} is invalid")
    solved = solve_v_miter_radius_ba_interface_trial(
        scene, v_edge_bend, second_bend, **basic, **measured,
    )
    return {
        "contract": _R_BA_TRIAL_CONTRACT,
        "manufacturing_status": _R_BA_UNCERTIFIED,
        "source_geometry_sha256": old["source_geometry_sha256"],
        "first_bend_index": old["first_bend_index"],
        "second_bend_index": old["second_bend_index"],
        "parameters": {
            **old["parameters"],
            "first_inner_radius_mm": solved.first_inner_radius_mm,
            "second_inner_radius_mm": solved.second_inner_radius_mm,
            "first_bend_allowance_mm": solved.first_bend_allowance_mm,
            "second_bend_allowance_mm": solved.second_bend_allowance_mm,
            "max_permitted_edge_trim_mm": solved.max_permitted_edge_trim_mm,
        },
    }


def _project_operator_v_miter_preview_source(
    source_snapshot: Mapping, *, key: str, contract: str,
    status: str, input_keys: frozenset,
) -> dict[str, object] | None:
    """Validate and copy stored CHECK inputs, never derived geometry.

    Both revisions remain independently replayable against the original
    CUTTING/BEND SHA. Project Open/Save cannot certify a manufacturing cut.
    """
    from copy import deepcopy

    if not isinstance(source_snapshot, Mapping):
        raise GeometryError("V-miter operator source snapshot must be a mapping")
    if key not in source_snapshot:
        return None
    row = source_snapshot[key]
    _validate_snapshot(
        row, contract=contract, status=status, input_keys=input_keys,
    )
    return deepcopy({
        "contract": row["contract"],
        "manufacturing_status": row["manufacturing_status"],
        "source_geometry_sha256": row["source_geometry_sha256"],
        "first_bend_index": row["first_bend_index"],
        "second_bend_index": row["second_bend_index"],
        "parameters": dict(row["parameters"]),
    })


def project_operator_v_miter_relief_preview_source(
    source_snapshot: Mapping,
) -> dict[str, object] | None:
    """Preserve a legacy V1 R/hole CHECK input through main GUI Open->Save."""
    return _project_operator_v_miter_preview_source(
        source_snapshot, key="v_miter_trial_preview",
        contract=_TRIAL_CONTRACT, status=_UNCERTIFIED,
        input_keys=_INPUT_KEYS,
    )


def project_operator_v_miter_radius_ba_preview_source(
    source_snapshot: Mapping,
) -> dict[str, object] | None:
    """Preserve a V2 measured-R/BA CHECK input through main GUI Open->Save."""
    return _project_operator_v_miter_preview_source(
        source_snapshot, key="v_miter_radius_ba_trial_preview",
        contract=_R_BA_TRIAL_CONTRACT, status=_R_BA_UNCERTIFIED,
        input_keys=_R_BA_INPUT_KEYS,
    )


def _resolve_saved_r_ba_trial_source(
    scene: DrawingScene, snapshot: Mapping,
) -> tuple[LinePrimitive, LinePrimitive, dict]:
    return _resolve_saved_trial_source(
        scene, snapshot,
        contract=_R_BA_TRIAL_CONTRACT,
        status=_R_BA_UNCERTIFIED,
        input_keys=_R_BA_INPUT_KEYS,
    )


def replay_v_miter_radius_ba_trial_snapshot(
    scene: DrawingScene, snapshot: Mapping,
) -> VMiterRadiusCompensatedInterfaceTrial:
    """Re-solve true R/BA/T 3D CHECK from saved source with no mesh trust."""
    first, second, parameters = _resolve_saved_r_ba_trial_source(
        scene, snapshot,
    )
    return solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **parameters,
    )


def build_saved_v_miter_radius_ba_check_scene(
    scene: DrawingScene, snapshot: Mapping,
    *,
    include_alignment_check: bool = False,
) -> DrawingScene:
    """Recreate V2 CHECK-only 2D with optional real-BEND alignment CHECK.

    The additional strokes are never MARKING layer entities and cannot
    release fifth-type CUTTING/BEND/MARKING manufacture or certify R/BA.
    """
    first, second, parameters = _resolve_saved_r_ba_trial_source(
        scene, snapshot,
    )
    preview = build_v_miter_radius_ba_full_sheet_check_scene(
        scene, first, second, **parameters,
    )
    return _append_saved_bend_alignment_check(
        preview, first, second,
        include_alignment_check=include_alignment_check,
    )
