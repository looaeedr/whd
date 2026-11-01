# -*- coding: utf-8 -*-
"""Canonical project Save/Reload authority for Door/Receiving/Quantity.

Physical Door and Divider identities must be Engine-owned, not recreated
by a GUI file codec. FinalScene remains derived, never saved as authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math

_TRANSIENT_DERIVED_SNAPSHOT_KEYS = (
    "divider_parts",
    "inner_door_frame_parts",
    "_receiving_runtime_selection",
)


def normalize_authoritative_door_state(snapshot):
    """Materialize/repair T10 Door authority without persisting derived geometry.

    Door layout, per-cell handle edge, inner-door config and the optional
    nameplate datum are project authority. Divider/frame geometry remains
    derived state and is intentionally omitted. Shared lower-frame references
    are resolved only *after* divider stable IDs have been regenerated from the
    saved topology, so a stale child reference cannot leak into 3D/DXF.
    """
    result = deepcopy(dict(snapshot or {}))
    for key in _TRANSIENT_DERIVED_SNAPSHOT_KEYS:
        result.pop(key, None)

    from ae_engine.cabinet_types.receiving import is_receiving_snapshot
    if is_receiving_snapshot(result) and result.get("door_nameplate_center_datum_top") is None:
        from ae_engine.cabinet_types.receiving import DOOR_NAMEPLATE_CENTER_DATUM_TOP
        result["door_nameplate_center_datum_top"] = float(DOOR_NAMEPLATE_CENTER_DATUM_TOP)
    elif result.get("door_nameplate_center_datum_top") is not None:
        raw = result["door_nameplate_center_datum_top"]
        if isinstance(raw, bool):
            raise ValueError(f"invalid door_nameplate_center_datum_top: {raw!r}")
        try:
            datum = float(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"invalid door_nameplate_center_datum_top: {raw!r}") from exc
        if not math.isfinite(datum):
            raise ValueError(f"invalid door_nameplate_center_datum_top: {raw!r}")
        result["door_nameplate_center_datum_top"] = datum

    def persisted_layout_mm(value, *, label):
        # Project authority must be JSON numeric, not a Tk entry string or
        # a boolean. Reject malformed topology before divider/DXF derivation.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"invalid {label}: {value!r}")
        try:
            measured = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"invalid {label}: {value!r}") from exc
        if not math.isfinite(measured):
            raise ValueError(f"invalid {label}: {value!r}")
        return measured

    raw_columns_source = result.get("door_layout_columns")
    if raw_columns_source is not None and not isinstance(raw_columns_source, (list, tuple)):
        raise ValueError("invalid door layout columns source")
    try:
        raw_columns = list(raw_columns_source or ())
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid door layout columns source") from exc
    columns = []
    for row in raw_columns:
        if (not isinstance(row, (list, tuple)) or len(row) != 2
                or not isinstance(row[1], (list, tuple))):
            raise ValueError(f"invalid door layout column: {row!r}")
        width = persisted_layout_mm(row[0], label="door layout column width")
        heights = [
            persisted_layout_mm(value, label="door layout cell height")
            for value in row[1]
        ]
        columns.append([width, heights])
    if "door_layout_columns" in result or columns:
        result["door_layout_columns"] = columns

    handle_aliases = {"左": "LEFT", "右": "RIGHT", "上": "TOP", "下": "BOTTOM"}
    handles = {}
    raw_handle_edges = result.get("door_handle_edges")
    # An explicit false/zero/blank is corrupt saved authority, not an empty
    # set of Handle-Editor edges. Keep legacy iterable key/value pairs valid.
    if raw_handle_edges is not None and not isinstance(raw_handle_edges, (Mapping, list, tuple)):
        raise ValueError("invalid door handle edges source")
    try:
        saved_handle_edges = dict(raw_handle_edges or {})
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid door handle edges source") from exc
    for raw_key, raw_value in saved_handle_edges.items():
        value = str(raw_value).strip().upper()
        value = handle_aliases.get(value, value)
        if value not in {"LEFT", "RIGHT", "TOP", "BOTTOM"}:
            raise ValueError(f"unsupported door handle edge: {raw_value!r}")
        handles[str(raw_key)] = value
    if columns:
        from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
        valid_cells = {
            f"{cell.column_index}:{cell.row_index}"
            for cell in derive_door_layout_cells(tuple((w, tuple(hs)) for w, hs in columns))
        }
        handles = {key: value for key, value in handles.items() if key in valid_cells}
    elif handles:
        handles = {}
    if "door_handle_edges" in result or handles:
        result["door_handle_edges"] = handles

    raw_inner_doors = result.get("inner_doors")
    # A project persists a list of door records. list("door") and list({...})
    # would otherwise fabricate invalid physical door entries on reopen.
    if raw_inner_doors is not None and not isinstance(raw_inner_doors, (list, tuple)):
        raise ValueError("invalid inner doors source")
    if any(not isinstance(item, dict) for item in (raw_inner_doors or ())):
        raise ValueError("invalid inner doors entry")
    inner_doors = deepcopy(list(raw_inner_doors or ()))
    for item in inner_doors:
        # Never stringify a boolean into a physical door or cell identity.
        if any(isinstance(item.get(field), bool) for field in ("stable_id", "cell_key")):
            raise ValueError("invalid inner-door identity source")
        # Receiving frame spans / finished dimensions are deterministic
        # derivatives of Door topology + family policy, never project truth.
        item.pop("frame_spans", None)
        item.pop("inner_door_finished_size", None)
    if inner_doors:
        if not columns or not bool(result.get("multi_door_enabled", False)):
            for item in inner_doors:
                if isinstance(item, dict):
                    item.pop("lower_frame_role", None)
        else:
            from ae_engine.door_dividers import derive_box_body_dividers, resolve_inner_door_lower_frame_role

            try:
                raw_depth, raw_thickness = result["d"], result["t"]
                # Keep the source types until validation: float(True) would
                # otherwise authorize a physical 1-mm Door/Divider dimension.
                if isinstance(raw_depth, bool) or isinstance(raw_thickness, bool):
                    raise ValueError("saved d/t cannot be boolean")
                depth = float(raw_depth)
                thickness = float(raw_thickness)
                if not (math.isfinite(depth) and math.isfinite(thickness)
                        and depth > 0.0 and thickness > 0.0):
                    raise ValueError("saved d/t must be finite positive dimensions")
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    "inner-door shared role requires finite positive saved d/t authority"
                ) from exc
            scope = str(result.get("door_layout_scope") or "main").strip() or "main"
            dividers = derive_box_body_dividers(
                tuple((w, tuple(hs)) for w, hs in columns),
                depth=depth,
                thickness=thickness,
                layout_scope=scope,
                handle_edges=handles,
            )
            for item in inner_doors:
                if not isinstance(item, dict):
                    continue
                door_id = str(item.get("stable_id") or "").strip()
                if not door_id:
                    item.pop("lower_frame_role", None)
                    continue
                previous_role = item.get("lower_frame_role")
                if previous_role is not None and not isinstance(previous_role, dict):
                    raise ValueError("invalid inner-door lower_frame_role source")
                previous = (previous_role or {}).get("divider_stable_id")
                role = resolve_inner_door_lower_frame_role(
                    door_id,
                    dividers,
                    previous_divider_stable_id=(str(previous) if previous else None),
                )
                if role is None:
                    item.pop("lower_frame_role", None)
                else:
                    item["lower_frame_role"] = {
                        "role": role.role,
                        "divider_stable_id": role.divider_stable_id,
                    }
        result["inner_doors"] = inner_doors
    return result


def normalize_project_snapshot_authority(snapshot):
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
    from ae_engine.cabinet_types.receiving import is_receiving_snapshot
    from ae_engine.receiving_layout import ensure_receiving_layout, project_primary_bay_legacy_aliases

    result = migrate_legacy_snapshot_joints(dict(snapshot or {}))
    # Single-cabinet panel names are project input, owned here alongside
    # the rest of canonical Save/Reload authority (#2696).
    from .panel_naming import normalize_panel_name
    if not is_receiving_snapshot(result):
        result["panel_name"] = normalize_panel_name(
            result.get("panel_name", ""), allow_blank=True,
        )
    if is_receiving_snapshot(result):
        result = ensure_receiving_layout(result)
        # Existing Door normalization still consumes d/t from the single-Bay
        # runtime view.  This is transient only; v2 writer strips the aliases.
        result = project_primary_bay_legacy_aliases(result)
    result = normalize_authoritative_door_state(result)
    if is_receiving_snapshot(result):
        from ae_engine.receiving_layout import RECEIVING_DOOR_STATE_KEYS
        base_without_door = {
            k: v for k, v in result.items()
            if k not in RECEIVING_DOOR_STATE_KEYS
        }
        for selected in result["receiving_layout"]["sets"]:
            for bay in selected["bays"]:
                if "door_state" not in bay:
                    continue
                view = {**base_without_door, **bay["door_state"], "w": bay["width"], "h": bay["height"], "d": bay["depth"]}
                normalized = normalize_authoritative_door_state(view)
                bay["door_state"] = {key: deepcopy(normalized[key]) for key in RECEIVING_DOOR_STATE_KEYS if key in normalized}
    from ae_engine.receiving_quantity_versions import normalize_quantity_snapshot
    return normalize_quantity_snapshot(result)
