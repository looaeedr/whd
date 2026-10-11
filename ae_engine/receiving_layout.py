# -*- coding: utf-8 -*-
"""Receiving Set/Bay/Joint project authority.

This module owns only the persisted multi-cabinet topology/input state.  Lock
geometry, effective dimensions, UI selection and other derived data are not
project truth and therefore never belong in ``receiving_layout``.
"""
from __future__ import annotations

from copy import deepcopy
from ae_engine.receiving_shared_settings import normalize_set_settings, setting_value
from typing import Mapping

RECEIVING_LAYOUT_SCHEMA = "receiving-layout-v1"
RECEIVING_RUNTIME_SELECTION_KEY = "_receiving_runtime_selection"
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
            if "door_state" in raw_bay:
                if not isinstance(raw_bay["door_state"], Mapping):
                    raise ValueError("每連門分割必須為物件")
                bay["door_state"] = {key: deepcopy(raw_bay["door_state"][key]) for key in RECEIVING_DOOR_STATE_KEYS if key in raw_bay["door_state"]}
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
        selected = {"stable_id": set_id, "bays": bays, "joints": joints}
        if "switch_brand" in raw_set:
            from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
            brand = str(raw_set["switch_brand"])
            if brand not in RECEIVING_SWITCH_BRANDS:
                raise ValueError("不支援的開關品牌")
            selected["switch_brand"] = brand
        if "settings" in raw_set:
            selected["settings"] = normalize_set_settings(raw_set["settings"], bays)
            for index, bay in enumerate(bays):
                bay["back_panel_mode"] = setting_value(selected, index, "back_panel_mode")
        sets.append(selected)

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
    if result.get("active_mode") == "quantity":
        from ae_engine.receiving_quantity_box import project_common_box
        return project_common_box(result)
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
    layout = result["receiving_layout"]
    legacy_switch = result.pop("receiving_switch_layout", None)
    if legacy_switch and not any("switch_brand" in row for row in layout["sets"]):
        from ae_engine.receiving_switch_layout import normalize_receiving_switch_layout
        switch = normalize_receiving_switch_layout(legacy_switch)
        layout = resize_receiving_sets(layout, set_count=max(len(layout["sets"]), len(switch["layers"])))
        for index, layer in enumerate(switch["layers"]):
            layout = resize_receiving_bays(layout, set_index=index, bay_count=max(len(layout["sets"][index]["bays"]), layer["connection_count"]))
            layout["sets"][index]["switch_brand"] = switch["switch_brand"]
    source_features = {**dict(result.get("surface_features") or {}), **dict(result.get("part_features") or {})}
    from ae_engine.sheetmetal_features import legacy_hole_to_feature
    for role in ("head", "tail"):
        if role not in source_features and result.get(f"{role}_holes"):
            source_features[role] = [legacy_hole_to_feature(hole) for hole in result[f"{role}_holes"]]
    if any(source_features.get(role) for role in ("head", "tail")):
        for selected in layout["sets"]:
            if "settings" not in selected:
                template_bays = deepcopy(selected["bays"])
                for bay in template_bays:
                    for role in ("head", "tail"):
                        bay[f"{role}_features"] = deepcopy(source_features.get(role, []))
                selected["settings"] = normalize_set_settings(None, template_bays)
    if "door_layout_columns" in result:
        door_state = {key: deepcopy(result[key]) for key in RECEIVING_DOOR_STATE_KEYS if key in result}
        for selected in layout["sets"]:
            for bay in selected["bays"]:
                bay.setdefault("door_state", deepcopy(door_state))
    result["receiving_layout"] = layout
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
    """Return the legacy Set1/Bay1 runtime projection used by project-file readers."""
    return project_receiving_bay_legacy_aliases(
        snapshot, set_index=0, bay_index=0, validate_common=False
    )



RECEIVING_DOOR_STATE_KEYS = (
    "multi_door_enabled", "door_layout_columns", "door_handle_edges",
    "door_layout_scope", "door_nameplate_center_datum_top", "inner_doors",
)

RECEIVING_BAY_COMMON_STATE_INVALID = "RECEIVING_BAY_COMMON_STATE_INVALID"


