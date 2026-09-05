# -*- coding: utf-8 -*-
"""Phase6 Fold Profile 與 linked EndCap mating chain 的單一所有權模組。"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping, Sequence

from ae_engine.sheetmetal_geometry import CornerTypeId
from ae_engine.contracts import FoldProfileSegment
from ae_engine.cabinet_types import policy as cabinet_family_policy
from phase6_endcap_semantics import (
    ENDCAP_FW_PARTS, normalize_endcap_fw_state, resolve_endcap_fw, resolve_box_assembly_type,
)

_BOX_BODY_TURNS = (90, -90, -90, -90, -90, -90, -90, 90)

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def _ui_len(value):
    """The user's fold editor displays operator fold lengths as integers."""
    return int(round(abs(_num(value))))

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



def _outside_profile_to_material(profile: Sequence[dict], thickness) -> list[dict]:
    """Convert operator outside segment lengths to canonical material lengths.

    Each real adjacent BEND contributes exactly 1T.  The bend count comes from
    the actual current topology, so deleting a bend automatically changes the
    conversion.  ``ui_len_add`` remains presentation metadata only.
    """
    t = max(0.0, _num(thickness))
    rows = apply_outside_dimension_compensation([dict(row) for row in profile], t)
    for seg in rows:
        outside = abs(_num(seg.get("len")))
        seg["len"] = _ui_len(max(0.0, outside - abs(_num(seg.get("ui_len_add")))))
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
            _ui_len(snapshot.get("fw")), _ui_len(snapshot.get("d")),
            _ui_len(snapshot.get("w")), _ui_len(snapshot.get("d")),
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
        if index < len(_BOX_BODY_TURNS):
            seg["angle"] = _BOX_BODY_TURNS[index]
        if core:
            seg["core"] = core
        result.append(seg)
    result = cabinet_family_policy.transform_box_body_profile(snapshot, result)
    if outside_family:
        return _outside_profile_to_material(result, t)
    return apply_outside_dimension_compensation(result, t)

def _signed_like(original, magnitude):
    return -abs(magnitude) if _num(original) < 0 else abs(magnitude)

def build_endcap_profile(snapshot: Mapping[str, object]) -> list[dict]:
    """Feed Phase6 top/depth/bottom material lengths into the original tab."""
    profile = [
        {"len": _ui_len(snapshot.get("ytop1")), "angle": -90, "phase6_key": "ytop1"},
        {"len": _ui_len(snapshot.get("d")), "angle": -90, "phase6_key": "endcap_d"},
        {"len": _ui_len(snapshot.get("ybottom1")), "phase6_key": "ybottom1"},
    ]
    return apply_outside_dimension_compensation(profile, snapshot.get("t", 2))

def read_endcap_profile(profile: Sequence[Mapping[str, object]]) -> dict:
    by_key = {str(seg.get("phase6_key")): seg for seg in profile if seg.get("phase6_key")}
    if not {"ytop1", "endcap_d", "ybottom1"}.issubset(by_key):
        raise ValueError("封頭/封尾折彎資料缺少原本三段")
    return {
        "ytop1": _ui_len(by_key["ytop1"].get("len")),
        "d": _ui_len(by_key["endcap_d"].get("len")),
        "ybottom1": _ui_len(by_key["ybottom1"].get("len")),
    }

