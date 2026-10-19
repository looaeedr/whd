# -*- coding: utf-8 -*-
"""#1503 original primary 2D must not silently render obsolete generic Base Plate."""
from types import SimpleNamespace
from copy import deepcopy

import pytest

from gui_modules.application.render_snapshots import base_plate_render_snapshot
from ae_engine.receiving_nfb_layer_physical_parts import expand_receiving_nfb_layer_parts
from ae_engine.contracts import ResolvedManufacturingGeometry
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _real_host(*, active="box_body"):
    source = _two_tier()
    actual = expand_receiving_nfb_layer_parts(source, (_source(source),))
    scene = ResolvedManufacturingGeometry(parts=actual)
    source_calls = []
    designer = SimpleNamespace(
        _phase6_input_snapshot=source,
        designer_workspace=SimpleNamespace(active_part=active),
        _phase6_resolve_manufacturing_geometry=(
            lambda: source_calls.append("real") or scene
        ),
    )
    host = SimpleNamespace(fold_designer_app=designer)
    return host, scene, source_calls


@pytest.mark.parametrize("active,physical_key", (
    ("box_body", "base_plate:nfb_layer:0"),
    ("base_plate:nfb_layer:0", "base_plate:nfb_layer:0"),
    ("base_plate:nfb_layer:1", "base_plate:nfb_layer:1"),
))
def test_primary_2d_uses_actual_NFB_tier_blank_not_generic_source(active, physical_key):
    host, scene, calls = _real_host(active=active)
    result = base_plate_render_snapshot(host, {"model": "受電箱", "w": 800, "h": 1600})
    assert calls == ["real"]
    assert result["receiving_physical_part_key"] == physical_key
    assert result["receiving_tier_keys"] == (
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"
    )
    expected = scene.part(physical_key).render_data
    assert result["render_data"] is expected
    assert result["render_data"].unfolded_topology.piece_id == physical_key
    assert result["bounds"] == tuple(expected.material.bounds)
    assert result["world_bounds"] == tuple(expected.material.bounds)
    assert "base_plate" not in result["receiving_tier_keys"]
    assert expected.metadata.get("manufacturing_ready") is False


def test_missing_receiving_physical_plate_cannot_draw_old_generic_plate():
    host, _, calls = _real_host()
    host.fold_designer_app._phase6_input_snapshot = {
        **host.fold_designer_app._phase6_input_snapshot,
        "receiving_base_plate": None,
    }
    with pytest.raises(ValueError, match="尚未設定實體來源"):
        base_plate_render_snapshot(host, {"model": "受電箱", "w":800, "h":1600})
    assert calls == []


def test_no_submitted_NFB_cannot_claim_an_unverified_old_root_is_real():
    host, scene, calls = _real_host()
    src = deepcopy(host.fold_designer_app._phase6_input_snapshot)
    src["nfb_config_submitted"] = False
    host.fold_designer_app._phase6_input_snapshot = src
    with pytest.raises(ValueError, match="未產生實體底板"):
        base_plate_render_snapshot(host, {"model": "受電箱", "w":800, "h":1600})
    assert calls == ["real"]
