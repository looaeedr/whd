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


def test_wrong_model_is_not_declared_left_from_depth_or_manual_legacy_choice():
    snap=_committed_two_left_tiers()
    snap["nfb_config"]["holes"][1]["model_filename"]="nfbv5:士林:3P125SN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"]
    )
    assert receiving_base_plate_values(snap) is None
    snap["receiving_base_plate"]={
        "pattern":"RIGHT_FLAT_SIDE","height":360.,
        "shrink_top":20.,"shrink_bottom":20.,
        "shrink_left":45.,"shrink_right":45.,"bend":20.,
    }
    # An unknown CSV tier does not acquire a machining source from a stale
    # manually entered generic RIGHT pattern.
    # Legacy manual sheets may remain visible as previews, but cannot
    # pretend an unmatched numeric CSV has an approved manufacturing shape.
    preview=expand_receiving_nfb_layer_parts(snap,(_source(snap),))
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
