# -*- coding: utf-8 -*-
"""#1502: original Base Plate has a separate Receiving physical-geometry route."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import (
    build_part_render_data, generate_part, save_resolved_manufacturing_geometry_dxf,
)
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_LEFT,
    RECEIVING_BASE_PATTERN_CENTER,
)
from ae_engine.receiving_base_plate_config import (
    receiving_base_plate_values, receiving_base_plate_blank_dimensions,
)
from phase6_settings_profile_projection import project_part_dimensions
from ae_engine.cabinet_types.receiving import apply_family_defaults


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


def _configured(pattern, *, height):
    center = pattern == RECEIVING_BASE_PATTERN_CENTER
    return {
        "pattern": pattern,
        "height": height,
        "shrink_top": 20.0,
        "shrink_bottom": 20.0,
        "shrink_left": 85.0 if center else 45.0,
        "shrink_right": 85.0 if center else 45.0,
        "bend": 20.0,
    }


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING"))
def test_unconfigured_receiving_preview_stays_open_but_never_exports_as_actual(family, tmp_path):
    spec = _plate(model=family)
    preview = build_part_render_data(spec)
    assert preview.metadata["receiving_base_plate_unconfigured"] is True
    path = tmp_path / "not_manufacturing.dxf"
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING"):
        generate_part(spec, path)
    assert not path.exists()

    resolved = SimpleNamespace(parts=(SimpleNamespace(part_key="base_plate", render_data=preview),))
    root = tmp_path / "atomic-export"
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING"):
        save_resolved_manufacturing_geometry_dxf(resolved, root)
    assert not root.exists()


@pytest.mark.parametrize("pattern,nominal_h,expected_size,expected_bends", (
    (RECEIVING_BASE_PATTERN_LEFT, 340.0, (710.0, 300.0), 2),
    (RECEIVING_BASE_PATTERN_CENTER, 280.0, (772.0, 240.0), 6),
))
def test_configured_receiving_uses_real_plate_dimensions_in_finalscene_and_ui_projection(
    pattern, nominal_h, expected_size, expected_bends,
):
    snapshot = apply_family_defaults({"model": "受電箱", "w": 800, "h": 1600, "t": 2})
    snapshot["receiving_base_plate"] = _configured(pattern, height=nominal_h)
    values = receiving_base_plate_values(snapshot)
    assert values["h"] == nominal_h
    assert values["receiving_bend_pattern"] == pattern
    assert receiving_base_plate_blank_dimensions(snapshot) == pytest.approx(expected_size)
    assert project_part_dimensions(snapshot)["base_plate"] == {
        "width": expected_size[0], "height": expected_size[1],
    }
    configured_spec = replace(
        _plate(pattern=pattern),
        height=values["h"],
        shrink_top=values["base_plate_shrink_top"],
        shrink_bottom=values["base_plate_shrink_bottom"],
        shrink_left=values["base_plate_shrink_left"],
        shrink_right=values["base_plate_shrink_right"],
        bend=values["base_plate_bend"],
    )
    render = build_part_render_data(configured_spec)
    assert (render.unfolded_topology.width, render.unfolded_topology.height) == pytest.approx(expected_size)
    assert render.metadata["receiving_bend_pattern"] == pattern
    assert "receiving_base_plate_unconfigured" not in render.metadata
    assert len([x for x in render.scene.primitives
                if isinstance(x, LinePrimitive) and x.layer == "BEND"]) == expected_bends


def test_receiving_does_not_guess_missing_physical_dimensions_or_pattern():
    s = apply_family_defaults({"w": 800.0, "t": 2.0})
    assert receiving_base_plate_values(s) is None
    assert receiving_base_plate_blank_dimensions(s) is None
    s["receiving_base_plate"] = {"pattern": RECEIVING_BASE_PATTERN_CENTER}
    with pytest.raises(ValueError, match="CONFIG_INCOMPLETE"):
        receiving_base_plate_values(s)
    s["receiving_base_plate"] = _configured("some_sketch", height=280.0)
    with pytest.raises(ValueError, match="PATTERN_INVALID"):
        receiving_base_plate_values(s)
    s["receiving_base_plate"] = _configured(RECEIVING_BASE_PATTERN_CENTER, height=280.0)
    s["receiving_base_plate"]["height"] = float("nan")
    with pytest.raises(ValueError, match="CONFIG_INVALID"):
        receiving_base_plate_values(s)


def test_other_cabinet_family_retains_standard_base_plate_path():
    preview = build_part_render_data(_plate(model="金庫型"))
    assert "receiving_base_plate_unconfigured" not in preview.metadata
    assert receiving_base_plate_values({"model": "金庫型", "receiving_base_plate": {"bad": 1}}) is None
