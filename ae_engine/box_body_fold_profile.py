# -*- coding: utf-8 -*-
"""Only Engine owns BoxBody outside-to-material Fold and DTO conversion.

The former Phase6/Worker source is a thin compatibility caller. This module
reuses canonical Cabinet Family policy and has no GUI/Tk/phase6 imports.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from .contracts import FoldProfileSegment
from .cabinet_types import policy as cabinet_family_policy

BOX_BODY_TURNS = (90, -90, -90, -90, -90, -90, -90, 90)

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def _ui_len(value):
    """The user's fold editor displays operator fold lengths as integers."""
    return int(round(abs(_num(value))))

def _common_dimension_len(snapshot, value):
    """Common Receiving dimensions keep precision; manual fold rows keep their UI contract."""
    if snapshot.get("active_mode") == "quantity" and snapshot.get("receiving_quantity_box"):
        return abs(_num(value))
    return _ui_len(value)

def _has_real_bend(segment: Mapping[str, object]) -> bool:
    """A segment owns the bend on its right boundary when angle is non-zero."""
    return "angle" in segment and abs(_num(segment.get("angle"))) > 1e-9

def apply_outside_dimension_compensation(profile: Sequence[dict], thickness) -> list[dict]:
    """Annotate material segments with operator outside-dimension compensation.

    Material/profile ``len`` values never change.  Each real bend adjacent to a
    segment contributes one sheet thickness to the operator-facing outside
    dimension: outer segments normally gain 1T and interior segments 2T.
    """
    t = max(0.0, _num(thickness))
    segs = list(profile)
    for index, seg in enumerate(segs):
        bend_count = 0
        if index > 0 and _has_real_bend(segs[index - 1]):
            bend_count += 1
        if index < len(segs) - 1 and _has_real_bend(seg):
            bend_count += 1
        if bend_count:
            seg["ui_len_add"] = bend_count * t
        else:
            seg.pop("ui_len_add", None)
    return segs



def outside_profile_to_material(profile: Sequence[dict], thickness, *, preserve_core_precision=False, preserve_precision=False) -> list[dict]:
    """Convert operator outside segment lengths to canonical material lengths.

    Each real adjacent BEND contributes exactly 1T.  The bend count comes from
    the actual current topology, so deleting a bend automatically changes the
    conversion.  ``ui_len_add`` remains presentation metadata only.
    """
    t = max(0.0, _num(thickness))
    rows = apply_outside_dimension_compensation([dict(row) for row in profile], t)
    for seg in rows:
        outside = abs(_num(seg.get("len")))
        # Operator-facing fold inputs are integers; internal flat/material
        # spans are NOT.  Keep fractional T here (e.g. 24 outside - 1.5T =
        # 22.5 material), or an early int(round(...)) silently changes 24 to
        # 23.5 when the mesh later restores formed/outside metadata.
        # 3D UI 包外是唯一輸入；料長保持精度，不把 material 取整。
        seg["len"] = _num(max(0.0, outside - abs(_num(seg.get("ui_len_add")))))
    return apply_outside_dimension_compensation(rows, t)

def build_box_body_profile(snapshot: Mapping[str, object]) -> list[dict]:
    """Map Phase6 box-body values into the original editor's segment list.

    D-W-D are explicit, fixed-position core segments.  Extra fold geometry is
    represented only by the existing Phase6 values surrounding that core.
    """
    t = _num(snapshot.get("t", 2), 2)
    outside_family = cabinet_family_policy.box_body_profile_uses_outside_dimensions(snapshot)
    outside_add = max(0.0, 2.0 * t)
    if outside_family:
        # Family defaults are operator outside dimensions. Build the
        # topology first, then convert every segment by its real adjacent bends.
        lengths = (
            _ui_len(snapshot.get("zl1")), _ui_len(snapshot.get("zl2")),
            _ui_len(snapshot.get("fw")), _common_dimension_len(snapshot, snapshot.get("d")),
            _common_dimension_len(snapshot, snapshot.get("w")), _common_dimension_len(snapshot, snapshot.get("d")),
            _ui_len(snapshot.get("fw")), _ui_len(snapshot.get("zr2")),
            _ui_len(snapshot.get("zr1")),
        )
    else:
        lengths = (
            _ui_len(snapshot.get("zl1")),
            _ui_len(snapshot.get("zl2")),
            _ui_len(snapshot.get("fw")),
            _ui_len(max(0.0, _num(snapshot.get("d")) - outside_add)),
            _ui_len(max(0.0, _num(snapshot.get("w")) - outside_add)),
            _ui_len(max(0.0, _num(snapshot.get("d")) - outside_add)),
            _ui_len(snapshot.get("fw")),
            _ui_len(snapshot.get("zr2")),
            _ui_len(snapshot.get("zr1")),
        )
    cores = (None, None, None, "D", "W", "D", None, None, None)
    phase6_keys = ("zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2", "zr1")
    result = []
    for index, (length, core, phase6_key) in enumerate(zip(lengths, cores, phase6_keys)):
        seg = {"len": length, "phase6_key": phase6_key}
        if index < len(BOX_BODY_TURNS):
            seg["angle"] = BOX_BODY_TURNS[index]
        if core:
            seg["core"] = core
        result.append(seg)
    result = cabinet_family_policy.transform_box_body_profile(snapshot, result)
    if outside_family:
        return outside_profile_to_material(result, t, preserve_core_precision=bool(snapshot.get("receiving_quantity_box") and snapshot.get("active_mode") == "quantity"))
    return apply_outside_dimension_compensation(result, t)


