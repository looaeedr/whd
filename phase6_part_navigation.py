# -*- coding: utf-8 -*-
"""Pure operator part-navigation projection for Phase6.

This module owns only View/navigation identity rules.  Manufacturing topology
remains authoritative in ``Phase6DesignerWorkspace.available_parts``.  No
function here mutates a workspace, Tk widget, render data, or manufacturing
geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class NavigationIntent(str, Enum):
    EXPLICIT_SELECT = "EXPLICIT_SELECT"
    RESTORE_CHILD_CONTEXT = "RESTORE_CHILD_CONTEXT"


@dataclass(frozen=True)
class NavigationMemory:
    remembered_box_body_child: str | None = None


@dataclass(frozen=True)
class NavigationRequest:
    requested_key: str | None
    intent: NavigationIntent = NavigationIntent.EXPLICIT_SELECT


@dataclass(frozen=True)
class NavigationRow:
    part_key: str
    parent_key: str | None
    depth: int


@dataclass(frozen=True)
class NavigationProjection:
    requested_key: str | None
    resolved_key: str | None
    selection_kind: str
    reason: str
    memory: NavigationMemory


def _keys(values: Iterable[object] | None) -> tuple[str, ...]:
    return tuple(str(value) for value in tuple(values or ()) if str(value or ""))


def is_box_body_physical_piece_key(value: object) -> bool:
    """Classify manufacturing-owned BoxBody child identities only."""
    key = str(value or "")
    return key.startswith("box_body:") and not key.startswith("box_body:divider:")


def box_body_piece_keys(values: Iterable[object] | None) -> tuple[str, ...]:
    """Return physical BoxBody children in authoritative source order."""
    return tuple(key for key in _keys(values) if is_box_body_physical_piece_key(key))


def project_hierarchy(values: Iterable[object] | None) -> tuple[NavigationRow, ...]:
    """Project authoritative identities into an operator hierarchy.

    A logical ``box_body`` parent is never invented.  Children are nested only
    when that real aggregate identity is present; otherwise every authoritative
    identity remains visible as a top-level row.
    """
    keys = _keys(values)
    children = box_body_piece_keys(keys)
    child_set = set(children)
    parent_present = "box_body" in keys
    rows: list[NavigationRow] = []
    for key in keys:
        if parent_present and key in child_set:
            continue
        rows.append(NavigationRow(key, None, 0))
        if parent_present and key == "box_body":
            rows.extend(NavigationRow(child, "box_body", 1) for child in children)
    return tuple(rows)


def operator_part_selector_keys(values: Iterable[object] | None) -> tuple[str, ...]:
    """Return top-level operator identities from the common hierarchy projection."""
    return tuple(row.part_key for row in project_hierarchy(values) if row.depth == 0)


def _validated_memory(
    children: tuple[str, ...], memory: NavigationMemory | None
) -> NavigationMemory:
    remembered = str(getattr(memory, "remembered_box_body_child", None) or "")
    return NavigationMemory(remembered if remembered in children else None)



def operator_part_label(
    value: object,
    *,
    snapshot: Mapping[str, object] | None = None,
    base_labels: Mapping[str, object] | None = None,
) -> str:
    """Project one stable part identity to its operator-facing label.

    This stays pure: callers provide any legacy/base label table plus an
    optional read-only snapshot used only for family/layout-sensitive labels.
    """
    key = str(value or "")
    labels = dict(base_labels or {})
    if key in labels:
        return str(labels[key])
    piece_labels = {
        "box_body:left_side": "左側板",
        "box_body:back": "後面板",
        "box_body:right_side": "右側板",
        "box_body_left_side": "左側板",
        "box_body_back": "後面板",
        "box_body_right_side": "右側板",
        "box_body:left": "左箱身",
        "box_body:middle": "中箱身",
        "box_body:right": "右箱身",
    }
    if key in piece_labels:
        return piece_labels[key]

    snap = dict(snapshot or {})
    model = str(
        snap.get("model")
        or snap.get("baseline_model")
        or snap.get("cabinet_family")
        or ""
    )
    columns = list(snap.get("door_layout_columns") or ())

    import re

    door_match = re.fullmatch(r"door_c(\d+)_r(\d+)", key)
    if door_match:
        col, row = (int(door_match.group(1)), int(door_match.group(2)))
        if model == "受電箱" and len(columns) == 1 and col == 1:
            if row == 1:
                return "上門"
            if row == 2:
                return "下門"
        return f"第{col}欄第{row}門"

    base_match = re.fullmatch(r"base_plate_c(\d+)_r(\d+)", key)
    if base_match:
        col, row = (int(base_match.group(1)), int(base_match.group(2)))
        if model == "受電箱" and len(columns) == 1 and col == 1:
            if row == 1:
                return "上門底板"
            if row == 2:
                return "下門底板"
        return f"第{col}欄第{row}門底板"

    if key.startswith("box_body:divider:"):
        axis = (
            "橫向"
            if ":HORIZONTAL:" in key
            else "直向"
            if ":VERTICAL:" in key
            else ""
        )
        return f"箱身中隔（{axis}）" if axis else "箱身中隔"

    if key.startswith("inner_door:") and key.endswith(":panel"):
        door_id = key.split(":", 2)[1]
        door_label = {"upper": "上層內門", "lower": "下層內門"}.get(door_id, "內門")
        return f"{door_label}門板"

    if key.startswith("inner_door:") and key.endswith("_frame"):
        side = key.rsplit(":", 1)[-1].removesuffix("_frame")
        side_label = {
            "top": "上框",
            "bottom": "下框",
            "left": "左框",
            "right": "右框",
        }.get(side, "框")
        door_id = key.split(":", 2)[1]
        door_label = {"upper": "上層內門", "lower": "下層內門"}.get(door_id, "內門")
        return f"{door_label}{side_label}"

    return key

def resolve_navigation(
    available_parts: Iterable[object] | None,
    request: NavigationRequest,
    memory: NavigationMemory | None = None,
) -> NavigationProjection:
    """Resolve operator intent without guessing a manufacturing identity.

    Explicit selection is exact.  A stale child fails closed even when another
    remembered/first child exists.  Child memory is consulted only for an
    explicit ``RESTORE_CHILD_CONTEXT`` request.
    """
    keys = _keys(available_parts)
    present = set(keys)
    children = box_body_piece_keys(keys)
    valid_memory = _validated_memory(children, memory)
    requested = str(request.requested_key or "") or None

    if request.intent == NavigationIntent.RESTORE_CHILD_CONTEXT:
        remembered = valid_memory.remembered_box_body_child
        return NavigationProjection(
            requested_key=requested,
            resolved_key=remembered,
            selection_kind="PHYSICAL_CHILD" if remembered else "NONE",
            reason="OK" if remembered else "NO_REMEMBERED_CHILD",
            memory=valid_memory,
        )

    if requested == "box_body":
        return NavigationProjection(
            requested_key=requested,
            resolved_key="box_body" if "box_body" in present else None,
            selection_kind="AGGREGATE_PARENT" if "box_body" in present else "NONE",
            reason="OK" if "box_body" in present else "PART_NOT_PRESENT",
            memory=valid_memory,
        )

    if is_box_body_physical_piece_key(requested):
        if requested in children:
            return NavigationProjection(
                requested_key=requested,
                resolved_key=requested,
                selection_kind="PHYSICAL_CHILD",
                reason="OK",
                memory=NavigationMemory(requested),
            )
        # The request itself is stale.  A different valid remembered sibling may
        # remain remembered, but it must never replace this explicit identity.
        remembered = valid_memory.remembered_box_body_child
        if str(getattr(memory, "remembered_box_body_child", None) or "") == requested:
            remembered = None
        return NavigationProjection(
            requested_key=requested,
            resolved_key=None,
            selection_kind="NONE",
            reason="STALE_PHYSICAL_CHILD",
            memory=NavigationMemory(remembered),
        )

    if requested and requested in present:
        return NavigationProjection(
            requested_key=requested,
            resolved_key=requested,
            selection_kind="REGULAR_PART",
            reason="OK",
            memory=valid_memory,
        )

    return NavigationProjection(
        requested_key=requested,
        resolved_key=None,
        selection_kind="NONE",
        reason="PART_NOT_PRESENT",
        memory=valid_memory,
    )
