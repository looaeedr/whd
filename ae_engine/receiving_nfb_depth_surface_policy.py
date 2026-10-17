# -*- coding: utf-8 -*-
"""Receiving NFB installation: REAL physical faces, never sheet mid-planes.

#1502 / #1503. Source of model depths: the selected brand/model CSV, passed
by its caller. This module deliberately does not guess a brand or certify 3D,
DXF, CUTTING/BEND or weld-ear MARKING from arithmetic alone.

The shop does not apply bend compensation. In particular the NFB face-to-face
step (107 - 72 = 35) is not automatically the outside dimension of one bend.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


FIRST_SIDE_FOLD_MM = -40.0


@dataclass(frozen=True)
class ReceivingNfbSurfaceChain:
    """All Zs measured inward from the SAME outer-door physical face (mm)."""

    inner_door_outer_face_mm: float
    inner_door_inner_face_mm: float
    reference_base_nfb_face_mm: float
    reference_base_back_face_mm: float
    fixing_plate_contact_face_mm: float
    fixing_plate_back_face_mm: float
    secondary_base_nfb_face_mm: float | None
    secondary_base_back_face_mm: float | None
    nfb_face_step_mm: float | None
    second_side_fold_mm: float | None

    @property
    def fixing_plate_contact_mark_from_front_mm(self) -> float:
        """Side-wall marking DEPTH target; not a released 2D MARKING entity.

        The actual side-sheet UV/X/Y, weld outline and projection must come
        from the real side-sheet/ear assembly; never draw a bogus DXF line.
        """
        return self.fixing_plate_contact_face_mm


def receiving_nfb_second_side_fold_mm(
    *, reference_nfb_depth_mm: float, secondary_nfb_depth_mm: float,
    base_plate_thickness_mm: float,
) -> float:
    """User's NON-FOLDED two-plate inference for the 2nd side return.

    Put both virtual flat base plates against the SAME inner-door inside
    physical face:
       NFB deep mount face = inside face + deep NFB depth
       NFB shallow mount face = inside face + shallow NFB depth
       shallow back skin     = shallow mount face + base T
       second return         = deep mount face - shallow back skin

    Shihlin 107/72, T2 => (107 - 72) - 2 = 33 mm.
    There is ONE base-plate T deduction, not two. The real pair of front
    NFB mounting surfaces is still 35 mm apart. FIRST side fold stays -40.
    This is a target material/face-chain dimension, NOT a claim that every
    BEND station-to-station material interval or one folded outside envelope
    equals 33, and not approval of manufacture.
    """
    d, s, t = (float(reference_nfb_depth_mm),
               float(secondary_nfb_depth_mm), float(base_plate_thickness_mm))
    if not all(isfinite(x) and x > 0 for x in (d, s, t)):
        raise ValueError("NFB depth and base plate T must be positive finite values")
    if d <= s:
        raise ValueError("reference NFB depth must be deeper than secondary")
    result = d - s - t
    if result <= 0:
        raise ValueError("NFB depth step too small for physical second side return")
    return result


def resolve_receiving_nfb_surface_chain(
    *, inner_door_outer_face_from_front_mm: float,
    inner_door_thickness_mm: float,
    base_plate_thickness_mm: float,
    fixing_plate_thickness_mm: float,
    reference_nfb_depth_mm: float,
    secondary_nfb_depth_mm: float | None = None,
) -> ReceivingNfbSurfaceChain:
    """Compute relative physical face positions without double-counting T.

    The 80-mm inner-door offset in a live GUI/3D snapshot may be a CENTER
    offset; only pass 80 here if verified to be its OUTER physical face.
    Callers must first resolve actual folded-mesh skins from the authoritative
    assembly transform. Passing an unverified placement center is forbidden.

    Deep base plate and BOTH fixing plates share one translated Z datum.
    The base BACK skin touches the fixing plate FRONT skin with zero gap.
    """
    outer, it, bt, ft, deep = (float(inner_door_outer_face_from_front_mm),
                             float(inner_door_thickness_mm),
                             float(base_plate_thickness_mm),
                             float(fixing_plate_thickness_mm),
                             float(reference_nfb_depth_mm))
    if not isfinite(outer) or outer < 0:
        raise ValueError("inner door outer physical face requires finite nonnegative offset")
    if not all(isfinite(v) and v > 0 for v in (it, bt, ft, deep)):
        raise ValueError("inner door/base/fixing thickness and NFB depth must be positive")
    door_inner = outer + it
    deep_front = door_inner + deep
    deep_back = deep_front + bt
    secondary_front = secondary_back = face_step = return_mm = None
    if secondary_nfb_depth_mm is not None:
        shallow = float(secondary_nfb_depth_mm)
        return_mm = receiving_nfb_second_side_fold_mm(
            reference_nfb_depth_mm=deep, secondary_nfb_depth_mm=shallow,
            base_plate_thickness_mm=bt,
        )
        secondary_front = door_inner + shallow
        secondary_back = secondary_front + bt
        face_step = deep_front - secondary_front
        assert abs((deep_front - secondary_back) - return_mm) < 1e-8
    return ReceivingNfbSurfaceChain(
        inner_door_outer_face_mm=outer,
        inner_door_inner_face_mm=door_inner,
        reference_base_nfb_face_mm=deep_front,
        reference_base_back_face_mm=deep_back,
        fixing_plate_contact_face_mm=deep_back,
        fixing_plate_back_face_mm=deep_back + ft,
        secondary_base_nfb_face_mm=secondary_front,
        secondary_base_back_face_mm=secondary_back,
        nfb_face_step_mm=face_step,
        second_side_fold_mm=return_mm,
    )