def build_endcap_xy_profiles(snapshot: Mapping[str, object], *, part_key: str = "head") -> dict[str, list[dict]]:
    """Map authoritative EndCap bends into the editor without mirroring tail.

    Head manufacturing scenes are Y-normalized once by AE, while tail scenes stay
    in their native orientation.  Therefore the editor Y-chain order must be
    part-aware: head walks top->bottom after normalization; tail walks the native
    bottom->top scene.  Lengths remain authoritative material lengths.
    """
    w = _num(snapshot.get("w", 500), 500)
    d = _num(snapshot.get("d", 200), 200)
    t = _num(snapshot.get("t", 2), 2)
    fw = resolve_endcap_fw(snapshot, part_key)
    material_fw = cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(snapshot)
    if material_fw:
        # Receiving operator FW is outside 29; canonical Y Fold Profile stores material 25.
        fw = max(0.0, float(fw) - 2.0 * t)
    x_core = max(0.0, w - 4.0 * t)
    depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(snapshot)
    y_core = max(0.0, d - depth_comp_t * t)
    outside_add = max(0.0, 2.0 * t)
    x_profile = [
        {"len": _ui_len(snapshot.get("yl1", 15)), "angle": -90, "phase6_key": "yl1"},
        {"len": _ui_len(x_core), "angle": -90, "phase6_key": "endcap_w_core",
         "core": "W-2T"},
        {"len": _ui_len(snapshot.get("yr1", 15)), "phase6_key": "yr1"},
    ]
    if resolve_box_assembly_type(snapshot) is CornerTypeId.OVERLAY:
        # 貼外型封頭／封尾沒有左右 X 折彎，因此整片 X 向材料寬就是 W。
        # 下方 CROSS + EXTRA_CUT 的 1.5T 只改角落 CUTTING，不得把
        # 原本 INSERT 型的 yl1 / yr1 折邊寬度加回整張材料外框。
        x_profile = [
            {"len": _ui_len(w), "phase6_key": "endcap_w_flat", "core": "W-FLAT"}
        ]

    profiles = {
        "X": x_profile,
        "Y": (
            [
                {"len": _ui_len(snapshot.get("ybottom1", 15)), "angle": -90, "phase6_key": "ybottom1"},
                {"len": _ui_len(y_core), "angle": -90, "phase6_key": "endcap_d_core",
                 "core": "D-T"},
                {"len": _ui_len(fw), "angle": -90, "phase6_key": "fw"},
                {"len": _ui_len(snapshot.get("ytop1", 16)), "phase6_key": "ytop1"},
            ]
            if str(part_key) == "tail" else
            [
                {"len": _ui_len(snapshot.get("ytop1", 16)), "angle": -90, "phase6_key": "ytop1"},
                {"len": _ui_len(fw), "angle": -90, "phase6_key": "fw"},
                {"len": _ui_len(y_core), "angle": -90, "phase6_key": "endcap_d_core",
                 "core": "D-T"},
                {"len": _ui_len(snapshot.get("ybottom1", 15)), "phase6_key": "ybottom1"},
            ]
        ),
    }
    profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
    profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
    return profiles

def _phase6_fold_tabs_for_part(snapshot: Mapping[str, object], part_key: str):
    """Return an explicit Fold-editor tab set only when topology requires it."""
    key = str(part_key or "")
    if key in ENDCAP_FW_PARTS and resolve_box_assembly_type(snapshot) is CornerTypeId.OVERLAY:
        # OVERLAY has no left/right X bends, so the 3D Fold editor must not offer
        # a fictitious X-axis bend page. Y remains the real editable fold chain.
        return ["Y"]
    return None

def _phase6_normalize_endcap_profile_order(profiles, snapshot, part_key):
    """Migrate legacy stored head/tail canonical profiles without touching extras."""
    copied = {
        "X": clone_profile((profiles or {}).get("X", ())),
        "Y": clone_profile((profiles or {}).get("Y", ())),
    }
    if str(part_key) != "tail":
        return copied
    canonical = ("ybottom1", "endcap_d_core", "fw", "ytop1")
    current = copied.get("Y", [])
    keyed = [seg.get("phase6_key") for seg in current if seg.get("phase6_key")]
    if len(current) != 4 or set(keyed) != set(canonical):
        return copied
    by_key = {seg.get("phase6_key"): dict(seg) for seg in current}
    defaults = build_endcap_xy_profiles(snapshot, part_key="tail")["Y"]
    reordered = []
    for default in defaults:
        key = default.get("phase6_key")
        seg = by_key[key]
        if "angle" in default:
            seg["angle"] = default["angle"]
        else:
            seg.pop("angle", None)
        for name in ("ui_len_add", "core"):
            if name in default:
                seg[name] = default[name]
            else:
                seg.pop(name, None)
        reordered.append(seg)
    copied["Y"] = reordered
    return copied

