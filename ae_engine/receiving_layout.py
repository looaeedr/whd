# -*- coding: utf-8 -*-
"""Receiving Set/Bay/Joint project authority.

This module owns only the persisted multi-cabinet topology/input state.  Lock
geometry, effective dimensions, UI selection and other derived data are not
project truth and therefore never belong in ``receiving_layout``.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

RECEIVING_LAYOUT_SCHEMA = "receiving-layout-v1"
_ALLOWED_BACK_PANEL_MODES = {"FULL", "HALF", "BACK_OPENING"}
_DERIVED_LAYOUT_KEYS = {
    "left_locked",
    "right_locked",
    "effective_d",
    "effective_h",
    "effective_D",
    "effective_H",
    "lock_features",
    "pairing_mark",
}


def _number(value: object, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if result <= 0.0:
        raise ValueError(f"{label} must be > 0")
    return result


def _stable_id(value: object, *, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} stable_id must not be empty")
    return result


def _back_panel_mode(value: object) -> str:
    mode = str(value or "FULL").strip().upper()
    if mode not in _ALLOWED_BACK_PANEL_MODES:
        raise ValueError(f"unsupported Receiving back_panel_mode: {value!r}")
    return mode


def new_receiving_layout(*, width: object, height: object, depth: object, back_panel_mode: object = "FULL") -> dict[str, object]:
    """Return the deterministic fresh/migrated one-Set one-Bay layout."""
    return {
        "schema": RECEIVING_LAYOUT_SCHEMA,
        "sets": [
            {
                "stable_id": "receiving:set:1",
                "bays": [
                    {
                        "stable_id": "receiving:set:1:bay:1",
                        "width": _number(width, label="Receiving Bay width"),
                        "height": _number(height, label="Receiving Bay height"),
                        "depth": _number(depth, label="Receiving Bay depth"),
                        "back_panel_mode": _back_panel_mode(back_panel_mode),
                    }
                ],
                "joints": [],
            }
        ],
    }


def normalize_receiving_layout(layout: Mapping[str, object] | None) -> dict[str, object]:
    """Validate and canonicalize persisted Receiving layout authority.

    The Set ``bays[]`` order is topology authority.  Every ``joints[i]`` must
    connect exactly ``bays[i]`` to ``bays[i+1]``.  Derived state is omitted from
    the canonical result even if a caller supplied it transiently.
    """
    if not isinstance(layout, Mapping):
        raise ValueError("Receiving layout must be a mapping")
    if str(layout.get("schema") or "") != RECEIVING_LAYOUT_SCHEMA:
        raise ValueError(f"unsupported Receiving layout schema: {layout.get('schema')!r}")
    raw_sets = layout.get("sets")
    if not isinstance(raw_sets, (list, tuple)) or not raw_sets:
        raise ValueError("Receiving layout must contain at least Set1")

    seen_ids: set[str] = set()
    sets: list[dict[str, object]] = []
    for set_index, raw_set in enumerate(raw_sets, start=1):
        if not isinstance(raw_set, Mapping):
            raise ValueError(f"Receiving Set{set_index} must be a mapping")
        set_id = _stable_id(raw_set.get("stable_id"), label=f"Receiving Set{set_index}")
        if set_id in seen_ids:
            raise ValueError(f"duplicate Receiving stable_id: {set_id}")
        seen_ids.add(set_id)

        raw_bays = raw_set.get("bays")
        if not isinstance(raw_bays, (list, tuple)) or not raw_bays:
            raise ValueError(f"Receiving Set{set_index} must contain at least one Bay")
        bays: list[dict[str, object]] = []
        for bay_index, raw_bay in enumerate(raw_bays, start=1):
            if not isinstance(raw_bay, Mapping):
                raise ValueError(f"Receiving Set{set_index} Bay{bay_index} must be a mapping")
            bay_id = _stable_id(raw_bay.get("stable_id"), label=f"Receiving Set{set_index} Bay{bay_index}")
            if bay_id in seen_ids:
                raise ValueError(f"duplicate Receiving stable_id: {bay_id}")
            seen_ids.add(bay_id)
            bay = {
                "stable_id": bay_id,
                "width": _number(raw_bay.get("width"), label=f"Receiving Set{set_index} Bay{bay_index} width"),
                "height": _number(raw_bay.get("height"), label=f"Receiving Set{set_index} Bay{bay_index} height"),
                "depth": _number(raw_bay.get("depth"), label=f"Receiving Set{set_index} Bay{bay_index} depth"),
                "back_panel_mode": _back_panel_mode(raw_bay.get("back_panel_mode")),
            }
            bays.append(bay)

        raw_joints = raw_set.get("joints")
        if raw_joints is None:
            raw_joints = []
        if not isinstance(raw_joints, (list, tuple)):
            raise ValueError(f"Receiving Set{set_index} joints must be a list")
        expected_count = max(len(bays) - 1, 0)
        if len(raw_joints) != expected_count:
            raise ValueError(
                f"Receiving Set{set_index} joint_count must equal bay_count-1: "
                f"expected {expected_count}, got {len(raw_joints)}"
            )
        joints: list[dict[str, object]] = []
        for joint_index, raw_joint in enumerate(raw_joints):
            if not isinstance(raw_joint, Mapping):
                raise ValueError(f"Receiving Set{set_index} Joint{joint_index + 1} must be a mapping")
            joint_id = _stable_id(raw_joint.get("stable_id"), label=f"Receiving Set{set_index} Joint{joint_index + 1}")
            if joint_id in seen_ids:
                raise ValueError(f"duplicate Receiving stable_id: {joint_id}")
            seen_ids.add(joint_id)
            left_id = str(raw_joint.get("left_bay_id") or "").strip()
            right_id = str(raw_joint.get("right_bay_id") or "").strip()
            expected_left = str(bays[joint_index]["stable_id"])
            expected_right = str(bays[joint_index + 1]["stable_id"])
            if left_id != expected_left or right_id != expected_right:
                raise ValueError(
                    f"Receiving Set{set_index} Joint{joint_index + 1} endpoints must match adjacent bays "
                    f"{expected_left!r}->{expected_right!r}; got {left_id!r}->{right_id!r}"
                )
            depth_alignment = str(raw_joint.get("depth_alignment") or "FRONT").strip().upper()
            height_alignment = str(raw_joint.get("height_alignment") or "BOTTOM").strip().upper()
            if depth_alignment not in {"FRONT", "REAR"}:
                raise ValueError(f"unsupported Receiving depth_alignment: {depth_alignment!r}")
            if height_alignment not in {"TOP", "BOTTOM"}:
                raise ValueError(f"unsupported Receiving height_alignment: {height_alignment!r}")
            joints.append(
                {
                    "stable_id": joint_id,
                    "left_bay_id": left_id,
                    "right_bay_id": right_id,
                    "depth_alignment": depth_alignment,
                    "height_alignment": height_alignment,
                }
            )
        sets.append({"stable_id": set_id, "bays": bays, "joints": joints})

    return {"schema": RECEIVING_LAYOUT_SCHEMA, "sets": sets}


def primary_bay(layout: Mapping[str, object]) -> dict[str, object]:
    normalized = normalize_receiving_layout(layout)
    return dict(normalized["sets"][0]["bays"][0])


def derive_bay_lock_state(layout: Mapping[str, object], *, set_index: int = 0, bay_index: int = 0) -> tuple[bool, bool]:
    normalized = normalize_receiving_layout(layout)
    sets = normalized["sets"]
    if set_index < 0 or set_index >= len(sets):
        raise IndexError("Receiving set_index out of range")
    bays = sets[set_index]["bays"]
    if bay_index < 0 or bay_index >= len(bays):
        raise IndexError("Receiving bay_index out of range")
    return bay_index > 0, bay_index < len(bays) - 1


def _legacy_structure_state(snapshot: Mapping[str, object]) -> Mapping[str, object] | None:
    workspace = snapshot.get("workspace")
    if isinstance(workspace, Mapping) and isinstance(workspace.get("box_body_structure"), Mapping):
        return workspace.get("box_body_structure")
    state = snapshot.get("box_body_structure")
    return state if isinstance(state, Mapping) else None


def _legacy_back_panel_mode(snapshot: Mapping[str, object]) -> str:
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import back_panel_mode

    state = _legacy_structure_state(snapshot)
    resolved = receiving.resolve_box_body_structure_state(dict(state) if isinstance(state, Mapping) else None)
    return back_panel_mode(resolved).value


def ensure_receiving_layout(snapshot: Mapping[str, object] | None) -> dict[str, object]:
    """Return snapshot with canonical ReceivingLayout, migrating legacy 1x1 state."""
    result = deepcopy(dict(snapshot or {}))
    from ae_engine.cabinet_types.receiving import is_receiving_snapshot

    if not is_receiving_snapshot(result):
        return result
    if result.get("receiving_layout") is None:
        from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS

        settings = result.get("settings")
        settings = settings if isinstance(settings, Mapping) else {}

        def legacy_dimension(key: str) -> object:
            if result.get(key) is not None:
                return result[key]
            if settings.get(key) is not None:
                return settings[key]
            # A small number of old/minimal project payloads only identified
            # the Receiving family and relied on family defaults. Preserve that
            # deterministic legacy behavior rather than inventing geometry.
            return BOX_BODY_DEFAULTS[key]

        result["receiving_layout"] = new_receiving_layout(
            width=legacy_dimension("w"),
            height=legacy_dimension("h"),
            depth=legacy_dimension("d"),
            back_panel_mode=_legacy_back_panel_mode(result),
        )
    else:
        result["receiving_layout"] = normalize_receiving_layout(result["receiving_layout"])
    return result


def _set_transient_back_panel_mode(snapshot: dict[str, object], mode: str) -> None:
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import set_side_back_back_panel_mode

    def projected(state: object) -> dict[str, object]:
        resolved = receiving.resolve_box_body_structure_state(state if isinstance(state, Mapping) else None)
        return set_side_back_back_panel_mode(resolved, mode)

    workspace = snapshot.get("workspace")
    if isinstance(workspace, Mapping):
        workspace_copy = deepcopy(dict(workspace))
        workspace_copy["box_body_structure"] = projected(workspace_copy.get("box_body_structure"))
        snapshot["workspace"] = workspace_copy
    if "box_body_structure" in snapshot:
        snapshot["box_body_structure"] = projected(snapshot.get("box_body_structure"))


def project_primary_bay_legacy_aliases(snapshot: Mapping[str, object] | None) -> dict[str, object]:
    """Return a runtime-only compatibility projection for existing single-Bay consumers."""
    result = ensure_receiving_layout(snapshot)
    if "receiving_layout" not in result:
        return result
    bay = primary_bay(result["receiving_layout"])
    result["w"] = float(bay["width"])
    result["h"] = float(bay["height"])
    result["d"] = float(bay["depth"])
    _set_transient_back_panel_mode(result, str(bay["back_panel_mode"]))
    return result


def _strip_back_panel_mode_from_structure(state: object) -> object:
    if not isinstance(state, Mapping):
        return deepcopy(state)
    result = deepcopy(dict(state))
    configs = result.get("configs")
    if isinstance(configs, Mapping):
        configs_copy = deepcopy(dict(configs))
        key = "three_piece_side_back_split"
        cfg = configs_copy.get(key)
        if isinstance(cfg, Mapping):
            cfg_copy = deepcopy(dict(cfg))
            cfg_copy.pop("back_panel_mode", None)
            configs_copy[key] = cfg_copy
        result["configs"] = configs_copy
    return result


def strip_legacy_receiving_aliases(snapshot: Mapping[str, object] | None) -> dict[str, object]:
    """Return v2 persisted Receiving snapshot with legacy single-box aliases removed."""
    result = ensure_receiving_layout(snapshot)
    if "receiving_layout" not in result:
        return result
    result["receiving_layout"] = normalize_receiving_layout(result["receiving_layout"])
    for key in ("w", "h", "d"):
        result.pop(key, None)
    workspace = result.get("workspace")
    if isinstance(workspace, Mapping):
        workspace_copy = deepcopy(dict(workspace))
        if "box_body_structure" in workspace_copy:
            workspace_copy["box_body_structure"] = _strip_back_panel_mode_from_structure(workspace_copy["box_body_structure"])
        result["workspace"] = workspace_copy
    if "box_body_structure" in result:
        result["box_body_structure"] = _strip_back_panel_mode_from_structure(result["box_body_structure"])
    for key in _DERIVED_LAYOUT_KEYS:
        result.pop(key, None)
    return result
