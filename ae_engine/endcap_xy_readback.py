# -*- coding: utf-8 -*-
"""Headless EndCap X/Y material-to-outside readback.

The existing Family authority determines Receiving 2T / Vault 3T D core,
material FW, and canonical EndCap topology. No GUI/Phase6 reverse import.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from .cabinet_types import policy as cabinet_family_policy
from .box_body_fold_profile import _num, _ui_len, _common_dimension_len


def fold_material_segment_outside_length(seg: Mapping[str, object]):
    """Existing adjacent-BEND metadata affects the operator outside span."""
    return _ui_len(_num(seg.get("len")) + _num(seg.get("ui_len_add")))


def resolve_endcap_xy_outside_dimensions(profiles: Mapping[str, Sequence[Mapping[str, object]]], original_snapshot: Mapping[str, object]) -> dict:
    """Read EndCap editor topology back into legacy scalar adapter values.

    ``ytop1`` is no longer structurally mandatory: when the BoxBody front
    topology removes its outer fold, linked EndCaps legitimately contain only
    FW -> D-core -> bottom (head) or the native reverse (tail).  Extra mating
    rows, when present, are aggregated only for the legacy ``fold_top`` scalar;
    authoritative BEND order/angles remain in the full Fold Profile.
    """
    x_rows = [dict(seg) for seg in profiles.get("X", ())]
    y_rows = [dict(seg) for seg in profiles.get("Y", ())]
    x = {str(seg.get("phase6_key")): seg for seg in x_rows if seg.get("phase6_key")}
    y = {str(seg.get("phase6_key")): seg for seg in y_rows if seg.get("phase6_key")}
    required_x = {"yl1", "endcap_w_core", "yr1"}
    required_y = {"fw", "endcap_d_core", "ybottom1"}
    flat_x = len(x_rows) == 1 and x_rows[0].get("phase6_key") == "endcap_w_flat"
    if (not required_x.issubset(x) and not flat_x) or not required_y.issubset(y):
        raise ValueError("封頭/封尾 X/Y 折彎資料不完整")
    t = _num(original_snapshot.get("t", 2), 2)
    top_fold = sum(
        _ui_len(seg.get("len"))
        for seg in y_rows
        if seg.get("phase6_key") not in {"fw", "endcap_d_core", "ybottom1"}
    )
    depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(original_snapshot)
    return {
        "w": (
            _common_dimension_len(original_snapshot, original_snapshot.get("w", 0))
            if flat_x else _common_dimension_len(original_snapshot, x["endcap_w_core"].get("len")) + 4.0 * t
        ),
        # The editor stores canonical EndCap material core. Convert back with
        # the same family compensation used by build_endcap_xy_profiles().
        # Using the vault legacy 3T here for receiving (2T) grew global D by
        # exactly +1T every time Head/Tail was saved during part switching.
        "d": _common_dimension_len(original_snapshot, y["endcap_d_core"].get("len")) + depth_comp_t * t,
        "fw": (fold_material_segment_outside_length(y["fw"]) if cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(original_snapshot) else _ui_len(y["fw"].get("len"))),
        "yl1": (
            _ui_len(original_snapshot.get("yl1", 15))
            if flat_x else _ui_len(x["yl1"].get("len"))
        ),
        "yr1": (
            _ui_len(original_snapshot.get("yr1", 15))
            if flat_x else _ui_len(x["yr1"].get("len"))
        ),
        "ytop1": _ui_len(top_fold),
        "ybottom1": _ui_len(y["ybottom1"].get("len")),
    }

