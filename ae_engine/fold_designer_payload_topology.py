# -*- coding: utf-8 -*-
"""Headless Fold Designer physical Door/BasePlate cell topology lookup.

The stable DoorLayoutCell IDs, frame edge flags, 1:1 operator W/H and model
normalization are owned by the same Engine domain as manufacturing/export.
This API does not certify any drawing or fill absent physical sources.
"""
from __future__ import annotations

from . import ae
from .corner_type_ui import is_unknown_model, normalize_custom_model_name
from .sheetmetal_part_adapters import (
    derive_door_layout_cells, door_layout_export_filename,
)

def resolve_fold_designer_payload_topology(part_key, payload):
    data = dict(payload or {})
    key = str(part_key or "")
    w = float(data.get("w", ae.W))
    h = float(data.get("h", ae.H))
    d = float(data.get("d", ae.D))
    t = float(data.get("t", ae.T))
    fw = float(data.get("fw", ae.FW))
    model = normalize_custom_model_name(data.get("model"))
    unknown = is_unknown_model(model)
    corner_state = data.get("corner_state") or {}
    features = tuple(data.get("features") or ())
    face_features = data.get("face_features") or {}
    door_cell = None
    base_plate_cell = None
    if key.startswith("door_c"):
        columns = tuple(
            (float(row[0]), tuple(float(value) for value in row[1]))
            for row in tuple(data.get("door_layout_columns") or ())
        )
        if not columns:
            raise ValueError(f"門格缺少 authoritative multi-door topology: {key}")
        door_cell = next(
            (
                cell for cell in derive_door_layout_cells(columns)
                if door_layout_export_filename(cell).removesuffix(".dxf") == key
            ),
            None,
        )
        if door_cell is None:
            raise ValueError(f"門格 stable_id 不存在於 authoritative topology: {key}")
        w = float(door_cell.start_width)
        h = float(door_cell.start_height)
    elif key.startswith("base_plate_c"):
        columns = tuple(
            (float(row[0]), tuple(float(value) for value in row[1]))
            for row in tuple(data.get("door_layout_columns") or ())
        )
        if not columns:
            raise ValueError(f"底板缺少 authoritative multi-door topology: {key}")
        owner_door_key = key.replace("base_plate_", "door_", 1)
        base_plate_cell = next(
            (
                cell for cell in derive_door_layout_cells(columns)
                if door_layout_export_filename(cell).removesuffix(".dxf") == owner_door_key
            ),
            None,
        )
        if base_plate_cell is None:
            raise ValueError(f"底板 stable_id 不存在於 authoritative topology: {key}")
        w = float(base_plate_cell.start_width)
        h = float(base_plate_cell.start_height)
    return (
        data, key, w, h, d, t, fw, model, unknown, corner_state,
        features, face_features, door_cell, base_plate_cell,
    )
