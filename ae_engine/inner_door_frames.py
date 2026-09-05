# -*- coding: utf-8 -*-
"""Canonical derived physical parts for one inner-door frame set.

The user's signed Fold Chain is preserved verbatim as direction semantics while
all manufacturable material lengths stay positive.  Stable IDs are derived only
from the authoritative inner-door ID plus frame side; geometry changes never
change identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .contracts import FoldProfileSegment

FRAME_SIDES = ("top", "bottom", "left", "right")
_FRAME_SIGNED_CHAINS = {
    "top": (22.0, 46.0, 22.0),
    "bottom": (22.0, 46.0, 22.0),
    "right": (22.0, 46.0, 22.0),
    "left": (-22.0, 20.0, 46.0, 22.0),
}


def _stable_inner_door_id(value: object) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError("inner_door_id must be a stable non-empty identifier")
    if ":" in result:
        raise ValueError("inner_door_id must not contain ':'")
    return result


def inner_door_frame_stable_id(inner_door_id: object, side: str) -> str:
    door_id = _stable_inner_door_id(inner_door_id)
    normalized = str(side or "").strip().lower()
    if normalized not in FRAME_SIDES:
        raise ValueError(f"unsupported inner-door frame side: {side!r}")
    return f"inner_door:{door_id}:{normalized}_frame"


@dataclass(frozen=True)
class InnerDoorFrameSet:
    """Authoritative parent input required to derive one inner-door frame set.

    ``spans`` are explicit longitudinal material spans supplied by the caller;
    this generic capability deliberately does not invent family-specific door
    clearance/frame-position formulas.
    """

    inner_door_id: str
    spans: Mapping[str, float]
    thickness: float
    included_sides: tuple[str, ...] = FRAME_SIDES


@dataclass(frozen=True)
class InnerDoorFramePart:
    stable_id: str
    inner_door_id: str
    side: str
    span: float
    thickness: float
    signed_fold_chain: tuple[float, ...]
    material_lengths: tuple[float, ...]
    fold_profile: tuple[FoldProfileSegment, ...]

    @property
    def blank_width(self) -> float:
        return sum(self.material_lengths)

    @property
    def blank_height(self) -> float:
        return float(self.span)


def _fold_profile_from_signed_chain(side: str, signed_chain: Sequence[float]) -> tuple[FoldProfileSegment, ...]:
    """Translate fixed signed-chain direction to the existing 90° fold profile.

    Phase6 signed length syntax carries direction, not negative material.  The
    standard frame bend adapter uses one right-angle bend after every segment
    except the last; the sign on a segment selects that bend's direction.
    """
    values = tuple(float(value) for value in signed_chain)
    rows = []
    for index, signed in enumerate(values):
        length = abs(signed)
        if length <= 0:
            raise ValueError("inner-door frame material length must be positive")
        angle = None if index == len(values) - 1 else (90.0 if signed >= 0 else -90.0)
        rows.append(FoldProfileSegment(
            length=length,
            angle=angle,
            phase6_key=f"inner_door_frame_{side}_{index + 1}",
        ))
    return tuple(rows)


def derive_inner_door_frames(
    inner_door_id: object,
    *,
    spans: Mapping[str, float],
    thickness: float,
    included_sides: Sequence[str] = FRAME_SIDES,
) -> tuple[InnerDoorFramePart, ...]:
    door_id = _stable_inner_door_id(inner_door_id)
    t = float(thickness)
    if t <= 0:
        raise ValueError("inner-door frame thickness must be > 0")
    include = tuple(str(side).strip().lower() for side in included_sides)
    if len(set(include)) != len(include):
        raise ValueError("inner-door frame sides must be unique")
    unknown = [side for side in include if side not in FRAME_SIDES]
    if unknown:
        raise ValueError(f"unsupported inner-door frame side: {unknown[0]!r}")

    result = []
    for side in FRAME_SIDES:
        if side not in include:
            continue
        if side not in spans:
            raise ValueError(f"missing explicit inner-door frame span: {side}")
        span = float(spans[side])
        if span <= 0:
            raise ValueError(f"inner-door frame span must be > 0: {side}")
        signed = _FRAME_SIGNED_CHAINS[side]
        material = tuple(abs(value) for value in signed)
        result.append(InnerDoorFramePart(
            stable_id=inner_door_frame_stable_id(door_id, side),
            inner_door_id=door_id,
            side=side,
            span=span,
            thickness=t,
            signed_fold_chain=tuple(signed),
            material_lengths=material,
            fold_profile=_fold_profile_from_signed_chain(side, signed),
        ))
    return tuple(result)


def derive_all_inner_door_frames(
    frame_sets: Sequence[InnerDoorFrameSet],
) -> tuple[InnerDoorFramePart, ...]:
    result = []
    stable_ids = set()
    for request in tuple(frame_sets or ()):
        frames = derive_inner_door_frames(
            request.inner_door_id,
            spans=request.spans,
            thickness=request.thickness,
            included_sides=request.included_sides,
        )
        for frame in frames:
            if frame.stable_id in stable_ids:
                raise ValueError(f"duplicate inner-door frame stable_id: {frame.stable_id}")
            stable_ids.add(frame.stable_id)
            result.append(frame)
    return tuple(result)


def inner_door_frame_part_profiles(frames: Sequence[InnerDoorFramePart]) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Project canonical frame parts into DesignerWorkspace fold profiles.

    This adapter carries only already-resolved physical-part geometry.  It never
    derives spans or family clearances, so GUI/workspace consumers cannot grow a
    second sizing formula.
    """
    result: dict[str, dict[str, list[dict[str, object]]]] = {}
    for frame in tuple(frames or ()):
        result[str(frame.stable_id)] = {
            "X": [
                {
                    "len": float(row.length),
                    **({"angle": float(row.angle)} if row.angle is not None else {}),
                    "phase6_key": str(row.phase6_key or ""),
                }
                for row in frame.fold_profile
            ],
            "Y": [{
                "len": float(frame.span),
                "phase6_key": "inner_door_frame_span",
            }],
        }
    return result


def is_inner_door_frame_part_key(value: object) -> bool:
    key = str(value or "")
    return key.startswith("inner_door:") and key.endswith("_frame")