def read_endcap_xy_profiles(profiles: Mapping[str, Sequence[Mapping[str, object]]], original_snapshot: Mapping[str, object]) -> dict:
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
            _ui_len(original_snapshot.get("w", 0))
            if flat_x else _ui_len(x["endcap_w_core"].get("len")) + 4.0 * t
        ),
        # The editor stores canonical EndCap material core. Convert back with
        # the same family compensation used by build_endcap_xy_profiles().
        # Using the vault legacy 3T here for receiving (2T) grew global D by
        # exactly +1T every time Head/Tail was saved during part switching.
        "d": _ui_len(y["endcap_d_core"].get("len")) + depth_comp_t * t,
        "fw": (engine_segment_length_to_ui(y["fw"]) if cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(original_snapshot) else _ui_len(y["fw"].get("len"))),
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

def engine_angle_to_ui(value):
    """Return the exact operator-facing angle for the stored engine convention."""
    angle = _num(value)
    if angle in (90.0, -90.0):
        angle = -angle
    return int(angle) if float(angle).is_integer() else angle

def ui_angle_to_engine(value):
    """Preserve the operator input through the existing engine sign convention."""
    angle = _num(value)
    if angle in (90.0, -90.0):
        angle = -angle
    return int(angle) if float(angle).is_integer() else angle

def formed_box_body_fw_widths(profile: Sequence[Mapping[str, object]], thickness) -> tuple[float | None, float | None]:
    """Return formed left/right Box Body FW outside widths from the actual fold topology.

    ``len`` is the flat/material FW.  Assembly insertion clearance must use the
    formed outside occupation, so adjacent real bends contribute their actual
    thickness compensation.  Recompute that compensation from the current
    profile instead of trusting stale saved ``ui_len_add`` metadata.
    """
    rows = apply_outside_dimension_compensation(clone_profile(profile), thickness)
    by_key = {str(seg.get("phase6_key") or ""): seg for seg in rows}
    def one(key):
        seg = by_key.get(key)
        if seg is None:
            return None
        return abs(_num(seg.get("len"))) + abs(_num(seg.get("ui_len_add")))
    return one("fw_left"), one("fw_right")


def engine_segment_length_to_ui(seg: Mapping[str, object]):
    """Return the operator-facing outside fold length for one engine segment.

    ``len`` remains the real Renderer/BEND-line span.  ``ui_len_add`` is only
    the outside-dimension compensation shown in the editor.
    """
    return _ui_len(_num(seg.get("len")) + _num(seg.get("ui_len_add")))

def ui_segment_length_to_engine(seg: Mapping[str, object], ui_value):
    """Convert an operator outside dimension back to the Renderer span."""
    return _ui_len(max(0.0, _num(ui_value) - _num(seg.get("ui_len_add"))))

def read_box_body_profile(profile: Sequence[Mapping[str, object]], original: Mapping[str, object]) -> dict:
    """Convert known Phase6 positions back while allowing extra outer folds."""
    by_key = {str(seg.get("phase6_key")): seg for seg in profile if seg.get("phase6_key")}
    d_segments = [seg for seg in profile if seg.get("core") == "D"]
    w_segments = [seg for seg in profile if seg.get("core") == "W"]
    if len(d_segments) != 2 or len(w_segments) != 1:
        raise ValueError("中央三段必須固定為 D-W-D")

    d_left = engine_segment_length_to_ui(d_segments[0])
    d_right = engine_segment_length_to_ui(d_segments[1])
    if d_left != d_right:
        raise ValueError("D-W-D 的兩個 D 必須相同")
    w_value = engine_segment_length_to_ui(w_segments[0])

    material_profile = cabinet_family_policy.box_body_profile_uses_outside_dimensions(original)
    fw_left_seg = by_key.get("fw_left")
    fw_right_seg = by_key.get("fw_right")
    if fw_left_seg is not None and fw_right_seg is not None:
        fw_left = engine_segment_length_to_ui(fw_left_seg) if material_profile else _ui_len(fw_left_seg.get("len"))
        fw_right = engine_segment_length_to_ui(fw_right_seg) if material_profile else _ui_len(fw_right_seg.get("len"))
        if fw_left != fw_right:
            raise ValueError("左右 FW 必須相同")
        fw_value = fw_left
    elif fw_left_seg is not None:
        fw_value = _ui_len(fw_left_seg.get("len"))
    elif fw_right_seg is not None:
        fw_value = _ui_len(fw_right_seg.get("len"))
    else:
        fw_value = _ui_len(original.get("fw"))

    def known_len(key, fallback):
        seg = by_key.get(key)
        if seg is None:
            return _ui_len(fallback)
        return engine_segment_length_to_ui(seg) if material_profile else _ui_len(seg.get("len"))

    return {
        "zl1": _signed_like(original.get("zl1"), known_len("zl1", original.get("zl1"))),
        "zl2": known_len("zl2", original.get("zl2")),
        "fw": fw_value,
        "d": d_left,
        "w": w_value,
        "zr2": known_len("zr2", original.get("zr2")),
        "zr1": _signed_like(original.get("zr1"), known_len("zr1", original.get("zr1"))),
    }

