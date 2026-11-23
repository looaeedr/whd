"""Persist exact live EndCap CHECK inputs, not virtual rays or geometry."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json

from .contracts import EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene
from .sheetmetal_geometry_core import GeometryError
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_material_trial import _single_source_material
from .v_miter_existing_circle_check import qualify_live_endcap_circle_source
from .v_miter_operator_gui_check import (
    V_MITER_GUI_CORNER_KEYS,
    V_MITER_GUI_UNCERTIFIED,
    VMiterOperatorGUICheck,
    _bound_endcap_corner_bends,
    project_operator_v_miter_live_corner_check,
)
from .v_miter_trial_snapshot import _bound_endcap_fold_sha256

_ENDCAP_LIVE_CHECK_CONTRACT = "V_MITER_ENDCAP_LIVE_CHECK_SOURCE_V1"
_KEYS = frozenset({
    "contract", "manufacturing_status", "corner_key", "first_bend_axis",
    "relief_mode", "source_fold_sha256",
})


def _bound_inputs(part_spec, render_data, corner_key, first_bend_axis, relief_mode):
    if not isinstance(part_spec, EndCapPartSpec):
        raise GeometryError("V_MITER_LIVE_SOURCE_ENDCAP_REQUIRED")
    if (not isinstance(render_data, PartRenderData)
            or not isinstance(render_data.scene, DrawingScene)):
        raise GeometryError("V_MITER_LIVE_SOURCE_FINAL_SCENE_REQUIRED")
    if type(corner_key) is not str or corner_key not in V_MITER_GUI_CORNER_KEYS:
        raise GeometryError("V_MITER_LIVE_SOURCE_CORNER_REQUIRED")
    if type(first_bend_axis) is not str or first_bend_axis not in ("x", "y"):
        raise GeometryError("V_MITER_LIVE_SOURCE_FIRST_BEND_REQUIRED")
    if type(relief_mode) is not str:
        raise GeometryError("V_MITER_LIVE_SOURCE_RELIEF_MODE_INVALID")
    try:
        relief_mode = VMiterReliefMode(relief_mode).value
    except ValueError as exc:
        raise GeometryError("V_MITER_LIVE_SOURCE_RELIEF_MODE_INVALID") from exc
    # The old V1/V2 physical digest remains strictly single-CUTTING.
    # Only this Custom EndCap live CHECK can qualify one real inner circle.
    scoped, source_circle, _void = qualify_live_endcap_circle_source(
        part_spec, render_data,
    )
    scene = scoped.scene
    _, _, x_h, y_h, _, _, x_bend, y_bend, x_angle, y_angle = (
        _bound_endcap_corner_bends(
            part_spec, scene, _single_source_material(scene), corner_key,
        )
    )
    if first_bend_axis == "x":
        first, second, first_h, second_h, second_angle = x_bend, y_bend, x_h, y_h, y_angle
    else:
        first, second, first_h, second_h, second_angle = y_bend, x_bend, y_h, x_h, x_angle
    fold_digest = _bound_endcap_fold_sha256(
        part_spec, scene, first, second, corner_key,
        second_angle_deg=abs(second_angle), thickness_mm=part_spec.thickness,
        first_flange_height_mm=first_h, second_flange_height_mm=second_h,
    )
    components = [
        _ENDCAP_LIVE_CHECK_CONTRACT, fold_digest, corner_key,
        first_bend_axis, relief_mode,
    ]
    if source_circle is not None:
        # Source geometry and its already-verified actual material inner ring
        # are 1:1. Bind the precise original circle so a +13 mm hole move
        # invalidates the old record without altering the V1 envelope.
        circle_row = [
            "VERIFIED_CUSTOM_ENDCAP_CUTTING_CIRCLE_V1",
            source_circle.center.x, source_circle.center.y,
            source_circle.radius, source_circle.source_type,
            source_circle.source_id,
        ]
        components.append(hashlib.sha256(json.dumps(
            circle_row, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest())
    digest = hashlib.sha256("|".join(components).encode("ascii")).hexdigest()
    return {
        "contract": _ENDCAP_LIVE_CHECK_CONTRACT,
        "manufacturing_status": V_MITER_GUI_UNCERTIFIED,
        "corner_key": corner_key,
        "first_bend_axis": first_bend_axis,
        "relief_mode": relief_mode,
        "source_fold_sha256": digest,
    }, first, second


def _solve_bound_live_check(part_spec, render_data, record, first, second):
    # Existing live Engine owns detached virtual station CHECK rays; neither
    # persisted data nor this adapter moves/extends physical BEND primitives.
    result = project_operator_v_miter_live_corner_check(
        part_spec, render_data, record["corner_key"],
        first_bend_axis=record["first_bend_axis"],
        relief_mode=record["relief_mode"],
    )
    if result.first_physical_bend is not first or result.second_physical_bend is not second:
        raise GeometryError("V_MITER_LIVE_SOURCE_SELECTED_BEND_CHANGED")
    if (result.manufacturing_status != V_MITER_GUI_UNCERTIFIED
            or result.full_sheet_check_scene is None
            or result.factory_bottom_relief_check is None):
        raise GeometryError("V_MITER_LIVE_SOURCE_RELIEF_CHECK_UNAVAILABLE")
    return result


def capture_endcap_live_v_miter_check_snapshot(
    part_spec: EndCapPartSpec, render_data: PartRenderData, corner_key: str,
    *, first_bend_axis: str, relief_mode: str = "ROUND_R",
) -> dict[str, str]:
    """Save a vetted CHECK source; do not serialize geometry or manufacture."""
    record, first, second = _bound_inputs(
        part_spec, render_data, corner_key, first_bend_axis, relief_mode,
    )
    _solve_bound_live_check(part_spec, render_data, record, first, second)
    return record


def normalize_endcap_live_v_miter_check_snapshot(record: Mapping) -> dict[str, str]:
    """Validate the JSON envelope for project loading; do not solve geometry."""
    if (not isinstance(record, Mapping) or set(record) != _KEYS
            or any(type(record[key]) is not str for key in _KEYS)
            or record["contract"] != _ENDCAP_LIVE_CHECK_CONTRACT
            or record["manufacturing_status"] != V_MITER_GUI_UNCERTIFIED
            or record["corner_key"] not in V_MITER_GUI_CORNER_KEYS
            or record["first_bend_axis"] not in ("x", "y")
            or record["relief_mode"] not in {mode.value for mode in VMiterReliefMode}):
        raise GeometryError("V_MITER_LIVE_SOURCE_RECORD_INVALID")
    expected_hash = record["source_fold_sha256"]
    if (len(expected_hash) != 64
            or any(token not in "0123456789abcdef" for token in expected_hash)):
        raise GeometryError("V_MITER_LIVE_SOURCE_DIGEST_INVALID")
    return dict(record)


def replay_endcap_live_v_miter_check_snapshot(
    part_spec: EndCapPartSpec, render_data: PartRenderData, record: Mapping,
) -> VMiterOperatorGUICheck:
    """Rebind on a fresh current source; reject stale input before solving."""
    record = normalize_endcap_live_v_miter_check_snapshot(record)
    current, first, second = _bound_inputs(
        part_spec, render_data, record["corner_key"],
        record["first_bend_axis"], record["relief_mode"],
    )
    if current != record:
        raise GeometryError("V_MITER_LIVE_SOURCE_CHANGED")
    return _solve_bound_live_check(part_spec, render_data, current, first, second)
