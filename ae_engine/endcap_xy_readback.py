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


def endcap_derived_core_lengths(snapshot: Mapping[str, object], width, depth) -> dict[str, int]:
    """Engine-owned EndCap X/Y material-core sizes for live Fold editor sync.

    Use the same canonical 4T W compensation and family-defined D compensation
    as build_endcap_xy_fold_profiles(). Legacy editor material rows round to
    whole millimetres, but do not write derived dimensions into saved Settings.
    """
    thickness = _num(snapshot.get("t", 2), 2)
    depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(snapshot)
    return {
        "endcap_w_core": _ui_len(max(0.0, float(width) - 4.0 * thickness)),
        "endcap_d_core": _ui_len(max(0.0, float(depth) - depth_comp_t * thickness)),
    }


def reconcile_endcap_live_outside_dimensions(
    snapshot: Mapping[str, object], *,
    top_width: int, top_depth: int, previous_width: int, previous_depth: int,
    profiles: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, int]:
    """Reconcile operator outside W/D edits against EndCap material Fold edits.

    Explicit top-panel input takes precedence over Fold changes. Otherwise
    changed EndCap cores become outside W/D using certified Family compensation.
    A missing core (e.g. OVERLAY with flat X) never fabricates dimensions.
    """
    def core_length(axis: str, part_key: str):
        for segment in profiles.get(axis, ()) or ():
            if segment.get("phase6_key") == part_key:
                return _ui_len(segment.get("len"))
        return None

    t = _num(snapshot.get("t", 2), 2)
    d_comp = cabinet_family_policy.endcap_depth_comp_t(snapshot)
    x_core = core_length("X", "endcap_w_core")
    y_core = core_length("Y", "endcap_d_core")
    expected_x = _ui_len(previous_width - 4.0 * t)
    expected_y = _ui_len(previous_depth - d_comp * t)
    width = (
        top_width if top_width != previous_width
        else _ui_len(x_core + 4.0 * t) if x_core is not None and x_core != expected_x
        else previous_width
    )
    depth = (
        top_depth if top_depth != previous_depth
        else _ui_len(y_core + d_comp * t) if y_core is not None and y_core != expected_y
        else previous_depth
    )
    return {"w": width, "d": depth}
