# -*- coding: utf-8 -*-
"""#1502 current NFB CSV is canonical source of normal 2D/3D/assembly screws."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.manufacturing_api import build_part_render_data
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from phase6_final_scene_contracts import AssemblyScenePart
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_source_derived_center_base import _spec
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _make(snap):
    spec = _spec(snap)
    placement = resolve_assembly_placement(snap, "base_plate")
    return AssemblyScenePart(
        part_key="base_plate", render_data=build_part_render_data(spec),
        x_profile=(), y_profile=(), placement="offset",
        offset=placement.world_offset,
    )


def _screws(part):
    return tuple(x for x in part.render_data.scene.primitives
                 if isinstance(x, CirclePrimitive)
                 and x.source_type == "NFB_V5_NUMERIC_BASE_TRIAL")


def _ears(part):
    return tuple(x for x in part.render_data.scene.primitives
                 if isinstance(x, PolylinePrimitive)
                 and x.layer == "CUTTING" and x.closed)


def test_committed_single_csv_is_automatically_cut_in_normal_source_scene():
    snap = _current()
    assert "receiving_base_plate" not in snap
    original = _make(snap)
    other = SimpleNamespace(part_key="box_body", render_data=object())
    changed = apply_committed_csv_v5_to_canonical_parts(snap, (original, other))
    assert len(changed) == 2 and changed[1] is other
    base = changed[0]
    assert base.part_key == original.part_key
    assert base.offset == original.offset
    assert len(_ears(base)) == len(_ears(original)) == 5
    assert len(_screws(base)) == 8
    assert base.render_data.material.area < original.render_data.material.area
    assert base.render_data.unfolded_topology == original.render_data.unfolded_topology
    assert base.render_data.metadata["nfb_trial_export_approved"] is False
    assert base.render_data.metadata["nfb_v5_source_models"] == (
        ("士林", "2P400"), ("士林", "3P125SN"),
    )


def test_committed_two_tiers_share_one_csv_datum_and_get_own_screw_sets():
    snap = _two_tier()
    for index, row in enumerate(snap["nfb_config"]["holes"]):
        row.update({
            "model_filename": ("nfbv5:士林:2P400", "nfbv5:士林:3P125SN")[index],
            "source_brand": "士林",
            "manual_x_state": "CONFIRMED",
            "manual_x_mm": (-100. if index == 0 else 100.),
            "datum_revision": "CURRENT_CSV_X",
            "datum_snapshot": {"w": 800., "inner_door": "upper"},
        })
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    blanks = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    assert len(blanks) == 2
    processed = apply_committed_csv_v5_to_canonical_parts(snap, blanks)
    assert tuple(v.part_key for v in processed) == (
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    )
    assert [len(_screws(p)) for p in processed] == [4, 4]
    assert [_ears(p) for p in processed] == [_ears(p) for p in blanks]
    assert [p.offset for p in processed] == [p.offset for p in blanks]
    assert set(v.source_id for v in _screws(processed[0])).isdisjoint(
        v.source_id for v in _screws(processed[1])
    )


def test_unconfirmed_csv_keeps_existing_editable_sheet_without_made_up_x():
    snap = _current()
    original = _make(snap)
    snap["nfb_config"]["holes"][0]["manual_x_state"] = "UNVERIFIED_BASIS"
    snap["nfb_config"]["holes"][0]["manual_x_mm"] = None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    assert apply_committed_csv_v5_to_canonical_parts(snap, (original,)) == (original,)


def test_legacy_native_dxf_project_keeps_old_scene_not_violated_by_csv_projection():
    snap = _two_tier()
    blanks = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    assert apply_committed_csv_v5_to_canonical_parts(snap, blanks) == blanks


def test_wrong_bay_identity_or_tampered_normal_base_rejected_before_overlay():
    snap = _current()
    original = _make(snap)
    snap["_receiving_runtime_selection"]["bay_id"] = "wrong"
    with pytest.raises(ValueError, match="IDENTITY_DRIFT"):
        apply_committed_csv_v5_to_canonical_parts(snap, (original,))
    snap = _current()
    original = _make(snap)
    broken = replace(original, offset=(0., original.offset[1] + 15., original.offset[2]))
    with pytest.raises(ValueError, match="安裝位置"):
        apply_committed_csv_v5_to_canonical_parts(snap, (broken,))
    other = replace(original, render_data=replace(
        original.render_data,
        metadata={**original.render_data.metadata,
                  "receiving_bend_pattern": "RIGHT_FLAT_SIDE"},
    ))
    with pytest.raises(ValueError, match="來源 PartSpec"):
        apply_committed_csv_v5_to_canonical_parts(snap, (other,))


def test_resolver_has_normal_source_seam_not_a_new_operator_export_button():
    import inspect
    import phase6_manufacturing_service
    from gui_modules.application import receiving_multi_settings_window
    resolver = inspect.getsource(phase6_manufacturing_service.resolve)
    window = inspect.getsource(receiving_multi_settings_window)
    assert "apply_committed_csv_v5_to_canonical_parts" in resolver
    assert "expand_receiving_nfb_layer_parts" in resolver
    assert resolver.index("expand_receiving_nfb_layer_parts") < resolver.index(
        "apply_committed_csv_v5_to_canonical_parts"
    )
    assert "輸出 CSV 底板 DXF（單片）" not in window
