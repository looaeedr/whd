"""Headless operator Door grid peer display-source projection."""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class DoorLayoutPeerCell:
    column_index: int
    row_index: int
    part_key: str
    scene: object = None
    width: float | None = None
    height: float | None = None

    @property
    def present(self):
        return self.scene is not None


def project_operator_door_layout_peer_cells(cells, sources):
    """Read canonical peer-door scene and material bounds for each grid cell."""
    from collections.abc import Mapping
    if not isinstance(sources, Mapping):
        raise ValueError("DOOR_LAYOUT_PEER_SOURCE_MAPPING_INVALID")
    rows, seen = [], set()
    for cell in tuple(cells or ()):
        col, row = getattr(cell, "column_index", None), getattr(cell, "row_index", None)
        if (type(col) is not int or type(row) is not int or col < 0
                or row < 0 or (col, row) in seen):
            raise ValueError("DOOR_LAYOUT_PEER_CELL_ID_INVALID")
        seen.add((col, row))
        key = f"door_c{col + 1}_r{row + 1}"
        source = sources.get(key)
        material, scene = getattr(source, "material", None), getattr(source, "scene", None)
        if (material is None or scene is None
                or bool(getattr(material, "is_empty", False))):
            rows.append(DoorLayoutPeerCell(col, row, key))
            continue
        try:
            bounds = tuple(float(v) for v in material.bounds)
            if len(bounds) != 4 or not all(isfinite(v) for v in bounds):
                raise ValueError("invalid bounds")
            x0, y0, x1, y1 = bounds
            if x1 < x0 or y1 < y0:
                raise ValueError("reversed bounds")
        except (TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise ValueError("DOOR_LAYOUT_PEER_SOURCE_BOUNDS_INVALID") from exc
        rows.append(DoorLayoutPeerCell(
            col, row, key, scene, max(x1 - x0, 1e-9), max(y1 - y0, 1e-9),
        ))
    return tuple(rows)
