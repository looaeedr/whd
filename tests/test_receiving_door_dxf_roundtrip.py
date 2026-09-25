from __future__ import annotations

from pathlib import Path

import pytest

from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import (
    build_part_render_data,
    save_part_render_data_dxf,
    verify_saved_part_render_data_dxf,
)
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _receiving_door(height: float, *, bottom_edge: bool) -> DoorPartSpec:
    return DoorPartSpec(
        width=800.0,
        height=float(height),
        thickness=2.0,
        frame_width=29.0,
        model_name="受電箱",
        gap_w=3.5,
        gap_h=3.5,
        fold_left=19.0,
        fold_right=19.0,
        fold_top=19.0,
        fold_bottom=19.0,
        frame_edges=DoorFrameEdges(bottom=bottom_edge),
    )


@pytest.mark.parametrize(
    ("name", "spec"),
    (
        ("upper", _receiving_door(1100.0, bottom_edge=False)),
        ("lower", _receiving_door(500.0, bottom_edge=True)),
    ),
)
def test_receiving_door_baseline_arc_line_cutting_reopens_as_same_final_material(
    tmp_path, name, spec
):
    render = build_part_render_data(
        spec,
        ManufacturingContext(resource_root=PROJECT_ROOT, draw_stock=False),
    )
    path = tmp_path / f"receiving_{name}_door.dxf"
    save_part_render_data_dxf(render, path, overwrite=True)

    result = verify_saved_part_render_data_dxf(render, path)

    assert result.ok is True, [
        (issue.category, issue.detail, issue.expected, issue.actual)
        for issue in result.issues
    ]
