# -*- coding: utf-8 -*-
"""#3317 physical first-bend provenance for Vault Tail bilateral lower V.

This is an operator selection of REAL finite CUTTING/BEND source lines,
not a CHECK corner field, a preview label, or a manufacturing authorization.
Both corners must explicitly select the same first-axis order for the
currently solved sharp two-stage model. Source drift is always rejected.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from .contracts import EndCapPartSpec
from .manufacturing_render_data import PartRenderData, material_polygon_from_final_scene
from .sheetmetal_drawing import LinePrimitive
from .sheetmetal_geometry_core import GeometryError
from .v_miter_operator_gui_check import _physical_corner_bends

TAIL_LOWER_V_FIRST_BENDS_KEY = "tail_lower_v_first_bends"
_CORNERS = ("bottom_left", "bottom_right")
_AXES = ("x", "y")
_TOL = 1e-7


def _coord(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise GeometryError("V_MITER_FIRST_BEND_SOURCE_COORDINATE_INVALID")
    number = round(float(value), 7)
    return 0.0 if number == 0.0 else number


def _segment(line):
    if not isinstance(line, LinePrimitive) or line.layer != "BEND":
        raise GeometryError("V_MITER_FIRST_BEND_REAL_FINITE_LINE_REQUIRED")
    points = sorted((
        [_coord(line.p1.x), _coord(line.p1.y)],
        [_coord(line.p2.x), _coord(line.p2.y)],
    ))
    if points[0] == points[1]:
        raise GeometryError("V_MITER_FIRST_BEND_ZERO_LENGTH")
    return points


def _all_bends(render):
    lines = [
        _segment(p) for p in render.scene.primitives
        if isinstance(p, LinePrimitive) and p.layer == "BEND"
    ]
    if len(lines) < 3 or len({str(x) for x in lines}) != len(lines):
        raise GeometryError("V_MITER_FIRST_BEND_FINITE_SOURCE_NOT_UNIQUE")
    return sorted(lines)


def _label(axis, segment):
    name = "側折線 X" if axis == "x" else "下折線 Y"
    p, q = segment
    return f"{name} ({p[0]:g},{p[1]:g})－({q[0]:g},{q[1]:g}) mm"


def project_operator_tail_lower_v_first_bend_options(spec, render_data):
    """Read BOTH physical choices at EACH source corner, including endpoints."""
    if not isinstance(spec, EndCapPartSpec) or not spec.is_tail or str(
        spec.model_name or ""
    ) not in ("金庫型", "VAULT"):
        raise GeometryError("V_MITER_FIRST_BEND_VAULT_TAIL_REQUIRED")
    if not isinstance(render_data, PartRenderData) or render_data.scene is None:
        raise GeometryError("V_MITER_FIRST_BEND_REAL_FINAL_SCENE_REQUIRED")
    material = material_polygon_from_final_scene(render_data.scene)
    if (material.geom_type != "Polygon" or not material.is_valid or
            render_data.material is None or
            material.symmetric_difference(render_data.material).area > 1e-5):
        raise GeometryError("V_MITER_FIRST_BEND_SOURCE_MATERIAL_MISMATCH")
    output = {"source_bends": _all_bends(render_data)}
    for corner in _CORNERS:
        selected = _physical_corner_bends(render_data.scene, material, corner)
        vx, hy = selected[6], selected[7]  # ACTUAL finite source lines.
        xs, ys = _segment(vx), _segment(hy)
        if (xs[0][0] != xs[1][0] or ys[0][1] != ys[1][1]
                or abs(ys[0][1] - float(spec.fold_bottom)) > _TOL):
            raise GeometryError("V_MITER_FIRST_BEND_SOURCE_STATION_MISMATCH")
        output[corner] = {
            "x": {"bend": xs, "label": _label("x", xs)},
            "y": {"bend": ys, "label": _label("y", ys)},
        }
    if output["bottom_left"]["y"]["bend"] != output["bottom_right"]["y"]["bend"]:
        raise GeometryError("V_MITER_FIRST_BEND_SHARED_BOTTOM_SOURCE_MISMATCH")
    return output


def _validate_both_axes(selections):
    if not isinstance(selections, Mapping):
        raise GeometryError("V_MITER_FIRST_BEND_BOTH_CORNERS_REQUIRED")
    if set(selections) != set(_CORNERS):
        raise GeometryError("V_MITER_FIRST_BEND_PARTIAL_SELECTION_FORBIDDEN")
    axes = []
    for key in _CORNERS:
        axis = selections[key]
        if type(axis) is not str or axis not in _AXES:
            raise GeometryError("V_MITER_FIRST_BEND_PHYSICAL_LINE_REQUIRED")
        axes.append(axis)
    if axes[0] != axes[1]:
        raise GeometryError("V_MITER_FIRST_BEND_MIXED_ORDER_UNSUPPORTED")
    return axes[0]


def commit_operator_tail_lower_v_first_bends(
    snapshot, selections, *, spec, render_data,
):
    """Commit only complete explicit X/X or Y/Y; never infer a missing side."""
    from .operator_tail_lower_v import TAIL_LOWER_V_SNAPSHOT_KEY
    if not isinstance(snapshot, Mapping) or snapshot.get(
        TAIL_LOWER_V_SNAPSHOT_KEY
    ) != "v90":
        raise GeometryError("V_MITER_FIRST_BEND_REQUIRES_SELECTED_V_SOURCE")
    axis = _validate_both_axes(selections)
    options = project_operator_tail_lower_v_first_bend_options(spec, render_data)
    recorded = {"source_bends": options["source_bends"]}
    for corner in _CORNERS:
        recorded[corner] = {
            "first": axis,
            "x": options[corner]["x"]["bend"],
            "y": options[corner]["y"]["bend"],
        }
    result = dict(snapshot)
    result[TAIL_LOWER_V_FIRST_BENDS_KEY] = recorded
    return result


def validate_operator_tail_lower_v_first_bends(
    recorded, *, spec, render_data,
):
    """Return explicit order or None for legacy nominal preview.

    A stored partial/mixed/stale identity is an ERROR, not a request for
    the historical nominal X preview.
    """
    if recorded is None:
        return None
    if not isinstance(recorded, Mapping) or set(recorded) != set(
        _CORNERS + ("source_bends",)
    ):
        raise GeometryError("V_MITER_FIRST_BEND_STORED_SOURCE_INVALID")
    axes = {}
    for corner in _CORNERS:
        row = recorded[corner]
        if not isinstance(row, Mapping) or set(row) != {"first", "x", "y"}:
            raise GeometryError("V_MITER_FIRST_BEND_STORED_SOURCE_INVALID")
        axes[corner] = row["first"]
    axis = _validate_both_axes(axes)
    current = project_operator_tail_lower_v_first_bend_options(spec, render_data)
    if recorded["source_bends"] != current["source_bends"] or any(
        recorded[corner][a] != current[corner][a]["bend"]
        for corner in _CORNERS for a in _AXES
    ):
        raise GeometryError("V_MITER_FIRST_BEND_SOURCE_CHANGED_RESELECT_REQUIRED")
    return axis


def project_operator_tail_lower_v_first_bend_status(snapshot):
    """UI readback only; physical identity is separately checked against Engine."""
    if not isinstance(snapshot, Mapping):
        raise GeometryError("V_MITER_FIRST_BEND_SNAPSHOT_REQUIRED")
    recorded = snapshot.get(TAIL_LOWER_V_FIRST_BENDS_KEY)
    if recorded is None:
        return {"bottom_left": None, "bottom_right": None, "selected": False}
    if not isinstance(recorded, Mapping):
        raise GeometryError("V_MITER_FIRST_BEND_STORED_SOURCE_INVALID")
    axes = {}
    for corner in _CORNERS:
        row = recorded.get(corner)
        if not isinstance(row, Mapping):
            raise GeometryError("V_MITER_FIRST_BEND_PARTIAL_SELECTION_FORBIDDEN")
        axes[corner] = row.get("first")
    _validate_both_axes(axes)
    return {**axes, "selected": True}
