"""#2517: real current NFB BasePlate 2D source belongs to Engine, not GUI."""
from types import SimpleNamespace
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import ResolvedManufacturingGeometry
from ae_engine.operator_base_plate_2d import (
    project_receiving_base_plate_2d_snapshot,
    project_legacy_base_plate_2d_bounds,
)
from ae_engine.receiving_nfb_layer_physical_parts import expand_receiving_nfb_layer_parts
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source
from gui_modules.application.render_snapshots import base_plate_render_snapshot


@pytest.mark.parametrize("active,expected", (
    ("box_body", "base_plate:nfb_layer:0"),
    ("base_plate:nfb_layer:0", "base_plate:nfb_layer:0"),
    ("base_plate:nfb_layer:1", "base_plate:nfb_layer:1"),
))
def test_headless_engine_matches_real_two_tier_material_and_gui(active, expected):
    snap = _two_tier()
    geometry = ResolvedManufacturingGeometry(
        parts=expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    )
    result = manufacturing_api.project_receiving_base_plate_2d_snapshot(
        snap, geometry, active_part=active,
    )
    assert manufacturing_api.project_receiving_base_plate_2d_snapshot is project_receiving_base_plate_2d_snapshot
    assert result["receiving_physical_part_key"] == expected
    assert result["render_data"] is geometry.part(expected).render_data
    assert result["receiving_tier_keys"] == (
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"
    )
    host = SimpleNamespace(fold_designer_app=SimpleNamespace(
        _phase6_input_snapshot=snap,
        designer_workspace=SimpleNamespace(active_part=active),
        _phase6_resolve_manufacturing_geometry=lambda: geometry,
    ))
    preview = base_plate_render_snapshot(host, {"model": "受電箱", "w": 800.0, "h": 1600.0})
    assert preview["render_data"] is result["render_data"]
    assert preview == result


def test_engine_rejects_no_committed_source_without_generic_fallback():
    snap = _two_tier()
    geometry = ResolvedManufacturingGeometry(
        parts=expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    )
    bad = {**snap, "nfb_config_submitted": False}
    with pytest.raises(ValueError, match="未產生實體底板"):
        project_receiving_base_plate_2d_snapshot(bad, geometry)
    with pytest.raises(TypeError, match="mapping"):
        project_receiving_base_plate_2d_snapshot(None, geometry)


def test_legacy_bounds_are_engine_only_and_keep_original_box_geometry():
    bounds = (-50.0, -20.0, 650.0, 1500.0)
    w, h = 800.0, 1600.0
    actual, rect = project_legacy_base_plate_2d_bounds(
        bounds, width=w, height=h, shrink_left=85.0,
        shrink_bottom=55.0, bend=20.0,
    )
    assert actual == (-65.0, -35.0, 735.0, 1565.0)
    assert rect == (-65.0, -35.0, w, h)


def test_gui_uses_public_engine_projection_instead_of_production_identity_rules():
    source = Path("gui_modules/application/render_snapshots.py").read_text(encoding="utf-8")
    start = source.index("def base_plate_render_snapshot(")
    end = source.index("def box_body_render_snapshot(", start)
    segment = source[start:end]
    assert "manufacturing_api.project_receiving_base_plate_2d_snapshot(" in segment
    assert "manufacturing_api.project_legacy_base_plate_2d_bounds(" in segment
    for forbidden in (
        "receiving_base_plate_values", "RECEIVING_BASE_PATTERN_CENTER",
        "base_plate:nfb_layer:", "receiving_bend_pattern", "nfb_rows",
        "topology.height", "source_shape_check",
    ):
        assert forbidden not in segment
