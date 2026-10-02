# -*- coding: utf-8 -*-
"""Receiving multi-Bay side-lock Joint geometry.

The lock pattern is certified by the existing Box Body baseline/family feature
resolver. This module only canonicalizes that certified side-face geometry into
a shared Joint frame and projects it back to the two physical mating side faces.
It does not own a second hole-coordinate table.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from . import ae
from .cabinet_types import policy as cabinet_family_policy
from .receiving_layout import normalize_receiving_layout
from .sheetmetal_features import (
    CircleFeature,
    FeatureAnchor,
    ResolvedCircle,
)
from .sheetmetal_geometry import Vec2


RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION = (
    "RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION"
)
RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION = "RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION"
RECEIVING_LOCK_PATTERN_BASELINE_UNAVAILABLE = "RECEIVING_LOCK_PATTERN_BASELINE_UNAVAILABLE"

DIRECTION_CONTRACT = {
    "front": "+Z",
    "rear": "-Z",
    "left": "-X",
    "right": "+X",
    "u": "FRONT_TO_REAR",
    "v": "BOTTOM_TO_TOP",
}

_TOL = 1e-6


class ReceivingJointLockPatternError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"{self.code}: {self.detail}")


@dataclass(frozen=True)
class ReceivingJointLockCircle:
    u: float
    v: float
    diameter: float
    layer: str


@dataclass(frozen=True)
class ReceivingJointLockParticipantProjection:
    bay_id: str
    face_key: str
    width: float
    height: float
    depth: float
    features: tuple[CircleFeature, ...]
    finished_centers: tuple[tuple[float, float], ...]
    joint_world_centers: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class ReceivingJointLockResolution:
    joint_id: str
    effective_depth: float
    effective_height: float
    depth_alignment: str
    height_alignment: str
    baseline_model: str
    canonical_pattern: tuple[ReceivingJointLockCircle, ...]
    left_bay: ReceivingJointLockParticipantProjection
    right_bay: ReceivingJointLockParticipantProjection
    direction_contract: Mapping[str, str]


def _cutting_side_pattern(
    face_features,
    *,
    participant_side: str,
    participant_width: float,
    effective_depth: float,
    effective_height: float,
) -> tuple[ReceivingJointLockCircle, ...]:
    """Extract one certified side-local lock group from the baseline W face.

    The Vault baseline stores the two side-lock groups on the authoritative
    width face, one group close to each W edge.  Their edge distance is the
    side-local FRONT->REAR datum reused by the mating side panel.  This keeps
    the certified resolver authoritative without inventing a second hole table.
    """
    side = str(participant_side).strip().lower()
    if side not in {"left", "right"}:
        raise ValueError(f"unsupported Receiving participant side: {participant_side!r}")
    width = float(participant_width)
    if width <= 0.0:
        raise ValueError("participant_width must be positive")

    rows = []
    for feature in tuple(dict(face_features or {}).get("back", ()) or ()):
        if not isinstance(feature, ResolvedCircle):
            continue
        layer = str(feature.layer or "").strip().upper()
        if layer not in {"CUTTING", "BLIND_HOLE"}:
            continue
        x = float(feature.center.x)
        # Split the certified W-face groups by participant side, then normalize
        # both to an edge-local positive distance so W itself cannot affect the
        # resulting Joint pattern.
        if side == "left":
            if x > width / 2.0 + _TOL:
                continue
            u = x
        else:
            if x < width / 2.0 - _TOL:
                continue
            u = width - x
        v = float(feature.center.y)
        radius = float(feature.radius)
        diameter = 2.0 * radius
        if (
            u - radius < -_TOL
            or u + radius > float(effective_depth) + _TOL
            or v - radius < -_TOL
            or v + radius > float(effective_height) + _TOL
        ):
            raise ReceivingJointLockPatternError(
                RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION,
                f"certified {side} side-local lock circle exceeds effective panel: "
                f"u={u}, v={v}, diameter={diameter}, "
                f"D={effective_depth}, H={effective_height}",
            )
        rows.append(
            ReceivingJointLockCircle(
                u=float(u),
                v=float(v),
                diameter=float(diameter),
                layer=layer,
            )
        )
    if not rows:
        raise ReceivingJointLockPatternError(
            RECEIVING_LOCK_PATTERN_BASELINE_UNAVAILABLE,
            f"certified baseline produced no {side} side-local lock circles",
        )
    return tuple(sorted(rows, key=lambda row: (row.u, row.v, row.diameter, row.layer)))

def _patterns_match(a, b) -> bool:
    if len(a) != len(b):
        return False
    for left, right in zip(a, b):
        if left.layer != right.layer:
            return False
        if abs(float(left.u) - float(right.u)) > _TOL:
            return False
        if abs(float(left.v) - float(right.v)) > _TOL:
            return False
        if abs(float(left.diameter) - float(right.diameter)) > _TOL:
            return False
    return True


def _project_participant(
    pattern,
    *,
    bay,
    face_key: str,
    joint_id: str,
    effective_depth: float,
    effective_height: float,
    depth_alignment: str,
    height_alignment: str,
) -> ReceivingJointLockParticipantProjection:
    width = float(bay["width"])
    height = float(bay["height"])
    depth = float(bay["depth"])
    depth_offset = 0.0 if depth_alignment == "FRONT" else depth - float(effective_depth)
    height_offset = 0.0 if height_alignment == "BOTTOM" else height - float(effective_height)

    features = []
    finished_centers = []
    world_centers = []
    for index, circle in enumerate(pattern):
        participant_u = depth_offset + float(circle.u)
        local_x = participant_u if face_key == "left" else depth - participant_u
        local_y = height_offset + float(circle.v)
        radius = float(circle.diameter) / 2.0
        if (
            local_x - radius < -_TOL
            or local_x + radius > depth + _TOL
            or local_y - radius < -_TOL
            or local_y + radius > height + _TOL
        ):
            raise ReceivingJointLockPatternError(
                RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION,
                f"{bay['stable_id']} projected lock circle exceeds physical side panel: "
                f"x={local_x}, y={local_y}, diameter={circle.diameter}, "
                f"D={depth}, H={height}",
            )

        # Define the Joint world frame from the selected shared alignment:
        # mating plane X=0, u points toward REAR (-Z), v points TOP (+Y).
        front_world_z = 0.0 if depth_alignment == "FRONT" else depth - float(effective_depth)
        bottom_world_y = 0.0 if height_alignment == "BOTTOM" else float(effective_height) - height
        world_y = bottom_world_y + local_y
        world_z = front_world_z - participant_u

        features.append(
            CircleFeature(
                diameter=float(circle.diameter),
                anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(float(local_x), float(local_y)),
                layer=str(circle.layer),
                source_type="receiving_joint_side_lock",
                source_params=(
                    ("joint_id", str(joint_id)),
                    ("bay_id", str(bay["stable_id"])),
                    ("pattern_index", int(index)),
                    ("canonical_u", float(circle.u)),
                    ("canonical_v", float(circle.v)),
                ),
            )
        )
        finished_centers.append((float(local_x), float(local_y)))
        world_centers.append((0.0, float(world_y), float(world_z)))

    return ReceivingJointLockParticipantProjection(
        bay_id=str(bay["stable_id"]),
        face_key=str(face_key),
        width=width,
        height=height,
        depth=depth,
        features=tuple(features),
        finished_centers=tuple(finished_centers),
        joint_world_centers=tuple(world_centers),
    )


def resolve_receiving_joint_lock_pattern(
    layout,
    *,
    set_index: int,
    joint_index: int,
    thickness: float = 2.0,
    frame_width: float = 29.0,
    baseline_resolver: Callable[..., Mapping[str, object]] | None = None,
) -> ReceivingJointLockResolution:
    """Resolve one adjacent-Bay side-lock Joint from the certified baseline owner."""
    normalized = normalize_receiving_layout(layout)
    sets = normalized["sets"]
    if set_index < 0 or set_index >= len(sets):
        raise IndexError("Receiving set_index out of range")
    selected = sets[set_index]
    joints = selected["joints"]
    if joint_index < 0 or joint_index >= len(joints):
        raise IndexError("Receiving joint_index out of range")
    if joint_index + 1 >= len(selected["bays"]):
        raise ValueError("Receiving Joint has no adjacent Bay pair")

    joint = joints[joint_index]
    left_bay = selected["bays"][joint_index]
    right_bay = selected["bays"][joint_index + 1]
    if str(joint["left_bay_id"]) != str(left_bay["stable_id"]) or str(joint["right_bay_id"]) != str(right_bay["stable_id"]):
        raise ValueError("Receiving Joint endpoints do not match adjacent Bays")

    effective_depth = min(float(left_bay["depth"]), float(right_bay["depth"]))
    effective_height = min(float(left_bay["height"]), float(right_bay["height"]))
    if effective_depth <= 0.0 or effective_height <= 0.0:
        raise ReceivingJointLockPatternError(
            RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION,
            "effective Receiving Joint panel dimensions must be positive",
        )

    depth_alignment = str(joint.get("depth_alignment") or "FRONT").strip().upper()
    height_alignment = str(joint.get("height_alignment") or "BOTTOM").strip().upper()
    if depth_alignment not in {"FRONT", "REAR"}:
        raise ValueError(f"unsupported Receiving depth_alignment: {depth_alignment!r}")
    if height_alignment not in {"TOP", "BOTTOM"}:
        raise ValueError(f"unsupported Receiving height_alignment: {height_alignment!r}")

    baseline_model = cabinet_family_policy.baseline_feature_model_name("受電箱")
    if not baseline_model:
        raise ReceivingJointLockPatternError(
            RECEIVING_LOCK_PATTERN_BASELINE_UNAVAILABLE,
            "Receiving certified baseline family is unavailable",
        )
    resolver = baseline_resolver or ae.get_box_body_baseline_face_features

    # Required invariant: execute the certified resolver once per participant W.
    # The virtual side panel uses the shared effective D/H in both calls.
    left_faces = resolver(
        baseline_model,
        w=float(left_bay["width"]),
        h=effective_height,
        d=effective_depth,
        t=float(thickness),
        fw=float(frame_width),
    )
    right_faces = resolver(
        baseline_model,
        w=float(right_bay["width"]),
        h=effective_height,
        d=effective_depth,
        t=float(thickness),
        fw=float(frame_width),
    )

    # Left Bay mates through its RIGHT face; Right Bay mates through its LEFT face.
    # Canonicalization removes the right-face REAR->FRONT manufacturing traversal.
    from_left_participant = _cutting_side_pattern(
        left_faces,
        participant_side="right",
        participant_width=float(left_bay["width"]),
        effective_depth=effective_depth,
        effective_height=effective_height,
    )
    from_right_participant = _cutting_side_pattern(
        right_faces,
        participant_side="left",
        participant_width=float(right_bay["width"]),
        effective_depth=effective_depth,
        effective_height=effective_height,
    )
    if not _patterns_match(from_left_participant, from_right_participant):
        raise ReceivingJointLockPatternError(
            RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION,
            f"certified side-local lock groups differ for participant W values "
            f"{left_bay['width']} and {right_bay['width']}",
        )

    pattern = from_left_participant
    left_projection = _project_participant(
        pattern,
        bay=left_bay,
        face_key="right",
        joint_id=str(joint["stable_id"]),
        effective_depth=effective_depth,
        effective_height=effective_height,
        depth_alignment=depth_alignment,
        height_alignment=height_alignment,
    )
    right_projection = _project_participant(
        pattern,
        bay=right_bay,
        face_key="left",
        joint_id=str(joint["stable_id"]),
        effective_depth=effective_depth,
        effective_height=effective_height,
        depth_alignment=depth_alignment,
        height_alignment=height_alignment,
    )
    if left_projection.joint_world_centers != right_projection.joint_world_centers:
        raise ValueError("Receiving Joint participant world projection diverged")

    return ReceivingJointLockResolution(
        joint_id=str(joint["stable_id"]),
        effective_depth=float(effective_depth),
        effective_height=float(effective_height),
        depth_alignment=depth_alignment,
        height_alignment=height_alignment,
        baseline_model=str(baseline_model),
        canonical_pattern=tuple(pattern),
        left_bay=left_projection,
        right_bay=right_projection,
        direction_contract=dict(DIRECTION_CONTRACT),
    )


__all__ = [
    "DIRECTION_CONTRACT",
    "RECEIVING_LOCK_PATTERN_BASELINE_UNAVAILABLE",
    "RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION",
    "RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION",
    "ReceivingJointLockCircle",
    "ReceivingJointLockParticipantProjection",
    "ReceivingJointLockPatternError",
    "ReceivingJointLockResolution",
    "resolve_receiving_joint_lock_pattern",
]
