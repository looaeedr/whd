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


def _source_geometry_sha256(scene: DrawingScene) -> str:
    """A deterministic fingerprint of this scene's actual physical sources.

    Ignore DATUM/CHECK/MARKING cosmetic or test overlay entities. Preserve
    CUTTING and BEND order: saved BEND indices cannot silently alias a
    different source after Save->Reload. This is a drift witness, not an HMAC
    or a manufacturing certification.
    """
    if not isinstance(scene, DrawingScene):
        raise GeometryError("V-miter snapshot needs DrawingScene source")
    rows = []
    for item in scene.primitives:
        if item.layer == "CUTTING":
            if not isinstance(item, PolylinePrimitive) or not isinstance(item.closed, bool):
                raise GeometryError("V-miter snapshot CUTTING source must be a closed polyline")
            rows.append(["CUTTING", item.closed, [_point_row(p) for p in item.points]])
        elif item.layer == "BEND":
            if not isinstance(item, LinePrimitive):
                raise GeometryError("V-miter snapshot BEND source must be a LinePrimitive")
            rows.append(["BEND", _point_row(item.p1), _point_row(item.p2)])
    if sum(row[0] == "CUTTING" for row in rows) != 1 or sum(
        row[0] == "BEND" for row in rows
    ) < 2:
        raise GeometryError("V-miter snapshot missing physical CUTTING/BEND source")
    encoded = json.dumps(
        rows, ensure_ascii=False, sort_keys=True,
        allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _owned_index(scene: DrawingScene, bend: LinePrimitive) -> int:
    for i, item in enumerate(scene.primitives):
        if item is bend:
            return i
    raise GeometryError("V-miter saved BEND must belong to original source scene")


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
    if contract == _R_BA_TRIAL_CONTRACT:
        # No booleans, text coerced to floats, NaNs or missing measurements
        # can be replayed as physical R/BA or certified source data.
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
    return {
        "contract": _TRIAL_CONTRACT,
        "manufacturing_status": _UNCERTIFIED,
        "source_geometry_sha256": _source_geometry_sha256(scene),
        "first_bend_index": _owned_index(scene, v_edge_bend),
        "second_bend_index": _owned_index(scene, second_bend),
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
    if snapshot["source_geometry_sha256"] != _source_geometry_sha256(scene):
        raise GeometryError("V-miter saved source geometry has changed since capture")
    try:
        first = scene.primitives[first_idx]
        second = scene.primitives[second_idx]
    except (IndexError, TypeError) as exc:
        raise GeometryError("V-miter saved source BEND indices are stale") from exc
    if (not isinstance(first, LinePrimitive) or first.layer != "BEND" or
            not isinstance(second, LinePrimitive) or second.layer != "BEND"):
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


def build_saved_v_miter_relief_trial_check_scene(
    scene: DrawingScene,
    snapshot: Mapping,
) -> DrawingScene:
    """A saved trial may only recreate CHECK/DATUM, never manufacturing DXF."""
    first, second, parameters = _resolve_saved_trial_source(scene, snapshot)
    return build_v_miter_relief_trial_check_scene(
        scene, first, second, **parameters,
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
) -> DrawingScene:
    """Recreate only CHECK/DATUM 2D from the original source R/BA trial.

    Do not substitute this preview for a fifth manufacturing CornerType
    or include CUTTING/BEND/MARKING production layers in the output.
    """
    first, second, parameters = _resolve_saved_r_ba_trial_source(
        scene, snapshot,
    )
    return build_v_miter_radius_ba_full_sheet_check_scene(
        scene, first, second, **parameters,
    )
