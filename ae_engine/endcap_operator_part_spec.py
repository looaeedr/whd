# -*- coding: utf-8 -*-
"""Engine-owned operator EndCap PartSpec request construction.

Consolidates the original Phase6 values, Family D/T compensation and verified
AssemblyJoint Bottom WRAP reserves.  This API creates a request only; a PartSpec
does not by itself certify output DXF or a complete assembly.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite

from .box_body_fold_profile import profile_to_fold_segments
from .cabinet_types import policy as cabinet_family_policy
from .contracts import EndCapPartSpec
from .endcap_bottom_wrap_state import (
    normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap,
)
from .operator_settings_transactions import (
    normalize_operator_settings_boolean, normalize_operator_source_dimension,
)


def _finite_operator_fold(raw, field):
    """Keep existing signed Fold/reserve semantics, reject invented numeric mm."""
    if isinstance(raw, bool):
        raise ValueError(f"ENDCAP_OPERATOR_SOURCE_INVALID: {field}")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"ENDCAP_OPERATOR_SOURCE_INVALID: {field}") from exc
    if not isfinite(value):
        raise ValueError(f"ENDCAP_OPERATOR_SOURCE_INVALID: {field}")
    return value


def build_endcap_operator_part_spec(
    values, *, model_name, is_tail, holes,
    corner_policy=None, fold_profiles=None, depth_comp_t=None,
    resolved_assembly_relief_cuts=(),
    box_body_formed_fw_left=None, box_body_formed_fw_right=None,
    box_body_structure_state=None, endcap_bottom_wrap_state=None,
    assembly_joints=None, assembly_joint_state=None,
) -> EndCapPartSpec:
    """Build the canonical Head/Tail PartSpec from operator and saved inputs.

    Optional Bottom WRAP reserves are projected from Engine AssemblyJoint state,
    never from a GUI drawing.  Legacy malformed optional wrap-state projection
    is tolerated exactly as before; manufacturing source verification is not
    bypassed by this readback compatibility.
    """
    physical = {
        key: normalize_operator_source_dimension(values[key], field=key)
        for key in ("w", "h", "d", "t", "fw")
    }
    tail = normalize_operator_settings_boolean(is_tail)
    profiles = dict(fold_profiles or {})
    x_rows = [dict(row) for row in profiles.get("X", ())]
    y_rows = [dict(row) for row in profiles.get("Y", ())]

    # A Receiving EndCap with an already-authored canonical X/Y Fold has no
    # reason to demand a second copy of the legacy yl1/yr1 scalar inputs from
    # CADSplit. Read the real physical segments in Engine; never fall back to
    # Vault/config.ini numbers or reconstruct missing Fold/Corner geometry.
    source_values = dict(values)
    missing = {
        key for key in ("yl1", "yr1", "ytop1", "ybottom1", "zr1")
        if key not in source_values
    }
    is_receiving = cabinet_family_policy.canonical_family_name(model_name) == "受電箱"
    if missing and is_receiving:
        if not x_rows or not y_rows or corner_policy is None:
            raise ValueError("RECEIVING_ENDCAP_AUTHORED_FOLD_REQUIRED")
        if (missing & {"yl1", "yr1"}
                and len(x_rows) == 1
                and x_rows[0].get("phase6_key") == "endcap_w_flat"):
            raise ValueError("RECEIVING_ENDCAP_X_FOLD_SOURCE_REQUIRED")
        from .endcap_xy_readback import resolve_endcap_xy_outside_dimensions
        from math import isclose
        projected = resolve_endcap_xy_outside_dimensions(
            profiles, {**source_values, "model": model_name}
        )
        for key in ("w", "d"):
            observed = physical[key]
            if not isfinite(observed) or not isclose(
                float(projected[key]), observed, rel_tol=0.0, abs_tol=1e-6
            ):
                raise ValueError("RECEIVING_ENDCAP_SOURCE_FOLD_CONFLICT")
        for key in ("yl1", "yr1", "ytop1", "ybottom1"):
            if key in missing:
                source_values[key] = float(projected[key])

    def scalar(key):
        if key in source_values:
            return _finite_operator_fold(source_values[key], key)
        if is_receiving and key == "zr1" and x_rows and y_rows and corner_policy is not None:
            return None  # Receiving split side/body has no terminal zr1 Fold.
        raise KeyError(key)

    if depth_comp_t is None:
        depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(model_name)

    structure = deepcopy(dict(box_body_structure_state or {}))
    joints = tuple(deepcopy(tuple(assembly_joints or ())))
    # The original saved Joint Graph may carry a schema version and extra
    # source data required by edge_relation_for_part. Keep that context when
    # the operator did not explicitly supply an override Joint list.
    joint_snapshot = (
        deepcopy(dict(assembly_joint_state))
        if assembly_joint_state is not None else {"assembly_joints": joints}
    )
    if cabinet_family_policy.supports_bottom_wrap_controls(model_name):
        try:
            part_key = "tail" if tail else "head"
            wrap_state = (
                endcap_bottom_wrap_state if endcap_bottom_wrap_state is not None
                else normalize_endcap_bottom_wrap_state({"model": model_name})
            )
            item = resolve_endcap_bottom_wrap(
                {"model": model_name, **joint_snapshot},
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
        width=physical["w"], height=physical["h"],
        depth=physical["d"], thickness=physical["t"],
        frame_width=physical["fw"], model_name=model_name,
        is_tail=tail,
        fold_left=scalar("yl1"), fold_right=scalar("yr1"),
        fold_top=scalar("ytop1"), fold_bottom=scalar("ybottom1"),
        box_fold_left=scalar("zl1"), box_fold_right=scalar("zr1"),
        box_body_formed_fw_left=(
            None if box_body_formed_fw_left is None
            else _finite_operator_fold(box_body_formed_fw_left, "box_body_formed_fw_left")
        ),
        box_body_formed_fw_right=(
            None if box_body_formed_fw_right is None
            else _finite_operator_fold(box_body_formed_fw_right, "box_body_formed_fw_right")
        ),
        box_body_structure_state=structure,
        assembly_joints=joints,
        fold_profile_x=profile_to_fold_segments(x_rows),
        fold_profile_y=profile_to_fold_segments(y_rows),
        holes=tuple(holes or ()), corner_policy=corner_policy,
        depth_comp_t=_finite_operator_fold(depth_comp_t, "depth_comp_t"),
        resolved_assembly_relief_cuts=tuple(
            tuple((float(x), float(y)) for x, y in polygon)
            for polygon in tuple(resolved_assembly_relief_cuts or ())
            if len(polygon) >= 3
        ),
    )
