"""#2517 Settings finished part dimensions and dynamic Door cells are Engine-owned."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ae_engine import (
    DoorPartProjection, door_part_projections, manufacturing_api, project_part_dimensions,
)
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
import phase6_settings_profile_projection as legacy


def test_public_engine_api_is_same_callable_as_settings_compatibility():
    assert manufacturing_api.DoorPartProjection is DoorPartProjection
    assert manufacturing_api.door_part_projections is door_part_projections
    assert manufacturing_api.project_part_dimensions is project_part_dimensions
    assert legacy.DoorPartProjection is DoorPartProjection
    assert legacy.door_part_projections is door_part_projections
    assert legacy.project_part_dimensions is project_part_dimensions


def test_engine_owns_default_physical_finished_dimensions_without_mutating_input():
    snapshot = {"model": "金庫型", "w": 800, "h": 1600, "d": 350,
                "t": 2, "fw": 29, "part_dimensions": {}}
    original = dict(snapshot)
    dimensions = project_part_dimensions(snapshot)
    assert dimensions["box_body"] == {"width": 800.0, "height": 1600.0}
    assert dimensions["head"] == {"width": 800.0, "height": 350.0}
    assert dimensions["tail"] == {"width": 800.0, "height": 350.0}
    assert dimensions["base_plate"] == {"width": 690.0, "height": 1490.0}
    assert dimensions["door"]["width"] > 0
    assert dimensions["door"]["height"] > 0
    assert snapshot == original


def test_engine_multidoor_cells_and_baseplate_identity_from_single_snapshot():
    snapshot = {
        "model": "金庫型",
        "w": 1100, "h": 1800, "d": 250, "t": 2, "fw": 25,
        "multi_door_enabled": True,
        "door_layout_columns": [[600.0, [600.0, 500.0, 700.0]], [500.0, [800.0, 1000.0]]],
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "part_dimensions": {"door_c9_r9": {"width": 1, "height": 1},
                            "base_plate_c9_r9": {"width": 1, "height": 1}},
    }
    rows = door_part_projections(snapshot)
    assert tuple(row.part_key for row in rows) == (
        "door_c1_r1", "door_c1_r2", "door_c1_r3", "door_c2_r1", "door_c2_r2"
    )
    assert rows[0].frame_edges == DoorFrameEdges(left=True, right=False, top=True, bottom=False)
    assert (rows[0].formed_width, rows[0].formed_height) == pytest.approx((564.0, 564.0))
    dims = project_part_dimensions(snapshot)
    assert "door" not in dims
    assert "door_c9_r9" not in dims
    assert "base_plate_c9_r9" not in dims
    assert dims["door_c1_r1"] == {"width": rows[0].formed_width, "height": rows[0].formed_height}
    assert dims["base_plate_c1_r1"] == {"width": 490.0, "height": 490.0}


def test_settings_adapter_contains_no_dimension_or_door_cell_manufacturing_code():
    path = Path(legacy.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    funcs = {item.name for item in tree.body if isinstance(item, ast.FunctionDef)}
    assert "project_part_dimensions" not in funcs
    assert "door_part_projections" not in funcs
    source = path.read_text(encoding="utf-8")
    assert "from ae_engine.manufacturing_api import" in source
    assert "def build_standard_part_profiles(" in source
