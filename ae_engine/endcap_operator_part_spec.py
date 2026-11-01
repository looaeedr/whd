# -*- coding: utf-8 -*-
"""Engine-owned operator EndCap PartSpec request construction.

Consolidates the original Phase6 values, Family D/T compensation and verified
AssemblyJoint Bottom WRAP reserves.  This API creates a request only; a PartSpec
does not by itself certify output DXF or a complete assembly.
"""
from __future__ import annotations

from copy import deepcopy

from .box_body_fold_profile import profile_to_fold_segments
from .cabinet_types import policy as cabinet_family_policy
from .contracts import EndCapPartSpec
from .endcap_bottom_wrap_state import (
    normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap,
)


def build_endcap_operator_part_spec(
    values, *, model_name, is_tail, holes,
    corner_policy=None, fold_profiles=None, depth_comp_t=None,
    resolved_assembly_relief_cuts=(),
    box_body_formed_fw_left=None, box_body_formed_fw_right=None,
    box_body_structure_state=None, endcap_bottom_wrap_state=None,
    assembly_joints=None,
) -> EndCapPartSpec:
    """Build the canonical Head/Tail PartSpec from operator and saved inputs.

    Optional Bottom WRAP reserves are projected from Engine AssemblyJoint state,
    never from a GUI drawing.  Legacy malformed optional wrap-state projection
    is tolerated exactly as before; manufacturing source verification is not
    bypassed by this readback compatibility.
    """
    profiles = dict(fold_profiles or {})
    x_rows = [dict(row) for row in profiles.get("X", ())]
    y_rows = [dict(row) for row in profiles.get("Y", ())]

    if depth_comp_t is None:
        depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(model_name)

    structure = deepcopy(dict(box_body_structure_state or {}))
    joints = tuple(deepcopy(tuple(assembly_joints or ())))
    if cabinet_family_policy.supports_bottom_wrap_controls(model_name):
        try:
            part_key = "tail" if is_tail else "head"
            wrap_state = (
                endcap_bottom_wrap_state if endcap_bottom_wrap_state is not None
                else normalize_endcap_bottom_wrap_state({"model": model_name})
            )
            item = resolve_endcap_bottom_wrap(
                {"model": model_name, "assembly_joints": joints},
                part_key, state=wrap_state,
            )
            structure = cabinet_family_policy.set_bottom_relief_reserves(
                model_name, structure,
                reserve_u=item["reserve_u"], reserve_v=item["reserve_v"],
            )
        except Exception:
            # Preserve old optional preview/state projection behavior only.
            pass

    return EndCapPartSpec(
        width=float(values["w"]), height=float(values["h"]),
        depth=float(values["d"]), thickness=float(values["t"]),
        frame_width=float(values["fw"]), model_name=model_name,
        is_tail=bool(is_tail),
        fold_left=float(values["yl1"]), fold_right=float(values["yr1"]),
        fold_top=float(values["ytop1"]), fold_bottom=float(values["ybottom1"]),
        box_fold_left=float(values["zl1"]), box_fold_right=float(values["zr1"]),
        box_body_formed_fw_left=(
            None if box_body_formed_fw_left is None
            else float(box_body_formed_fw_left)
        ),
        box_body_formed_fw_right=(
            None if box_body_formed_fw_right is None
            else float(box_body_formed_fw_right)
        ),
        box_body_structure_state=structure,
        assembly_joints=joints,
        fold_profile_x=profile_to_fold_segments(x_rows),
        fold_profile_y=profile_to_fold_segments(y_rows),
        holes=tuple(holes or ()), corner_policy=corner_policy,
        depth_comp_t=float(depth_comp_t),
        resolved_assembly_relief_cuts=tuple(
            tuple((float(x), float(y)) for x, y in polygon)
            for polygon in tuple(resolved_assembly_relief_cuts or ())
            if len(polygon) >= 3
        ),
    )
