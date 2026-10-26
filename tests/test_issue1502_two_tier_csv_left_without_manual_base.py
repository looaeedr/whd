# -*- coding: utf-8 -*-
"""#1502: committed TWO-tier numeric CSV builds two real bases without a second manual base source."""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine.receiving_base_plate_config import (
    receiving_base_plate_values, receiving_base_plate_blank_dimensions,
)
from ae_engine.receiving_nfb_layer_physical_parts import (
    source_receiving_nfb_tier_base_specs, expand_receiving_nfb_layer_parts,
)
from ae_engine.receiving_tier_ear_z_targets import (
    resolve_receiving_tier_base_z_targets,
)
from tests.test_receiving_two_tier_physical_base_parts import (
    _two_tier, _source,
)


def _committed_two_left_tiers():
    snap=_two_tier()
    snap.pop("receiving_base_plate",None)
    for hole in snap["nfb_config"]["holes"]:
        hole.update(
            model_filename="nfbv5:士林:2P400",
            source_brand="士林",
            manual_x_state="CONFIRMED",
            manual_x_mm=(-100. if hole["layer_index"]==0 else 100.),
            datum_revision="CURRENT_CSV_X",
            datum_snapshot={"w":800.,"inner_door":"upper"},
        )
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"]
    )
    return snap


def test_submitted_two_left_tiers_derive_real_plate_without_manual_pattern():
    snap=_committed_two_left_tiers()
    assert "receiving_base_plate" not in snap
    original=deepcopy(snap)
    values=receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"]=="LEFT_FLAT_SIDE"
    assert values["h"]==340.
    assert receiving_base_plate_blank_dimensions(snap)==(710.,300.)
    specs=source_receiving_nfb_tier_base_specs(snap)
    assert set(specs)=={0,1}
    assert [specs[i].physical_id for i in (0,1)]==[
        "base_plate:nfb_layer:0","base_plate:nfb_layer:1"
    ]
    assert all(specs[i].receiving_bend_pattern=="LEFT_FLAT_SIDE" for i in (0,1))
    actual=expand_receiving_nfb_layer_parts(snap,(_source(snap),))
    assert tuple(p.part_key for p in actual)==(
        "base_plate:nfb_layer:0","base_plate:nfb_layer:1"
    )
    targets=resolve_receiving_tier_base_z_targets(snap)
    assert all(t.physical_skin_z_resolved for t in targets)
    assert [p.offset[2] for p in actual]==pytest.approx([
        t.world_offset_z_mm for t in targets
    ])
    assert all(p.render_data.material.area>0 for p in actual)
    assert all(p.render_data.metadata["manufacturing_ready"] is False
               for p in actual)
    assert snap==original, "source derivation must not persist a fake manual setting"


def test_two_distinct_known_csv_tiers_ignore_stale_manual_right_pattern():
    snap=_committed_two_left_tiers()
    snap["nfb_config"]["holes"][1]["model_filename"]="nfbv5:士林:3P125SN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"]
    )
    # A shallow second tier needs a brand-max-anchored CENTER return.
    # Its source, not the old one-tier flat LEFT assumption, owns the blank.
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"]=="CENTER_DOUBLE_SIDE_FOLD"
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)
    snap["receiving_base_plate"]={
        "pattern":"RIGHT_FLAT_SIDE","height":360.,
        "shrink_top":20.,"shrink_bottom":20.,
        "shrink_left":45.,"shrink_right":45.,"bend":20.,
    }
    # The old manual RIGHT cannot override real submitted numeric CSV.
    # The 107/72 source is CENTER 772x240, not an invented flat RIGHT/LEFT.
    values = receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"] == "CENTER_DOUBLE_SIDE_FOLD"
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)
    specs = source_receiving_nfb_tier_base_specs(snap)
    assert set(specs) == {0, 1}
    assert all(spec.receiving_bend_pattern == "CENTER_DOUBLE_SIDE_FOLD"
               for spec in specs.values())
    assert specs[1].receiving_nfb_depth_pair_mm == (107., 72.)
    preview=expand_receiving_nfb_layer_parts(snap,(_source(snap),))
    assert len(preview)==2
    assert {part.part_key for part in preview} == {
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    }
    assert all(part.render_data.metadata.get("manufacturing_ready") is False
               for part in preview)
    assert all(part.render_data.metadata.get("nfb_layer_manufacturing_status")
               is not None for part in preview)


def test_unsubmitted_and_stale_bay_identity_never_authorize_automatic_tiers():
    snap=_committed_two_left_tiers()
    unsubmitted=deepcopy(snap)
    unsubmitted["nfb_config_submitted"]=False
    assert receiving_base_plate_values(unsubmitted) is None
    stale=deepcopy(snap)
    stale["_receiving_runtime_selection"]["bay_id"]="other"
    with pytest.raises(ValueError,match="IDENTITY_DRIFT"):
        receiving_base_plate_values(stale)


