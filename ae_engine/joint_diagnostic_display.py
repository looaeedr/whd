"""Headless Engine projection of existing canonical Joint 3D diagnostics.

A diagnostic overlay is a read-only view of solved contact/penetration
evidence. It cannot certify a Joint or authorize any additional manufacturing.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class JointDiagnosticOverlaySource:
    joint_id: str
    groups: tuple
    direction_origin: tuple | None = None
    direction_delta: tuple | None = None


_FIELDS = (
    "contact_segments", "penetration_segments",
    "preserve_segments", "relief_segments",
)


def _point(raw):
    try:
        if len(raw) < 3:
            return None
        point = tuple(float(raw[i]) for i in range(3))
        return point if all(isfinite(v) for v in point) else None
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _segment(raw):
    try:
        if len(raw) != 2:
            return None
        a, b = raw
    except (TypeError, ValueError):
        return None
    a, b = _point(a), _point(b)
    return (a, b) if a is not None and b is not None else None


def project_joint_diagnostic_display_sources(render_data):
    """Select true solver-produced 3D segments for the requested Joint only."""
    diagnostics = tuple(getattr(render_data, "joint_diagnostics", ()) or ())
    selected = str(getattr(render_data, "selected_joint_id", "") or "")
    result = []
    for diag in diagnostics:
        joint_id = str(getattr(diag, "joint_id", "") or "")
        if selected and joint_id != selected:
            continue
        groups = tuple(
            (field, tuple(
                segment for source in tuple(getattr(diag, field, ()) or ())
                if (segment := _segment(source)) is not None
            ))
            for field in _FIELDS
        )
        direction = _segment(getattr(diag, "direction_segment", None))
        origin, delta = None, None
        if direction is not None:
            origin = direction[0]
            delta = tuple(direction[1][i] - origin[i] for i in range(3))
        result.append(JointDiagnosticOverlaySource(
            joint_id, groups, origin, delta,
        ))
    return tuple(result)