class ReceivingBayProjectionError(ValueError):
    """Raised when one Bay cannot reuse the existing single-box consumers safely."""

    def __init__(self, *, set_index: int, bay_index: int, cause: Exception):
        self.set_index = int(set_index)
        self.bay_index = int(bay_index)
        self.cause = cause
        super().__init__(
            f"{RECEIVING_BAY_COMMON_STATE_INVALID}: "
            f"Set{self.set_index + 1}/Bay{self.bay_index + 1}: {cause}"
        )


def _layout_set(layout: Mapping[str, object], set_index: int) -> tuple[dict[str, object], dict[str, object]]:
    normalized = normalize_receiving_layout(layout)
    sets = normalized["sets"]
    if set_index < 0 or set_index >= len(sets):
        raise IndexError("Receiving set_index out of range")
    return normalized, sets[set_index]


def _copy_bay_fields(bay: Mapping[str, object], *, stable_id: str) -> dict[str, object]:
    """Copy only persisted per-Bay input fields; never create a live link."""
    return {
        **({"door_state": deepcopy(bay["door_state"])} if "door_state" in bay else {}),
        "stable_id": str(stable_id),
        "width": float(bay["width"]),
        "height": float(bay["height"]),
        "depth": float(bay["depth"]),
        "back_panel_mode": _back_panel_mode(bay.get("back_panel_mode")),
    }


def _new_joint(*, set_number: int, joint_number: int, left_id: str, right_id: str, previous: Mapping[str, object] | None) -> dict[str, object]:
    if previous is None:
        depth_alignment = "FRONT"
        height_alignment = "BOTTOM"
    else:
        depth_alignment = str(previous.get("depth_alignment") or "FRONT").strip().upper()
        height_alignment = str(previous.get("height_alignment") or "BOTTOM").strip().upper()
    return {
        "stable_id": f"receiving:set:{set_number}:joint:{joint_number}",
        "left_bay_id": str(left_id),
        "right_bay_id": str(right_id),
        "depth_alignment": depth_alignment,
        "height_alignment": height_alignment,
    }