def can_remove_segment(segment: Mapping[str, object]) -> bool:
    """Keep D/W core and the two global FW fields structurally present."""
    if segment.get("core"):
        return False
    return str(segment.get("phase6_key") or "") not in {"fw_left", "fw_right"}

def clone_profile(profile: Sequence[Mapping[str, object]]) -> list[dict]:
    return deepcopy(list(profile))


def profile_to_fold_segments(profile: Sequence[Mapping[str, object]]):
    """Convert editor dictionaries into the GUI-independent manufacturing contract."""
    rows = []
    for seg in profile or ():
        rows.append(FoldProfileSegment(
            length=float(seg.get("len", 0.0)),
            angle=(float(seg["angle"]) if "angle" in seg else None),
            core=(str(seg.get("core")) if seg.get("core") else None),
            phase6_key=(str(seg.get("phase6_key")) if seg.get("phase6_key") else None),
        ))
    return tuple(rows)

def _phase6_is_untouched_canonical_box_profile(
    profile: Sequence[Mapping[str, object]],
    snapshot: Mapping[str, object] | None = None,
) -> bool:
    """Recognize the active Cabinet Family's canonical BoxBody topology.

    Canonical family transforms may legitimately remove mapped outer segments
    (Receiving removes terminal ``zr1``).  Comparing against a hard-coded Vault
    key list makes that transformed canonical profile look user-custom and sends
    it through the generic one-row-per-source mating mapper, which duplicates
    ``zl1``/``zl2`` as two EndCap Y folds.  Match topology against the family's
    own canonical builder instead; segment lengths remain intentionally ignored.
    """
    rows = list(profile or ())
    if snapshot is None:
        expected_keys = ("zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2", "zr1")
        if tuple(seg.get("phase6_key") for seg in rows) != expected_keys:
            return False
        turns = tuple(_num(seg.get("angle")) for seg in rows[:-1])
        return turns == tuple(float(v) for v in _BOX_BODY_TURNS)

    canonical = build_box_body_profile(snapshot)
    if len(rows) != len(canonical):
        return False
    for actual, expected in zip(rows, canonical):
        if actual.get("phase6_key") != expected.get("phase6_key"):
            return False
        if actual.get("core") != expected.get("core"):
            return False
        actual_has_angle = "angle" in actual
        expected_has_angle = "angle" in expected
        if actual_has_angle != expected_has_angle:
            return False
        if actual_has_angle and _num(actual.get("angle")) != _num(expected.get("angle")):
            return False
    return True

