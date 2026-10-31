# -*- coding: utf-8 -*-
"""Engine-only arbitrary BoxBody→Head/Tail mating Fold topology owner.

The original Phase6 5/20+ segment logic is migrated unchanged: D-W-D authority,
real input BEND angles, explicit FW, conserved front budget and native tail
reverse bend ownership. No TK/phase6 import or new CUTTING/relief constants.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from copy import deepcopy
from .box_body_fold_profile import (
    BOX_BODY_TURNS as _BOX_BODY_TURNS, _num, _ui_len, _common_dimension_len,
    build_box_body_profile, apply_outside_dimension_compensation,
)
from .cabinet_types import policy as cabinet_family_policy
from .endcap_factory_fold import (
    ENDCAP_FW_PARTS, normalize_endcap_fw_state, resolve_endcap_fw,
    build_endcap_xy_fold_profiles,
)


def clone_profile(profile: Sequence[Mapping[str, object]]) -> list[dict]:
    return deepcopy(list(profile))


def is_canonical_box_body_mating_profile(
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

def box_body_front_mating_fold_chain(profile: Sequence[Mapping[str, object]]) -> list[dict]:
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

def build_linked_endcap_xy_fold_profiles(snapshot: Mapping[str, object], box_profile: Sequence[Mapping[str, object]]):
    """Derive EndCap mating topology without corrupting FW semantics.

    The box chain supplies order/turn topology. Each end cap keeps its effective
    FW as an explicit frame-width dimension. The remaining established front
    material (normally ytop1) is apportioned only across non-FW mating rows, so
    arbitrary topology stays linked while the end-cap blank span is conserved.
    """
    if is_canonical_box_body_mating_profile(box_profile, snapshot):
        return {
            "head": build_endcap_xy_fold_profiles(snapshot, part_key="head"),
            "tail": build_endcap_xy_fold_profiles(snapshot, part_key="tail"),
        }

    t = _num(snapshot.get("t", 2), 2)
    fw_state = normalize_endcap_fw_state(snapshot)
    defaults = {
        part: build_endcap_xy_fold_profiles(snapshot, part_key=part)
        for part in ENDCAP_FW_PARTS
    }
    source_front = box_body_front_mating_fold_chain(box_profile)

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
        raw_fw = resolve_endcap_fw(snapshot, part, state=fw_state)
        if cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(snapshot):
            raw_fw = max(0.0, float(raw_fw) - 2.0 * t)
        effective_fw = _ui_len(raw_fw)
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
        core_row = {"len": _common_dimension_len(snapshot, y_core), "phase6_key": "endcap_d_core", "core": "D-T"}
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

