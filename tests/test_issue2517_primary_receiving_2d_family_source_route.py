"""#2517: both primary physical 2D tabs follow Engine Family aliases.

The GUI may choose presentation tabs, never fall back to legacy synthetic
BasePlate / BoxBody when the registered Receiving FinalScene is committed.
"""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ResolvedManufacturingGeometry
from ae_engine.receiving_nfb_layer_physical_parts import expand_receiving_nfb_layer_parts
from gui_modules.application import render_snapshots as gui
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source
from tests.test_issue1503_ear_side_check_only_dxf import _actual


@pytest.mark.parametrize("alias", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  "))
def test_public_engine_family_2d_source_route_uses_registry_aliases(alias):
    source = {"model": alias, "active_mode": "set_bay"}
    old = deepcopy(source)
    assert family_policy.canonical_family_name(source) == "受電箱"
    assert api.uses_operator_receiving_committed_2d_source(source) is True
    assert source == old


@pytest.mark.parametrize("source", (
    None, {}, {"model": "金庫型"}, {"model": "VAULT"},
    {"model": "unregistered"}, {"active_mode": "set_bay"},
))
def test_only_registered_receiving_has_committed_2d_source_route(source):
    assert api.uses_operator_receiving_committed_2d_source(source) is False


@pytest.mark.parametrize("alias", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_primary_base_plate_2d_always_reads_same_real_nfb_tier(alias):
    source = _two_tier()
    source_before = deepcopy(source)
    geometry = ResolvedManufacturingGeometry(
        parts=expand_receiving_nfb_layer_parts(source, (_source(source),))
    )
    current = {**source, "model": alias}
    active = "base_plate:nfb_layer:1"
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot=current,
            designer_workspace=SimpleNamespace(active_part=active),
            _phase6_resolve_manufacturing_geometry=lambda: geometry,
        ),
        _base_plate_part_spec=lambda *_: pytest.fail("legacy plate spec must not be called"),
    )
    physical = api.project_receiving_base_plate_2d_snapshot(
        current, geometry, active_part=active,
    )
    actual = gui.base_plate_render_snapshot(host, {"model": alias, "w": source["w"], "h": source["h"]})
    assert actual == physical
    assert actual["render_data"] is geometry.part(active).render_data
    assert actual["receiving_physical_part_key"] == active
    assert source == source_before


@pytest.mark.parametrize("alias", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_primary_box_body_2d_uses_actual_side_mother_scene(monkeypatch, alias):
    original, geometry = _actual(_two_tier)
    current = {**original, "model": alias}
    real = geometry.part("box_body").render_data
    left = next(p for p in real.pieces if p.role == "left_side")
    shown = []
    from gui_modules.application import receiving_ear_side_2d
    monkeypatch.setattr(
        receiving_ear_side_2d, "present_receiving_ear_side_piece_2d",
        lambda _host, render, piece, key: (shown.append((render, piece, key)) or piece, None),
    )
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot=current,
            _phase6_resolve_manufacturing_geometry=lambda: geometry,
        ),
        _box_body_part_spec=lambda *_: pytest.fail("legacy box spec must not be called"),
        _refresh_box_body_piece_tabs_2d=lambda _rd: "box_body:left_side",
    )
    result = gui.box_body_render_snapshot(host, {"w": original["w"], "h": original["h"], "d": original["d"]})
    assert result["render_data"] is real
    assert result["piece"] is left
    assert shown == [(real, left, "box_body:left_side")]


@pytest.mark.parametrize("alias", ("receiving", "ReCeIvInG"))
def test_receiving_missing_committed_source_rejects_both_tabs(alias):
    designer = SimpleNamespace(_phase6_input_snapshot={"model": alias})
    host = SimpleNamespace(fold_designer_app=designer)
    with pytest.raises(ValueError, match="缺少已提交的製造幾何來源"):
        gui.base_plate_render_snapshot(host, {"w": 800, "h": 1600})
    with pytest.raises(ValueError, match="缺少 FoldDesigner 實體製造來源"):
        gui.box_body_render_snapshot(host, {"w": 800, "h": 1600, "d": 350})


def test_gui_has_no_receiving_family_manufacturing_switch():
    text = inspect.getsource(gui.base_plate_render_snapshot) + inspect.getsource(gui.box_body_render_snapshot)
    assert text.count("manufacturing_api.uses_operator_receiving_committed_2d_source(current)") == 2
    assert 'current.get("model") in ("受電箱", "RECEIVING")' not in text
    from ae_engine import operator_box_body_2d
    assert "from gui_modules" not in inspect.getsource(operator_box_body_2d)