def test_two_tier_source_equivalent_models_share_exact_physical_left_blank():
    # Different catalog aliases, exactly identical current CSV body, opening,
    # screw-hole groups and depths: they are NOT different physical blanks.
    snap = _committed_two_left_tiers()
    extra = deepcopy(snap["nfb_config"]["holes"][0])
    extra.update(
        physical_hole_id="nfb:alias-400",
        slot_index=1,
        model_filename="nfbv5:士林:3P400SN",
        manual_x_mm=100.,
    )
    snap["nfb_config"]["holes"].append(extra)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    vals = receiving_base_plate_values(snap)
    assert vals is not None
    assert vals["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert receiving_base_plate_blank_dimensions(snap) == (710., 300.)


def test_two_tier_current_cross_brand_nfb_keeps_one_original_sheet_per_tier():
    # Two brands may use one physical flat sheet per tier. Their apertures
    # and screws still belong to distinct per-switch CSV sources.
    snap = _committed_two_left_tiers()
    extra = deepcopy(snap["nfb_config"]["holes"][0])
    extra.update(
        physical_hole_id="nfb:other-brand",
        slot_index=1,
        model_filename="nfbv5:伍菱:3P400SN",
        source_brand="伍菱",
        manual_x_mm=100.,
    )
    snap["nfb_config"]["holes"].append(extra)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert receiving_base_plate_blank_dimensions(snap) == (710., 300.)


def test_three_horizontal_400_switches_on_one_of_two_source_left_tiers():
    snap = _committed_two_left_tiers()
    first = snap["nfb_config"]["holes"][0]
    first["manual_x_mm"] = -180.
    for slot, x, model in ((1, 0., "3P400SN"), (2, 180., "2P400")):
        extra = deepcopy(first)
        extra.update(physical_hole_id=f"nfb:upper:{slot}", slot_index=slot,
                     manual_x_mm=x, model_filename=f"nfbv5:士林:{model}")
        snap["nfb_config"]["holes"].append(extra)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    values = receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert receiving_base_plate_blank_dimensions(snap) == (710., 300.)
    specs = source_receiving_nfb_tier_base_specs(snap)
    assert set(specs) == {0, 1}
    targets = resolve_receiving_tier_base_z_targets(snap)
    assert len(targets) == 2 and all(x.physical_skin_z_resolved for x in targets)
    assert all(x.source_depths_mm == (107.,) for x in targets)
    actual = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    assert {p.part_key for p in actual} == {
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"
    }


def test_two_tiers_different_complete_csv_models_derive_independent_flat_sheets():
    snap = _committed_two_left_tiers()
    # Two separate vertical tiers each have their own model/depth and plate;
    # the illustrative 400 screw pitch is not required on the 125 tier.
    snap["nfb_config"]["holes"][1]["model_filename"] = "nfbv5:士林:3P125SN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    # Two separately placed tiers still use source-derived CENTER returns
    # where one selected tier is shallower than the one-brand maximum.
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "CENTER_DOUBLE_SIDE_FOLD"
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)
    targets = resolve_receiving_tier_base_z_targets(snap)
    assert len(targets) == 2 and all(t.physical_skin_z_resolved for t in targets)
    assert [t.source_depths_mm for t in targets] == [(107.,), (72.,)]
    specs = source_receiving_nfb_tier_base_specs(snap)
    assert set(specs) == {0, 1}
    assert specs[0].physical_id == "base_plate:nfb_layer:0"
    assert specs[1].physical_id == "base_plate:nfb_layer:1"
    assert specs[1].receiving_nfb_depth_pair_mm == (107., 72.)
    assert all(spec.receiving_bend_pattern == "CENTER_DOUBLE_SIDE_FOLD"
               for spec in specs.values())
    actual = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    assert len(actual) == 2
    assert all(part.render_data.metadata.get("manufacturing_ready") is False
               for part in actual)


def test_two_tiers_flat_source_with_mixed_depth_pad_stays_unreleased():
    snap = _committed_two_left_tiers()
    shallow = deepcopy(snap["nfb_config"]["holes"][0])
    shallow.update(physical_hole_id="nfb:shallow-in-upper", slot_index=1,
                   model_filename="nfbv5:士林:3P125SN", manual_x_mm=100.)
    snap["nfb_config"]["holes"].append(shallow)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    # CURRENT: different Z faces in one tier are separated by a per-switch
    # generated PAD, not by inventing a new folded CENTER base-plate source.
    # The LEFT physical blank is previewable only; PAD itself remains
    # manufacturing-blocked until its folded/assembly/BOM proof is approved.
    values = receiving_base_plate_values(snap)
    assert values is not None
    assert values["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert values["receiving_nfb_depth_pair_mm"] is None

    from ae_engine.receiving_nfb_numeric_catalog import model_spec
    from ae_engine.receiving_nfb_pad_generator import (
        read_pad_tooling_rule, generate_nfb_pad_patterns,
    )
    sources = (model_spec("士林", "2P400"), model_spec("士林", "3P125SN"))
    assert all(s is not None and s.dimensionally_complete for s in sources)
    pads = generate_nfb_pad_patterns(
        sources, plate_thickness_mm=float(snap["t"]),
        tooling=read_pad_tooling_rule(),
    )
    assert len(pads) == 1
    assert pads[0].switch_index == 1
    assert pads[0].rise_mm == pytest.approx(35.)
    assert pads[0].manufacturing_ready is False
