# -*- coding: utf-8 -*-
"""Engine-owned classification of existing persisted physical part identities.

No new IDs are allocated and recognition does not confer DXF capability.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


def is_box_body_physical_piece_key(value: object) -> bool:
    """Classify manufacturing-owned BoxBody child identities only."""
    key = str(value or "")
    return key.startswith("box_body:") and not key.startswith("box_body:divider:")


def is_derived_physical_part_key(value: object) -> bool:
    key = str(value or "")
    return (
        re.fullmatch(r"door_c\d+_r\d+", key) is not None
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
        or key.startswith("base_plate:fixing_plate:")
        or key.startswith("base_plate:nfb_layer:")
        or key.startswith("nfb_pad:")
        or is_box_body_physical_piece_key(key)
        or key.startswith("box_body:divider:")
        or (key.startswith("inner_door:") and key.endswith("_frame"))
        or (key.startswith("inner_door:") and key.endswith(":panel"))
    )


def door_display_part_role(value: object) -> str:
    """Canonical persisted Door/panel identity for 3D presentation, not release.

    Display opacity and true CUTTING hole-rim visibility may depend on this
    immutable physical identity. A lookalike name must not be a Door sheet.
    """
    key = str(value or "")
    if key == "door" or re.fullmatch(r"door_c\d+_r\d+", key) is not None:
        return "outer"
    if key.startswith("inner_door:") and key.endswith(":panel"):
        return "inner"
    return "other"


@dataclass(frozen=True)
class OperatorHoleEditorRoute:
    """Presentation route for one persisted physical identity, not DXF authority."""
    kind: str
    part_key: str
    column_index: int | None = None
    row_index: int | None = None


def project_operator_hole_editor_route(
    part_key: object, *, model: object,
    multi_door_enabled: object = False, has_fold_designer: bool = False,
) -> OperatorHoleEditorRoute:
    """Classify operator editor intent using Engine physical/Families identities.

    This only chooses the UI entry. The corresponding physical Editor Context
    and actual manufactured feature/surface remain separate Engine validations.
    An unsupported part must fail before GUI active selection can be mutated.
    """
    from .cabinet_types.policy import canonical_family_name
    from .operator_settings_transactions import normalize_operator_settings_boolean

    if type(part_key) is not str or not part_key:
        raise ValueError("HOLE_EDITOR_PART_ID_INVALID")
    if type(has_fold_designer) is not bool:
        raise ValueError("HOLE_EDITOR_CONTEXT_INVALID")
    multi = normalize_operator_settings_boolean(multi_door_enabled)
    key = part_key

    if key in {"head", "tail"}:
        return OperatorHoleEditorRoute("endcap", key)
    door_cell = re.fullmatch(r"door_c(\d+)_r(\d+)", key)
    if door_cell is not None:
        column, row = int(door_cell.group(1)), int(door_cell.group(2))
        if column < 1 or row < 1:
            raise ValueError("HOLE_EDITOR_DOOR_CELL_ID_INVALID")
        return OperatorHoleEditorRoute("door_cell", key, column - 1, row - 1)
    if (
        key.startswith(("box_body:divider:", "base_plate:fixing_plate:",
                        "base_plate_c", "custom:"))
        or is_box_body_physical_piece_key(key)
        or (key.startswith("inner_door:") and key.endswith("_frame"))
    ):
        return OperatorHoleEditorRoute("workspace_sheet", key)
    if key == "base_plate" and has_fold_designer and (
        canonical_family_name(model) == "受電箱"
    ):
        return OperatorHoleEditorRoute("workspace_sheet", key)
    if key == "box_body":
        return OperatorHoleEditorRoute("box_body_face", key)
    if key.startswith("inner_door:") and key.endswith(":panel"):
        return OperatorHoleEditorRoute("inner_door_panel", key)
    if key == "door" and multi:
        return OperatorHoleEditorRoute("selected_door_cell", key)
    if key in {"door", "base_plate", "indicator_box", "indicator_door"}:
        return OperatorHoleEditorRoute("simple_part", key)
    raise ValueError("HOLE_EDITOR_PART_ID_UNSUPPORTED")
