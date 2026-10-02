# -*- coding: utf-8 -*-
"""Pure Assembly Parts presentation contracts and projections.

This module owns presentation-only structure.  It does not own live visibility,
physical topology, geometry solving, persistence, or widget state.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Iterable, Mapping

from phase6_part_navigation import operator_part_selector_keys


@dataclass(frozen=True)
class AssemblyPresentationRow:
    part_key: str
    label: str
    visible_seed: bool = True
    formed_text_seed: str | None = None
    blank_text_seed: str | None = None
    corner_text_seed: str | None = None
    has_piece_host: bool = False


@dataclass(frozen=True)
class AssemblySyntheticGroup:
    presentation_key: str
    label: str
    children: tuple[AssemblyPresentationRow, ...]


@dataclass(frozen=True)
class AssemblyPresentationModel:
    entries: tuple[AssemblyPresentationRow | AssemblySyntheticGroup, ...]


@dataclass(frozen=True)
class AssemblyBoxBodyPieceRow:
    part_key: str
    label: str
    formed_width: float
    formed_height: float
    blank_width: float
    blank_height: float


_DOOR_KEY = re.compile(r"door_c\d+_r\d+")
_BASE_PLATE_KEY = re.compile(r"base_plate_c\d+_r\d+")


def _seed_for(key: str, values: Mapping[str, object] | None) -> bool:
    if values is None or key not in values:
        return True
    return bool(values[key])


def _row(
    key: str,
    *,
    label_for: Callable[[str], str],
    visible_seed_by_key: Mapping[str, object] | None,
) -> AssemblyPresentationRow:
    return AssemblyPresentationRow(
        part_key=key,
        label=str(label_for(key)),
        visible_seed=_seed_for(key, visible_seed_by_key),
        has_piece_host=(key == "box_body"),
    )


def build_assembly_presentation_model(
    available_parts: Iterable[object] | None,
    *,
    label_for: Callable[[str], str],
    visible_seed_by_key: Mapping[str, object] | None = None,
) -> AssemblyPresentationModel:
    """Project authoritative top-level part identities into presentation rows.

    Door and BasePlate dynamic children are grouped under synthetic presentation
    headers.  Child identities and source order are preserved exactly.
    """
    keys = tuple(operator_part_selector_keys(available_parts))
    door_children = tuple(key for key in keys if _DOOR_KEY.fullmatch(key))
    base_children = tuple(key for key in keys if _BASE_PLATE_KEY.fullmatch(key))

    entries: list[AssemblyPresentationRow | AssemblySyntheticGroup] = []
    emitted: set[str] = set()

    for key in keys:
        if key in door_children:
            if "door" not in emitted:
                entries.append(
                    AssemblySyntheticGroup(
                        presentation_key="door",
                        label=str(label_for("door")),
                        children=tuple(
                            _row(
                                child,
                                label_for=label_for,
                                visible_seed_by_key=visible_seed_by_key,
                            )
                            for child in door_children
                        ),
                    )
                )
                emitted.add("door")
            continue

        if key in base_children:
            if "base_plate" not in emitted:
                entries.append(
                    AssemblySyntheticGroup(
                        presentation_key="base_plate",
                        label=str(label_for("base_plate")),
                        children=tuple(
                            _row(
                                child,
                                label_for=label_for,
                                visible_seed_by_key=visible_seed_by_key,
                            )
                            for child in base_children
                        ),
                    )
                )
                emitted.add("base_plate")
            continue

        entries.append(
            _row(
                key,
                label_for=label_for,
                visible_seed_by_key=visible_seed_by_key,
            )
        )

    return AssemblyPresentationModel(entries=tuple(entries))


def legacy_assembly_presentation_groups(
    values: Iterable[object] | None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Project legacy Bridge grouping tuples from the pure presentation model."""
    model = build_assembly_presentation_model(values, label_for=str)
    return tuple(
        (
            str(entry.presentation_key),
            tuple(str(child.part_key) for child in entry.children),
        )
        if isinstance(entry, AssemblySyntheticGroup)
        else (str(entry.part_key), ())
        for entry in model.entries
    )


def project_box_body_piece_rows(
    render_data: object,
    *,
    label_for: Callable[[str], str],
) -> tuple[AssemblyBoxBodyPieceRow, ...]:
    """Copy render-time BoxBody physical-piece dimensions into pure rows."""
    rows: list[AssemblyBoxBodyPieceRow] = []
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "").strip()
        key = f"box_body:{role}" if role else str(getattr(piece, "key", "") or "")
        formed_width, formed_height = (
            float(value) for value in tuple(piece.formed_outer_dimensions)
        )
        blank_width, blank_height = (
            float(value) for value in tuple(piece.material_dimensions)
        )
        rows.append(
            AssemblyBoxBodyPieceRow(
                part_key=key,
                label=str(label_for(key)),
                formed_width=formed_width,
                formed_height=formed_height,
                blank_width=blank_width,
                blank_height=blank_height,
            )
        )
    return tuple(rows)