def _phase6_box_mating_front_chain(profile: Sequence[Mapping[str, object]]) -> list[dict]:
    """Return the ordered box-body front mating chain before the left D core.

    D-W-D stays the structural center. Everything before the first D is an
    arbitrary front-edge fold chain and is therefore propagated without any
    segment-count assumptions. ``fw_left`` is renamed to the shared end-cap FW
    semantic key; user-added rows keep stable diagnostic keys.
    """
    rows = clone_profile(profile)
    d_indexes = [i for i, seg in enumerate(rows) if seg.get("core") == "D"]
    w_indexes = [i for i, seg in enumerate(rows) if seg.get("core") == "W"]
    if len(d_indexes) != 2 or len(w_indexes) != 1 or not (d_indexes[0] < w_indexes[0] < d_indexes[1]):
        raise ValueError("箱身折法必須保留 D-W-D 核心")
    front = rows[:d_indexes[0]]
    result = []
    for index, seg in enumerate(front):
        row = {"len": _ui_len(seg.get("len"))}
        if "angle" in seg:
            # The Fold Chain input is authoritative.  Derived EndCap topology
            # may move bend ownership, but it must never invent/change angle.
            row["angle"] = float(_num(seg.get("angle")))
        key = seg.get("phase6_key")
        if key == "fw_left":
            row["phase6_key"] = "fw"
        elif key:
            row["phase6_key"] = f"box_mating:{key}"
        else:
            row["phase6_key"] = f"box_mating:extra:{index}"
        result.append(row)
    return result

