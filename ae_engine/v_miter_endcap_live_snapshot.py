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


def _verified_original_no_hole_fold_equivalence(
    part_spec: EndCapPartSpec, render_data: PartRenderData, record: Mapping,
) -> bool:
    """Narrow original #3416 zero-hole .p6fold compatibility, fail closed.

    Before #3417, Main Tk captured an unprofiled EndCap PartSpec. Project
    Open may materialize the original BoxBody-linked Factory X/Y profiles.
    An old digest is accepted ONLY if the old unprofiled PartSpec reproduces
    that exact stored digest and BOTH Engine rebuilds have identical original
    ordered CUTTING/BEND, material and signed angle at *every* physical bend.
    A real width, stock, finite BEND or authored Fold change must fail.
    No user hole, second CUTTING or non-EndCap is compatible.
    """
    if (not isinstance(part_spec, EndCapPartSpec) or part_spec.holes
            or not isinstance(render_data, PartRenderData)
            or not isinstance(render_data.scene, DrawingScene)
            or getattr(render_data.material, "interiors", ())):
        return False
    from dataclasses import replace
    from .manufacturing_api import build_operator_part_render_data
    from .v_miter_operator_gui_check import (
        _endcap_existing_fold_angle_sources, _orthogonal_bends,
        _profile_angle_at_bend,
    )
    from .v_miter_trial_snapshot import _physical_sources
    legacy_spec = replace(part_spec, fold_profile_x=(), fold_profile_y=())
    try:
        canonical = build_operator_part_render_data(part_spec)
        original = build_operator_part_render_data(legacy_spec)
        current_rows, _ = _physical_sources(render_data.scene)
        canonical_rows, _ = _physical_sources(canonical.scene)
        legacy_rows, _ = _physical_sources(original.scene)
        def same_physical_cutting_and_finite_bends(a, b):
            # Project Open's original linked Fold reorders BEND rows and
            # reverses p1/p2 without moving the actual finite segment.
            # Do not relax either normal source hash: only this fully
            # provenance-verified no-hole compatibility compares unoriented
            # segments WITH multiplicity and exact CUTTING source.
            cuts_a = [row for row in a if row[0] == "CUTTING"]
            cuts_b = [row for row in b if row[0] == "CUTTING"]
            def bends(rows):
                return sorted(
                    tuple(sorted((tuple(row[1]), tuple(row[2]))))
                    for row in rows if row[0] == "BEND"
                )
            return cuts_a == cuts_b and bends(a) == bends(b)

        if (not same_physical_cutting_and_finite_bends(current_rows, canonical_rows)
                or not same_physical_cutting_and_finite_bends(current_rows, legacy_rows)):
            return False
        current_stock = _single_source_material(render_data.scene)
        canonical_stock = _single_source_material(canonical.scene)
        legacy_stock = _single_source_material(original.scene)
        if (current_stock.symmetric_difference(canonical_stock).area > 1e-8
                or current_stock.symmetric_difference(legacy_stock).area > 1e-8
                or render_data.material.symmetric_difference(current_stock).area > 1e-8):
            return False
        part_key = "tail" if part_spec.is_tail else "head"
        new_px, new_py = _endcap_existing_fold_angle_sources(part_spec, part_key)
        old_px, old_py = _endcap_existing_fold_angle_sources(legacy_spec, part_key)
        minx, miny, _, _ = current_stock.bounds
        vertical, horizontal = _orthogonal_bends(render_data.scene)
        if not vertical or not horizontal:
            return False
        # Full physical BEND ownership, not just the selected two bends.
        # A -75.5 degree authored turn cannot be erased by this migration.
        for bend in vertical:
            position = bend.p1.x
            if (_profile_angle_at_bend(new_px, position, minx)
                    != _profile_angle_at_bend(old_px, position, minx)):
                return False
        for bend in horizontal:
            position = bend.p1.y
            if (_profile_angle_at_bend(new_py, position, miny)
                    != _profile_angle_at_bend(old_py, position, miny)):
                return False
        historical, _, _ = _bound_inputs(
            legacy_spec, original, record["corner_key"],
            record["first_bend_axis"], record["relief_mode"],
        )
        return historical == record
    except (GeometryError, ValueError, TypeError, AttributeError):
        return False


def replay_endcap_live_v_miter_check_snapshot(
    part_spec: EndCapPartSpec, render_data: PartRenderData, record: Mapping,
) -> VMiterOperatorGUICheck:
    """Rebind on a fresh current source; reject stale input before solving."""
    record = normalize_endcap_live_v_miter_check_snapshot(record)
    current, first, second = _bound_inputs(
        part_spec, render_data, record["corner_key"],
        record["first_bend_axis"], record["relief_mode"],
    )
    if current != record and not _verified_original_no_hole_fold_equivalence(
        part_spec, render_data, record,
    ):
        raise GeometryError("V_MITER_LIVE_SOURCE_CHANGED")
    return _solve_bound_live_check(part_spec, render_data, current, first, second)