def resize_receiving_bays(layout: Mapping[str, object], *, set_index: int, bay_count: int) -> dict[str, object]:
    """Tail-only Bay resize.

    Append clones the previous Bay by value and appends exactly one adjacent
    Joint per new Bay. The first Joint defaults FRONT+BOTTOM; subsequent Joints
    inherit the previous Joint alignment. Truncation removes only the tail.
    """
    normalized, selected = _layout_set(layout, set_index)
    try:
        wanted = int(bay_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("Receiving bay_count must be an integer") from exc
    if wanted < 1:
        raise ValueError("Receiving Set must contain at least one Bay")

    bays = [deepcopy(dict(row)) for row in selected["bays"]]
    joints = [deepcopy(dict(row)) for row in selected["joints"]]
    set_number = int(set_index) + 1

    while len(bays) < wanted:
        bay_number = len(bays) + 1
        previous_bay = bays[-1]
        new_bay = _copy_bay_fields(
            previous_bay,
            stable_id=f"receiving:set:{set_number}:bay:{bay_number}",
        )
        previous_joint = joints[-1] if joints else None
        joints.append(
            _new_joint(
                set_number=set_number,
                joint_number=len(joints) + 1,
                left_id=str(previous_bay["stable_id"]),
                right_id=str(new_bay["stable_id"]),
                previous=previous_joint,
            )
        )
        if "settings" in selected:
            for kind, row in selected["settings"].items():
                prior_ref = row["refs"][previous_bay["stable_id"]]
                ref = f"{new_bay['stable_id']}:{kind}"
                row["refs"][new_bay["stable_id"]] = ref
                row["values"][ref] = deepcopy(row["values"][prior_ref])
        bays.append(new_bay)

    if len(bays) > wanted:
        bays = bays[:wanted]
        joints = joints[: max(wanted - 1, 0)]

    normalized["sets"][set_index] = {
        **selected,
        "stable_id": str(selected["stable_id"]),
        "bays": bays,
        "joints": joints,
    }
    return normalize_receiving_layout(normalized)


def append_receiving_set(layout: Mapping[str, object]) -> dict[str, object]:
    """Append exactly one progressive Set using Set1/Bay1 as the template."""
    normalized = normalize_receiving_layout(layout)
    template = normalized["sets"][0]["bays"][0]
    set_number = len(normalized["sets"]) + 1
    normalized["sets"].append(
        {
            "stable_id": f"receiving:set:{set_number}",
            "bays": [
                _copy_bay_fields(
                    template,
                    stable_id=f"receiving:set:{set_number}:bay:1",
                )
            ],
            "joints": [],
        }
    )
    return normalize_receiving_layout(normalized)


def resize_receiving_sets(layout: Mapping[str, object], *, set_count: int) -> dict[str, object]:
    """Progressive tail-only Set resize; Set1 is permanent."""
    normalized = normalize_receiving_layout(layout)
    try:
        wanted = int(set_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("Receiving set_count must be an integer") from exc
    if wanted < 1:
        raise ValueError("Receiving Set1 cannot be removed")
    while len(normalized["sets"]) < wanted:
        normalized = append_receiving_set(normalized)
    if len(normalized["sets"]) > wanted:
        normalized["sets"] = normalized["sets"][:wanted]
    return normalize_receiving_layout(normalized)


def update_receiving_bay(layout: Mapping[str, object], *, set_index: int, bay_index: int, **changes: object) -> dict[str, object]:
    """Update persisted per-Bay fields without touching sibling Bay objects."""
    normalized, selected = _layout_set(layout, set_index)
    bays = selected["bays"]
    if bay_index < 0 or bay_index >= len(bays):
        raise IndexError("Receiving bay_index out of range")
    bay = deepcopy(dict(bays[bay_index]))
    allowed = {"width", "height", "depth", "back_panel_mode", "door_state"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"unsupported Receiving Bay fields: {sorted(unknown)}")
    if "width" in changes:
        bay["width"] = _number(changes["width"], label="Receiving Bay width")
    if "height" in changes:
        bay["height"] = _number(changes["height"], label="Receiving Bay height")
    if "depth" in changes:
        bay["depth"] = _number(changes["depth"], label="Receiving Bay depth")
    if "back_panel_mode" in changes:
        mode = _back_panel_mode(changes["back_panel_mode"])
        bay["back_panel_mode"] = mode
        if "settings" in selected:
            row = selected["settings"]["back_panel_mode"]
            row["values"][row["refs"][bay["stable_id"]]] = mode
    if "door_state" in changes:
        bay["door_state"] = deepcopy(dict(changes["door_state"]))
    bays[bay_index] = bay
    normalized["sets"][set_index] = {
        **selected,
        "stable_id": str(selected["stable_id"]),
        "bays": [deepcopy(dict(row)) for row in bays],
        "joints": [deepcopy(dict(row)) for row in selected["joints"]],
    }
    return normalize_receiving_layout(normalized)


def _validate_common_receiving_state(snapshot: Mapping[str, object]) -> None:
    """Reuse existing Door/Divider/Inner Door validators for one projected Bay."""
    data = dict(snapshot or {})
    if not bool(data.get("multi_door_enabled", False)):
        return
    columns = tuple(
        (float(row[0]), tuple(float(v) for v in row[1]))
        for row in tuple(data.get("door_layout_columns") or ())
    )
    if not columns:
        raise ValueError("enabled Door topology requires door_layout_columns")

    from ae_engine.sheetmetal_part_adapters import validate_door_layout_dimensions
    from ae_engine.door_dividers import derive_box_body_dividers

    validate_door_layout_dimensions(
        columns,
        total_width=float(data["w"]),
        total_height=float(data["h"]),
    )
    derive_box_body_dividers(
        columns,
        depth=float(data["d"]),
        thickness=float(data.get("t", 2.0)),
        frame_width=float(data.get("fw", 29.0)),
        layout_scope=str(data.get("door_layout_scope") or "receiving-main"),
        handle_edges=dict(data.get("door_handle_edges") or {}),
        model_name="受電箱",
    )

    inner_doors = list(data.get("inner_doors") or ())
    if inner_doors:
        from ae_engine.cabinet_types import receiving

        # These existing derivations validate authoritative Door cell identity,
        # Divider lower-frame role and positive Inner Door panel/frame geometry.
        receiving.derive_inner_door_panels(data)
        receiving.derive_inner_door_frame_sets(data)


def project_receiving_bay_legacy_aliases(
    snapshot: Mapping[str, object] | None,
    *,
    set_index: int = 0,
    bay_index: int = 0,
    validate_common: bool = True,
) -> dict[str, object]:
    """Runtime-only projection of one Bay into existing single-box consumers.

    ``receiving_layout`` itself is preserved byte-for-byte by value. Only the
    compatibility aliases W/H/D/back-panel mode are projected into this copy.
    """
    result = ensure_receiving_layout(snapshot)
    if "receiving_layout" not in result:
        return result
    persisted_layout = deepcopy(result["receiving_layout"])
    normalized, selected = _layout_set(persisted_layout, set_index)
    bays = selected["bays"]
    if bay_index < 0 or bay_index >= len(bays):
        raise IndexError("Receiving bay_index out of range")
    bay = bays[bay_index]
    result["receiving_layout"] = persisted_layout
    result[RECEIVING_RUNTIME_SELECTION_KEY] = {
        "set_index": int(set_index),
        "bay_index": int(bay_index),
        "set_id": str(selected["stable_id"]),
        "bay_id": str(bay["stable_id"]),
    }
    if "door_state" in bay:
        for key in RECEIVING_DOOR_STATE_KEYS:
            result.pop(key, None)
        result.update(deepcopy(bay["door_state"]))
    result["w"] = float(bay["width"])
    result["h"] = float(bay["height"])
    result["d"] = float(bay["depth"])
    _set_transient_back_panel_mode(result, str(bay["back_panel_mode"]))
    if "settings" in selected:
        features = deepcopy(dict(result.get("surface_features") or {}))
        for role in ("head", "tail"):
            features[role] = setting_value(selected, bay_index, f"{role}_features")
        result["surface_features"] = features
        part_features = deepcopy(dict(result.get("part_features") or {}))
        for role in ("head", "tail"):
            part_features[role] = deepcopy(features[role])
        result["part_features"] = part_features
        result["receiving_inner_door_layers"] = setting_value(selected, bay_index, "inner_door_layers")
    if validate_common:
        try:
            _validate_common_receiving_state(result)
        except Exception as exc:
            raise ReceivingBayProjectionError(
                set_index=set_index,
                bay_index=bay_index,
                cause=exc,
            ) from exc
    # Validation/legacy projection must never mutate the persisted authority.
    result["receiving_layout"] = persisted_layout
    if result.get("active_mode") == "quantity":
        from phase6_quantity_model import normalize_quantity_snapshot
        result = normalize_quantity_snapshot(result)
        result["surface_features"] = {**dict(result.get("surface_features") or {}),
                                      **{role: deepcopy(result["part_features"][role]) for role in ("head", "tail")}}
    return result



def receiving_joint_alignment_editability(
    layout: Mapping[str, object], *, set_index: int, joint_index: int
) -> dict[str, bool]:
    """Return whether D/H alignment controls can affect this adjacent Bay pair."""
    _normalized, selected = _layout_set(layout, set_index)
    joints = selected["joints"]
    if joint_index < 0 or joint_index >= len(joints):
        raise IndexError("Receiving joint_index out of range")
    left = selected["bays"][joint_index]
    right = selected["bays"][joint_index + 1]
    return {
        "depth_alignment": float(left["depth"]) != float(right["depth"]),
        "height_alignment": float(left["height"]) != float(right["height"]),
    }


def update_receiving_joint_alignment(
    layout: Mapping[str, object],
    *,
    set_index: int,
    joint_index: int,
    depth_alignment: object | None = None,
    height_alignment: object | None = None,
) -> dict[str, object]:
    """Update alignment only on axes where unequal dimensions make it meaningful."""
    normalized, selected = _layout_set(layout, set_index)
    joints = selected["joints"]
    if joint_index < 0 or joint_index >= len(joints):
        raise IndexError("Receiving joint_index out of range")
    editable = receiving_joint_alignment_editability(
        normalized, set_index=set_index, joint_index=joint_index
    )
    row = deepcopy(dict(joints[joint_index]))
    if depth_alignment is not None and editable["depth_alignment"]:
        value = str(depth_alignment).strip().upper()
        if value not in {"FRONT", "REAR"}:
            raise ValueError(f"unsupported Receiving depth_alignment: {value!r}")
        row["depth_alignment"] = value
    if height_alignment is not None and editable["height_alignment"]:
        value = str(height_alignment).strip().upper()
        if value not in {"TOP", "BOTTOM"}:
            raise ValueError(f"unsupported Receiving height_alignment: {value!r}")
        row["height_alignment"] = value
    joints[joint_index] = row
    normalized["sets"][set_index] = {
        **selected,
        "stable_id": str(selected["stable_id"]),
        "bays": [deepcopy(dict(item)) for item in selected["bays"]],
        "joints": [deepcopy(dict(item)) for item in joints],
    }
    return normalize_receiving_layout(normalized)

def receiving_destructive_tail_ids(
    layout: Mapping[str, object],
    *,
    set_index: int | None = None,
    bay_count: int | None = None,
    set_count: int | None = None,
) -> tuple[str, ...]:
    """Return stable IDs that a tail-only edit would destroy, for UI confirmation."""
    normalized = normalize_receiving_layout(layout)
    removed: list[str] = []
    if set_count is not None:
        wanted = int(set_count)
        if wanted < 1:
            raise ValueError("Receiving Set1 cannot be removed")
        for row in normalized["sets"][wanted:]:
            removed.append(str(row["stable_id"]))
            removed.extend(str(bay["stable_id"]) for bay in row["bays"])
            removed.extend(str(joint["stable_id"]) for joint in row["joints"])
    if bay_count is not None:
        if set_index is None:
            raise ValueError("set_index is required for Bay truncation")
        _, selected = _layout_set(normalized, set_index)
        wanted = int(bay_count)
        if wanted < 1:
            raise ValueError("Receiving Set must contain at least one Bay")
        removed.extend(str(bay["stable_id"]) for bay in selected["bays"][wanted:])
        removed.extend(str(joint["stable_id"]) for joint in selected["joints"][max(wanted - 1, 0):])
    return tuple(removed)

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


def receiving_bay_assembly_offsets(layout, *, set_index=0):
    """由相鄰 Joint 與包外 W/H/D 解析各連中心；不從 renderer bbox 推算。

    Assembly 使用置中箱體座標，FRONT=+Z、TOP=+Y。每個相鄰
    Joint 對齊指定的外表面，故中心差為兩側包外尺寸差的一半。
    """
    normalized, selected = _layout_set(layout, set_index)
    bays = selected["bays"]
    offsets = [(0.0, 0.0, 0.0)]
    for index, joint in enumerate(selected["joints"]):
        left, right = bays[index:index + 2]
        x, y, z = offsets[-1]
        x += (float(left["width"]) + float(right["width"])) / 2
        height_delta = (float(right["height"]) - float(left["height"])) / 2
        depth_delta = (float(right["depth"]) - float(left["depth"])) / 2
        y += height_delta if joint["height_alignment"] == "BOTTOM" else -height_delta
        z += -depth_delta if joint["depth_alignment"] == "FRONT" else depth_delta
        offsets.append((x, y, z))
    return tuple(offsets)


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
    for selected in result["receiving_layout"]["sets"]:
        if "settings" in selected:
            for bay in selected["bays"]:
                bay.pop("back_panel_mode", None)
    if all("door_state" in bay for selected in result["receiving_layout"]["sets"] for bay in selected["bays"]):
        for key in RECEIVING_DOOR_STATE_KEYS:
            result.pop(key, None)
    if any("settings" in selected for selected in result["receiving_layout"]["sets"]):
        result.pop("head_holes", None)
        result.pop("tail_holes", None)
        for key in ("surface_features", "part_features"):
            if isinstance(result.get(key), Mapping):
                result[key] = {role: value for role, value in result[key].items() if role not in ("head", "tail")}
    for key in _DERIVED_LAYOUT_KEYS:
        result.pop(key, None)
    return result


def receiving_bay_joint_face_features(layout, *, set_index, bay_index, thickness, frame_width, existing=None):
    """取得本連相鄰接合的 canonical lock feature；原有非接合特徵保留。"""
    from ae_engine.receiving_joint_locks import resolve_receiving_joint_lock_pattern
    normalized, selected = _layout_set(layout, set_index)
    if bay_index < 0 or bay_index >= len(selected["bays"]):
        raise IndexError("連選取超出範圍")
    result = {face: [feature for feature in values if getattr(feature, "source_type", "") != "receiving_joint_side_lock"] for face, values in dict(existing or {}).items()}
    for joint_index in (bay_index - 1, bay_index):
        if joint_index < 0 or joint_index >= len(selected["joints"]):
            continue
        resolved = resolve_receiving_joint_lock_pattern(normalized, set_index=set_index, joint_index=joint_index, thickness=thickness, frame_width=frame_width)
        participant = resolved.right_bay if joint_index == bay_index - 1 else resolved.left_bay
        result.setdefault(participant.face_key, []).extend(participant.features)
    return result
