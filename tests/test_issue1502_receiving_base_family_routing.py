# -*- coding: utf-8 -*-
"""#1502: Receiving must never inherit the generic Base Plate blank silently."""
import pytest

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import build_part_render_data, generate_part
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_LEFT,
    RECEIVING_BASE_PATTERN_CENTER,
)


def _plate(*, model="受電箱", pattern=None):
    center = pattern == RECEIVING_BASE_PATTERN_CENTER
    return BasePlatePartSpec(
        width=800.0, height=280.0 if center else 340.0, thickness=2.0,
        shrink_top=20.0, shrink_bottom=20.0,
        shrink_left=85.0 if center else 45.0,
        shrink_right=85.0 if center else 45.0,
        bend=20.0, model_name=model,
        receiving_bend_pattern=pattern, physical_id="base_plate",
    )


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING"))
def test_receiving_without_actual_pattern_must_not_render_generic_base(family, tmp_path):
    spec = _plate(model=family)
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED"):
        build_part_render_data(spec)
    output = tmp_path / "unresolved_receiving_base.dxf"
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED"):
        generate_part(spec, output)
    assert not output.exists()


@pytest.mark.parametrize("pattern,expected_size,expected_bends", (
    (RECEIVING_BASE_PATTERN_LEFT, (710.0, 300.0), 2),
    (RECEIVING_BASE_PATTERN_CENTER, (772.0, 240.0), 6),
))
def test_explicit_receiving_variant_uses_its_own_plate_geometry(
    pattern, expected_size, expected_bends,
):
    render = build_part_render_data(_plate(pattern=pattern))
    assert (render.unfolded_topology.width, render.unfolded_topology.height) == pytest.approx(expected_size)
    assert render.metadata["receiving_bend_pattern"] == pattern
    assert len([
        item for item in render.scene.primitives
        if isinstance(item, LinePrimitive) and item.layer == "BEND"
    ]) == expected_bends