# The narrow Custom Tail two-corner CHECK keeps two independent old V1 records.
# It verifies one *source* sheet and one *shared* finite Y BEND, but does NOT
# claim a combined two-V manufactured mother, joint 3D or two-fold mesh.
_TAIL_BOTTOM_PAIR = ("bottom_left", "bottom_right")


def _bound_tail_bottom_pair(part_spec, render_data, *, axes, relief_modes):
    if (not isinstance(part_spec, EndCapPartSpec)
            or not part_spec.is_tail or part_spec.model_name is not None
            or not isinstance(render_data, PartRenderData)
            or not isinstance(render_data.scene, DrawingScene)
            or not isinstance(axes, Mapping) or not isinstance(relief_modes, Mapping)
            or set(axes) != set(_TAIL_BOTTOM_PAIR)
            or set(relief_modes) != set(_TAIL_BOTTOM_PAIR)
            or any(axes[key] != "x" for key in _TAIL_BOTTOM_PAIR)):
        raise GeometryError("V_MITER_TAIL_PAIR_EXPLICIT_CUSTOM_X_FIRST_REQUIRED")
    bound = {}
    for corner in _TAIL_BOTTOM_PAIR:
        bound[corner] = _bound_inputs(
            part_spec, render_data, corner, axes[corner], relief_modes[corner],
        )
    left = bound["bottom_left"]
    right = bound["bottom_right"]
    # X-first: first is each side's actual X BEND; second is the one
    # original, finite, physically SHARED Y BEND object, not two copies.
    if (left[1] is right[1] or left[2] is not right[2]
            or left[1].p1.x == right[1].p1.x):
        raise GeometryError("V_MITER_TAIL_PAIR_SHARED_PHYSICAL_BEND_REQUIRED")
    return bound


def capture_endcap_live_v_miter_bottom_pair_snapshots(
    part_spec: EndCapPartSpec, render_data: PartRenderData, *,
    first_bend_axes: Mapping, relief_modes: Mapping,
) -> dict[str, dict[str, str]]:
    """Atomically qualify both independent CHECK records on ONE live Tail.

    Neither a combined V outline nor a formed combined 3D is calculated.
    Callers must only publish the returned rows once BOTH Engine projections
    have completed; a failed right corner must not publish the left.
    """
    bound = _bound_tail_bottom_pair(
        part_spec, render_data, axes=first_bend_axes, relief_modes=relief_modes,
    )
    rows = {}
    for corner in _TAIL_BOTTOM_PAIR:
        record, first, second = bound[corner]
        _solve_bound_live_check(part_spec, render_data, record, first, second)
        rows[corner] = record
    return rows


def replay_endcap_live_v_miter_bottom_pair_snapshots(
    part_spec: EndCapPartSpec, render_data: PartRenderData,
    saved_rows: Mapping,
) -> dict[str, VMiterOperatorGUICheck]:
    """Both stored records must match one current physical Tail or show none."""
    if not isinstance(saved_rows, Mapping) or set(saved_rows) != set(_TAIL_BOTTOM_PAIR):
        raise GeometryError("V_MITER_TAIL_PAIR_SAVED_BOTH_SOURCES_REQUIRED")
    records = {
        key: normalize_endcap_live_v_miter_check_snapshot(saved_rows[key])
        for key in _TAIL_BOTTOM_PAIR
    }
    if any(records[key]["corner_key"] != key for key in _TAIL_BOTTOM_PAIR):
        raise GeometryError("V_MITER_TAIL_PAIR_SAVED_CORNER_MISMATCH")
    bound = _bound_tail_bottom_pair(
        part_spec, render_data,
        axes={key: records[key]["first_bend_axis"] for key in _TAIL_BOTTOM_PAIR},
        relief_modes={key: records[key]["relief_mode"] for key in _TAIL_BOTTOM_PAIR},
    )
    # Check BOTH sources before projecting either view; the original source
    # digest is never relaxed and can still detect any real Fold/width drift.
    for key in _TAIL_BOTTOM_PAIR:
        if bound[key][0] != records[key]:
            raise GeometryError("V_MITER_LIVE_SOURCE_CHANGED")
    return {
        key: _solve_bound_live_check(part_spec, render_data, *bound[key])
        for key in _TAIL_BOTTOM_PAIR
    }