def build_linked_endcap_xy_profiles(snapshot: Mapping[str, object], box_profile: Sequence[Mapping[str, object]]):
    """Derive EndCap mating topology without corrupting FW semantics.

    The box chain supplies order/turn topology. Each end cap keeps its effective
    FW as an explicit frame-width dimension. The remaining established front
    material (normally ytop1) is apportioned only across non-FW mating rows, so
    arbitrary topology stays linked while the end-cap blank span is conserved.
    """
    if _phase6_is_untouched_canonical_box_profile(box_profile, snapshot):
        return {
            "head": build_endcap_xy_profiles(snapshot, part_key="head"),
            "tail": build_endcap_xy_profiles(snapshot, part_key="tail"),
        }

    t = _num(snapshot.get("t", 2), 2)
    fw_state = normalize_endcap_fw_state(snapshot)
    defaults = {
        part: build_endcap_xy_profiles(snapshot, part_key=part)
        for part in ENDCAP_FW_PARTS
    }
    source_front = _phase6_box_mating_front_chain(box_profile)

    def allocate_integer_budget(weights, budget):
        weights = [max(0.0, _num(v)) for v in weights]
        target = max(0, _ui_len(budget))
        if not weights:
            return []
        total = sum(weights)
        if total <= 1e-9:
            weights = [1.0] * len(weights)
            total = float(len(weights))
        result = []
        remaining = target
        remaining_weight = total
        for index, weight in enumerate(weights):
            if index == len(weights) - 1:
                assigned = remaining
            else:
                assigned = int(round(remaining * weight / remaining_weight)) if remaining_weight > 1e-9 else 0
                assigned = max(0, min(remaining, assigned))
            result.append(assigned)
            remaining -= assigned
            remaining_weight -= weight
        return result

    def build_front(part):
        default_y = defaults[part]["Y"]
        core_index = next(i for i, row in enumerate(default_y) if row.get("core") == "D-T")
        by_key = {row.get("phase6_key"): row for row in default_y if row.get("phase6_key")}
        effective_fw = _ui_len(resolve_endcap_fw(snapshot, part, state=fw_state))
        # ytop1 is the end-cap's own non-FW front material. Tail stores it after
        # the D core because of native orientation, so never infer this budget
        # from list position.
        non_fw_budget = _ui_len((by_key.get("ytop1") or {}).get("len", snapshot.get("ytop1", 16)))
        # Build the mating front chain in one canonical forward direction.
        # Tail's stored/native Y profile ends at ytop1, so its ytop1 row owns no
        # angle; using that terminal row as a forward template would erase the
        # FW->outer-flange bend when the chain is reversed back to tail-native
        # order. Head's forward profile provides the shared mating-turn semantic.
        forward_by_key = {
            row.get("phase6_key"): row
            for row in defaults["head"]["Y"]
            if row.get("phase6_key")
        }
        default_front = [
            forward_by_key.get("ytop1", {"phase6_key": "ytop1", "angle": -90.0}),
            {"phase6_key": "fw", "len": effective_fw, "angle": -90.0},
        ]

        non_fw_sources = [row for row in source_front if row.get("phase6_key") != "fw"]
        allocations = iter(allocate_integer_budget(
            [_num(row.get("len")) for row in non_fw_sources], non_fw_budget
        ))
        rows = []
        saw_non_fw = False
        saw_fw = False
        for source in source_front:
            key = source.get("phase6_key")
            if key == "fw":
                row = {"len": effective_fw, "phase6_key": "fw"}
                saw_fw = True
            else:
                row = {"len": next(allocations), "phase6_key": key}
                saw_non_fw = True
            if "angle" in source:
                row["angle"] = float(_num(source.get("angle")))
            rows.append(row)

        # The end-cap mating topology follows the box front chain exactly.
        # If the box has no non-FW fold outside FW (for example the 5-segment
        # FW-D-W-D-FW chain), do not resurrect the legacy ytop1 fold.  The
        # end-cap blank must shrink with the removed fold and both head/tail
        # must expose only the remaining real BEND boundaries.
        if not saw_fw:
            # FW is a dimension semantic, not an optional topology identity.
            # Defensive fallback only: if a malformed profile lost the FW key,
            # preserve a row but do not fabricate a bend angle.
            rows.append({"len": effective_fw, "phase6_key": "fw"})
        return rows, default_y, core_index

    head_front, head_default_y, head_core_index = build_front("head")
    tail_front, tail_default_y, tail_core_index = build_front("tail")
    head_by_key = {row.get("phase6_key"): row for row in head_default_y if row.get("phase6_key")}
    y_core = _num((head_by_key.get("endcap_d_core") or {}).get("len"))
    back_len = _num((head_by_key.get("ybottom1") or {}).get("len", snapshot.get("ybottom1", 15)))

    # The bend after the D core uses the next explicit BoxBody input angle.
    # For a 5-segment FW-D-W-D-FW profile this is the angle stored on d_left.
    box_rows = list(box_profile or ())
    first_d_index = next(i for i, row in enumerate(box_rows) if row.get("core") == "D")
    d_turn = box_rows[first_d_index].get("angle")

    def build_forward(front_rows):
        rows = clone_profile(front_rows)
        core_row = {"len": _ui_len(y_core), "phase6_key": "endcap_d_core", "core": "D-T"}
        if d_turn is not None:
            core_row["angle"] = float(_num(d_turn))
        rows.append(core_row)
        rows.append({"len": _ui_len(back_len), "phase6_key": "ybottom1"})
        return rows

    head_y = build_forward(head_front)
    tail_forward = build_forward(tail_front)

    # Tail is stored in its real native reverse order.  Reverse bend ownership
    # together with the rows, but preserve the exact entered angle value/sign.
    tail_y = []
    for rev_index, source_row in enumerate(reversed(tail_forward)):
        row = {k: v for k, v in source_row.items() if k != "angle"}
        owner_index = len(tail_forward) - 2 - rev_index
        if owner_index >= 0 and "angle" in tail_forward[owner_index]:
            row["angle"] = float(_num(tail_forward[owner_index].get("angle")))
        tail_y.append(row)
    if tail_y:
        tail_y[-1].pop("angle", None)

    head_y = apply_outside_dimension_compensation(head_y, t)
    tail_y = apply_outside_dimension_compensation(tail_y, t)
    return {
        "head": {"X": clone_profile(defaults["head"]["X"]), "Y": head_y},
        "tail": {"X": clone_profile(defaults["tail"]["X"]), "Y": tail_y},
    }

def merge_box_body_profile(profile: Sequence[Mapping[str, object]], snapshot: Mapping[str, object]) -> list[dict]:
    """Refresh shared semantic core values without changing user Fold topology.

    Once an operator removes/adds a mapped outer segment, that structural choice
    is authoritative. Missing canonical keys are never recreated. Existing
    semantic keys (notably D-W-D/FW) still receive current material lengths.
    """
    merged = clone_profile(profile)
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

