# -*- coding: utf-8 -*-
"""Manufacturing DTO freeze's numeric normalization must not erase NFB tier identity."""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_manufacturing_transport import (
    restore_receiving_nfb_dto_selectors,
)
from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
)
from phase6_manufacturing_contracts import (
    freeze_manufacturing_value, thaw_manufacturing_value,
)
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def test_exact_two_tier_source_survives_real_manufacturing_dto_roundtrip():
    current = _two_tier()
    # CURRENT DTO preserves physical integer identities. Still verify the
    # explicit restore helper for historical float-valued payloads below.
    thawed = thaw_manufacturing_value(freeze_manufacturing_value(current))
    assert type(thawed["nfb_config"]["layer_count"]) is int
    assert type(thawed["receiving_layout"]["sets"][0]["bays"][0]
                ["nfb_config"]["holes"][0]["layer_index"]) is int
    restored = restore_receiving_nfb_dto_selectors(thawed)
    for cfg in (restored["nfb_config"],
                restored["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]):
        assert type(cfg["layer_count"]) is int and cfg["layer_count"] == 2
        assert [p["layer_index"] for p in cfg["holes"]] == [0, 1]
        assert all(type(p["layer_index"]) is int for p in cfg["holes"])
    assert restored["nfb_config"] == restored["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]
    # Same real T2 physical blank/owner assembly previously skipped due
    # float IDs must now be built and remain explicitly manufacturing-blocked.
    physical = expand_receiving_nfb_layer_parts(restored, (_source(current),))
    assert [p.part_key for p in physical] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"
    ]
    assert all(p.render_data.metadata["manufacturing_ready"] is False for p in physical)


def test_draft_never_transforms_into_submitted_source():
    sample = _two_tier()
    sample.pop("nfb_config_submitted", None)
    sample["receiving_layout"]["sets"][0]["bays"][0].pop("nfb_config_submitted", None)
    snap = thaw_manufacturing_value(freeze_manufacturing_value(sample))
    result = restore_receiving_nfb_dto_selectors(snap)
    assert "nfb_config_submitted" not in result


@pytest.mark.parametrize("wrong", (0.5, float("nan"), True, "2"))
def test_invalid_fractional_or_non_numeric_tier_identity_rejected(wrong):
    data = {"model":"受電箱","nfb_config_submitted":True,
            "nfb_config":{"layer_count":wrong,"holes":[
                {"physical_hole_id":"nfb:0","layer_index":0.0,"slot_index":0.0},
            ]}}
    with pytest.raises(ValueError, match="INVALID_SELECTOR"):
        restore_receiving_nfb_dto_selectors(data)