def profile_to_fold_segments(profile: Sequence[Mapping[str, object]]):
    """Convert editor dictionaries into the GUI-independent manufacturing contract.

    ``length`` remains the flat/material span. When the editor profile carries
    topology-derived outside-dimension compensation, preserve that semantic as an
    independent ``formed_length`` instead of dropping it at the GUI→manufacturing
    seam. ``formed_length`` is metadata for physical outside-face resolution;
    the folded material midline still consumes ``length``. Core D/W segments
    keep their separate assembly datum and do not receive outside-leg metadata.
    """
    rows = []
    for seg in profile or ():
        material_length = float(seg.get("len", 0.0))
        ui_add = seg.get("ui_len_add")
        phase6_key = str(seg.get("phase6_key") or "")
        formed_length = (
            material_length + abs(float(ui_add))
            if ui_add is not None and not seg.get("core")
            else None
        )
        rows.append(FoldProfileSegment(
            length=material_length,
            angle=(float(seg["angle"]) if "angle" in seg else None),
            core=(str(seg.get("core")) if seg.get("core") else None),
            phase6_key=(phase6_key if phase6_key else None),
            formed_length=formed_length,
        ))
    return tuple(rows)



def merge_box_body_fold_profile(profile: Sequence[Mapping[str, object]], snapshot: Mapping[str, object]) -> list[dict]:
    """Refresh shared semantic core values without changing user Fold topology.

    Once an operator removes/adds a mapped outer segment, that structural choice
    is authoritative. Missing canonical keys are never recreated. Existing
    semantic keys (notably D-W-D/FW) still receive current material lengths.
    """
    merged = deepcopy(list(profile))
    if not merged:
        return build_box_body_profile(snapshot)
    canonical = {seg.get("phase6_key"): seg for seg in build_box_body_profile(snapshot)}
    for seg in merged:
        key = seg.get("phase6_key")
        source = canonical.get(key)
        if source is None:
            continue
        # D/W/FW remain tied to current global dimensions. Removed outer folds
        # are not resurrected; retained outer mapped folds keep their own edited
        # length unless they are structural shared dimensions.
        if key in {"d_left", "w", "d_right", "fw_left", "fw_right"}:
            seg["len"] = source["len"]
        for name in ("ui_len_add", "core"):
            if name in source:
                seg[name] = source[name]
            else:
                seg.pop(name, None)
    # Cabinet-family topology is authoritative over a previous family's saved
    # outer folds.  In particular, receiving removes terminal ``zr1``; keeping
    # the vault row merely because it existed before the family switch leaks the
    # vault topology back into the live receiving editor.
    merged = cabinet_family_policy.transform_box_body_profile(snapshot, merged)
    apply_outside_dimension_compensation(merged, snapshot.get("t", 2))
    # The D-W-D core is mandatory and cannot be removed through the UI. Reject
    # corrupt files rather than silently replacing their topology.
    d_segments = [seg for seg in merged if seg.get("core") == "D"]
    w_segments = [seg for seg in merged if seg.get("core") == "W"]
    if len(d_segments) != 2 or len(w_segments) != 1:
        raise ValueError("箱身折法資料缺少 D-W-D 核心")
    return merged
