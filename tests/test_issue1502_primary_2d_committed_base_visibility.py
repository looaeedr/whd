# -*- coding: utf-8 -*-
"""#1502: source-established receiving Base Plates are visible before MFG-2 release.

This exercises the REAL current PartRenderData in the resolved 2D/3D scene.
Manufacturing proof is separate: no extra DXF permission or synthetic drawing.
"""
from types import SimpleNamespace

import pytest

from ae_engine.contracts import ResolvedManufacturingGeometry
from ae_engine.manufacturing_api import build_part_render_data
from gui_modules.application.render_snapshots import base_plate_render_snapshot
from tests.test_issue1502_source_derived_center_base import _source_snapshot, _spec
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _source, _two_tier


def _host(snapshot, parts, *, active="box_body"):
    resolved = ResolvedManufacturingGeometry(parts=tuple(parts))
    calls = []
    designer = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        designer_workspace=SimpleNamespace(active_part=active),
        _phase6_resolve_manufacturing_geometry=(
            lambda: calls.append("resolved") or resolved
        ),
    )
    return SimpleNamespace(fold_designer_app=designer), resolved, calls


def test_committed_one_tier_preserves_existing_real_base_selection():
    snap = _assembled()
    source = _source(snap)
    host, scene, calls = _host(snap, (source,), active="base_plate")
    drawn = base_plate_render_snapshot(host, {"model": "受電箱"})
    assert calls == ["resolved"]
    assert drawn["receiving_physical_part_key"] == "base_plate"
    assert drawn["receiving_tier_keys"] == ()
    assert drawn["render_data"] is scene.part("base_plate").render_data
    assert drawn["bounds"] == tuple(source.render_data.material.bounds)
    assert source.render_data.metadata["receiving_nfb_base_mfg2_release_approved"] is False


def test_source_derived_flat_pad_without_manual_setting_is_visible_in_primary_2d():
    snap = _source_snapshot()
    assert "receiving_base_plate" not in snap
    render = build_part_render_data(_spec(snap))
    source = SimpleNamespace(part_key="base_plate", render_data=render)
    host, scene, calls = _host(snap, (source,))
    drawn = base_plate_render_snapshot(host, {"model": "受電箱"})
    assert calls == ["resolved"]
    assert drawn["render_data"] is scene.part("base_plate").render_data
    assert drawn["receiving_physical_part_key"] == "base_plate"
    assert drawn["receiving_tier_keys"] == ()
    # Current submitted mixed V5 depth picks source-backed FLAT + PAD, not
    # the old implicit CENTER. The sheet is still a real 2D part before MFG.
    from ae_engine.receiving_base_plate_config import receiving_base_plate_blank_dimensions
    assert render.metadata["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert render.unfolded_topology.width == receiving_base_plate_blank_dimensions(snap)[0] == 710.
    assert render.metadata["receiving_nfb_base_mfg2_release_approved"] is False


def test_changed_csv_source_cannot_display_previous_center_plate():
    snap = _source_snapshot(shallow="2P400")
    valid = _source_snapshot()
    # An explicitly approved historical CENTER plate is a REAL other plate;
    # it must not be reused for a new Bay that selects a FLAT source.
    valid['receiving_base_plate'] = {'pattern': 'CENTER_DOUBLE_SIDE_FOLD'}
    root = SimpleNamespace(
        part_key="base_plate", render_data=build_part_render_data(_spec(valid)),
    )
    host, _, calls = _host(snap, (root,))
    # With complete current V5 CSV, the flat source exists. The old
    # CENTER-shaped FinalScene is now a *stale actual part*, not a missing
    # model. Reject wrong source instead of displaying it in 2D.
    with pytest.raises(ValueError, match="目前 CSV 來源與已載入 2D 實體板型不一致"):
        base_plate_render_snapshot(host, {"model": "受電箱"})
    assert calls == ["resolved"]


def test_submitted_two_tier_cannot_downgrade_to_one_root_in_2d():
    snap = _two_tier()
    root = _source(snap)
    host, _, calls = _host(snap, (root,))
    with pytest.raises(ValueError, match="沒有對應的受電箱分層底板"):
        base_plate_render_snapshot(host, {"model": "受電箱"})
    assert calls == ["resolved"]


def test_single_tier_complete_125_model_is_visible_as_real_csv_flat_sheet_in_2d():
    snap = _source_snapshot()
    snap["nfb_config"]["holes"] = [snap["nfb_config"]["holes"][1]]
    snap["nfb_config"]["holes"][0]["slot_index"] = 0
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = __import__(
        "copy"
    ).deepcopy(snap["nfb_config"])
    assert "receiving_base_plate" not in snap
    real = build_part_render_data(_spec(snap))
    source = SimpleNamespace(part_key="base_plate", render_data=real)
    host, scene, calls = _host(snap, (source,))
    drawn = base_plate_render_snapshot(host, {"model": "受電箱"})
    assert calls == ["resolved"]
    assert drawn["receiving_physical_part_key"] == "base_plate"
    assert drawn["render_data"] is scene.part("base_plate").render_data
    assert real.unfolded_topology.width == 710.
    assert real.unfolded_topology.height == 300.
    assert real.metadata["receiving_nfb_base_mfg2_release_approved"] is False
