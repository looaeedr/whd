from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.manufacturing_api import build_box_body_divider_render_data
from ae_engine.sheetmetal_drawing import CirclePrimitive


def _receiving_divider():
    parts = derive_box_body_dividers(
        ((800.0, (1100.0, 500.0)),),
        depth=350.0,
        thickness=2.0,
        layout_scope="receiving-main",
        handle_edges={},
        model_name="受電箱",
    )
    assert len(parts) == 1
    return parts[0]


def test_receiving_divider_uses_confirmed_material_and_outside_fold_contract():
    divider = _receiving_divider()

    assert divider.material_lengths == pytest.approx((16.0, 25.0, 102.0, 15.0))
    assert tuple(abs(value) for value in divider.signed_fold_chain) == pytest.approx(
        (18.0, 29.0, 106.0, 17.0)
    )
    assert divider.formed_core_depth == pytest.approx(106.0)
    assert divider.core_segment_index == 2
    assert divider.span == pytest.approx(796.0)


def test_non_receiving_divider_keeps_existing_generic_depth_derived_contract():
    divider = derive_box_body_dividers(
        ((800.0, (1100.0, 500.0)),),
        depth=350.0,
        thickness=2.0,
        layout_scope="generic-main",
        handle_edges={},
    )[0]

    assert divider.material_lengths == pytest.approx((18.0, 20.0, 25.0, 342.0, 15.0))
    assert divider.signed_fold_chain == pytest.approx((18.0, 20.0, 25.0, 346.0, 15.0))


def test_receiving_divider_baseline_asset_is_vault_shared_feature_source():
    baseline = Path("基準檔") / "金庫型" / "中隔.dxf"
    assert baseline.is_file()

    doc = ezdxf.readfile(baseline)
    circles = list(doc.modelspace().query("CIRCLE"))
    assert len(circles) == 6
    assert sum(abs(float(entity.dxf.radius) - 3.2) <= 1e-6 for entity in circles) == 3


def test_receiving_divider_render_maps_all_baseline_holes_without_using_baseline_outer_cutting():
    divider = _receiving_divider()
    render = build_box_body_divider_render_data(
        divider,
        context=ManufacturingContext(resource_root=Path.cwd()),
    )

    holes = [
        primitive
        for primitive in render.scene.primitives
        if isinstance(primitive, CirclePrimitive)
        and primitive.source_type == "baseline_divider_hole"
    ]
    assert len(holes) == 6

    minx, miny, maxx, maxy = map(float, render.material.bounds)
    for primitive in holes:
        radius = float(primitive.radius)
        assert minx + radius <= float(primitive.center.x) <= maxx - radius
        assert miny + radius <= float(primitive.center.y) <= maxy - radius

    # T2 owns nominal baseline features only. T3 will own Assembly Relief.
    exterior = list(render.material.exterior.coords)
    assert len(exterior) == 5
    assert render.metadata["baseline_feature_model"] == "金庫型"
    assert render.metadata["baseline_divider_hole_count"] == 6


def test_receiving_divider_hole_group_preserves_source_relative_vectors():
    divider = _receiving_divider()
    render = build_box_body_divider_render_data(
        divider,
        context=ManufacturingContext(resource_root=Path.cwd()),
    )
    centers = sorted(
        (
            (float(p.center.x), float(p.center.y))
            for p in render.scene.primitives
            if isinstance(p, CirclePrimitive)
            and p.source_type == "baseline_divider_hole"
            and abs(float(p.radius) - 3.2) <= 1e-6
        )
    )

    # Derive expected vectors from the authoritative baseline under the
    # production clockwise rigid rotation: (dx,dy) -> (dy,-dx).
    # Translation/edge anchoring cancels out of relative vectors.
    doc = ezdxf.readfile(Path("基準檔") / "金庫型" / "中隔.dxf")
    source = [
        (float(e.dxf.center.x), float(e.dxf.center.y))
        for e in doc.modelspace().query("CIRCLE")
        if abs(float(e.dxf.radius) - 3.2) <= 1e-6
    ]
    rotated = sorted((y, -x) for x, y in source)

    actual_a = centers[0]
    expected_a = rotated[0]
    actual_vectors = [
        (x - actual_a[0], y - actual_a[1]) for x, y in centers[1:]
    ]
    expected_vectors = [
        (x - expected_a[0], y - expected_a[1]) for x, y in rotated[1:]
    ]
    assert actual_vectors == pytest.approx(expected_vectors)
