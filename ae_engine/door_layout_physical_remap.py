# -*- coding: utf-8 -*-
"""Canonical physical identity remap when an operator deletes a Door grid cell.

All inner-door persistent IDs, 2D cell keys and Workspace feature owner
transitions are computed in Engine. GUI is limited to submitting the deletion
and applying the complete detached result to its presentation workspaces.
This is identity migration, not manufacturing approval or a new hole source.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy


def receiving_inner_door_stable_id_for_cell(cell_key):
    """Preserve the project's persisted upper/lower/cNrN naming contract."""
    key = str(cell_key or "").strip()
    if key == "0:0":
        return "upper"
    if key == "0:1":
        return "lower"
    try:
        column, row = (int(v) for v in key.split(":", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid door cell key: {cell_key!r}") from exc
    if column < 0 or row < 0:
        raise ValueError(f"invalid door cell key: {cell_key!r}")
    return f"c{column + 1}r{row + 1}"


def remap_receiving_door_layout_after_delete(
    *, operation, column_index, row_index=None, inner_doors=None,
    cell_sources=None, physical_sources=None, cell_transitions=None,
):
    """Produce a detached, whole-source remap for a Door row/column deletion.

    physical_sources may include 'surface', 'workspace', 'workspace_face',
    'designer', and 'designer_face'.  Rebuild the canonical physical Door cell
    feature aliases for the three full part stores; face stores contain only
    per-part face features. Collision or invalid operation raises *before*
    any caller's data is modified. All existing source features are preserved.
    """
    if operation == "map_cells":
        # Legacy operator mappings are only cell-index requests. The Engine
        # still owns and validates every persisted physical part identity.
        if not isinstance(cell_transitions, Mapping):
            raise ValueError("Door cell transitions must be a mapping")
        if any(not isinstance(k, str) or
               (v is not None and not isinstance(v, str))
               for k, v in cell_transitions.items()):
            raise ValueError("Door cell transitions must contain cell keys")
    elif type(column_index) is not int or column_index < 0:
        raise ValueError("Door column deletion requires an actual grid index")
    elif operation == "delete_column":
        if row_index is not None:
            raise ValueError("Column deletion cannot specify a row")
    elif operation == "delete_row":
        if type(row_index) is not int or row_index < 0:
            raise ValueError("Door row deletion requires an actual grid index")
    else:
        raise ValueError("Unsupported Door layout deletion")

    if cell_sources is None:
        cell_sources = {}
    if physical_sources is None:
        physical_sources = {}
    if not isinstance(cell_sources, Mapping) or not isinstance(physical_sources, Mapping):
        raise ValueError("Door feature stores must be mappings")

    def mapped(column, row):
        if operation == "delete_column":
            if column == column_index:
                return None
            return (column - 1 if column > column_index else column, row)
        if column == column_index and row == row_index:
            return None
        return (column, row - 1 if column == column_index and row > row_index else row)

    def mapped_cell_key(value):
        if operation == "map_cells":
            return cell_transitions.get(str(value))
        try:
            col_s, row_s = str(value).split(":", 1)
            target = mapped(int(col_s), int(row_s))
        except (TypeError, ValueError):
            return None
        return None if target is None else f"{target[0]}:{target[1]}"

    next_rows, id_changes = [], {}
    if isinstance(inner_doors, list):
        for raw in inner_doors:
            if not isinstance(raw, dict):
                continue
            old_id = str(raw.get("stable_id") or "").strip()
            next_key = mapped_cell_key(raw.get("cell_key", ""))
            if next_key is None:
                if old_id:
                    id_changes[old_id] = None
                continue
            new_id = receiving_inner_door_stable_id_for_cell(next_key)
            row = deepcopy(raw)
            row["cell_key"] = next_key
            row["stable_id"] = new_id
            next_rows.append(row)
            if old_id and old_id != new_id:
                id_changes[old_id] = new_id

    next_cells = {}
    for label, source in cell_sources.items():
        updated = {}
        for key, value in dict(source or {}).items():
            target = mapped_cell_key(key)
            if target is not None:
                if target in updated and updated[target] != value:
                    raise ValueError(f"Door cell remap feature collision: {target}")
                updated[target] = deepcopy(value)
        next_cells[label] = updated

    def remap_physical(source):
        updated = {}
        for key, value in dict(source or {}).items():
            target = str(key)
            for old_id, new_id in id_changes.items():
                prefix = f"inner_door:{old_id}:"
                if target.startswith(prefix):
                    target = (
                        None if new_id is None
                        else f"inner_door:{new_id}:" + target[len(prefix):]
                    )
                    break
            if target is None:
                continue
            if target in updated and updated[target] != value:
                raise ValueError(f"內門重映射特徵身份衝突: {target}")
            updated[target] = deepcopy(value)
        return updated

    next_physical = {}
    for label, source in physical_sources.items():
        if label not in {
            "surface", "workspace", "workspace_face", "designer", "designer_face"
        }:
            raise ValueError(f"Unsupported Door physical store: {label}")
        updated = remap_physical(source)
        if label in ("surface", "workspace", "designer"):
            for key in tuple(updated):
                if key.startswith("door_c"):
                    updated.pop(key)
            for cell_key, items in next_cells.get("door_layout_features", {}).items():
                try:
                    c_text, r_text = str(cell_key).split(":", 1)
                    part_id = f"door_c{int(c_text) + 1}_r{int(r_text) + 1}"
                except (TypeError, ValueError):
                    continue
                if part_id in updated and updated[part_id] != items:
                    raise ValueError(f"Door physical feature collision: {part_id}")
                updated[part_id] = deepcopy(list(items))
        next_physical[label] = updated

    return {
        "inner_doors": next_rows if isinstance(inner_doors, list) else None,
        "identity_changes": id_changes,
        "cell_sources": next_cells,
        "physical_sources": next_physical,
    }
