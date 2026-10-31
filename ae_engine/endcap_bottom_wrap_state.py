# -*- coding: utf-8 -*-
"""Engine-owned EndCap Bottom WRAP pair state and canonical Assembly Joint port.

Preserves approved Receiving/Vault family defaults, legacy saved linkage,
operator reserve values and the actual bottom-edge Joint Graph authority.
The Phase6 GUI compatibility module only forwards public API calls.
"""
from __future__ import annotations

from collections.abc import Mapping
from .box_body_fold_profile import _num
from .cabinet_types import policy as cabinet_family_policy
from .endcap_factory_fold import ENDCAP_FW_PARTS

WRAP_LINKED = "LINKED"
WRAP_FOLLOW_HEAD = "FOLLOW_HEAD"
WRAP_FOLLOW_TAIL = "FOLLOW_TAIL"
WRAP_INDEPENDENT = "INDEPENDENT"
ENDCAP_BOTTOM_WRAP_MODES = (WRAP_LINKED, WRAP_FOLLOW_HEAD, WRAP_FOLLOW_TAIL, WRAP_INDEPENDENT)


def _default_bottom_wrap_item(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {
        "enabled": cabinet_family_policy.default_bottom_wrap_enabled(snapshot),
        "reserve_u": 2.0,
        "reserve_v": 1.0,
    }


def _normalize_bottom_wrap_item(raw, default):
    raw = raw if isinstance(raw, Mapping) else {}
    try:
        reserve_u = max(0.0, float(raw.get("reserve_u", default["reserve_u"])))
    except (TypeError, ValueError):
        reserve_u = float(default["reserve_u"])
    try:
        reserve_v = max(0.0, float(raw.get("reserve_v", default["reserve_v"])))
    except (TypeError, ValueError):
        reserve_v = float(default["reserve_v"])
    return {
        "enabled": bool(raw.get("enabled", default["enabled"])),
        "reserve_u": reserve_u,
        "reserve_v": reserve_v,
    }


def normalize_endcap_bottom_wrap_state(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Canonical Head/Tail lower-WRAP pair state.

    Default receiving behaviour is linked.  Editing one side makes it the pair
    leader; editing the opposite side afterwards splits the pair to independent
    values, matching the existing EndCap FW linkage semantics.
    """
    raw = snapshot.get("endcap_bottom_wrap")
    if raw is None:
        workspace = snapshot.get("workspace")
        if isinstance(workspace, Mapping):
            raw = workspace.get("endcap_bottom_wrap")
    raw = raw if isinstance(raw, Mapping) else {}
    default = _default_bottom_wrap_item(snapshot)
    head = _normalize_bottom_wrap_item(raw.get("head"), default)
    tail = _normalize_bottom_wrap_item(raw.get("tail"), default)
    mode = str(raw.get("mode", WRAP_LINKED) or WRAP_LINKED).upper()
    if mode not in ENDCAP_BOTTOM_WRAP_MODES:
        mode = WRAP_LINKED
    result = {"mode": mode, "head": head, "tail": tail}
    if mode == WRAP_LINKED:
        # A linked snapshot stores one effective value; prefer Head as stable source.
        result["tail"] = dict(result["head"])
    elif mode == WRAP_FOLLOW_HEAD:
        result["tail"] = dict(result["head"])
    elif mode == WRAP_FOLLOW_TAIL:
        result["head"] = dict(result["tail"])
    return result


def resolve_endcap_bottom_wrap(snapshot: Mapping[str, object], part_key: str, *, state=None) -> dict[str, object]:
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    normalized = normalize_endcap_bottom_wrap_state(snapshot) if state is None else state
    item = dict((normalized or {}).get(part_key) or _default_bottom_wrap_item(snapshot))
    enabled = bool(item.get("enabled", False))
    # Once an explicit Joint Graph exists, UI state is only a projection of the
    # BOTTOM relation.  The legacy enabled mirror may still carry reserve/link
    # persistence but may not override the graph.
    if "assembly_joints" in snapshot or "assembly_joint_schema_version" in snapshot:
        try:
            from .assembly_joint import AssemblyJointRelation, edge_relation_for_part
            relation = edge_relation_for_part(snapshot, part_key, "BOTTOM")
            if relation is not None:
                enabled = relation is AssemblyJointRelation.WRAP
        except Exception:
            pass
    return {
        "enabled": enabled,
        "reserve_u": max(0.0, _num(item.get("reserve_u", 2.0), 2.0)),
        "reserve_v": max(0.0, _num(item.get("reserve_v", 1.0), 1.0)),
    }


def commit_endcap_bottom_wrap_joint(snapshot: Mapping[str, object], part_key: str, enabled: bool) -> dict[str, object]:
    """Write the receiving switch to the canonical BOTTOM AssemblyJoint."""
    from .assembly_joint import AssemblyJointRelation, set_part_edge_relation
    return set_part_edge_relation(
        snapshot, str(part_key), "BOTTOM",
        AssemblyJointRelation.WRAP if bool(enabled) else AssemblyJointRelation.INSERT,
    )


def commit_endcap_bottom_wrap(state, part_key: str, *, enabled=None, reserve_u=None, reserve_v=None) -> dict:
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    mode = str(state.get("mode", WRAP_LINKED) or WRAP_LINKED)
    leader = WRAP_FOLLOW_HEAD if part_key == "head" else WRAP_FOLLOW_TAIL
    opposite = WRAP_FOLLOW_TAIL if part_key == "head" else WRAP_FOLLOW_HEAD
    base = dict(state.get(part_key) or {"enabled": True, "reserve_u": 2.0, "reserve_v": 1.0})
    if enabled is not None:
        base["enabled"] = bool(enabled)
    if reserve_u is not None:
        base["reserve_u"] = max(0.0, float(reserve_u))
    if reserve_v is not None:
        base["reserve_v"] = max(0.0, float(reserve_v))
    if mode in {WRAP_LINKED, leader}:
        state["mode"] = leader
        state["head"] = dict(base)
        state["tail"] = dict(base)
    elif mode == opposite:
        state["mode"] = WRAP_INDEPENDENT
        state.setdefault("head", dict(base))
        state.setdefault("tail", dict(base))
        state[part_key] = dict(base)
    else:
        state["mode"] = WRAP_INDEPENDENT
        state.setdefault("head", dict(base))
        state.setdefault("tail", dict(base))
        state[part_key] = dict(base)
    return state
